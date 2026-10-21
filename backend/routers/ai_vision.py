"""Document & Image Exam Extractor (PDF, AI Vision, OCR Studio) & Media Upload APIRouter."""
from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request, Query

from backend.dependencies import require_api_token, _require_admin
from backend.database import (
    bulk_insert_questions,
    insert_or_update_question,
    log_collector_event,
)
from backend.models import (
    OcrLearnRequest,
    OcrCorrectionCreate,
    AiVisionSettingsRequest,
    AiVisionTestConnectionRequest,
    QuestionCreate,
)
from backend.normalizer import normalize_question_payload, is_valid_question_payload
from backend.pdf_extractor import (
    extract_questions_from_pdf,
    extract_questions_from_image,
    SUPPORTED_IMAGE_EXTENSIONS,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA_DIR = os.path.join(BASE_DIR, "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

logger = logging.getLogger("eduquest.ai_vision")

router = APIRouter(tags=["AI Vision & OCR"])

# ----------------- Document & Image Exam Extractor (PDF & OCR) -----------------

@router.post("/api/import/pdf")
async def import_pdf_exam(
    file: UploadFile = File(...),
    save_to_bank: bool = Form(False),
    engine: str = Form("ai_vision")
):
    """Imports exam from either PDF or Image (.png, .jpg, .jpeg, .webp, .bmp) with intelligent auto-routing."""
    content = await file.read()
    filename = file.filename or "exam_file"
    ext = os.path.splitext(filename)[1].lower()
    ai_vision_logs: List[str] = []
    media_url: Optional[str] = None
    
    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        # Save image to MEDIA_DIR so it can be previewed, zoomed, and cropped
        img_id = uuid.uuid4().hex[:12]
        saved_filename = f"ocr_{img_id}{ext}"
        saved_filepath = os.path.join(MEDIA_DIR, saved_filename)
        with open(saved_filepath, "wb") as f:
            f.write(content)
        media_url = f"/media/{saved_filename}"

        if engine.lower() in ("ai_vision", "vision"):
            from backend.ai_vision import extract_questions_with_ai_vision
            extracted_questions, engine_used = await extract_questions_with_ai_vision(
                content, filename=filename, media_url=media_url, log_collector=ai_vision_logs
            )
            if not extracted_questions:
                extracted_questions = extract_questions_from_image(content, filename=filename, engine="rapid")
                engine_used = (extracted_questions[0].get("ocr_engine_used") if extracted_questions else "rapid") + " (AI Vision fallback)"
        else:
            extracted_questions = extract_questions_from_image(content, filename=filename, engine=engine)
            engine_used = extracted_questions[0].get("ocr_engine_used", engine) if extracted_questions else engine

        for q in extracted_questions:
            if not q.get("images"):
                q["images"] = [media_url]
            if not q.get("source_image_url"):
                q["source_image_url"] = media_url
        source_label = "Ảnh đề thi (Image OCR)"
    else:
        extracted_questions = extract_questions_from_pdf(content, filename=filename)
        source_label = "file PDF"
        engine_used = "pdf_native"
        
    saved_count = 0
    if save_to_bank and extracted_questions:
        normalized_list = []
        for q in extracted_questions:
            norm = await normalize_question_payload(q)
            normalized_list.append(norm)
        saved_count = bulk_insert_questions(normalized_list)
        log_collector_event(
            platform=extracted_questions[0].get("source_platform", "manual"),
            status="success",
            message=f"Bóc tách {source_label}: {filename} (Engine: {engine}), lưu {saved_count} câu hỏi",
            count=saved_count
        )
        
    actual_engine = engine_used if 'engine_used' in locals() and engine_used else (extracted_questions[0].get("ocr_engine_used") if extracted_questions else engine)

    return {
        "success": True,
        "filename": filename,
        "file_type": "image" if ext in SUPPORTED_IMAGE_EXTENSIONS else "pdf",
        "ocr_engine": engine,
        "engine_used": actual_engine,
        "image_url": media_url,
        "source_image_url": media_url,
        "ai_vision_logs": ai_vision_logs,
        "total_extracted": len(extracted_questions),
        "saved_to_bank": save_to_bank,
        "saved_count": saved_count,
        "preview_questions": extracted_questions,
        "questions": extracted_questions
    }

@router.post("/api/import/image")
async def import_image_exam(
    file: UploadFile = File(...),
    save_to_bank: bool = Form(False),
    engine: str = Form("ai_vision")
):
    """Dedicated endpoint for Image OCR exam paper extraction (.png, .jpg, .jpeg, .webp, .bmp)."""
    filename = file.filename or "exam_image.png"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng tệp không được hỗ trợ. Vui lòng tải lên một trong các định dạng: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}"
        )
        
    content = await file.read()
    img_id = uuid.uuid4().hex[:12]
    saved_filename = f"ocr_{img_id}{ext}"
    saved_filepath = os.path.join(MEDIA_DIR, saved_filename)
    with open(saved_filepath, "wb") as f:
        f.write(content)
    media_url = f"/media/{saved_filename}"

    engine_used = engine
    ai_vision_logs: List[str] = []
    if engine.lower() in ("ai_vision", "vision"):
        from backend.ai_vision import extract_questions_with_ai_vision
        extracted_questions, vision_engine_name = await extract_questions_with_ai_vision(
            content, filename=filename, media_url=media_url, log_collector=ai_vision_logs
        )
        if extracted_questions:
            engine_used = vision_engine_name
        else:
            extracted_questions = extract_questions_from_image(content, filename=filename, engine="rapid")
            engine_used = (extracted_questions[0].get("ocr_engine_used") if extracted_questions else "rapid") + " (AI Vision fallback)"
    else:
        extracted_questions = extract_questions_from_image(content, filename=filename, engine=engine)
        if extracted_questions:
            engine_used = extracted_questions[0].get("ocr_engine_used", engine)
    
    for q in extracted_questions:
        if not q.get("images"):
            q["images"] = [media_url]
        if not q.get("source_image_url"):
            q["source_image_url"] = media_url

    saved_count = 0
    if save_to_bank and extracted_questions:
        normalized_list = []
        for q in extracted_questions:
            norm = await normalize_question_payload(q)
            normalized_list.append(norm)
        saved_count = bulk_insert_questions(normalized_list)
        log_collector_event(
            platform="image_ocr",
            status="success",
            message=f"Bóc tách Ảnh đề thi OCR: {filename} (Engine: {engine}), lưu {saved_count} câu hỏi",
            count=saved_count
        )
        
    actual_engine = engine_used if 'engine_used' in locals() and engine_used else (extracted_questions[0].get("ocr_engine_used") if extracted_questions else engine)

    return {
        "success": True,
        "filename": filename,
        "file_type": "image",
        "ocr_engine": engine,
        "engine_used": actual_engine,
        "image_url": media_url,
        "source_image_url": media_url,
        "ai_vision_logs": ai_vision_logs,
        "total_extracted": len(extracted_questions),
        "saved_to_bank": save_to_bank,
        "saved_count": saved_count,
        "preview_questions": extracted_questions,
        "questions": extracted_questions
    }

