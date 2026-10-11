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
from backend.db.questions import row_to_dict


# Exam functions
def create_exam(exam: Dict[str, Any]) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    exam_id = exam.get("id") or str(uuid.uuid4())[:8]
    now = datetime.now(VN_TZ).isoformat()
    q_ids_str = json.dumps(exam.get("question_ids", []), ensure_ascii=False)
    
    cursor.execute("""
        INSERT INTO exams (id, title, grade, duration_minutes, header_info, notes, question_ids, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exam_id,
        exam.get("title", "Đề thi mới"),
        exam.get("grade", 5),
        exam.get("duration_minutes", 45),
        exam.get("header_info"),
        exam.get("notes"),
        q_ids_str,
        now
    ))
    conn.commit()
    conn.close()
    return exam_id



def get_exams() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exams ORDER BY created_at DESC")
    rows = cursor.fetchall()
    exams = [row_to_dict(r) for r in rows]
    conn.close()
    return exams



def get_exam_by_id(exam_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    exam = row_to_dict(row)
    
    # Fetch all questions in this exam
    q_ids = exam.get("question_ids", [])
    questions = []
    for qid in q_ids:
        cursor.execute("SELECT * FROM questions WHERE id = ?", (qid,))
        qr = cursor.fetchone()
        if qr:
            questions.append(row_to_dict(qr))
            
    exam["questions"] = questions
    conn.close()
    return exam



def delete_exam(exam_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
