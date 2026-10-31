"""
Modern Async Web Server for Twitch Username Checker.
Provides REST API, WebSockets, and hosts the Dark-Mode Web Dashboard.
"""

import os
import sys
import re
import itertools
import json
import asyncio
import aiohttp
import time
from datetime import datetime
from aiohttp import web
from pathlib import Path
from typing import Set

# Ensure backend can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from backend.config import BASE_DIR, MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH
from backend.database import (
    init_db,
    get_statistics,
    get_recent_results,
    export_usernames,
    clear_all_results,
    save_batch_results
)
from backend.generators import (
    generate_3char_letters,
    generate_3char_alphanumeric,
    generate_4char_letters,
    generate_4char_alphanumeric,
    load_dictionary_words,
    generate_pronounceable,
    generate_aesthetic_patterns,
    generate_by_pattern,
    load_custom_wordlist,
    is_valid_syntax
)
from backend.checker_engine import CheckerEngine

# Global instances
engine = CheckerEngine()
active_websockets: Set[web.WebSocketResponse] = set()

async def broadcast_status(data: dict):
    """Broadcast status dictionary to all connected WebSocket clients."""
    if not active_websockets:
        return
    msg = json.dumps({"type": "status_update", "data": data})
    closed = set()
    for ws in active_websockets:
        if ws.closed:
            closed.add(ws)
            continue
        try:
            await ws.send_str(msg)
        except Exception:
            closed.add(ws)
    active_websockets.difference_update(closed)

def engine_update_handler(status_dict: dict):
    """Callback fired by engine during scan."""
    asyncio.create_task(broadcast_status(status_dict))

engine.on_update_callback = engine_update_handler

# ----------------- HTTP Route Handlers -----------------

async def handle_index(request: web.Request) -> web.Response:
    """Serve main web dashboard."""
    index_file = BASE_DIR / "web" / "index.html"
    return web.FileResponse(index_file)

async def handle_status(request: web.Request) -> web.Response:
    """Get current scanner status and overall database stats."""
    engine_status = engine.get_status()
    db_stats = get_statistics()
    return web.json_response({
        "engine": engine_status,
        "database": db_stats
    })