@router.post("/api/pdf/extract")
@router.post("/api/import/exam-file")
async def import_exam_file(
    file: UploadFile = File(...),
    save_to_bank: bool = Form(False),
    engine: str = Form("rapid")
):
    """Unified file ingestion endpoint accepting both PDF and Image formats with engine selection."""
    return await import_pdf_exam(file=file, save_to_bank=save_to_bank, engine=engine)

# ----------------- AI Agent Exam Data Importer (JSON, DOCX, Text, Markdown) -----------------

@router.get("/api/import/ai-agent-template")
async def get_ai_agent_template_endpoint():
    """Returns standardized system prompt and schemas for external AI agents."""
    from backend.ai_agent_importer import get_ai_agent_template_info
    return {"success": True, "template": get_ai_agent_template_info()}

@router.post("/api/import/ai-agent-data")
async def import_ai_agent_data_endpoint(request: Request):
    """
    Ingests exam questions generated by external AI agents (ChatGPT, Claude, Gemini, DeepSeek...).
    Supports JSON, Word (.docx), Markdown, and plain text formats.
    Accepts both multipart/form-data (file upload / form fields) and application/json.
    """
    import json
    from backend.ai_agent_importer import parse_ai_agent_payload
    from backend.normalizer import is_valid_question_payload

    content_type = request.headers.get("content-type", "").lower()
    raw_content = ""
    filename = ""
    save_to_bank = False
    default_grade = 5
    default_subject = "math"
    default_topic = "Đề thi AI Agent"

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        raw_text = form.get("raw_text")
        save_to_bank = str(form.get("save_to_bank", "false")).lower() in ("true", "1", "yes")
        try:
            default_grade = int(form.get("default_grade", 5))
        except (ValueError, TypeError):
            default_grade = 5
        default_subject = str(form.get("default_subject", "math"))
        default_topic = str(form.get("default_topic", "Đề thi AI Agent"))

        if uploaded_file and hasattr(uploaded_file, "read"):
            raw_content = await uploaded_file.read()
            filename = getattr(uploaded_file, "filename", "") or "ai_agent_file"
        elif raw_text:
            raw_content = str(raw_text)
    else:
        # JSON body
        try:
            body = await request.json()
        except Exception:
            body = {}
        if isinstance(body, list):
            raw_content = json.dumps(body, ensure_ascii=False)
            save_to_bank = False
            default_grade = 5
            default_subject = "math"
            default_topic = "Đề thi AI Agent"
        elif isinstance(body, dict):
            raw_content = body.get("raw_text") or body.get("questions") or body.get("content") or ""
            if isinstance(raw_content, (list, dict)):
                raw_content = json.dumps(raw_content, ensure_ascii=False)
            save_to_bank = bool(body.get("save_to_bank", False))
            default_grade = int(body.get("default_grade", 5))
            default_subject = str(body.get("default_subject", "math"))
            default_topic = str(body.get("default_topic", "Đề thi AI Agent"))
        else:
            raw_content = str(body)

    parsed_questions, warnings = parse_ai_agent_payload(
        content=raw_content,
        filename=filename,
        default_grade=default_grade,
        default_subject=default_subject,
        default_topic=default_topic
    )

    saved_count = 0
    if save_to_bank and parsed_questions:
        normalized_list = []
        for q in parsed_questions:
            norm = await normalize_question_payload(q)
            valid, reason = is_valid_question_payload(norm)
            if valid:
                normalized_list.append(norm)
            else:
                warnings.append(f"Câu '{q.get('content_text', '')[:30]}...' không hợp lệ: {reason}")
        if normalized_list:
            saved_count = bulk_insert_questions(normalized_list)
            log_collector_event(
                platform="ai_agent_import",
                status="success",
                message=f"Nhập câu hỏi từ AI Agent: đã lưu {saved_count} câu vào CSDL",
                count=saved_count
            )

    return {
        "success": bool(parsed_questions),
        "total_parsed": len(parsed_questions),
        "saved_to_bank": save_to_bank,
        "saved_count": saved_count,
        "questions": parsed_questions,
        "preview_questions": parsed_questions,
        "warnings": warnings
    }

