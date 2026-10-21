"""Interactive Practice Arena, Grading & Spaced Repetition APIRouter."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from backend.database import (
    get_exam_by_id,
    get_questions,
    get_question_by_id,
    save_practice_history,
    get_practice_history,
    get_practice_history_by_id,
    get_practice_analytics,
    get_due_reviews,
    get_review_stats,
    record_review_results,
)
from backend.models import PracticeSubmitRequest

VN_TZ = timezone(timedelta(hours=7))
logger = logging.getLogger("eduquest.practice")

router = APIRouter(tags=["Practice Arena"])


@router.post("/api/practice/generate")
async def generate_practice_session(payload: dict):
    """
    Generates a set of questions tailored for interactive practice.
    Supports either pre-built exam by exam_id, or dynamic criteria (subject, grade, count, difficulty).
    """
    exam_id = payload.get("exam_id")
    subject = payload.get("subject", "math")
    grade = int(payload.get("grade", 5))
    count = int(payload.get("count", 10))
    difficulty = payload.get("difficulty", "all")
    
    if exam_id:
        exam = get_exam_by_id(exam_id)
        if exam:
            return {
                "success": True,
                "exam_id": exam["id"],
                "exam_title": exam["title"],
                "duration_minutes": exam.get("duration_minutes", 45),
                "duration_seconds": exam.get("duration_minutes", 45) * 60,
                "grade": exam.get("grade", grade),
                "subject": subject,
                "total_questions": len(exam.get("questions", [])),
                "questions": exam.get("questions", [])
            }
            
    # Dynamic generation from question bank
    items, total = get_questions(
        subject=subject,
        grade=grade,
        difficulty=difficulty if difficulty != "all" else None,
        page=1,
        page_size=count
    )
    
    # If insufficient, relax difficulty
    if len(items) < count and difficulty != "all":
        extra, _ = get_questions(
            subject=subject,
            grade=grade,
            page=1,
            page_size=count
        )
        existing_ids = {q["id"] for q in items}
        for eq in extra:
            if eq["id"] not in existing_ids:
                items.append(eq)
                existing_ids.add(eq["id"])
            if len(items) >= count:
                break
                
    title = f"Đề luyện tập {subject.upper()} - Lớp {grade}"
    duration_mins = max(15, len(items) * 2)
    return {
        "success": True,
        "exam_id": None,
        "exam_title": title,
        "duration_minutes": duration_mins,
        "duration_seconds": duration_mins * 60,
        "grade": grade,
        "subject": subject,
        "total_questions": len(items),
        "questions": items
    }


@router.post("/api/practice/submit")
async def submit_practice_exam(submission: PracticeSubmitRequest):
    """
    Grades user answers against question bank, computes score (10.0 and 100.0 scales),
    determines academic ranking, stores session into SQLite practice_history,
    and returns comprehensive score breakdown.
    """
    total_q = len(submission.answers)
    if total_q == 0:
        raise HTTPException(status_code=400, detail="Bài nộp không có câu hỏi nào để chấm điểm")

    correct_count = 0
    wrong_count = 0
    skipped_count = 0
    answers_detail = []

    for item in submission.answers:
        q_record = get_question_by_id(item.question_id)
        selected_ans = (item.selected_answer or "").strip()
        
        if not q_record:
            is_correct = False
            correct_ans = ""
            explanation = ""
            options = []
            q_text = f"Câu hỏi #{item.question_id}"
            subject_name = submission.subject
            topic_name = "Luyện tập"
        else:
            correct_ans = (q_record.get("correct_answer") or "").strip()
            options = q_record.get("options") or []
            q_text = q_record.get("content_text") or ""
            explanation = q_record.get("explanation") or ""
            subject_name = q_record.get("subject") or submission.subject
            topic_name = q_record.get("topic") or "Luyện tập"
            
            # If correct_answer field is empty, infer from options where is_correct is True
            if not correct_ans and options:
                for opt in options:
                    if opt.get("is_correct"):
                        correct_ans = opt.get("id", "")
                        break

        # Check correctness
        if not selected_ans:
            is_correct = False
            skipped_count += 1
        else:
            norm_sel = selected_ans.strip().upper()
            norm_corr = correct_ans.strip().upper()
            
            if norm_sel == norm_corr:
                is_correct = True
                correct_count += 1
            else:
                matched_by_content = False
                for opt in options:
                    if opt.get("is_correct") and (opt.get("content", "").strip().lower() == selected_ans.lower()):
                        matched_by_content = True
                        break
                if matched_by_content:
                    is_correct = True
                    correct_count += 1
                else:
                    is_correct = False
                    wrong_count += 1

        answers_detail.append({
            "question_id": item.question_id,
            "question_text": q_text,
            "selected_answer": selected_ans if selected_ans else None,
            "correct_answer": correct_ans,
            "is_correct": is_correct,
            "time_spent_seconds": item.time_spent_seconds or 0,
            "options": options,
            "explanation": explanation,
            "subject": subject_name,
            "topic": topic_name
        })

    # Scoring scales
    score_10 = round((correct_count / total_q) * 10.0, 2)
    score_100 = round((correct_count / total_q) * 100.0, 1)

    # Ranking determination
    if score_10 >= 9.0:
        ranking = "Xuất sắc"
    elif score_10 >= 8.0:
        ranking = "Giỏi"
    elif score_10 >= 6.5:
        ranking = "Khá"
    elif score_10 >= 5.0:
        ranking = "Trung bình"
    else:
        ranking = "Cần cố gắng"

    history_record = {
        "id": f"prac_{uuid.uuid4().hex[:12]}",
        "exam_id": submission.exam_id,
        "exam_title": submission.exam_title,
        "subject": submission.subject,
        "grade": submission.grade,
        "total_questions": total_q,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "skipped_count": skipped_count,
        "score": score_10,
        "max_score": 10.0,
        "duration_seconds": submission.duration_seconds,
        "time_spent_seconds": submission.time_spent_seconds,
        "ranking": ranking,
        "answers_detail": answers_detail,
        "created_at": datetime.now(VN_TZ).isoformat()
    }

    record_id = save_practice_history(history_record)
    history_record["id"] = record_id
    history_record["score_100"] = score_100

    # P1.3b: feed per-question outcomes into the spaced-repetition queue
    # (best-effort — never fails the submit if review tracking errors).
    try:
        record_review_results([
            {
                "question_id": a.get("question_id", ""),
                "correct": bool(a.get("is_correct", False)),
                "subject": a.get("subject") or submission.subject,
                "grade": submission.grade,
            }
            for a in answers_detail
            if a.get("question_id")
        ])
    except Exception as e:
        logger.warning(f"[review] record_review_results failed: {e}")
    try:
        review_stats = get_review_stats()
    except Exception:
        review_stats = {"total_tracked": 0, "due_count": 0}

    return {
        "success": True,
        "id": record_id,
        "exam_id": submission.exam_id,
        "exam_title": submission.exam_title,
        "subject": submission.subject,
        "grade": submission.grade,
        "total_questions": total_q,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "skipped_count": skipped_count,
        "score": score_10,
        "max_score": 10.0,
        "score_100": score_100,
        "duration_seconds": submission.duration_seconds,
        "time_spent_seconds": submission.time_spent_seconds,
        "ranking": ranking,
        "created_at": history_record["created_at"],
        "answers_detail": answers_detail,
        "review_stats": review_stats
    }


@router.get("/api/practice/history")
async def list_practice_history(
    limit: int = Query(50, ge=1, le=500),
    subject: Optional[str] = Query(None),
    grade: Optional[int] = Query(None)
):
    """Returns chronological list of student practice history records."""
    records = get_practice_history(limit=limit, subject=subject, grade=grade)
    return {"success": True, "count": len(records), "records": records}


@router.get("/api/practice/history/{record_id}")
async def get_practice_record_detail(record_id: str):
    """Returns a specific practice session with full question answers detail."""
    rec = get_practice_history_by_id(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử bài luyện tập này")
    return {"success": True, "record": rec}


@router.get("/api/practice/analytics")
async def get_practice_analytics_report(
    subject: Optional[str] = Query(None),
    grade: Optional[int] = Query(None)
):
    """
    Returns aggregated learning analytics:
    trending scores progression, subject mastery breakdown, and unlocked gamification badges.
    """
    report = get_practice_analytics(subject=subject, grade=grade)
    return {"success": True, "analytics": report}


@router.get("/api/practice/review-due")
async def list_review_due(
    subject: Optional[str] = Query(None),
    grade: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """Returns questions due for spaced-repetition review (oldest due first)."""
    due = get_due_reviews(subject=subject, grade=grade, limit=limit)
    return {"success": True, "count": len(due), "due": due}


@router.get("/api/practice/review-stats")
async def get_review_stats_report(
    subject: Optional[str] = Query(None),
    grade: Optional[int] = Query(None)
):
    """Returns spaced-repetition stats: total tracked + due count."""
    stats = get_review_stats(subject=subject, grade=grade)
    return {"success": True, "stats": stats}
