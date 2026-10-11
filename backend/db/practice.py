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



# ----------------- Practice History & Analytics -----------------

def save_practice_history(record: Dict[str, Any]) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    p_id = record.get("id") or str(uuid.uuid4())[:12]
    now = record.get("created_at") or datetime.now(VN_TZ).isoformat()
    
    answers_detail_str = None
    if "answers_detail" in record and record["answers_detail"] is not None:
        if isinstance(record["answers_detail"], str):
            answers_detail_str = record["answers_detail"]
        else:
            answers_detail_str = json.dumps(record["answers_detail"], ensure_ascii=False)
            
    cursor.execute("""
        INSERT INTO practice_history (
            id, exam_id, exam_title, subject, grade, total_questions,
            correct_count, wrong_count, skipped_count, score, max_score,
            duration_seconds, time_spent_seconds, ranking, answers_detail, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p_id,
        record.get("exam_id"),
        record.get("exam_title", "Bài luyện tập"),
        record.get("subject", "math"),
        record.get("grade", 5),
        record.get("total_questions", 0),
        record.get("correct_count", 0),
        record.get("wrong_count", 0),
        record.get("skipped_count", 0),
        round(float(record.get("score", 0.0)), 2),
        round(float(record.get("max_score", 10.0)), 2),
        record.get("duration_seconds", 0),
        record.get("time_spent_seconds", 0),
        record.get("ranking", "Trung bình"),
        answers_detail_str,
        now
    ))
    conn.commit()
    conn.close()
    return p_id



def get_practice_history(limit: int = 50, subject: Optional[str] = None, grade: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    if grade is not None and str(grade).strip() != "" and int(grade) >= 0:
        conditions.append("grade = ?")
        params.append(int(grade))
        
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cursor.execute(f"""
        SELECT * FROM practice_history
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
    """, params + [limit])
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("answers_detail"):
            try:
                d["answers_detail"] = json.loads(d["answers_detail"])
            except Exception:
                pass
        if d.get("max_score") and d["max_score"] > 0:
            d["score_100"] = round((d["score"] / d["max_score"]) * 100.0, 1)
        else:
            d["score_100"] = round(d["score"] * 10.0, 1)
        results.append(d)
    conn.close()
    return results



def get_practice_history_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM practice_history WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("answers_detail"):
        try:
            d["answers_detail"] = json.loads(d["answers_detail"])
        except Exception:
            pass
    if d.get("max_score") and d["max_score"] > 0:
        d["score_100"] = round((d["score"] / d["max_score"]) * 100.0, 1)
    else:
        d["score_100"] = round(d["score"] * 10.0, 1)
    return d



def _evaluate_badges(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Evaluates 8 distinct gamification achievement badges."""
    total_attempts = len(history)
    max_score = max([float(h.get("score") or 0) for h in history], default=0.0)
    avg_score = round(sum([float(h.get("score") or 0) for h in history]) / total_attempts, 2) if total_attempts > 0 else 0.0
    excellent_count = sum(1 for h in history if (h.get("ranking") == "Xuất sắc" or float(h.get("score") or 0) >= 9.0))
    math_attempts = sum(1 for h in history if h.get("subject") == "math")
    subjects_practiced = set(h.get("subject") for h in history if h.get("subject"))
    fast_attempts = sum(1 for h in history if (h.get("time_spent_seconds", 0) > 0 and h.get("duration_seconds", 0) > 0 and h.get("time_spent_seconds", 0) <= h.get("duration_seconds", 0) / 2 and float(h.get("score") or 0) >= 8.0))
    perfect_attempts = sum(1 for h in history if float(h.get("score") or 0) >= float(h.get("max_score") or 10.0))
    
    badge_defs = [
        {
            "id": "badge_first_step",
            "title": "Bước Đầu Chinh Phục",
            "description": "Hoàn thành bài thi luyện tập đầu tiên",
            "icon": "🌱",
            "category": "milestone",
            "unlocked": total_attempts >= 1,
            "progress": f"{min(total_attempts, 1)}/1 bài"
        },
        {
            "id": "badge_perfect_score",
            "title": "Điểm Mười Hoàn Hảo",
            "description": "Đạt điểm tuyệt đối (10/10) trong một bài luyện tập",
            "icon": "💯",
            "category": "accuracy",
            "unlocked": perfect_attempts >= 1 or max_score >= 10.0,
            "progress": f"{perfect_attempts}/1 lần điểm 10"
        },
        {
            "id": "badge_speed_racer",
            "title": "Tốc Độ Siêu Phàm",
            "description": "Nộp bài dưới 50% thời gian cho phép và đạt điểm Giỏi trở lên",
            "icon": "⚡",
            "category": "speed",
            "unlocked": fast_attempts >= 1,
            "progress": f"{fast_attempts}/1 lần"
        },
        {
            "id": "badge_math_master",
            "title": "Chiến Binh Toán Học",
            "description": "Luyện tập hoàn thành ít nhất 3 đề Toán",
            "icon": "📐",
            "category": "subject",
            "unlocked": math_attempts >= 3,
            "progress": f"{min(math_attempts, 3)}/3 bài Toán"
        },
        {
            "id": "badge_scholar",
            "title": "Học Giả Xuất Sắc",
            "description": "Đạt xếp loại Xuất sắc (>= 9.0) ít nhất 3 lần",
            "icon": "👑",
            "category": "mastery",
            "unlocked": excellent_count >= 3,
            "progress": f"{min(excellent_count, 3)}/3 lần Xuất sắc"
        },
        {
            "id": "badge_persistent",
            "title": "Chiến Binh Bền Bỉ",
            "description": "Kiên trì hoàn thành 5 bài thi luyện tập",
            "icon": "🛡️",
            "category": "persistence",
            "unlocked": total_attempts >= 5,
            "progress": f"{min(total_attempts, 5)}/5 bài"
        },
        {
            "id": "badge_multilingual",
            "title": "Toàn Năng Đa Môn",
            "description": "Luyện tập tối thiểu 2 môn học khác nhau",
            "icon": "🌟",
            "category": "breadth",
            "unlocked": len(subjects_practiced) >= 2,
            "progress": f"{min(len(subjects_practiced), 2)}/2 môn"
        },
        {
            "id": "badge_top_tier",
            "title": "Đỉnh Cao Tri Thức",
            "description": "Duy trì điểm trung bình tổng thể từ 8.5 điểm trở lên",
            "icon": "🏆",
            "category": "excellence",
            "unlocked": total_attempts >= 3 and avg_score >= 8.5,
            "progress": f"ĐTB {avg_score}/8.5 ({total_attempts}/3 bài)"
        }
    ]
    return badge_defs



def get_practice_analytics(subject: Optional[str] = None, grade: Optional[int] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    conditions = []
    params = []
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    if grade is not None and str(grade).strip() != "" and int(grade) >= 0:
        conditions.append("grade = ?")
        params.append(int(grade))
        
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    
    cursor.execute(f"SELECT COUNT(*) FROM practice_history {where_clause}", params)
    total_attempts = cursor.fetchone()[0]
    
    if total_attempts == 0:
        conn.close()
        return {
            "total_attempts": 0,
            "total_questions_answered": 0,
            "total_correct": 0,
            "overall_accuracy": 0.0,
            "average_score": 0.0,
            "highest_score": 0.0,
            "trending_scores": [],
            "subject_mastery": [],
            "recent_history": [],
            "badges": _evaluate_badges([])
        }
        
    cursor.execute(f"""
        SELECT 
            SUM(total_questions) as total_q,
            SUM(correct_count) as total_c,
            AVG(score) as avg_s,
            MAX(score) as max_s
        FROM practice_history {where_clause}
    """, params)
    agg = cursor.fetchone()
    total_questions = agg[0] or 0
    total_correct = agg[1] or 0
    avg_score = round(float(agg[2] or 0.0), 2)
    max_score = round(float(agg[3] or 0.0), 2)
    overall_accuracy = round((total_correct / total_questions * 100.0), 1) if total_questions > 0 else 0.0
    
    # Chronological trending scores (up to 30)
    cursor.execute(f"""
        SELECT id, exam_title, subject, score, max_score, created_at, ranking
        FROM practice_history {where_clause}
        ORDER BY created_at ASC
        LIMIT 30
    """, params)
    trend_rows = cursor.fetchall()
    trending_scores = []
    for r in trend_rows:
        sc = float(r["score"])
        m_sc = float(r["max_score"]) if r["max_score"] else 10.0
        pct = round((sc / m_sc * 100.0), 1) if m_sc > 0 else sc * 10.0
        trending_scores.append({
            "id": r["id"],
            "exam_title": r["exam_title"],
            "subject": r["subject"],
            "score": sc,
            "max_score": m_sc,
            "percentage": pct,
            "ranking": r["ranking"],
            "created_at": r["created_at"]
        })
        
    # Subject mastery breakdown
    cursor.execute("""
        SELECT 
            subject,
            COUNT(*) as attempts,
            SUM(total_questions) as sub_total_q,
            SUM(correct_count) as sub_correct,
            AVG(score) as sub_avg_score
        FROM practice_history
        GROUP BY subject
    """)
    sub_rows = cursor.fetchall()
    subject_labels = {
        "math": "Toán học",
        "vietnamese": "Tiếng Việt",
        "english": "Tiếng Anh",
        "science": "Khoa học",
        "informatics": "Tin học"
    }
    subject_mastery = []
    for sr in sub_rows:
        s_name = sr["subject"] or "math"
        s_tot = sr["sub_total_q"] or 0
        s_cor = sr["sub_correct"] or 0
        s_acc = round((s_cor / s_tot * 100.0), 1) if s_tot > 0 else 0.0
        subject_mastery.append({
            "subject": s_name,
            "subject_label": subject_labels.get(s_name, s_name.capitalize()),
            "attempts": sr["attempts"],
            "total_questions": s_tot,
            "correct_count": s_cor,
            "accuracy_rate": s_acc,
            "average_score": round(float(sr["sub_avg_score"] or 0.0), 2)
        })
        
    cursor.execute("SELECT * FROM practice_history ORDER BY created_at DESC")
    all_history = [dict(r) for r in cursor.fetchall()]
    badges = _evaluate_badges(all_history)
    
    conn.close()
    recent_history = get_practice_history(limit=10, subject=subject, grade=grade)
    
    return {
        "total_attempts": total_attempts,
        "total_questions_answered": total_questions,
        "total_correct": total_correct,
        "overall_accuracy": overall_accuracy,
        "average_score": avg_score,
        "highest_score": max_score,
        "trending_scores": trending_scores,
        "subject_mastery": subject_mastery,
        "recent_history": recent_history,
        "badges": badges
    }