# ----------------- OCR Engine Status & Active Lexicon Learning APIs -----------------

@router.get("/api/ocr/engine-status")
async def get_ocr_engine_status():
    """Returns status of OCR engines (RapidOCR, VietOCR ONNX, AI Vision) and learned lexicon statistics."""
    from backend.vietocr_onnx import get_vietocr_engine
    from backend.database import get_ocr_corrections
    from backend.ai_vision import get_ai_vision_settings
    
    v_engine = get_vietocr_engine()
    v_status = v_engine.get_status()
    v_settings = get_ai_vision_settings()
    _, total_rules = get_ocr_corrections(page=1, page_size=1)
    
    ai_vision_ready = bool(v_settings.get("has_openrouter") or v_settings.get("has_opencode"))
    
    return {
        "success": True,
        "engines": {
            "ai_vision": {
                "id": "ai_vision",
                "name": "AI Vision (OpenRouter / OpenCode)",
                "display_name": "AI Vision (OpenRouter / OpenCode)",
                "ready": ai_vision_ready,
                "speed": "Thông minh (~2s)",
                "accuracy": "Chính xác tuyệt đối (100% dấu TV & công thức)",
                "provider": v_settings.get("provider", "auto"),
                "has_openrouter": v_settings.get("has_openrouter", False),
                "has_opencode": v_settings.get("has_opencode", False),
                "active_model": v_settings.get("openrouter_model") if v_settings.get("has_openrouter") else v_settings.get("opencode_model")
            },
            "rapid": {
                "id": "rapid",
                "name": "RapidOCR (PaddleOCR ONNX)",
                "display_name": "RapidOCR (PaddleOCR ONNX)",
                "ready": True,
                "speed": "Siêu tốc (~0.2s)",
                "accuracy": "Cao (kèm Bộ ngữ nghĩa Transformer)"
            },
            "vietocr": {
                "id": "vietocr",
                "name": "VietOCR ONNX DeepDoc Engine",
                "display_name": "VietOCR ONNX DeepDoc Engine",
                "ready": v_status["ready"],
                "speed": "Trung bình (~1.5s)",
                "accuracy": "Chuyên sâu tiếng Việt",
                "model_path": v_status["model_path"],
                "message": v_status["message"]
            },
            "vietocr_onnx": {
                "id": "vietocr_onnx",
                "name": "VietOCR ONNX DeepDoc Engine",
                "display_name": "VietOCR ONNX DeepDoc Engine",
                "ready": v_status["ready"],
                "speed": "Trung bình (~1.5s)",
                "accuracy": "Chuyên sâu tiếng Việt",
                "model_path": v_status["model_path"],
                "message": v_status["message"]
            }
        },
        "default_engine": "ai_vision" if ai_vision_ready else "rapid",
        "ai_vision_settings": v_settings,
        "total_learned_rules": total_rules,
        "active_lexicon_rules_count": total_rules
    }

@router.get("/api/ai-vision/settings")
async def get_ai_vision_settings_api():
    """Returns AI Vision settings including OpenRouter and OpenCode keys/models."""
    from backend.ai_vision import get_ai_vision_settings
    return {"success": True, "settings": get_ai_vision_settings()}

