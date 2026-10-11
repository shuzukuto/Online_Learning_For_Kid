from __future__ import annotations
"""EduQuest Pro — Spaced-repetition review queue (P1.3b).

Minimal Leitner-style scheduler: each tracked question keeps
``repetitions`` (consecutive correct streak), ``interval_days`` and
``due_at``. Correct → advance 1→3→7→14→30d; wrong → reset to 1 day.

Works against the live DB (via backend.db.base) or any explicit
sqlite path (tests pass a temp file).
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

VN_TZ = timezone(timedelta(hours=7))

INTERVALS = [1, 3, 7, 14, 30]


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    if db_path is None:
        from backend.db.base import get_connection
        return get_connection()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS review_queue (
            question_id TEXT PRIMARY KEY,
            subject TEXT DEFAULT 'math',
            grade INTEGER DEFAULT 5,
            repetitions INTEGER DEFAULT 0,
            interval_days INTEGER DEFAULT 1,
            due_at TEXT,
            last_result TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()


def record_review_results(
    db_or_results: Union[str, List[Dict[str, Any]], None] = None,
    results: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> int:
    """Records per-question correct/wrong outcomes; returns rows touched.

    Accepts record_review_results(db_path, results) or
    record_review_results(results) for the live DB.
    """
    if isinstance(db_or_results, list) or db_or_results is None and isinstance(results, list):
        db_path = None
        items = db_or_results if isinstance(db_or_results, list) else results
    else:
        db_path = db_or_results
        items = results or []
    now = now or datetime.now(VN_TZ)
    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        touched = 0
        for r in items or []:
            qid = str(r.get("question_id", "")).strip()
            if not qid:
                continue
            correct = bool(r.get("correct", False))
            subject = r.get("subject", "math")
            grade = r.get("grade", 5)
            row = conn.execute(
                "SELECT repetitions, interval_days FROM review_queue WHERE question_id = ?",
                (qid,),
            ).fetchone()
            reps = int(row["repetitions"]) if row else 0
            if correct:
                reps += 1
                interval = INTERVALS[min(reps - 1, len(INTERVALS) - 1)]
            else:
                reps = 0
                interval = INTERVALS[0]
            due_at = (now + timedelta(days=interval)).isoformat()
            conn.execute(
                """
                INSERT INTO review_queue
                    (question_id, subject, grade, repetitions, interval_days, due_at, last_result, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(question_id) DO UPDATE SET
                    subject=excluded.subject, grade=excluded.grade,
                    repetitions=excluded.repetitions, interval_days=excluded.interval_days,
                    due_at=excluded.due_at, last_result=excluded.last_result,
                    updated_at=excluded.updated_at
                """,
                (qid, subject, grade, reps, interval, due_at,
                 "correct" if correct else "wrong", now.isoformat()),
            )
            touched += 1
        conn.commit()
        return touched
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def get_review_state(db_path: Optional[str], question_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT * FROM review_queue WHERE question_id = ?", (question_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_due_reviews(
    db_path: Optional[str] = None,
    subject: Optional[str] = None,
    grade: Optional[int] = None,
    limit: int = 50,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    now = now or datetime.now(VN_TZ)
    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        q = "SELECT * FROM review_queue WHERE due_at IS NOT NULL AND due_at <= ?"
        params: List[Any] = [now.isoformat()]
        if subject:
            q += " AND subject = ?"
            params.append(subject)
        if grade is not None:
            q += " AND grade = ?"
            params.append(grade)
        q += " ORDER BY due_at ASC LIMIT ?"
        params.append(max(1, int(limit)))
        return [_row_to_dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def get_review_stats(
    db_path: Optional[str] = None,
    subject: Optional[str] = None,
    grade: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(VN_TZ)
    conn = _connect(db_path)
    try:
        _ensure_table(conn)
        q = "SELECT COUNT(*) AS c FROM review_queue WHERE 1=1"
        params: List[Any] = []
        if subject:
            q += " AND subject = ?"
            params.append(subject)
        if grade is not None:
            q += " AND grade = ?"
            params.append(grade)
        total = conn.execute(q, params).fetchone()["c"]
        due = len(get_due_reviews(db_path, subject=subject, grade=grade, limit=100000, now=now))
        return {"total_tracked": total, "due_count": due}
    finally:
        conn.close()