async def handle_check_single(request: web.Request) -> web.Response:
    """Directly check a single username."""
    try:
        data = await request.json()
        username = data.get("username", "").strip()
        if not username:
            return web.json_response({"error": "Username required"}, status=400)
        
        result = await engine.check_single_username(username)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_scan_start(request: web.Request) -> web.Response:
    """Start scan with chosen generator mode."""
    try:
        data = await request.json()
        mode = data.get("mode", "3char_letters")
        speed = data.get("speed", "normal")
        skip_checked = data.get("skip_checked", True)
        
        names_to_check = []
        if mode == "3char_letters":
            names_to_check = list(generate_3char_letters())
        elif mode == "3char_alphanumeric":
            names_to_check = list(generate_3char_alphanumeric())
        elif mode == "4char_words":
            names_to_check = load_dictionary_words(4)
        elif mode == "5char_words":
            names_to_check = load_dictionary_words(5)
        elif mode == "3char_words":
            names_to_check = load_dictionary_words(3)
        elif mode == "4char_letters":
            names_to_check = list(generate_4char_letters())
        elif mode == "pronounceable_3":
            names_to_check = list(generate_pronounceable(3))
        elif mode == "pronounceable_4":
            names_to_check = list(generate_pronounceable(4))
        elif mode == "aesthetic_4":
            names_to_check = list(generate_aesthetic_patterns(4))
        elif mode == "pattern":
            pattern = data.get("pattern", "z***")
            names_to_check = list(generate_by_pattern(pattern))
        elif mode == "custom_list":
            raw_text = data.get("custom_text", "")
            lines = [l.strip().lower() for l in raw_text.splitlines() if l.strip()]
            names_to_check = list(dict.fromkeys(lines))  # Unique preserved
        else:
            return web.json_response({"error": f"Unknown mode: {mode}"}, status=400)

        if not names_to_check:
            return web.json_response({"error": "No valid usernames generated for this selection"}, status=400)

        success, msg = engine.start_scan(names_to_check, speed_mode=speed, skip_already_checked=skip_checked)
        if success:
            return web.json_response({"status": "ok", "message": msg, "count": len(names_to_check)})
        else:
            return web.json_response({"error": msg}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_scan_pause(request: web.Request) -> web.Response:
    success, msg = engine.pause_scan()
    return web.json_response({"success": success, "message": msg})

async def handle_scan_resume(request: web.Request) -> web.Response:
    success, msg = engine.resume_scan()
    return web.json_response({"success": success, "message": msg})

async def handle_scan_stop(request: web.Request) -> web.Response:
    success, msg = engine.stop_scan()
    return web.json_response({"success": success, "message": msg})

async def handle_get_results(request: web.Request) -> web.Response:
    """Fetch paginated, filterable database results."""
    status = request.query.get("status")
    length = int(request.query.get("length", 0)) if request.query.get("length") else None
    search = request.query.get("search")
    limit = int(request.query.get("limit", 100))
    offset = int(request.query.get("offset", 0))

    results = get_recent_results(status=status, length=length, search=search, limit=limit, offset=offset)
    return web.json_response({"results": results})

async def handle_export(request: web.Request) -> web.Response:
    """Export usernames as TXT or CSV download."""
    fmt = request.query.get("format", "txt").lower()
    status = request.query.get("status", "available")
    names = export_usernames(status=status)
    
    if fmt == "csv":
        content = "username,status,twitch_url\n" + "\n".join([f"{n},{status},https://twitch.tv/{n}" for n in names])
        return web.Response(
            text=content,
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="twitch_{status}_usernames.csv"'}
        )
    else:
        content = "\n".join(names)
        return web.Response(
            text=content,
            content_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="twitch_{status}_usernames.txt"'}
        )

async def handle_clear_db(request: web.Request) -> web.Response:
    """Clear all results from database."""
    clear_all_results()
    return web.json_response({"status": "ok", "message": "Database cleared"})

# ----------------- WebSocket Handler -----------------

async def handle_websocket(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    active_websockets.add(ws)

    # Send initial status immediately on connect
    initial_payload = {
        "type": "initial_state",
        "engine": engine.get_status(),
        "database": get_statistics()
    }
    await ws.send_str(json.dumps(initial_payload))

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    # Support client-side commands via WS if needed
                    cmd = data.get("cmd")
                    if cmd == "request_status":
                        await ws.send_str(json.dumps({
                            "type": "status_update",
                            "data": engine.get_status(),
                            "database": get_statistics()
                        }))
                except Exception:
                    pass
            elif msg.type == aiohttp.WSMsgType.ERROR:
                pass
    finally:
        active_websockets.discard(ws)

    return ws

# ----------------- In-Browser Bridge (Twitch Tab <-> Dashboard) -----------------

bridge_state = {
    "connected": False,
    "twitch_user": None,
    "state": "IDLE",
    "speed": 0.0,
    "tested": 0,
    "current_batch": "",
    "available": [],
    "last_seen": 0,
    "pending_command": None
}

twitch_tab_ws: Set[web.WebSocketResponse] = set()

async def broadcast_bridge_update():
    """Notify dashboard clients about bridge changes."""
    msg = json.dumps({"type": "bridge_update", "bridge": bridge_state})
    for ws in list(active_websockets):
        if not ws.closed:
            try:
                await ws.send_str(msg)
            except Exception:
                pass

async def handle_bridge_ws(request: web.Request) -> web.WebSocketResponse:
    """WebSocket connection specifically from the Twitch tab sniper script."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    twitch_tab_ws.add(ws)
    bridge_state["connected"] = True
    bridge_state["last_seen"] = time.time()
    await broadcast_bridge_update()

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    payload = json.loads(msg.data)
                    event_type = payload.get("type")
                    if event_type == "client_init":
                        bridge_state["twitch_user"] = payload.get("user")
                        bridge_state["connected"] = True
                    elif event_type == "progress":
                        bridge_state["state"] = payload.get("state", "RUNNING")
                        bridge_state["tested"] = payload.get("tested", 0)
                        bridge_state["speed"] = payload.get("speed", 0.0)
                        bridge_state["current_batch"] = payload.get("batch", "")
                    elif event_type == "hit":
                        hit_name = payload.get("username")
                        if hit_name and hit_name not in bridge_state["available"]:
                            bridge_state["available"].insert(0, hit_name)
                            # Persist hit to DB
                            save_batch_results([{
                                "username": hit_name,
                                "status": "available",
                                "length": len(hit_name),
                                "channel_id": None,
                                "display_name": None,
                                "checked_at": datetime.now().isoformat()
                            }])
                    bridge_state["last_seen"] = time.time()
                    await broadcast_bridge_update()
                except Exception as e:
                    pass
    finally:
        twitch_tab_ws.discard(ws)
        if not twitch_tab_ws:
            bridge_state["connected"] = False
        await broadcast_bridge_update()

    return ws

async def handle_bridge_command(request: web.Request) -> web.Response:
    """Send command from Dashboard to the Twitch tab."""
    try:
        data = await request.json()
        cmd = data.get("command")  # "start", "stop", "fill"
        payload = data.get("payload", {})

        bridge_state["pending_command"] = {"command": cmd, "payload": payload, "id": time.time()}

        # Send over WebSocket to Twitch tab if connected
        msg_str = json.dumps({"command": cmd, "payload": payload})
        for ws in list(twitch_tab_ws):
            if not ws.closed:
                try:
                    await ws.send_str(msg_str)
                except Exception:
                    pass

        return web.json_response({"status": "ok", "command": cmd})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_bridge_sync(request: web.Request) -> web.Response:
    """HTTP fallback sync endpoint for Twitch tab."""
    try:
        data = await request.json()
        bridge_state["connected"] = True
        bridge_state["last_seen"] = time.time()
        if "user" in data:
            bridge_state["twitch_user"] = data["user"]
        if "version" in data:
            bridge_state["bridge_version"] = data["version"]
        if "tested" in data:
            bridge_state["tested"] = data["tested"]
        if "speed" in data:
            bridge_state["speed"] = data["speed"]
        if "state" in data:
            bridge_state["state"] = data["state"]
        if "batch" in data:
            bridge_state["current_batch"] = data["batch"]
        if "hit" in data:
            hit_name = data["hit"]
            if hit_name and hit_name not in bridge_state["available"]:
                bridge_state["available"].insert(0, hit_name)
                save_batch_results([{
                    "username": hit_name,
                    "status": "available",
                    "length": len(hit_name),
                    "channel_id": None,
                    "display_name": None,
                    "checked_at": datetime.now().isoformat()
                }])

        await broadcast_bridge_update()

        # Pop any pending command for the client
        cmd = bridge_state.get("pending_command")
        bridge_state["pending_command"] = None
        return web.json_response({"status": "ok", "command": cmd})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_bridge_status(request: web.Request) -> web.Response:
    now = time.time()
    if (now - bridge_state.get("last_seen", 0)) > 6.0 and not twitch_tab_ws:
        bridge_state["connected"] = False
    return web.json_response(bridge_state)

async def handle_words_4char(request: web.Request) -> web.Response:
    """Serve 4-letter words list."""
    words_file = BASE_DIR / "data" / "words_4char.txt"
    if words_file.exists():
        return web.Response(text=words_file.read_text(encoding="utf-8"), content_type="text/plain")
    return web.Response(text="", status=404)

async def handle_words_5char(request: web.Request) -> web.Response:
    """Serve 5-letter words list."""
    words_file = BASE_DIR / "data" / "words_5char.txt"
    if words_file.exists():
        return web.Response(text=words_file.read_text(encoding="utf-8"), content_type="text/plain")
    return web.Response(text="", status=404)

async def handle_get_candidates(request: web.Request) -> web.Response:
    """Generate or retrieve candidates based on requested category / pattern."""
    try:
        if request.method == "POST":
            data = await request.json()
        else:
            data = request.query

        source = data.get("source", "pronounceable_4")
        pattern = data.get("pattern", "")
        custom_raw = data.get("custom_list", [])
        limit = int(data.get("limit", 15000))

        candidates = []

        if source == "custom_paste" and custom_raw:
            if isinstance(custom_raw, str):
                names = [x.strip().lower() for x in re.split(r"[\r\n,]+", custom_raw) if x.strip()]
            else:
                names = [str(x).strip().lower() for x in custom_raw if str(x).strip()]
            candidates = [w for w in names if is_valid_syntax(w)]

        elif source == "custom_pattern" or (pattern and (source.startswith("wildcard_") or source == "custom_pattern")):
            pat = pattern if pattern else "z***"
            candidates = list(itertools.islice(generate_by_pattern(pat), limit))

        elif source == "pronounceable_4":
            candidates = list(itertools.islice(generate_pronounceable(4), limit))

        elif source == "aesthetic_4":
            candidates = list(itertools.islice(generate_aesthetic_patterns(4), limit))

        elif source == "dictionary_4":
            candidates = load_dictionary_words(4)

        elif source == "dictionary_5":
            candidates = load_dictionary_words(5)

        elif source == "pronounceable_5":
            candidates = list(itertools.islice(generate_pronounceable(5), limit))

        elif source == "aesthetic_5":
            candidates = list(itertools.islice(generate_aesthetic_patterns(5), limit))

        elif source == "wildcard_z":
            candidates = list(generate_by_pattern("z***"))

        elif source == "wildcard_x":
            candidates = list(generate_by_pattern("x***"))

        elif source == "wildcard_q":
            candidates = list(generate_by_pattern("q***"))

        elif source == "wildcard_v":
            candidates = list(generate_by_pattern("v***"))

        elif source == "wildcard_k":
            candidates = list(generate_by_pattern("k***"))

        elif source == "wildcard_vk":
            candidates = list(generate_by_pattern("vk**"))

        elif source == "wildcard_svk_4":
            candidates = list(generate_by_pattern("*svk"))

        elif source == "wildcard_svk_5":
            candidates = list(generate_by_pattern("**svk"))

        elif source == "wildcard_cz_4":
            candidates = list(generate_by_pattern("*cz"))

        elif source == "wildcard_cz_5":
            candidates = list(generate_by_pattern("**cz"))

        elif source == "wildcard_og":
            candidates = list(generate_by_pattern("**og")) + list(generate_by_pattern("**gg")) + list(generate_by_pattern("**tv"))

        elif source == "wildcard_numbers":
            candidates = list(generate_by_pattern("**77")) + list(generate_by_pattern("**99")) + list(generate_by_pattern("**00"))

        elif source == "all_4char_alphanumeric":
            candidates = list(itertools.islice(generate_4char_alphanumeric(), limit))

        elif source in ("letters_4", "all_4char_letters"):
            candidates = list(itertools.islice(generate_4char_letters(), limit))

        elif source == "letters_4_a_e":
            all_l = "abcdefghijklmnopqrstuvwxyz"
            candidates = list(itertools.islice((f"{a}{b}{c}{d}" for a in "abcde" for b in all_l for c in all_l for d in all_l), limit))

        elif source == "letters_4_f_j":
            all_l = "abcdefghijklmnopqrstuvwxyz"
            candidates = list(itertools.islice((f"{a}{b}{c}{d}" for a in "fghij" for b in all_l for c in all_l for d in all_l), limit))

        elif source == "letters_4_k_o":
            all_l = "abcdefghijklmnopqrstuvwxyz"
            candidates = list(itertools.islice((f"{a}{b}{c}{d}" for a in "klmno" for b in all_l for c in all_l for d in all_l), limit))

        elif source == "letters_4_p_t":
            all_l = "abcdefghijklmnopqrstuvwxyz"
            candidates = list(itertools.islice((f"{a}{b}{c}{d}" for a in "pqrst" for b in all_l for c in all_l for d in all_l), limit))

        elif source == "letters_4_u_z":
            all_l = "abcdefghijklmnopqrstuvwxyz"
            candidates = list(itertools.islice((f"{a}{b}{c}{d}" for a in "uvwxyz" for b in all_l for c in all_l for d in all_l), limit))

        elif source == "alphanumeric_digits_first":
            all_an = "abcdefghijklmnopqrstuvwxyz0123456789"
            candidates = list(itertools.islice((f"{a}{b}{c}{d}" for a in "0123456789" for b in all_an for c in all_an for d in all_an), limit))

        elif source == "local_scanner":
            db_res = get_recent_results(limit=limit, status_filter="available")
            candidates = [r["username"] for r in db_res if len(r["username"]) >= 4]

        else:
            candidates = list(itertools.islice(generate_pronounceable(4), limit))

        # Return unique in order
        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return web.json_response({
            "source": source,
            "count": len(unique),
            "candidates": unique
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_userscript(request: web.Request) -> web.Response:
    """Serve Tampermonkey 1-click installable Userscript (Live Auto-updating loader)."""
    userscript_content = """// ==UserScript==
// @name         Twitch Short Username Sniper Bridge
// @namespace    http://localhost:5050/
// @version      4.0
// @description  Connects Twitch settings directly to your local Name Sniper Dashboard (20x HyperTurbo)
// @match        https://www.twitch.tv/settings/profile*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

(function () {
  console.log("🚀 Twitch Sniper Bridge v4.0 HyperTurbo Loader initializing...");
  function loadSniper() {
    if (typeof GM_xmlhttpRequest !== "undefined") {
      GM_xmlhttpRequest({
        method: "GET",
        url: "http://127.0.0.1:5050/static/browser_sniper.js?t=" + Date.now(),
        onload: function (res) {
          try {
            new Function(res.responseText)();
          } catch (e) {
            console.error("Sniper script execution error:", e);
          }
        },
        onerror: function (err) {
          console.warn("GM_xmlhttpRequest failed, falling back to fetch", err);
          fetch("http://127.0.0.1:5050/static/browser_sniper.js?t=" + Date.now())
            .then(r => r.text())
            .then(code => new Function(code)())
            .catch(console.error);
        }
      });
    } else {
      fetch("http://127.0.0.1:5050/static/browser_sniper.js?t=" + Date.now())
        .then(r => r.text())
        .then(code => new Function(code)())
        .catch(console.error);
    }
  }
  loadSniper();
})();
"""
    return web.Response(
        text=userscript_content,
        content_type="text/javascript",
        headers={"Content-Disposition": 'inline; filename="twitch_sniper.user.js"'}
    )

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

def create_app() -> web.Application:
    init_db()
    app = web.Application(middlewares=[cors_middleware])
    
    # Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/check-single", handle_check_single)
    app.router.add_post("/api/scan/start", handle_scan_start)
    app.router.add_post("/api/scan/pause", handle_scan_pause)
    app.router.add_post("/api/scan/resume", handle_scan_resume)
    app.router.add_post("/api/scan/stop", handle_scan_stop)
    app.router.add_get("/api/results", handle_get_results)
    app.router.add_get("/api/export", handle_export)
    app.router.add_post("/api/clear", handle_clear_db)
    app.router.add_get("/ws", handle_websocket)

    # Bridge routes (Twitch Tab <-> Dashboard)
    app.router.add_get("/api/bridge/status", handle_bridge_status)
    app.router.add_post("/api/bridge/sync", handle_bridge_sync)
    app.router.add_post("/api/bridge/command", handle_bridge_command)
    app.router.add_get("/ws/bridge", handle_bridge_ws)
    app.router.add_get("/twitch_sniper.user.js", handle_userscript)
    app.router.add_get("/api/words/4char", handle_words_4char)
    app.router.add_get("/api/words/5char", handle_words_5char)
    app.router.add_route("*", "/api/candidates", handle_get_candidates)

    # Static files for web assets
    web_dir = BASE_DIR / "web"
    app.router.add_static("/static/", path=str(web_dir), name="static")

    return app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 Starting Twitch Username Checker Dashboard at http://localhost:{port}")
    app = create_app()
    web.run_app(app, host="127.0.0.1", port=port)
