"""
SQLite Database manager for caching and persisting checked Twitch usernames.
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from .config import DB_PATH

_lock = threading.Lock()

def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize database tables and indexes."""
    with _lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checked_usernames (
                username TEXT PRIMARY KEY,
                status TEXT NOT NULL,           -- 'available', 'taken', 'locked', 'invalid'
                length INTEGER NOT NULL,
                channel_id TEXT,
                display_name TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON checked_usernames(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_length ON checked_usernames(length)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checked_at ON checked_usernames(checked_at)")
        conn.commit()
        conn.close()

def save_batch_results(results: List[Dict[str, Any]], db_path: Path = DB_PATH) -> None:
    """Insert or replace a batch of results."""
    if not results:
        return
    with _lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR REPLACE INTO checked_usernames 
            (username, status, length, channel_id, display_name, checked_at)
            VALUES (:username, :status, :length, :channel_id, :display_name, :checked_at)
        """, results)
        conn.commit()
        conn.close()

def get_already_checked_usernames(db_path: Path = DB_PATH) -> Set[str]:
    """Retrieve set of all previously checked usernames."""
    with _lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM checked_usernames")
        rows = cursor.fetchall()
        conn.close()
        return {r["username"] for r in rows}

def get_statistics(db_path: Path = DB_PATH) -> Dict[str, int]:
    """Get aggregate statistics."""
    with _lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN status = 'taken' THEN 1 ELSE 0 END) as taken,
                SUM(CASE WHEN status = 'locked' THEN 1 ELSE 0 END) as locked,
                SUM(CASE WHEN status = 'invalid' THEN 1 ELSE 0 END) as invalid
            FROM checked_usernames
        """)
        row = cursor.fetchone()
        conn.close()
        return {
            "total": row["total"] or 0,
            "available": row["available"] or 0,
            "taken": row["taken"] or 0,
            "locked": row["locked"] or 0,
            "invalid": row["invalid"] or 0
        }

def get_recent_results(
    status: Optional[str] = None,
    length: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db_path: Path = DB_PATH
) -> List[Dict[str, Any]]:
    """Query results with filtering and pagination."""
    query = "SELECT username, status, length, channel_id, display_name, checked_at FROM checked_usernames WHERE 1=1"
    params = []

    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    if length and length > 0:
        query += " AND length = ?"
        params.append(length)
    if search:
        query += " AND username LIKE ?"
        params.append(f"%{search.lower()}%")

    query += " ORDER BY CASE WHEN status = 'available' THEN 0 ELSE 1 END, checked_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with _lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def export_usernames(status: str = "available", filepath: Optional[Path] = None, db_path: Path = DB_PATH) -> List[str]:
    """Export usernames matching status as a list of strings."""
    with _lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM checked_usernames WHERE status = ? ORDER BY length ASC, username ASC", (status,))
        rows = cursor.fetchall()
        conn.close()
        names = [r["username"] for r in rows]

    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            for n in names:
                f.write(f"{n}\n")
    return names

def clear_all_results(db_path: Path = DB_PATH) -> None:
    """Clear all results from database."""
    with _lock:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM checked_usernames")
        conn.commit()
        conn.close()
