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
from backend.db.base import DB_PATH, get_connection, resequence_question_numbers
from backend.db.questions import clean_duplicate_questions


def run_database_diagnostics() -> Dict[str, Any]:
    """Runs a complete diagnostic health check on the SQLite database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Integrity check
    cursor.execute("PRAGMA integrity_check")
    integrity = cursor.fetchone()[0]
    
    # 2. Total questions & unique questions
    cursor.execute("SELECT COUNT(*) FROM questions")
    total_q = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT LOWER(TRIM(content_text))) FROM questions")
    unique_q = cursor.fetchone()[0]
    duplicate_count = total_q - unique_q
    
    # 3. Breakdown by subject
    cursor.execute("SELECT subject, COUNT(*) FROM questions GROUP BY subject")
    by_subject = {r[0] or "unknown": r[1] for r in cursor.fetchall()}
    
    # 4. Breakdown by grade
    cursor.execute("SELECT grade, COUNT(*) FROM questions GROUP BY grade ORDER BY grade")
    by_grade = {f"Lớp {r[0]}": r[1] for r in cursor.fetchall()}
    
    # 5. Breakdown by platform
    cursor.execute("SELECT source_platform, COUNT(*) FROM questions GROUP BY source_platform")
    by_platform = {r[0] or "unknown": r[1] for r in cursor.fetchall()}
    
    # 6. Breakdown by difficulty
    cursor.execute("SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty")
    by_diff = {r[0] or "medium": r[1] for r in cursor.fetchall()}
    
    # 7. Quality Anomalies & Content Validity Check
    cursor.execute("SELECT COUNT(*) FROM questions WHERE options IS NULL OR options = '[]' OR options = ''")
    no_options_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE correct_answer IS NULL OR correct_answer = ''")
    no_answer_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE explanation IS NULL OR explanation = ''")
    no_explanation_count = cursor.fetchone()[0]

    from backend.normalizer import is_valid_question_payload
    cursor.execute("SELECT id, content_text, content_html, options, question_type FROM questions")
    all_diag_rows = cursor.fetchall()
    corrupt_ids = []
    for r in all_diag_rows:
        try:
            opts = json.loads(r[3]) if r[3] else []
        except Exception:
            opts = []
        q_dict = {
            "id": r[0],
            "content_text": r[1],
            "content_html": r[2],
            "options": opts,
            "question_type": r[4]
        }
        valid, _ = is_valid_question_payload(q_dict)
        if not valid:
            corrupt_ids.append(r[0])
    corrupt_count = len(corrupt_ids)
    
    # 8. Table stats
    cursor.execute("SELECT COUNT(*) FROM exams")
    total_exams = cursor.fetchone()[0]
    try:
        cursor.execute("SELECT COUNT(*) FROM collector_logs")
        total_logs = cursor.fetchone()[0]
    except Exception:
        total_logs = 0

    # 9. File size
    file_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    
    conn.close()
    
    return {
        "success": True,
        "status": "healthy" if integrity == "ok" and duplicate_count == 0 and corrupt_count == 0 else "needs_attention",
        "integrity": integrity,
        "sqlite_integrity": integrity,
        "total_questions": total_q,
        "unique_questions": unique_q,
        "duplicate_copies": duplicate_count,
        "duplicate_copies_count": duplicate_count,
        "by_subject": by_subject,
        "by_grade": by_grade,
        "by_platform": by_platform,
        "by_difficulty": by_diff,
        "anomalies": {
            "corrupt_questions": corrupt_count,
            "no_options": no_options_count,
            "no_correct_answer": no_answer_count,
            "no_explanation": no_explanation_count
        },
        "table_stats": {
            "questions": total_q,
            "exams": total_exams,
            "system_logs": total_logs
        },
        "db_file_size_kb": round(file_size_bytes / 1024, 1),
        "db_path": DB_PATH
    }



def fix_database_issues() -> Dict[str, Any]:
    """Repairs and optimizes the database by cleaning corrupt questions, removing duplicates, and optimizing storage."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 0. Clean corrupt and invalid non-question entries (HTML dumps, contact info, blog descriptions)
    from backend.normalizer import is_valid_question_payload
    cursor.execute("SELECT id, content_text, content_html, options, question_type FROM questions")
    all_rows = cursor.fetchall()
    corrupt_ids = []
    for r in all_rows:
        try:
            opts = json.loads(r[3]) if r[3] else []
        except Exception:
            opts = []
        q_dict = {
            "id": r[0],
            "content_text": r[1],
            "content_html": r[2],
            "options": opts,
            "question_type": r[4]
        }
        valid, _ = is_valid_question_payload(q_dict)
        if not valid:
            corrupt_ids.append(r[0])
            
    corrupt_deleted = 0
    if corrupt_ids:
        placeholders = ",".join("?" for _ in corrupt_ids)
        cursor.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", corrupt_ids)
        corrupt_deleted = cursor.rowcount
        resequence_question_numbers(cursor)
    conn.commit()
    conn.close()

    # 1. Clean duplicates (keep oldest)
    clean_res = clean_duplicate_questions(action="keep_oldest")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 2. Fix empty subjects
    from backend.classifier import classify_subject
    cursor.execute("SELECT id, content_text FROM questions WHERE subject IS NULL OR subject = '' OR subject = 'unknown'")
    unknown_rows = cursor.fetchall()
    reclassified = 0
    for row in unknown_rows:
        q_id, c_text = row[0], row[1]
        correct_sub = classify_subject(c_text)
        cursor.execute("UPDATE questions SET subject = ? WHERE id = ?", (correct_sub, q_id))
        reclassified += 1
        
    # 3. Resequence numbers again to guarantee 1..N continuous numbering
    resequence_question_numbers(cursor)

    # 4. Vacuum and analyze SQLite DB
    conn.commit()
    cursor.execute("VACUUM")
    cursor.execute("ANALYZE")
    conn.close()
    
    diag = run_database_diagnostics()
    return {
        "success": True,
        "corrupt_cleaned": corrupt_deleted,
        "duplicates_cleaned": clean_res["deleted_count"],
        "subjects_reclassified": reclassified,
        "current_total": diag["total_questions"],
        "diagnostics": diag
    }