@router.post("/api/ai-vision/models")
@router.get("/api/ai-vision/models")
async def fetch_ai_vision_models_api(request: Request, provider: str = Query("openrouter"), api_key: str = Query(""), base_url: str = Query("")):
    """Scans and retrieves currently active live vision models from the provider.

    Prefers POST JSON body {provider, api_key, base_url}; legacy GET query params
    are kept for backward compatibility (frontend migrated to POST).
    """
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
        provider = body.get("provider", provider)
        api_key = body.get("api_key", api_key)
        base_url = body.get("base_url", base_url)
    from backend.ai_vision import fetch_live_vision_models
    res = await fetch_live_vision_models(provider=provider, api_key=api_key, base_url=base_url)
    return res

@router.post("/api/ai-vision/settings")
async def save_ai_vision_settings_api(req: AiVisionSettingsRequest):
    """Saves AI Vision configuration parameters."""
    from backend.ai_vision import save_ai_vision_settings, get_ai_vision_settings
    save_ai_vision_settings(req.model_dump(exclude_unset=True))
    updated = get_ai_vision_settings()
    return {"success": True, "settings": updated, "message": "Đã lưu cài đặt AI Vision thành công!"}

@router.post("/api/ai-vision/test-connection")
async def test_ai_vision_connection_api(req: AiVisionTestConnectionRequest):
    """Tests connectivity to OpenRouter, OpenCode, or custom 9Router gateway."""
    from backend.ai_vision import test_ai_vision_connection
    res = await test_ai_vision_connection(
        provider=req.provider,
        base_url=req.base_url,
        api_key=req.api_key,
        model=req.model
    )
    return res

@router.post("/api/ocr/learn")
async def learn_ocr_corrections(req: OcrLearnRequest):
    """Explicitly extracts and learns new phrase corrections between raw OCR text and corrected text."""
    from backend.database import record_ocr_learning_diff
    learned = record_ocr_learning_diff(req.raw_text, req.corrected_text, source=req.source or "manual_feedback")
    return {
        "success": True,
        "learned_count": len(learned),
        "learned_items": learned,
        "message": f"AI đã học được {len(learned)} cụm từ đính chính mới!" if learned else "Không phát hiện thay đổi cụm từ cần ghi nhớ."
    }

@router.get("/api/ocr/corrections")
async def list_ocr_corrections(page: int = 1, page_size: int = 50, search: str = ""):
    """Lists learned OCR correction rules with pagination and search."""
    from backend.database import get_ocr_corrections
    items, total = get_ocr_corrections(page=page, page_size=page_size, search=search)
    return {
        "success": True,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.post("/api/ocr/corrections")
async def add_ocr_correction(req: OcrCorrectionCreate):
    """Manually adds or updates a specific correction rule in the lexicon."""
    from backend.database import add_manual_ocr_correction
    try:
        res = add_manual_ocr_correction(req.wrong_text, req.correct_text, source=req.source or "manual_rule")
        return {"success": True, "item": res, "message": "Đã thêm quy tắc sửa đổi thành công"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api/ocr/corrections/{correction_id}")
async def remove_ocr_correction(correction_id: int, _auth=Depends(require_api_token)):
    """Deletes a specific correction rule from the lexicon."""
    from backend.database import delete_ocr_correction
    ok = delete_ocr_correction(correction_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy quy tắc cần xóa")
    return {"success": True, "message": "Đã xóa quy tắc thành công"}

@router.post("/api/ocr/corrections/clear")
async def clear_ocr_corrections(_auth=Depends(require_api_token)):
    """Clears all learned correction rules."""
    from backend.database import clear_all_ocr_corrections
    count = clear_all_ocr_corrections()
    return {"success": True, "cleared_count": count, "message": f"Đã xóa toàn bộ {count} quy tắc từ điển"}



# ----------------- Media Upload Endpoint -----------------

@router.post("/api/media/upload")
async def upload_media_file(file: UploadFile = File(...)):
    """Upload a single image file to the media directory. Returns the public URL."""
    import imghdr
    allowed_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Định dạng file không hỗ trợ: {ext}. Chỉ chấp nhận: {', '.join(allowed_ext)}")
    
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File quá lớn. Giới hạn tối đa 10MB.")
    
    unique_name = f"{uuid.uuid4().hex[:12]}_{file.filename or 'image'}"
    # Sanitize filename
    unique_name = "".join(c for c in unique_name if c.isalnum() or c in '._-')
    if not unique_name:
        unique_name = f"{uuid.uuid4().hex[:12]}.png"
    
    filepath = os.path.join(MEDIA_DIR, unique_name)
    with open(filepath, "wb") as f:
        f.write(contents)
    
    public_url = f"/media/{unique_name}"
    return {"success": True, "url": public_url, "filename": unique_name, "size": len(contents)}

