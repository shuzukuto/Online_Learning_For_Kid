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


# ============================================================================
# Active Lexicon Learning (Human-in-the-Loop OCR Memory)
# ============================================================================
_ocr_corrections_cache = {"data": None, "timestamp": 0}


OCR_CORRECTIONS_TTL = 15  # seconds



def invalidate_ocr_corrections_cache():
    """Expires in-memory cache of user-trained OCR corrections."""
    _ocr_corrections_cache["data"] = None
    _ocr_corrections_cache["timestamp"] = 0



def record_ocr_learning_diff(raw_text: str, corrected_text: str, source: str = "manual_feedback") -> List[Dict[str, Any]]:
    """
    Compares original raw OCR text with human-corrected text using SequenceMatcher.
    Extracts phrase/word-level corrections and stores/updates them in ocr_corrections.
    Returns list of newly learned or incremented items.
    """
    if not raw_text or not corrected_text:
        return []

    import difflib
    import unicodedata

    raw_norm = unicodedata.normalize('NFC', raw_text.strip())
    corr_norm = unicodedata.normalize('NFC', corrected_text.strip())
    if raw_norm == corr_norm:
        return []

    raw_tokens = raw_norm.split()
    corr_tokens = corr_norm.split()

    matcher = difflib.SequenceMatcher(None, raw_tokens, corr_tokens)
    learned = []

    now_iso = datetime.now(VN_TZ).isoformat()
    conn = get_connection()
    cursor = conn.cursor()

    try:
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                raw_slice = raw_tokens[i1:i2]
                corr_slice = corr_tokens[j1:j2]

                # Limit phrase length to max 12 words to avoid full-paragraph mismatches
                if len(raw_slice) > 12 or len(corr_slice) > 12:
                    continue

                w = " ".join(raw_slice).strip('.,:;!?()[]{}"\' \t\n')
                c = " ".join(corr_slice).strip('.,:;!?()[]{}"\' \t\n')

                if not w or not c:
                    continue
                if w.lower() == c.lower():
                    continue
                if len(w) < 2 or len(c) < 2:
                    continue
                if w.isdigit() and c.isdigit():
                    continue

                # Upsert into ocr_corrections
                cursor.execute("""
                    INSERT INTO ocr_corrections (wrong_text, correct_text, frequency, source, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                    ON CONFLICT(wrong_text) DO UPDATE SET
                        correct_text = excluded.correct_text,
                        frequency = frequency + 1,
                        updated_at = excluded.updated_at
                """, (w, c, source, now_iso, now_iso))

                learned.append({"wrong": w, "correct": c})

        conn.commit()
        if learned:
            invalidate_ocr_corrections_cache()
    except Exception as e:
        print(f"[record_ocr_learning_diff] Error: {e}")
    finally:
        conn.close()

    return learned



def get_ocr_corrections_map() -> Dict[str, str]:
    """Returns mapping wrong_text -> correct_text ordered by descending length so longer phrases replace first."""
    global _ocr_corrections_cache
    now = time.time()
    if _ocr_corrections_cache["data"] is not None and (now - _ocr_corrections_cache["timestamp"] < OCR_CORRECTIONS_TTL):
        return _ocr_corrections_cache["data"]

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT wrong_text, correct_text FROM ocr_corrections ORDER BY LENGTH(wrong_text) DESC")
        rows = cursor.fetchall()
        mapping = {r[0]: r[1] for r in rows}
        _ocr_corrections_cache["data"] = mapping
        _ocr_corrections_cache["timestamp"] = now
        return mapping
    except Exception as e:
        return {}
    finally:
        conn.close()



def get_ocr_corrections(page: int = 1, page_size: int = 50, search: str = "") -> Tuple[List[Dict[str, Any]], int]:
    """Retrieves paginated list of learned OCR corrections for dashboard view."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where_clause = ""
        params = []
        if search:
            where_clause = "WHERE wrong_text LIKE ? OR correct_text LIKE ?"
            s_param = f"%{search}%"
            params.extend([s_param, s_param])

        cursor.execute(f"SELECT COUNT(*) FROM ocr_corrections {where_clause}", params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        cursor.execute(f"""
            SELECT id, wrong_text, correct_text, frequency, source, created_at, updated_at
            FROM ocr_corrections
            {where_clause}
            ORDER BY frequency DESC, updated_at DESC
            LIMIT ? OFFSET ?
        """, params)
        items = [dict(r) for r in cursor.fetchall()]
        return items, total
    finally:
        conn.close()



def add_manual_ocr_correction(wrong_text: str, correct_text: str, source: str = "manual_rule") -> Dict[str, Any]:
    """Manually adds or updates a specific correction rule in the lexicon."""
    w = wrong_text.strip()
    c = correct_text.strip()
    if not w or not c:
        raise ValueError("Từ sai và từ sửa đổi không được để trống")
    now_iso = datetime.now(VN_TZ).isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ocr_corrections (wrong_text, correct_text, frequency, source, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?, ?)
            ON CONFLICT(wrong_text) DO UPDATE SET
                correct_text = excluded.correct_text,
                frequency = frequency + 1,
                updated_at = excluded.updated_at
        """, (w, c, source, now_iso, now_iso))
        conn.commit()
        cursor.execute("SELECT id, wrong_text, correct_text, frequency, source, created_at, updated_at FROM ocr_corrections WHERE wrong_text = ?", (w,))
        row = cursor.fetchone()
        invalidate_ocr_corrections_cache()
        return dict(row) if row else {"wrong_text": w, "correct_text": c, "source": source}
    finally:
        conn.close()



def delete_ocr_correction(correction_id: int) -> bool:
    """Deletes a learned correction rule by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ocr_corrections WHERE id = ?", (correction_id,))
        affected = cursor.rowcount > 0
        conn.commit()
        if affected:
            invalidate_ocr_corrections_cache()
        return affected
    finally:
        conn.close()



def clear_all_ocr_corrections() -> int:
    """Clears all learned corrections."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ocr_corrections")
        affected = cursor.rowcount
        conn.commit()
        invalidate_ocr_corrections_cache()
        return affected
    finally:
        conn.close()
