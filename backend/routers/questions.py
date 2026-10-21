"""Question Bank Management APIRouter."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import require_api_token
from backend.database import (
    get_questions,
    get_question_by_id,
    insert_or_update_question,
    bulk_insert_questions,
    delete_question,
    bulk_delete_questions,
    bulk_update_questions_grade,
    get_duplicate_questions_summary,
    clean_duplicate_questions,
    log_collector_event,
)
from backend.models import (
    QuestionCreate,
    QuestionUpdate,
    BulkQuestionCreate,
    BulkDeleteRequest,
    BulkUpdateGradeRequest,
    CleanDuplicatesRequest,
)
from backend.normalizer import (
    normalize_question_payload,
    is_valid_question_payload,
)

router = APIRouter(tags=["Question Bank"])


@router.get("/api/questions")
async def list_questions(
    platform: Optional[str] = Query(None),
    grade: Optional[int] = Query(None),
    subject: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    question_type: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source_detail: Optional[str] = Query(None),
    created_date: Optional[str] = Query(None),
    only_duplicates: bool = Query(False),
    sort_by: str = Query("q_number_asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    has_handwriting: Optional[bool] = Query(None)
):
    items, total = get_questions(
        platform=platform,
        grade=grade,
        subject=subject,
        topic=topic,
        question_type=question_type,
        difficulty=difficulty,
        search=search,
        source_detail=source_detail,
        created_date=created_date,
        only_duplicates=only_duplicates,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        has_handwriting=has_handwriting
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
    }


@router.get("/api/questions/duplicates")
async def get_duplicates_summary():
    """Returns summary of all duplicate question groups in database."""
    return get_duplicate_questions_summary()


@router.post("/api/questions/duplicates/clean")
async def clean_duplicates(data: CleanDuplicatesRequest, _auth=Depends(require_api_token)):
    """Cleans duplicate questions keeping the primary record or specific IDs."""
    res = clean_duplicate_questions(action=data.action, delete_ids=data.delete_ids)
    log_collector_event(
        platform="database",
        status="success",
        message=f"Đã dọn dẹp {res['deleted_count']} câu hỏi trùng lặp khỏi CSDL.",
        count=res['deleted_count']
    )
    return res


@router.get("/api/questions/{question_id}")
async def get_question(question_id: str):
    q = get_question_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi")
    return q


@router.post("/api/questions")
async def create_single_question(data: QuestionCreate):
    raw_dict = data.model_dump()
    raw_ocr = raw_dict.get("raw_ocr_content")
    content_text = raw_dict.get("content_text") or ""

    # Active Lexicon Learning (Human-in-the-Loop Feedback)
    learned_items = []
    if raw_ocr and content_text:
        from backend.database import record_ocr_learning_diff
        learned_items = record_ocr_learning_diff(raw_ocr, content_text, source="manual_feedback")

    normalized = await normalize_question_payload(raw_dict)
    valid, reason = is_valid_question_payload(normalized)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Câu hỏi không hợp lệ: {reason}")
    q_id = insert_or_update_question(normalized)
    return {
        "success": True, 
        "id": q_id, 
        "message": "Lưu câu hỏi thành công",
        "learned_count": len(learned_items),
        "learned_items": learned_items
    }


@router.post("/api/questions/bulk")
async def bulk_create_questions(data: BulkQuestionCreate):
    normalized_list = []
    skipped_count = 0
    for q in data.questions:
        norm = await normalize_question_payload(q.model_dump())
        valid, reason = is_valid_question_payload(norm)
        if not valid:
            skipped_count += 1
            continue
        normalized_list.append(norm)
    count = bulk_insert_questions(normalized_list)
    if count > 0:
        log_collector_event(
            platform=data.questions[0].source_platform if data.questions else "bulk",
            status="success",
            message=f"Đã nạp {count} câu hỏi qua Extension/API (bỏ qua {skipped_count} câu không hợp lệ)",
            count=count
        )
    return {"success": True, "inserted_count": count, "skipped_count": skipped_count}


@router.put("/api/questions/{question_id}")
async def update_question(question_id: str, data: QuestionUpdate):
    existing = get_question_by_id(question_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Câu hỏi không tồn tại")
    
    update_data = data.model_dump(exclude_unset=True)
    existing.update(update_data)
    normalized = await normalize_question_payload(existing)
    insert_or_update_question(normalized)
    return {"success": True, "id": question_id, "message": "Cập nhật thành công"}


@router.delete("/api/questions/{question_id}")
async def remove_question(question_id: str, _auth=Depends(require_api_token)):
    success = delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi để xóa")
    return {"success": True, "message": "Đã xóa câu hỏi"}


@router.post("/api/questions/bulk-delete")
async def bulk_delete_questions_endpoint(payload: BulkDeleteRequest, _auth=Depends(require_api_token)):
    """API xóa hàng loạt câu hỏi trong 1 transaction SQLite."""
    if not payload.question_ids:
        return {"success": True, "status": "success", "deleted_count": 0, "message": "Không có câu hỏi nào được chọn"}
    try:
        count = bulk_delete_questions(payload.question_ids)
        log_collector_event(
            platform="database",
            status="success",
            message=f"Đã xóa hàng loạt {count} câu hỏi khỏi CSDL qua thao tác chọn nhiều",
            count=count
        )
        return {
            "success": True,
            "status": "success",
            "deleted_count": count,
            "message": f"Đã xóa thành công {count} câu hỏi"
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa hàng loạt: {str(err)}")


@router.post("/api/questions/bulk-update-grade")
async def bulk_update_grade_endpoint(payload: BulkUpdateGradeRequest, _auth=Depends(require_api_token)):
    """API cập nhật khối lớp (Lớp 1 đến 12) hàng loạt trong 1 transaction SQLite."""
    if not (1 <= payload.grade <= 12):
        raise HTTPException(status_code=400, detail="Khối lớp không hợp lệ (chỉ chấp nhận từ 1 đến 12)")
    if not payload.question_ids:
        return {"success": True, "status": "success", "updated_count": 0, "grade": payload.grade, "message": "Không có câu hỏi nào được chọn"}
    try:
        count = bulk_update_questions_grade(payload.question_ids, payload.grade)
        log_collector_event(
            platform="database",
            status="success",
            message=f"Đã đổi khối lớp thành Lớp {payload.grade} cho {count} câu hỏi",
            count=count
        )
        return {
            "success": True,
            "status": "success",
            "updated_count": count,
            "grade": payload.grade,
            "message": f"Đã cập nhật khối lớp thành Lớp {payload.grade} cho {count} câu hỏi"
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật khối lớp: {str(err)}")
