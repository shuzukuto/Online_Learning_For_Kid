from __future__ import annotations
import hashlib
import json
import os
import random
import re
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from backend.db.base import VN_TZ, get_connection


# Logs
def log_collector_event(platform: str, status: str, message: str, count: int = 0):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now(VN_TZ).isoformat()
    cursor.execute("""
        INSERT INTO collector_logs (platform, status, message, items_count, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (platform, status, message, count, now))
    conn.commit()
    conn.close()



def get_collector_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM collector_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows



def clear_collector_logs() -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM collector_logs")
    conn.commit()
    conn.close()
    return True



def get_system_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves a configuration value from system_config table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            return row[0]
        return default
    except Exception:
        return default
    finally:
        conn.close()



def set_system_config(key: str, value: str) -> None:
    """Sets or updates a configuration value in system_config table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
    finally:
        conn.close()
