"""
Async Checker Engine for high-speed Twitch username availability checking.
Uses aiohttp and batched Twitch GraphQL queries with dual (channel & user) verification.
"""

import asyncio
import aiohttp
import time
import random
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime

from .config import (
    TWITCH_GQL_URL,
    DEFAULT_CLIENT_ID,
    DEFAULT_USER_AGENT,
    USER_AGENTS,
    BATCH_ITEMS_PER_REQ,
    RESERVED_USERNAMES
)
from .database import save_batch_results, get_already_checked_usernames
from .generators import is_valid_syntax

class CheckerEngine:
    def __init__(self):
        self.state: str = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED, COMPLETED
        self.total_target: int = 0
        self.checked_count: int = 0
        self.available_count: int = 0
        self.taken_count: int = 0
        self.locked_count: int = 0
        self.invalid_count: int = 0
        
        self.start_time: Optional[float] = None
        self.current_speed: float = 0.0  # names per second
        self.eta_seconds: int = 0
        
        self.newly_found: List[Dict[str, Any]] = []
        self.on_update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # Unpaused initially
        self._stop_flag: bool = False
        self._task: Optional[asyncio.Task] = None
        
        # Concurrency & Batch Settings
        self.names_per_batch_item = 7   # 7 names * 2 aliases (channel + user) = 14 aliases (limit is 15)
        self.batch_items_per_req = 15   # 15 items in array (limit is 35)
        self.chunk_size = self.names_per_batch_item * self.batch_items_per_req  # 105 names per HTTP POST
        self.concurrency = 3            # 3 concurrent worker requests (~300-500 names/sec)
        self.delay_between_requests = 0.15 # seconds polite delay to avoid any 429
        
    def get_status(self) -> Dict[str, Any]:
        """Return the current engine metrics and status."""
        elapsed = time.time() - self.start_time if self.start_time and self.state == "RUNNING" else 0
        progress_pct = (self.checked_count / self.total_target * 100) if self.total_target > 0 else 0
        
        return {
            "state": self.state,
            "total": self.total_target,
            "checked": self.checked_count,
            "available": self.available_count,
            "taken": self.taken_count,
            "locked": self.locked_count,
            "invalid": self.invalid_count,
            "speed": round(self.current_speed, 1),
            "progress_percent": round(progress_pct, 1),
            "eta_seconds": self.eta_seconds,
            "elapsed_seconds": int(elapsed),
            "newly_found": self.newly_found[-20:]  # Last 20 newly found available
        }

    async def check_single_username(self, username: str) -> Dict[str, Any]:
        """Directly check a single username and return comprehensive information."""
        u = username.lower().strip()
        if not is_valid_syntax(u):
            reason = "Violates syntax rules"
            if len(u) < 4:
                reason = "Too short (Twitch strictly requires at least 4 characters. Note: The Slovak interface has a translation typo saying 'od 3 do 25', but Twitch's system validator enforces a minimum of 4 characters)."
            elif len(u) > 25:
                reason = "Too long (max 25 characters)"
            elif u.startswith("_"):
                reason = "Cannot start with an underscore"
            elif u in RESERVED_USERNAMES:
                reason = "Reserved Twitch platform keyword"
            return {
                "username": u,
                "status": "invalid",
                "reason": reason,
                "length": len(u),
                "is_available": False
            }

        query = """
        query CheckSingle($name: String!) {
            channel(name: $name) {
                id
                name
            }
            user(login: $name) {
                id
                login
                displayName
            }
        }
        """
        headers = {
            "Client-Id": DEFAULT_CLIENT_ID,
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT
        }
        payload = {"query": query, "variables": {"name": u}}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(TWITCH_GQL_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        d = data.get("data", {})
                        ch = d.get("channel")
                        us = d.get("user")
                        
                        if not ch and not us:
                            status = "available"
                            channel_id = None
                            display_name = None
                        elif us:
                            status = "taken"
                            channel_id = us.get("id")
                            display_name = us.get("displayName")
                        else:
                            status = "locked"  # Banned, deactivated, or Justin.tv legacy
                            channel_id = ch.get("id") if ch else None
                            display_name = None

                        record = {
                            "username": u,
                            "status": status,
                            "length": len(u),
                            "channel_id": channel_id,
                            "display_name": display_name,
                            "checked_at": datetime.now().isoformat(),
                            "is_available": (status == "available")
                        }
                        # Save result
                        save_batch_results([record])
                        return record
                    else:
                        return {"username": u, "status": "error", "error": f"HTTP {resp.status}"}
            except Exception as e:
                return {"username": u, "status": "error", "error": str(e)}

    def start_scan(self, name_list: List[str], speed_mode: str = "normal", skip_already_checked: bool = True):
        """Start a new background scanning task."""
        if self.state == "RUNNING":
            return False, "A scan is already running"

        if speed_mode == "safe":
            self.concurrency = 2
            self.delay_between_requests = 0.3
        elif speed_mode == "turbo":
            self.concurrency = 5
            self.delay_between_requests = 0.05
        else:  # normal
            self.concurrency = 3
            self.delay_between_requests = 0.15

        # Filter out already checked names if requested
        if skip_already_checked:
            checked_set = get_already_checked_usernames()
            filtered_names = [n for n in name_list if n not in checked_set]
        else:
            filtered_names = list(name_list)

        self.total_target = len(filtered_names)
        self.checked_count = 0
        self.available_count = 0
        self.taken_count = 0
        self.locked_count = 0
        self.invalid_count = 0
        self.newly_found.clear()
        self.start_time = time.time()
        self.current_speed = 0.0
        self.eta_seconds = 0
        self._stop_flag = False
        self._pause_event.set()
        self.state = "RUNNING"

        # Spawn background task
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._scan_worker(filtered_names))
        return True, f"Scan started with {self.total_target} usernames"

    def pause_scan(self):
        """Pause running scan."""
        if self.state == "RUNNING":
            self._pause_event.clear()
            self.state = "PAUSED"
            return True, "Scan paused"
        return False, "Scan not running"

    def resume_scan(self):
        """Resume paused scan."""
        if self.state == "PAUSED":
            self._pause_event.set()
            self.state = "RUNNING"
            return True, "Scan resumed"
        return False, "Scan not paused"

    def stop_scan(self):
        """Stop running or paused scan."""
        if self.state in ("RUNNING", "PAUSED"):
            self._stop_flag = True
            self._pause_event.set()  # Unblock if paused so worker can exit
            self.state = "STOPPED"
            return True, "Scan stopped"
        return False, "Scan is not active"

    async def _scan_worker(self, names: List[str]):
        """Main async orchestration loop."""
        queue = asyncio.Queue()
        # Enqueue in chunks of `chunk_size`
        for i in range(0, len(names), self.chunk_size):
            chunk = names[i:i + self.chunk_size]
            await queue.put(chunk)

        # Worker tasks
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(limit=self.concurrency * 2)
        
        speed_window = []
        last_speed_calc = time.time()
        checked_since_calc = 0

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            workers = []
            for w_id in range(self.concurrency):
                workers.append(asyncio.create_task(self._worker_loop(w_id, session, queue)))

            # Monitor progress while workers run
            while not queue.empty() and not self._stop_flag:
                await asyncio.sleep(0.5)
                # Compute rolling speed
                now = time.time()
                dt = now - last_speed_calc
                if dt >= 1.0:
                    speed = checked_since_calc / dt
                    speed_window.append(speed)
                    if len(speed_window) > 5:
                        speed_window.pop(0)
                    self.current_speed = sum(speed_window) / len(speed_window) if speed_window else 0
                    
                    remaining = self.total_target - self.checked_count
                    if self.current_speed > 0:
                        self.eta_seconds = int(remaining / self.current_speed)
                    else:
                        self.eta_seconds = 0
                    
                    checked_since_calc = 0
                    last_speed_calc = now
                    
                    if self.on_update_callback:
                        self.on_update_callback(self.get_status())

            # Wait for all workers to finish
            await queue.join()
            for w in workers:
                w.cancel()

        if self._stop_flag:
            self.state = "STOPPED"
        else:
            self.state = "COMPLETED"
            
        self.current_speed = 0.0
        self.eta_seconds = 0
        if self.on_update_callback:
            self.on_update_callback(self.get_status())

    async def _worker_loop(self, worker_id: int, session: aiohttp.ClientSession, queue: asyncio.Queue):
        """Individual worker pulling chunks from the queue."""
        while not self._stop_flag:
            # Respect pause
            await self._pause_event.wait()
            
            try:
                chunk = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            await self._process_chunk(session, chunk)
            queue.task_done()
            
            if self.delay_between_requests > 0:
                await asyncio.sleep(self.delay_between_requests)

    async def _process_chunk(self, session: aiohttp.ClientSession, chunk: List[str]):
        """Build GraphQL array batch request and parse results."""
        # Split chunk into subqueries of `names_per_batch_item`
        payload = []
        chunk_names = []
        for i in range(0, len(chunk), self.names_per_batch_item):
            sub_names = chunk[i:i + self.names_per_batch_item]
            chunk_names.append(sub_names)
            
            alias_parts = []
            for j, name in enumerate(sub_names):
                alias_parts.append(f'c{j}: channel(name: "{name}") {{ id name }}')
                alias_parts.append(f'u{j}: user(login: "{name}") {{ id displayName }}')
                
            q = "query Batch {\n" + "\n".join(alias_parts) + "\n}"
            payload.append({"query": q})

        headers = {
            "Client-Id": DEFAULT_CLIENT_ID,
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENTS)
        }

        retries = 3
        backoff = 1.0
        results_to_save = []
        
        while retries > 0 and not self._stop_flag:
            try:
                async with session.post(TWITCH_GQL_URL, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            now_str = datetime.now().isoformat()
                            
                            for batch_idx, batch_res in enumerate(data):
                                if batch_idx >= len(chunk_names):
                                    continue
                                sub_names = chunk_names[batch_idx]
                                res_data = batch_res.get("data", {}) if isinstance(batch_res, dict) else {}
                                
                                for j, name in enumerate(sub_names):
                                    ch = res_data.get(f'c{j}')
                                    us = res_data.get(f'u{j}')
                                    
                                    if not ch and not us:
                                        status = "available"
                                        channel_id = None
                                        display_name = None
                                        self.available_count += 1
                                        item_info = {
                                            "username": name,
                                            "status": status,
                                            "length": len(name),
                                            "checked_at": now_str
                                        }
                                        self.newly_found.append(item_info)
                                    elif us:
                                        status = "taken"
                                        channel_id = us.get("id")
                                        display_name = us.get("displayName")
                                        self.taken_count += 1
                                    else:
                                        status = "locked"  # Banned, deactivated, or Justin.tv reserved
                                        channel_id = ch.get("id") if ch else None
                                        display_name = None
                                        self.locked_count += 1

                                    self.checked_count += 1
                                    results_to_save.append({
                                        "username": name,
                                        "status": status,
                                        "length": len(name),
                                        "channel_id": channel_id,
                                        "display_name": display_name,
                                        "checked_at": now_str
                                    })
                            break
                        else:
                            retries -= 1
                            await asyncio.sleep(backoff)
                            backoff *= 2
                    elif resp.status == 429:  # Rate limited
                        retries -= 1
                        await asyncio.sleep(backoff + 1.0)
                        backoff *= 2
                    else:
                        retries -= 1
                        await asyncio.sleep(backoff)
                        backoff *= 1.5
            except Exception as e:
                retries -= 1
                await asyncio.sleep(backoff)
                backoff *= 2

        # Save to database
        if results_to_save:
            save_batch_results(results_to_save)
