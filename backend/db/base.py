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
VN_TZ = timezone(timedelta(hours=7))



DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "questions.db",
)



# --- Performance: Stats Cache (TTL 5s) ---
_stats_cache = {"data": None, "timestamp": 0}


STATS_CACHE_TTL = 5



def invalidate_stats_cache():
    """Call after any INSERT/DELETE/UPDATE on questions to expire cached stats."""
    _stats_cache["data"] = None
    _stats_cache["timestamp"] = 0



def compute_content_hash(text: str) -> str:
    """Compute MD5 hash of normalized content for fast dedup lookups."""
    normalized = (text or "").strip().lower()
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()




def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 30000;")
    cursor.close()
    return conn



def resequence_question_numbers(cursor=None):
    """Ensures all questions in the bank have strict sequential numbers 1 to N without gaps.
    Uses indexed UPDATE ... FROM with WHERE questions.q_number IS NOT numbered.rn to avoid O(N^2) scans
    and avoid triggering FTS updates on unchanged rows.
    """
    own_conn = False
    if cursor is None:
        conn = get_connection()
        cursor = conn.cursor()
        own_conn = True
        
    cursor.execute("""
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC) as rn
            FROM questions
        )
        UPDATE questions
        SET q_number = numbered.rn
        FROM numbered
        WHERE questions.id = numbered.id AND questions.q_number IS NOT numbered.rn;
    """)
    
    if own_conn:
        conn.commit()
        conn.close()
