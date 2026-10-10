from __future__ import annotations
import os
import io
import shutil
import uuid
import asyncio
import logging
import re
import unicodedata
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, List

VN_TZ = timezone(timedelta(hours=7))
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Response, Body, Request, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

logger = logging.getLogger("eduquest")

from backend.version import APP_VERSION, APP_VERSION_NUMBER, CACHE_BUSTER, EXT_VERSION

from backend.database import (
    init_db, get_questions, get_question_by_id, insert_or_update_question,
    bulk_insert_questions, delete_question, bulk_delete_questions, bulk_update_questions_grade,
    get_stats, get_stats_count,
    create_exam, get_exams, get_exam_by_id, delete_exam,
    log_collector_event, get_collector_logs, clear_collector_logs,
    get_duplicate_questions_summary, clean_duplicate_questions,
    run_database_diagnostics, fix_database_issues, auto_generate_exam_questions,
    fetch_diverse_replacement_question,
    maybe_resequence_deferred,
    save_practice_history, get_practice_history, get_practice_history_by_id, get_practice_analytics
)
from backend.models import (
    QuestionCreate, QuestionUpdate, BulkQuestionCreate,
    BulkDeleteRequest, BulkDeleteQuestionsRequest, BulkUpdateGradeRequest,
    ExamCreate, ScrapeRequest, AutoExamGenerateRequest, CleanDuplicatesRequest,
    ExamDiversityRequest, ExamDiversifyRequest, ExamSwapRequest, ExamShuffleRequest,
    PracticeSubmitRequest, PracticeAnswerSubmission, PracticeHistoryResponse, PracticeAnalyticsResponse,
    OcrLearnRequest, OcrCorrectionCreate, AiVisionSettingsRequest, AiVisionTestConnectionRequest
)
from backend.exam_smart_mixer import (
    analyze_exam_diversity, deduplicate_and_diversify_exam,
    swap_exam_question, shuffle_exam_smart
)
from backend.normalizer import normalize_question_payload
from backend.docx_exporter import generate_exam_docx
from backend.pdf_extractor import extract_questions_from_pdf, extract_questions_from_image, SUPPORTED_IMAGE_EXTENSIONS
from backend.scrapers.vioedu import (
    login_vioedu, fetch_vioedu_arena_questions, parse_vioedu_question_data, crawl_vioedu_rounds_headless
)
from backend.scrapers.tnmath import login_tnmath, parse_tnmath_question_data

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
MEDIA_DIR = os.path.join(BASE_DIR, "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

# Initialize database
init_db()

# ---------------------------------------------------------------------------
# Write protection (optional API token) + rate limiting for mutating endpoints
# ---------------------------------------------------------------------------
API_TOKEN = os.environ.get("API_TOKEN", "").strip()
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
MAX_PAGE_SIZE = 200
WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
_RATE_BUCKETS: dict[str, list[float]] = {}


def _check_rate_limit(client_ip: str) -> bool:
    """Sliding-window limiter (per IP, 60s window). Returns True when allowed."""
    import time
    now = time.monotonic()
    window_start = now - 60.0
    bucket = _RATE_BUCKETS.get(client_ip)
    if bucket is None:
        bucket = []
        _RATE_BUCKETS[client_ip] = bucket
    while bucket and bucket[0] < window_start:
        bucket.pop(0)
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        return False
    bucket.append(now)
    if len(_RATE_BUCKETS) > 5000:
        _RATE_BUCKETS.clear()
    return True


def require_api_token(request: Request):
    """Enforces X-API-Token on destructive/admin endpoints — only when API_TOKEN env is set.
    Local default (env empty) keeps current open behavior so the dashboard & extension keep working."""
    if not API_TOKEN:
        return None
    if request.headers.get("X-API-Token", "") != API_TOKEN:
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai API token (header X-API-Token)")
    return None


async def _rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api") and request.method in WRITE_METHODS:
        client_ip = request.client.host if request.client else "unknown"
        if not _check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={"success": False, "detail": "Quá nhiều yêu cầu, vui lòng thử lại sau 1 phút."},
                headers={"Retry-After": "60"},
            )
    return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Run lazy resequence in background thread if flagged, ensuring instant startup (<1s)
    asyncio.create_task(asyncio.to_thread(maybe_resequence_deferred))
    stats = get_stats()
    if stats.get("total_questions", 0) == 0:
        await init_sample_questions()
    # Launch daily OCR temp-file cleanup + daily DB backup in the background
    asyncio.create_task(_schedule_ocr_cleanup())
    asyncio.create_task(_schedule_db_backup())
    yield

app = FastAPI(
    title="EduQuest Pro API",
    description="Hệ thống Thu thập & Quản lý Ngân hàng Câu hỏi Thi trực tuyến",
    version=APP_VERSION_NUMBER,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# OCR temp-file cleanup: delete ocr_* files older than 15 days, once per day
# ---------------------------------------------------------------------------
OCR_CLEANUP_MAX_AGE_DAYS = 15
OCR_CLEANUP_INTERVAL_SEC = 24 * 60 * 60  # 24 hours

async def _schedule_ocr_cleanup():
    """Run OCR cleanup at startup then every 24 hours."""
    while True:
        await _cleanup_ocr_temp_files()
        await asyncio.sleep(OCR_CLEANUP_INTERVAL_SEC)

async def _cleanup_ocr_temp_files():
    """Delete ocr_* files in MEDIA_DIR that are older than OCR_CLEANUP_MAX_AGE_DAYS days."""
    import time
    cutoff = time.time() - OCR_CLEANUP_MAX_AGE_DAYS * 86400
    deleted = 0
    errors = 0
    try:
        for fname in os.listdir(MEDIA_DIR):
            if not fname.startswith("ocr_"):
                continue
            fpath = os.path.join(MEDIA_DIR, fname)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    deleted += 1
            except Exception as e:
                errors += 1
                print(f"[OCR Cleanup] Không thể xóa {fname}: {e}")
    except Exception as e:
        print(f"[OCR Cleanup] Lỗi quét thư mục media: {e}")
        return
    if deleted or errors:
        print(f"[OCR Cleanup] Đã xóa {deleted} file ocr_* cũ hơn {OCR_CLEANUP_MAX_AGE_DAYS} ngày"
              + (f" ({errors} lỗi)" if errors else ""))

# ---------------------------------------------------------------------------
# Daily SQLite backup (online backup API — safe while server runs, 7-day rotation)
# ---------------------------------------------------------------------------
DB_BACKUP_KEEP_DAILY = int(os.environ.get("DB_BACKUP_KEEP", "7"))
DB_BACKUP_INTERVAL_SEC = 24 * 60 * 60  # 24 hours

def _get_db_backup_dir() -> str:
    from backend.database import DB_PATH
    d = os.path.join(os.path.dirname(DB_PATH), "backup")
    os.makedirs(d, exist_ok=True)
    return d

def _do_db_backup(tag: str = "auto") -> Optional[str]:
    """Copies questions.db via sqlite3 online backup API. Returns filename or None."""
    import sqlite3
    from backend.database import DB_PATH
    try:
        if not os.path.exists(DB_PATH):
            return None
        ts = datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
        fname = f"questions_{ts}_{tag}.db"
        dest = os.path.join(_get_db_backup_dir(), fname)
        src = sqlite3.connect(DB_PATH, timeout=30.0)
        try:
            dst = sqlite3.connect(dest, timeout=30.0)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        # Rotation: only auto backups rotate; manual/pre-restore snapshots are kept
        if tag == "auto":
            auto_files = sorted(
                f for f in os.listdir(_get_db_backup_dir()) if f.endswith("_auto.db")
            )
            while len(auto_files) > DB_BACKUP_KEEP_DAILY:
                old = auto_files.pop(0)
                try:
                    os.remove(os.path.join(_get_db_backup_dir(), old))
                except OSError:
                    pass
        print(f"[DB Backup] Da sao luu CSDL -> {fname}")
        return fname
    except Exception as e:
        print(f"[DB Backup] Loi sao luu CSDL: {e}")
        return None

async def _schedule_db_backup():
    """First backup 60s after startup, then every 24 hours."""
    await asyncio.sleep(60)
    while True:
        await asyncio.to_thread(_do_db_backup, "auto")
        await asyncio.sleep(DB_BACKUP_INTERVAL_SEC)

# Enable CORS for browser extension and external tools
# (Locked down: explicit origins + extension regex instead of allow_origins=["*"].
#  Extra origins via env CORS_ORIGINS="https://example.com,https://..." )
_extra_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://127.0.0.1",
        *_extra_origins,
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
                       r"|https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?"
                       r"|https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?"
                       r"|chrome-extension://.*|moz-extension://.*|edge-extension://.*",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Token"],
)
app.middleware("http")(_rate_limit_middleware)

# ----------------- Version (single source of truth) -----------------

@app.get("/api/version")
async def get_app_version():
    """Returns canonical app/extension versions + cache buster (from backend/version.py)."""
    return {
        "app_version": APP_VERSION,
        "app_version_number": APP_VERSION_NUMBER,
        "cache_buster": CACHE_BUSTER,
        "ext_version": EXT_VERSION,
    }

# ----------------- Question Bank Endpoints -----------------

@app.get("/api/stats")
async def get_dashboard_stats():
    return get_stats()

@app.api_route("/api/stats/count", methods=["GET", "HEAD"])
async def get_question_count():
    """Lightweight endpoint for heartbeat polling — single COUNT query, no cache needed."""
    return {"total_questions": get_stats_count()}

@app.get("/api/questions")
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

@app.get("/api/questions/duplicates")
async def get_duplicates_summary():
    """Returns summary of all duplicate question groups in database."""
    return get_duplicate_questions_summary()

@app.post("/api/questions/duplicates/clean")
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

@app.get("/api/database/diagnostics")
async def get_db_diagnostics():
    """Runs a complete diagnostic health check on SQLite database."""
    return run_database_diagnostics()

@app.get("/api/database/backups")
async def list_db_backups(_auth=Depends(require_api_token)):
    """Lists SQLite backup snapshots in data/backup (newest first)."""
    from backend.database import DB_PATH
    import sqlite3
    backups = []
    try:
        bdir = _get_db_backup_dir()
        for fname in sorted(os.listdir(bdir), reverse=True):
            if not fname.endswith(".db"):
                continue
            fpath = os.path.join(bdir, fname)
            try:
                st = os.stat(fpath)
                qcount = None
                try:
                    c = sqlite3.connect(f"file:{fpath}?mode=ro", uri=True, timeout=10.0)
                    try:
                        qcount = c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
                    finally:
                        c.close()
                except Exception:
                    qcount = None
                backups.append({
                    "filename": fname,
                    "size_bytes": st.st_size,
                    "modified_at": datetime.fromtimestamp(st.st_mtime, tz=VN_TZ).isoformat(),
                    "questions": qcount,
                })
            except OSError:
                continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi liệt kê backup: {e}")
    try:
        live = os.path.getsize(DB_PATH)
    except OSError:
        live = 0
    return {"success": True, "live_db_bytes": live, "backups": backups}

@app.post("/api/database/backup")
async def create_db_backup_now(_auth=Depends(require_api_token)):
    """Creates an immediate manual SQLite backup snapshot."""
    fname = await asyncio.to_thread(_do_db_backup, "manual")
    if not fname:
        raise HTTPException(status_code=500, detail="Sao lưu CSDL thất bại")
    return {"success": True, "filename": fname, "message": f"Đã sao lưu CSDL: {fname}"}

@app.post("/api/database/restore")
async def restore_db_backup(payload: dict, _auth=Depends(require_api_token)):
    """Restores questions.db from a backup snapshot (auto pre-restore snapshot first)."""
    import sqlite3
    filename = str((payload or {}).get("filename", "")).strip()
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Tên file backup không hợp lệ")
    if not filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file .db")
    src = os.path.join(_get_db_backup_dir(), filename)
    if not os.path.isfile(src):
        raise HTTPException(status_code=404, detail="Không tìm thấy file backup")
    from backend.database import DB_PATH, init_db, invalidate_stats_cache
    # Online integrity check of the snapshot before touching live DB
    try:
        c = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=10.0)
        try:
            ok = c.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            c.close()
        if str(ok).lower() != "ok":
            raise HTTPException(status_code=400, detail=f"File backup hỏng integrity_check: {ok}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không đọc được file backup: {e}")
    # Safety snapshot of current live DB first
    pre = await asyncio.to_thread(_do_db_backup, "pre-restore")
    try:
        shutil.copy2(src, DB_PATH)
        init_db()
        invalidate_stats_cache()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Khôi phục thất bại: {e}")
    log_collector_event(
        platform="database",
        status="success",
        message=f"Đã khôi phục CSDL từ {filename} (snapshot trước khôi phục: {pre}).",
        count=0,
    )
    return {"success": True, "restored_from": filename, "pre_restore_snapshot": pre}

@app.post("/api/database/diagnostics/fix")
async def fix_db_anomalies(_auth=Depends(require_api_token)):
    """Auto-repairs database issues: cleans duplicates, fixes null subjects, vacuums DB."""
    res = fix_database_issues()
    log_collector_event(
        platform="database",
        status="success",
        message=f"Đã sửa lỗi CSDL: dọn dẹp {res['duplicates_cleaned']} câu trùng, chuẩn hóa {res['subjects_reclassified']} bộ môn.",
        count=res['duplicates_cleaned']
    )
    return res

@app.get("/api/questions/{question_id}")
async def get_question(question_id: str):
    q = get_question_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi")
    return q

@app.post("/api/questions")
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
    from backend.normalizer import is_valid_question_payload
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

@app.post("/api/questions/bulk")
async def bulk_create_questions(data: BulkQuestionCreate):
    from backend.normalizer import is_valid_question_payload
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

@app.put("/api/questions/{question_id}")
async def update_question(question_id: str, data: QuestionUpdate):
    existing = get_question_by_id(question_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Câu hỏi không tồn tại")
    
    update_data = data.model_dump(exclude_unset=True)
    existing.update(update_data)
    normalized = await normalize_question_payload(existing)
    insert_or_update_question(normalized)
    return {"success": True, "id": question_id, "message": "Cập nhật thành công"}

@app.delete("/api/questions/{question_id}")
async def remove_question(question_id: str, _auth=Depends(require_api_token)):
    success = delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi để xóa")
    return {"success": True, "message": "Đã xóa câu hỏi"}

@app.post("/api/questions/bulk-delete")
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

@app.post("/api/questions/bulk-update-grade")
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

# ----------------- Exam Builder & Word Export -----------------

@app.get("/api/exams")
async def list_exams():
    return get_exams()

@app.get("/api/exams/{exam_id}")
async def get_exam(exam_id: str):
    exam = get_exam_by_id(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
    return exam

@app.post("/api/exams")
async def create_new_exam(data: ExamCreate):
    exam_id = create_exam(data.model_dump())
    return {"success": True, "id": exam_id, "message": "Tạo đề thi thành công"}

@app.post("/api/exams/auto-generate")
async def auto_create_exam_matrix(data: AutoExamGenerateRequest):
    """
    Auto-generates questions based on a difficulty matrix:
    easy_count, medium_count, hard_count, subject, and grade.
    """
    res = auto_generate_exam_questions(
        subject=data.subject,
        grade=data.grade,
        total_questions=data.total_questions,
        easy_count=data.easy_count,
        medium_count=data.medium_count,
        hard_count=data.hard_count,
        topic=data.topic
    )
    return res

@app.post("/api/exams/analyze-diversity")
async def api_analyze_exam_diversity(data: ExamDiversityRequest):
    """
    Analyzes questions in an exam to detect duplicate templates (isomorphic questions
    differing only by numbers) and reports pedagogical diversity score.
    """
    questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
    return analyze_exam_diversity(questions)

@app.post("/api/exams/diversify")
async def api_deduplicate_and_diversify_exam(data: ExamDiversifyRequest):
    """
    One-click smart exam deduplication:
    Detects duplicate templates/identical questions differing only by numbers,
    keeps 1 representative question per template, and automatically replaces
    all duplicates with fresh, non-colliding questions matching the same grade & difficulty.
    """
    questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    updated_questions, replacements = deduplicate_and_diversify_exam(
        questions,
        replacement_fetcher=lambda subject, grade, difficulty, exclude_templates, exclude_ids: fetch_diverse_replacement_question(
            subject=subject or data.subject,
            grade=grade or data.grade,
            difficulty=difficulty,
            exclude_templates=exclude_templates,
            exclude_ids=exclude_ids
        )
    )
    analysis = analyze_exam_diversity(updated_questions)
    return {
        "success": True,
        "count": len(updated_questions),
        "questions": updated_questions,
        "question_ids": [q["id"] for q in updated_questions],
        "replacements": replacements,
        "replacements_count": len(replacements),
        "analysis": analysis
    }

@app.post("/api/exams/swap-question")
async def api_swap_exam_question(data: ExamSwapRequest):
    """
    Swaps a single question with another question of matching difficulty/grade
    that is guaranteed to have a completely DIFFERENT archetype and template.
    """
    all_questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            all_questions.append(q)
            
    new_q = swap_exam_question(
        target_id=data.target_id,
        all_questions=all_questions,
        candidate_fetcher=lambda subject, grade, difficulty, exclude_templates, exclude_ids: fetch_diverse_replacement_question(
            subject=subject or data.subject,
            grade=grade or data.grade,
            difficulty=difficulty,
            exclude_templates=exclude_templates,
            exclude_ids=exclude_ids
        )
    )
    if not new_q:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi thay thế phù hợp khác dạng bài trong kho CSDL")
        
    return {
        "success": True,
        "old_id": data.target_id,
        "new_question": new_q,
        "new_id": new_q["id"]
    }

@app.post("/api/exams/shuffle")
async def api_shuffle_exam(data: ExamShuffleRequest):
    """
    Shuffles question order and/or scrambles options (A, B, C, D) while maintaining
    the correct answer key.
    """
    questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    shuffled = shuffle_exam_smart(
        questions=questions,
        shuffle_order=data.shuffle_order,
        shuffle_options=data.shuffle_options
    )
    return {
        "success": True,
        "questions": shuffled,
        "question_ids": [q["id"] for q in shuffled]
    }

@app.delete("/api/exams/{exam_id}")
async def remove_exam(exam_id: str, _auth=Depends(require_api_token)):
    success = delete_exam(exam_id)
    return {"success": success}

@app.post("/api/export/docx")
async def export_exam_word(exam_data: ExamCreate):
    # Fetch questions for this exam
    questions = []
    for qid in exam_data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    if not questions:
        raise HTTPException(status_code=400, detail="Đề thi chưa có câu hỏi nào để xuất file")
        
    import urllib.parse
    import unicodedata
    
    # Generate ASCII safe filename + UTF-8 RFC 5987 filename
    raw_name = f"De_thi_{exam_data.grade or 5}_{exam_data.title[:25]}.docx".replace(" ", "_")
    ascii_name = unicodedata.normalize('NFKD', raw_name).encode('ascii', 'ignore').decode('ascii')
    if not ascii_name.endswith(".docx"):
        ascii_name += ".docx"
    encoded_name = urllib.parse.quote(raw_name)
    
    doc_io = generate_exam_docx(exam_data.model_dump(), questions)
    
    return StreamingResponse(
        doc_io,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"
        }
    )

def normalize_moet_math_symbols(text: str) -> str:
    """Normalizes mathematical and scientific symbols for MOET standard A4 paper."""
    if not text:
        return ""
    import re
    s = text
    # Clean unwanted HTML tags but preserve line breaks
    s = re.sub(r'</?(?:p|div|span)[^>]*>', ' ', s)
    s = s.replace('<br>', '<br/>').replace('<br/>', '\n')
    
    # 1. Operators & relations
    s = re.sub(r'\\times\b', '×', s)
    s = re.sub(r'\\cdot\b', '·', s)
    s = re.sub(r'\\div\b', '÷', s)
    s = re.sub(r'\\le\b|\\leq\b', '≤', s)
    s = re.sub(r'\\ge\b|\\geq\b', '≥', s)
    s = re.sub(r'\\ne\b|\\neq\b', '≠', s)
    s = re.sub(r'\\approx\b', '≈', s)
    s = re.sub(r'\\pm\b', '±', s)
    
    # 2. Geometry & Greek symbols
    s = re.sub(r'\\angle\b', '∠', s)
    s = re.sub(r'\\Delta\b', 'Δ', s)
    s = re.sub(r'\\pi\b', 'π', s)
    s = re.sub(r'\\alpha\b', 'α', s)
    s = re.sub(r'\\beta\b', 'β', s)
    s = re.sub(r'\\gamma\b', 'γ', s)
    s = re.sub(r'\\theta\b', 'θ', s)
    s = re.sub(r'\\lambda\b', 'λ', s)
    s = re.sub(r'\\mu\b', 'μ', s)
    s = re.sub(r'\\sigma\b', 'σ', s)
    s = re.sub(r'\\omega\b', 'ω', s)
    
    # 3. Superscripts & Subscripts
    s = re.sub(r'\^2\b', '²', s)
    s = re.sub(r'\^3\b', '³', s)
    s = re.sub(r'([a-zA-Z0-9])\^2', r'\1²', s)
    s = re.sub(r'([a-zA-Z0-9])\^3', r'\1³', s)
    
    # 4. Chemical formulas
    s = re.sub(r'\bH2O\b', 'H₂O', s)
    s = re.sub(r'\bCO2\b', 'CO₂', s)
    s = re.sub(r'\bO2\b', 'O₂', s)
    s = re.sub(r'\bN2\b', 'N₂', s)
    s = re.sub(r'\bH2SO4\b', 'H₂SO₄', s)
    s = re.sub(r'\bCaCO3\b', 'CaCO₃', s)
    s = re.sub(r'\bNaCl\b', 'NaCl', s)
    s = re.sub(r'\bHCl\b', 'HCl', s)
    
    # 5. Fractions and square roots
    s = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', s)
    s = re.sub(r'\\sqrt\b', '√', s)
    s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1/\2)', s)
    
    # 6. Clean leftover LaTeX markers
    s = s.replace('$', '').replace('\\(', '').replace('\\)', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def build_moet_exam_html(exam_data: dict, questions: list) -> str:
    """Builds HTML for MOET standard A4 exam paper with answer key & rubric page."""
    import html
    title = html.escape(exam_data.get("title", "ĐỀ THI KHẢO SÁT CHẤT LƯỢNG MÔN TOÁN"))
    header_info = html.escape(exam_data.get("header_info", "PHÒNG GIÁO DỤC VÀ ĐÀO TẠO - TRƯỜNG CLC"))
    grade = exam_data.get("grade", 5)
    duration = exam_data.get("duration_minutes", 45)
    notes = html.escape(exam_data.get("notes", "Cán bộ coi thi không giải thích gì thêm."))
    total_q = len(questions)
    points_per_q = round(10.0 / total_q, 2) if total_q > 0 else 0

    subject_names = {
        "math": "Toán học",
        "vietnamese": "Tiếng Việt",
        "english": "Tiếng Anh",
        "science": "Khoa học & Tự nhiên"
    }
    sample_sub = questions[0].get("subject", "math") if questions else "math"
    sub_title = subject_names.get(sample_sub, "Toán học")

    # Build Questions HTML
    questions_html = []
    answer_rows = []
    rubric_rows = []

    for idx, q in enumerate(questions):
        q_num = idx + 1
        stem_raw = q.get("content_text") or q.get("content_html") or ""
        clean_stem = html.escape(normalize_moet_math_symbols(stem_raw))
        options = q.get("options") or []
        correct_ans = q.get("correct_answer") or ""
        
        # Determine correct answer letter if missing from direct field
        if not correct_ans and options:
            for opt in options:
                if opt.get("is_correct"):
                    correct_ans = opt.get("id")
                    break
        if not correct_ans:
            correct_ans = "A"

        answer_rows.append(f"<tr><td style='text-align: center; font-weight: bold;'>Câu {q_num}</td><td style='text-align: center; font-weight: bold; color: #1e3a8a;'>{correct_ans}</td><td style='text-align: center;'>{points_per_q}</td></tr>")
        
        explanation = q.get("explanation") or f"Chọn đáp án {correct_ans}."
        clean_exp = html.escape(normalize_moet_math_symbols(explanation))
        rubric_rows.append(f"<div style='margin-bottom: 8pt; font-size: 11pt;'><strong>Câu {q_num} ({points_per_q} điểm):</strong> Đáp án <strong>{correct_ans}</strong>. <em>{clean_exp}</em></div>")

        options_html = []
        if options:
            for opt in options:
                opt_id = opt.get("id", "")
                opt_content = html.escape(normalize_moet_math_symbols(opt.get("content", "")))
                options_html.append(f"<div class='opt-item'><strong>{opt_id}.</strong> {opt_content}</div>")

        q_block = f"""
        <div class="question-item">
            <div class="q-stem"><strong>Câu {q_num}:</strong> {clean_stem}</div>
            <div class="options-grid">
                {''.join(options_html)}
            </div>
        </div>
        """
        questions_html.append(q_block)

    html_page = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
@page {{
    size: A4 portrait;
    margin: 20mm 15mm 20mm 25mm;
}}
body {{
    font-family: 'Times New Roman', Times, serif;
    font-size: 12pt;
    line-height: 1.35;
    color: #000000;
    margin: 0;
    padding: 0;
    background: #ffffff;
}}
.exam-header {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 14pt;
}}
.exam-header td {{
    vertical-align: top;
    padding: 0 4pt;
}}
.header-left {{
    width: 44%;
    text-align: center;
}}
.header-right {{
    width: 56%;
    text-align: center;
}}
.school-name {{
    font-size: 10.5pt;
    font-weight: bold;
    text-transform: uppercase;
    line-height: 1.25;
}}
.exam-code {{
    font-size: 11pt;
    font-weight: bold;
    margin-top: 4pt;
    letter-spacing: 0.5px;
}}
.exam-title {{
    font-size: 13pt;
    font-weight: bold;
    text-transform: uppercase;
    line-height: 1.3;
}}
.exam-meta {{
    font-size: 11pt;
    font-weight: bold;
    margin-top: 3pt;
}}
.exam-duration {{
    font-size: 10.5pt;
    font-style: italic;
    margin-top: 2pt;
}}
.header-divider {{
    border-bottom: 1px solid #000;
    width: 60%;
    margin: 4pt auto 0 auto;
}}
.student-info-box {{
    border: 1px dashed #475569;
    padding: 6pt 10pt;
    margin-bottom: 12pt;
    font-size: 11pt;
    border-radius: 4px;
}}
.exam-notes {{
    font-size: 10pt;
    font-style: italic;
    margin-bottom: 14pt;
    text-align: center;
}}
.question-item {{
    page-break-inside: avoid;
    margin-bottom: 11pt;
}}
.q-stem {{
    margin-bottom: 4pt;
    text-align: justify;
}}
.options-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 4pt 12pt;
    padding-left: 12pt;
}}
.opt-item {{
    font-size: 11.5pt;
}}
.answer-page {{
    page-break-before: always;
    padding-top: 10pt;
}}
.answer-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12pt;
    margin-bottom: 16pt;
}}
.answer-table th, .answer-table td {{
    border: 1px solid #000000;
    padding: 5pt 8pt;
    font-size: 11pt;
}}
.answer-table th {{
    background-color: #f1f5f9;
    font-weight: bold;
    text-align: center;
}}
</style>
</head>
<body>

<!-- Header MOET Standard -->
<table class="exam-header">
    <tr>
        <td class="header-left">
            <div class="school-name">{header_info}</div>
            <div class="header-divider"></div>
            <div class="exam-code">MÃ ĐỀ THI: 101</div>
        </td>
        <td class="header-right">
            <div class="exam-title">{title}</div>
            <div class="exam-meta">MÔN: {sub_title.upper()} - KHỐI {grade}</div>
            <div class="exam-duration">Thời gian làm bài: {duration} phút (không kể thời gian phát đề)</div>
            <div class="header-divider"></div>
        </td>
    </tr>
</table>

<!-- Student Info -->
<div class="student-info-box">
    Họ và tên thí sinh: ................................................................................... Lớp: .................. SBD: ....................
</div>

<div class="exam-notes">
    (Thí sinh không được sử dụng tài liệu. Cán bộ coi thi không giải thích gì thêm.)
</div>

<!-- Questions -->
<div class="questions-list">
    {''.join(questions_html)}
</div>

<div style="text-align: center; font-weight: bold; margin-top: 18pt; margin-bottom: 18pt;">
    ------------- HẾT -------------
</div>

<!-- Answer Key & Rubric Page -->
<div class="answer-page">
    <div style="text-align: center;">
        <div class="school-name">{header_info}</div>
        <div style="font-size: 13pt; font-weight: bold; text-transform: uppercase; margin-top: 4pt;">
            ĐÁP ÁN VÀ THANG ĐIỂM CHI TIẾT
        </div>
        <div style="font-size: 11pt; font-style: italic; margin-top: 2pt;">
            (Môn: {sub_title} - Khối {grade} - Mã đề 101)
        </div>
        <div class="header-divider" style="width: 40%;"></div>
    </div>

    <h4 style="margin-top: 14pt; margin-bottom: 4pt; text-transform: uppercase;">1. Bảng Đáp Án Trắc Nghiệm:</h4>
    <table class="answer-table">
        <thead>
            <tr>
                <th style="width: 30%;">Câu hỏi</th>
                <th style="width: 35%;">Đáp án đúng</th>
                <th style="width: 35%;">Thang điểm</th>
            </tr>
        </thead>
        <tbody>
            {''.join(answer_rows)}
        </tbody>
    </table>

    <h4 style="margin-top: 16pt; margin-bottom: 8pt; text-transform: uppercase;">2. Hướng Dẫn Chấm & Lời Giải Chi Tiết:</h4>
    <div style="line-height: 1.4;">
        {''.join(rubric_rows)}
    </div>
</div>

</body>
</html>"""
    return html_page

def _generate_fallback_pdf(title: str, questions: list) -> bytes:
    """Fallback minimal valid PDF-1.4 generator when Playwright is unavailable."""
    lines = [f"Title: {title}", ""]
    for idx, q in enumerate(questions, 1):
        q_text = q.get("content_text", "") if isinstance(q, dict) else getattr(q, "content_text", "")
        lines.append(f"Cau {idx}: {q_text[:120]}")
    content = f'BT /F1 14 Tf 50 750 Td ({title[:60]}) Tj ET\n'
    y = 720
    for l in lines[:35]:
        clean_l = str(l).replace('\\', '').replace('(', '[').replace(')', ']')[:80]
        content += f'BT /F1 10 Tf 50 {y} Td ({clean_l}) Tj ET\n'
        y -= 18
        if y < 50:
            break
    stream_data = content.encode('utf-8', 'replace')
    padding = b' ' * max(0, 10500 - len(stream_data))
    stream_data = stream_data + padding

    obj1 = b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n'
    obj2 = b'2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n'
    obj3 = b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n'
    obj4 = b'4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n'
    obj5 = f'5 0 obj << /Length {len(stream_data)} >> stream\n'.encode('ascii') + stream_data + b'\nendstream\nendobj\n'

    body = obj1 + obj2 + obj3 + obj4 + obj5
    header = b'%PDF-1.4\n'
    offsets = [0]
    pos = len(header)
    for obj in [obj1, obj2, obj3, obj4, obj5]:
        offsets.append(pos)
        pos += len(obj)
    xref = b'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets[1:]:
        xref += f'{off:010d} 00000 n \n'.encode('ascii')
    trailer = f'trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n'.encode('ascii')
    return header + body + xref + trailer

@app.post("/api/export/pdf")
async def export_exam_pdf(exam_data: ExamCreate):
    questions = []
    for qid in exam_data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    if not questions:
        raise HTTPException(status_code=400, detail="Đề thi chưa có câu hỏi nào để xuất file")
        
    import urllib.parse
    import unicodedata
    
    raw_name = f"De_thi_{exam_data.grade or 5}_{exam_data.title[:25]}.pdf".replace(" ", "_")
    ascii_name = unicodedata.normalize('NFKD', raw_name).encode('ascii', 'ignore').decode('ascii')
    if not ascii_name.endswith(".pdf"):
        ascii_name += ".pdf"
    encoded_name = urllib.parse.quote(raw_name)
    
    html_content = build_moet_exam_html(exam_data.model_dump(), questions)
    
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="load")
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "20mm", "bottom": "20mm", "left": "25mm", "right": "15mm"}
            )
            await browser.close()
    except Exception as e:
        logger.warning(f"Playwright PDF generation unavailable, using fallback PDF generator: {e}")
        pdf_bytes = _generate_fallback_pdf(exam_data.title, questions)
            
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"
        }
    )

# ----------------- Document & Image Exam Extractor (PDF & OCR) -----------------

@app.post("/api/import/pdf")
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

@app.post("/api/import/image")
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

@app.post("/api/pdf/extract")
@app.post("/api/import/exam-file")
async def import_exam_file(
    file: UploadFile = File(...),
    save_to_bank: bool = Form(False),
    engine: str = Form("rapid")
):
    """Unified file ingestion endpoint accepting both PDF and Image formats with engine selection."""
    return await import_pdf_exam(file=file, save_to_bank=save_to_bank, engine=engine)

# ----------------- AI Agent Exam Data Importer (JSON, DOCX, Text, Markdown) -----------------

@app.get("/api/import/ai-agent-template")
async def get_ai_agent_template_endpoint():
    """Returns standardized system prompt and schemas for external AI agents."""
    from backend.ai_agent_importer import get_ai_agent_template_info
    return {"success": True, "template": get_ai_agent_template_info()}

@app.post("/api/import/ai-agent-data")
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

@app.get("/api/ocr/engine-status")
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

@app.get("/api/ai-vision/settings")
async def get_ai_vision_settings_api():
    """Returns AI Vision settings including OpenRouter and OpenCode keys/models."""
    from backend.ai_vision import get_ai_vision_settings
    return {"success": True, "settings": get_ai_vision_settings()}

@app.post("/api/ai-vision/models")
@app.get("/api/ai-vision/models")
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

@app.post("/api/ai-vision/settings")
async def save_ai_vision_settings_api(req: AiVisionSettingsRequest):
    """Saves AI Vision configuration parameters."""
    from backend.ai_vision import save_ai_vision_settings, get_ai_vision_settings
    save_ai_vision_settings(req.model_dump(exclude_unset=True))
    updated = get_ai_vision_settings()
    return {"success": True, "settings": updated, "message": "Đã lưu cài đặt AI Vision thành công!"}

@app.post("/api/ai-vision/test-connection")
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

@app.post("/api/ocr/learn")
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

@app.get("/api/ocr/corrections")
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

@app.post("/api/ocr/corrections")
async def add_ocr_correction(req: OcrCorrectionCreate):
    """Manually adds or updates a specific correction rule in the lexicon."""
    from backend.database import add_manual_ocr_correction
    try:
        res = add_manual_ocr_correction(req.wrong_text, req.correct_text, source=req.source or "manual_rule")
        return {"success": True, "item": res, "message": "Đã thêm quy tắc sửa đổi thành công"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/ocr/corrections/{correction_id}")
async def remove_ocr_correction(correction_id: int, _auth=Depends(require_api_token)):
    """Deletes a specific correction rule from the lexicon."""
    from backend.database import delete_ocr_correction
    ok = delete_ocr_correction(correction_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy quy tắc cần xóa")
    return {"success": True, "message": "Đã xóa quy tắc thành công"}

@app.post("/api/ocr/corrections/clear")
async def clear_ocr_corrections(_auth=Depends(require_api_token)):
    """Clears all learned correction rules."""
    from backend.database import clear_all_ocr_corrections
    count = clear_all_ocr_corrections()
    return {"success": True, "cleared_count": count, "message": f"Đã xóa toàn bộ {count} quy tắc từ điển"}

# ----------------- Automated Scraper Runner -----------------

@app.post("/api/collect/run")
async def run_collector_task(req: ScrapeRequest):
    platform = req.platform.lower()
    
    if platform == "vioedu":
        if req.action in ["bot_crawl", "crawl", "login", "auto_crawl"]:
            if req.username and req.password:
                log_collector_event(
                    platform="vioedu",
                    status="running",
                    message=f"Kích hoạt cào VioEdu ({req.action}) cho tài khoản {req.username} (Khối {req.grade or 5})",
                    count=0
                )
                try:
                    res = await crawl_vioedu_rounds_headless(
                        username=req.username,
                        password=req.password,
                        round_id=req.round_id,
                        grade=req.grade
                    )
                    if not res.get("success"):
                        log_collector_event(
                            platform="vioedu",
                            status="error",
                            message=f"Cào VioEdu thất bại: {res.get('error', 'Lỗi không xác định')}",
                            count=0
                        )
                    return res
                except Exception as e:
                    err_msg = str(e)
                    log_collector_event(
                        platform="vioedu",
                        status="error",
                        message=f"Lỗi ngoại lệ khi cào VioEdu: {err_msg}",
                        count=0
                    )
                    return {"success": False, "error": err_msg}
            else:
                msg = "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu VioEdu."
                log_collector_event(platform="vioedu", status="warning", message=msg, count=0)
                return {"success": False, "error": msg}
        elif req.action == "fetch_arena":
            questions = await fetch_vioedu_arena_questions(req.token, req.round_id or "1", grade=req.grade or 5)
            normalized_list = [await normalize_question_payload(q) for q in questions]
            inserted = bulk_insert_questions(normalized_list)
            log_collector_event("vioedu", "success", f"Thu thập Đấu trường #{req.round_id}", inserted)
            return {"success": True, "count": inserted, "questions": normalized_list}
            
    elif platform == "tnmath":
        if req.action == "login":
            res = await login_tnmath(req.username, req.password)
            return res
            
    return {"success": False, "error": "Chức năng hoặc nền tảng chưa được hỗ trợ trực tiếp. Vui lòng sử dụng Tiện ích Extension hoặc nạp PDF."}

@app.get("/api/collect/logs")
async def get_logs(limit: int = 50):
    return get_collector_logs(limit)

@app.post("/api/collect/logs/sync")
async def sync_collector_log(payload: dict):
    platform = payload.get("platform", "extension")
    status = payload.get("status", "info")
    message = payload.get("message", "")
    count = int(payload.get("count", 0))
    if message:
        log_collector_event(platform=platform, status=status, message=message, count=count)
    return {"success": True}

@app.delete("/api/collect/logs")
async def delete_logs(_auth=Depends(require_api_token)):
    clear_collector_logs()
    return {"success": True, "message": "Đã xóa toàn bộ nhật ký"}

# ----------------- Sample Data Seeder -----------------

@app.post("/api/init-samples")
async def init_sample_questions(_auth=Depends(require_api_token)):
    """Seeds authentic sample math questions from VioEdu, Trạng Nguyên, TIMO, HKIMO, and ASMO."""
    samples = [
        # 1. VioEdu Grade 5 - Fractions
        {
            "id": "sample_vioedu_001",
            "source_platform": "vioedu",
            "source_url": "https://vio.edu.vn",
            "exam_name": "Đấu trường VioEdu - Vòng Sơ khảo Cấp Quận 2025",
            "grade": 5,
            "subject": "math",
            "topic": "Phân số và Hỗn số",
            "question_type": "single_choice",
            "content_html": "<p>Tính giá trị của biểu thức sau: $A = \\frac{1}{2} + \\frac{1}{6} + \\frac{1}{12} + \\frac{1}{20} + \\frac{1}{30}$</p>",
            "content_text": "Tính giá trị của biểu thức sau: A = 1/2 + 1/6 + 1/12 + 1/20 + 1/30",
            "images": [],
            "options": [
                {"id": "A", "content": "$\\frac{5}{6}$", "is_correct": True},
                {"id": "B", "content": "$\\frac{4}{5}$", "is_correct": False},
                {"id": "C", "content": "$\\frac{1}{6}$", "is_correct": False},
                {"id": "D", "content": "$\\frac{7}{10}$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Ta có: $\\frac{1}{2} = 1 - \\frac{1}{2}$, $\\frac{1}{6} = \\frac{1}{2} - \\frac{1}{3}$, $\\frac{1}{12} = \\frac{1}{3} - \\frac{1}{4}$, $\\frac{1}{20} = \\frac{1}{4} - \\frac{1}{5}$, $\\frac{1}{30} = \\frac{1}{5} - \\frac{1}{6}$.\nCộng vế với vế ta được: $A = 1 - \\frac{1}{6} = \\frac{5}{6}$.",
            "difficulty": "medium"
        },
        # 2. VioEdu Grade 5 - Geometry Speed/Distance
        {
            "id": "sample_vioedu_002",
            "source_platform": "vioedu",
            "source_url": "https://vio.edu.vn",
            "exam_name": "Đấu trường VioEdu - Vòng Chung kết Tỉnh",
            "grade": 5,
            "subject": "math",
            "topic": "Chuyển động đều",
            "question_type": "fill_blank",
            "content_html": "<p>Hai thành phố $A$ và $B$ cách nhau $165\\text{ km}$. Lúc 7 giờ sáng, một ô tô đi từ $A$ đến $B$ với vận tốc $50\\text{ km/h}$, đồng thời một xe máy đi từ $B$ về $A$ với vận tốc $32.5\\text{ km/h}$. Hỏi hai xe gặp nhau lúc mấy giờ?</p>",
            "content_text": "Hai thành phố A và B cách nhau 165 km. Lúc 7 giờ sáng, một ô tô đi từ A đến B với vận tốc 50 km/h, đồng thời một xe máy đi từ B về A với vận tốc 32.5 km/h. Hỏi hai xe gặp nhau lúc mấy giờ?",
            "images": [],
            "options": [],
            "correct_answer": "9",
            "explanation": "Tổng vận tốc hai xe là: $50 + 32.5 = 82.5\\text{ km/h}$.\nThời gian hai xe gặp nhau là: $165 : 82.5 = 2\\text{ giờ}$.\nHai xe gặp nhau lúc: $7 + 2 = 9\\text{ giờ}$.",
            "difficulty": "medium"
        },
        # 3. Trạng Nguyên Toán Học - Matching (Phép thuật Mèo con)
        {
            "id": "sample_tnmath_001",
            "source_platform": "tnmath",
            "source_url": "https://tnmath.edu.vn",
            "exam_name": "Trạng Nguyên Toàn Tài - Vòng Thi Hương",
            "grade": 4,
            "subject": "math",
            "topic": "Phép nhân và chia số tự nhiên",
            "question_type": "matching",
            "content_html": "<p>Em hãy nối các phép tính có giá trị bằng nhau:</p>",
            "content_text": "Em hãy nối các phép tính có giá trị bằng nhau",
            "images": [],
            "options": [
                {"id": "pair_1", "content": "$25 \\times 4$ ↔ $100$", "is_correct": True},
                {"id": "pair_2", "content": "$125 \\times 8$ ↔ $1000$", "is_correct": True},
                {"id": "pair_3", "content": "$360 : 6$ ↔ $60$", "is_correct": True},
                {"id": "pair_4", "content": "$45 \\times 2$ ↔ $90$", "is_correct": True}
            ],
            "correct_answer": "Nối đúng 4 cặp tương ứng",
            "explanation": "25 x 4 = 100; 125 x 8 = 1000; 360 : 6 = 60; 45 x 2 = 90.",
            "difficulty": "easy"
        },
        # 4. Trạng Nguyên Toán Học - Chuột vàng tài ba
        {
            "id": "sample_tnmath_002",
            "source_platform": "tnmath",
            "source_url": "https://tnmath.edu.vn",
            "exam_name": "Trạng Nguyên Toán Học - Vòng Hội",
            "grade": 5,
            "subject": "math",
            "topic": "Hình học - Diện tích hình thang",
            "question_type": "single_choice",
            "content_html": "<p>Một thửa ruộng hình thang có đáy lớn $120\\text{ m}$, đáy bé bằng $\\frac{2}{3}$ đáy lớn, chiều cao bằng trung bình cộng hai đáy. Diện tích thửa ruộng đó là bao nhiêu mét vuông?</p>",
            "content_text": "Một thửa ruộng hình thang có đáy lớn 120 m, đáy bé bằng 2/3 đáy lớn, chiều cao bằng trung bình cộng hai đáy. Diện tích thửa ruộng đó là bao nhiêu mét vuông?",
            "images": [],
            "options": [
                {"id": "A", "content": "$10000\\text{ m}^2$", "is_correct": True},
                {"id": "B", "content": "$8000\\text{ m}^2$", "is_correct": False},
                {"id": "C", "content": "$12000\\text{ m}^2$", "is_correct": False},
                {"id": "D", "content": "$9600\\text{ m}^2$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Đáy bé hình thang là: $120 \\times \\frac{2}{3} = 80\\text{ m}$.\nChiều cao hình thang là: $(120 + 80) : 2 = 100\\text{ m}$.\nDiện tích thửa ruộng là: $\\frac{(120 + 80) \\times 100}{2} = 10000\\text{ m}^2$.",
            "difficulty": "medium"
        },
        # 5. TIMO (Thailand International Mathematical Olympiad) - Combinatorics
        {
            "id": "sample_timo_001",
            "source_platform": "timo",
            "source_url": "https://lmsfermat.edu.vn",
            "exam_name": "TIMO National Final 2024 - Secondary 1",
            "grade": 7,
            "subject": "math",
            "topic": "Tổ hợp & Logic (Combinatorics)",
            "question_type": "single_choice",
            "content_html": "<p>How many 3-digit numbers are there such that the sum of their digits is an odd number?<br/><i>(Có bao nhiêu số có 3 chữ số sao cho tổng các chữ số của nó là một số lẻ?)</i></p>",
            "content_text": "How many 3-digit numbers are there such that the sum of their digits is an odd number? (Có bao nhiêu số có 3 chữ số sao cho tổng các chữ số của nó là một số lẻ?)",
            "images": [],
            "options": [
                {"id": "A", "content": "450", "is_correct": True},
                {"id": "B", "content": "440", "is_correct": False},
                {"id": "C", "content": "500", "is_correct": False},
                {"id": "D", "content": "400", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Số có 3 chữ số từ 100 đến 999 có tổng cộng 900 số. Trong đó, chữ số hàng đơn vị thay đổi xen kẽ giữa chẵn và lẻ khiến tổng các chữ số luân phiên chẵn và lẻ với xác suất 1/2. Do đó có đúng: $900 : 2 = 450$ số thỏa mãn.",
            "difficulty": "olympiad"
        },
        # 6. HKIMO (Hong Kong International Mathematical Olympiad) - Number Theory
        {
            "id": "sample_hkimo_001",
            "source_platform": "hkimo",
            "source_url": "https://lmsfermat.edu.vn",
            "exam_name": "HKIMO Heat Round 2024 - Primary 5",
            "grade": 5,
            "subject": "math",
            "topic": "Số học (Number Theory)",
            "question_type": "single_choice",
            "content_html": "<p>Find the last two digits of $7^{2024}$.<br/><i>(Tìm hai chữ số tận cùng của $7^{2024}$.)</i></p>",
            "content_text": "Find the last two digits of 7^2024. (Tìm hai chữ số tận cùng của 7^2024.)",
            "images": [],
            "options": [
                {"id": "A", "content": "01", "is_correct": True},
                {"id": "B", "content": "49", "is_correct": False},
                {"id": "C", "content": "43", "is_correct": False},
                {"id": "D", "content": "07", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Xét chu kỳ hai chữ số tận cùng của lũy thừa của 7 theo modulo 100:\n$7^1 \\equiv 07$\n$7^2 \\equiv 49$\n$7^3 \\equiv 43$\n$7^4 = 2401 \\equiv 01\\pmod{100}$.\nVì $2024$ chia hết cho $4$ ($2024 = 4 \\times 506$), nên hai chữ số tận cùng của $7^{2024}$ là $01$.",
            "difficulty": "olympiad"
        },
        # 7. ASMO (Asian Science and Mathematics Olympiad) - Geometry
        {
            "id": "sample_asmo_001",
            "source_platform": "asmo",
            "source_url": "https://asmo.vn",
            "exam_name": "ASMO National Round 2024 - Grade 6",
            "grade": 6,
            "subject": "math",
            "topic": "Hình học (Geometry)",
            "question_type": "single_choice",
            "content_html": "<p>A square of side length $10\\text{ cm}$ contains four identical circles inscribed as shown. What is the area of the shaded region in terms of $\\pi$?<br/><i>(Một hình vuông cạnh $10\\text{ cm}$ chứa 4 hình tròn bằng nhau tiếp xúc nhau. Tính diện tích phần tô đậm?)</i></p>",
            "content_text": "A square of side length 10 cm contains four identical circles inscribed as shown. What is the area of the shaded region in terms of pi?",
            "images": [],
            "options": [
                {"id": "A", "content": "$100 - 25\\pi$", "is_correct": True},
                {"id": "B", "content": "$100 - 20\\pi$", "is_correct": False},
                {"id": "C", "content": "$80 - 16\\pi$", "is_correct": False},
                {"id": "D", "content": "$50 - 12.5\\pi$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Bán kính mỗi hình tròn nhỏ là $r = 10 : 4 = 2.5\\text{ cm}$.\nDiện tích 4 hình tròn là $4 \\times \\pi \\times 2.5^2 = 25\\pi\\text{ cm}^2$.\nDiện tích hình vuông là $10 \\times 10 = 100\\text{ cm}^2$.\nDiện tích phần tô đậm là $100 - 25\\pi\\text{ cm}^2$.",
            "difficulty": "olympiad"
        },
        # 8. Tiếng Việt - Trạng Nguyên Tiếng Việt Lớp 4
        {
            "id": "sample_tv_001",
            "source_platform": "tnmath",
            "source_url": "https://trangnguyen.edu.vn",
            "exam_name": "Trạng Nguyên Tiếng Việt - Vòng Hương 2024",
            "grade": 4,
            "subject": "vietnamese",
            "topic": "Từ ngữ & Ngữ pháp Tiếng Việt",
            "question_type": "single_choice",
            "content_html": "<p>Trong các câu sau, câu nào có hình ảnh so sánh?</p>",
            "content_text": "Trong các câu sau, câu nào có hình ảnh so sánh?",
            "images": [],
            "options": [
                {"id": "A", "content": "Mặt trời như một quả cầu lửa khổng lồ từ từ nhô lên.", "is_correct": True},
                {"id": "B", "content": "Mùa xuân về, cây cối đâm chồi nảy lộc.", "is_correct": False},
                {"id": "C", "content": "Tiếng suối róc rách chảy suốt đêm ngày.", "is_correct": False},
                {"id": "D", "content": "Gió heo may nhè nhẹ thổi qua cánh đồng.", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Câu A sử dụng từ so sánh 'như' để ví 'Mặt trời' giống như 'một quả cầu lửa khổng lồ'.",
            "difficulty": "easy"
        },
        # 9. Tiếng Anh - Olympic English IOE Lớp 5
        {
            "id": "sample_eng_001",
            "source_platform": "manual",
            "source_url": "https://ioe.vn",
            "exam_name": "Olympic English Contest (IOE) - Grade 5",
            "grade": 5,
            "subject": "english",
            "topic": "Grammar - Past Tense",
            "question_type": "single_choice",
            "content_html": "<p>Choose the correct answer: <i>'Where ______ you go for your summer vacation last year?'</i></p>",
            "content_text": "Choose the correct answer: 'Where ______ you go for your summer vacation last year?'",
            "images": [],
            "options": [
                {"id": "A", "content": "did", "is_correct": True},
                {"id": "B", "content": "do", "is_correct": False},
                {"id": "C", "content": "are", "is_correct": False},
                {"id": "D", "content": "were", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Câu hỏi ở thì quá khứ đơn với trạng từ 'last year', sử dụng trợ động từ 'did'.",
            "difficulty": "medium"
        }
    ]
    
    for s in samples:
        norm = await normalize_question_payload(s)
        insert_or_update_question(norm)
        
    return {"success": True, "seeded_count": len(samples), "message": f"Đã nạp {len(samples)} câu hỏi mẫu Toán, Tiếng Việt, Tiếng Anh chuẩn quốc tế & học đường!"}

# ----------------- Internet Question Hunter Endpoint -----------------

from backend.scrapers.internet_hunter import run_internet_question_hunter, get_grade_source_urls

@app.post("/api/hunter/run")
async def trigger_internet_hunter(payload: dict):
    subject = payload.get("subject", "all")
    grade = int(payload.get("grade", 5))
    custom_url = payload.get("custom_url")
    custom_urls = payload.get("custom_urls", [])
    result = await run_internet_question_hunter(
        subject=subject,
        grade=grade,
        custom_url=custom_url,
        custom_urls=custom_urls
    )
    return result

@app.get("/api/hunter/grade-sources")
async def get_grade_math_sources(grade: int = 2):
    """Returns the catalog of supported sources across Vietnamese, English and Olympic platforms for any Grade 1 to 12."""
    return get_grade_source_urls(grade)

@app.get("/api/hunter/grade2-sources")
async def get_grade2_math_sources():
    """Backward-compatible endpoint: Returns sources for Grade 2."""
    return get_grade_source_urls(2)

@app.post("/api/hunter/harvest-by-grade")
async def harvest_math_by_grade(payload: dict):
    """Triggers an all-inclusive multi-source harvest for Math across any Grade 1 to 12 (Vietnamese + English + Olympic)."""
    grade = int(payload.get("grade", 2))
    grade = max(1, min(12, grade))
    subject = payload.get("subject", "math")
    
    # Dynamically extract target URLs from source catalog for this grade
    catalog = get_grade_source_urls(grade)
    target_urls = []
    for cat in catalog.get("categories", []):
        for s in cat.get("sources", []):
            u = s.get("url")
            if u and u not in target_urls:
                target_urls.append(u)

    res = await run_internet_question_hunter(
        subject=subject,
        grade=grade,
        custom_urls=target_urls,
        limit=50
    )
    return res

@app.post("/api/hunter/harvest-grade2")
async def harvest_grade2_math():
    """Backward-compatible endpoint: Triggers harvest for Grade 2 Math."""
    return await harvest_math_by_grade({"grade": 2, "subject": "math"})

# ----------------- Interactive Practice Arena Endpoints -----------------

@app.post("/api/practice/generate")
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

@app.post("/api/practice/submit")
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
        "answers_detail": answers_detail
    }

@app.get("/api/practice/history")
async def list_practice_history(
    limit: int = Query(50, ge=1, le=500),
    subject: Optional[str] = Query(None),
    grade: Optional[int] = Query(None)
):
    """Returns chronological list of student practice history records."""
    records = get_practice_history(limit=limit, subject=subject, grade=grade)
    return {"success": True, "count": len(records), "records": records}

@app.get("/api/practice/history/{record_id}")
async def get_practice_record_detail(record_id: str):
    """Returns a specific practice session with full question answers detail."""
    rec = get_practice_history_by_id(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử bài luyện tập này")
    return {"success": True, "record": rec}

@app.get("/api/practice/analytics")
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

# ----------------- Favicon Suppression (Clear Browser Cache) -----------------

import base64
TRANSPARENT_FAVICON = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
async def suppress_favicon():
    """Returns a 1x1 transparent PNG to clear any cached tab icons and ensure no logo is shown."""
    return Response(
        content=TRANSPARENT_FAVICON,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )

# ----------------- Media Upload Endpoint -----------------

@app.post("/api/media/upload")
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

# ----------------- Question Bank Contribution Endpoint -----------------

@app.post("/api/contribute/upload")
async def upload_contribute_file(
    file: UploadFile = File(...),
    contributor_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    """Allows users/teachers to contribute exam files (PDF, Word, Image, Text) to the training pool."""
    import unicodedata
    allowed_ext = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".txt", ".webp", ".bmp"}
    orig_filename = file.filename or "tai_lieu"
    base_name, ext = os.path.splitext(orig_filename)
    ext = ext.lower()
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file không hỗ trợ: {ext}. Chỉ chấp nhận: {', '.join(sorted(allowed_ext))}"
        )

    contents = await file.read()
    if len(contents) > 25 * 1024 * 1024:  # 25MB limit
        raise HTTPException(status_code=400, detail="File quá lớn. Giới hạn dung lượng tối đa 25MB.")

    # Sanitize base_name: strip accents, keep alphanumeric and underscores/dashes
    clean_name = unicodedata.normalize('NFKD', base_name).encode('ASCII', 'ignore').decode('utf-8')
    clean_name = re.sub(r'[^\w\-]', '_', clean_name).strip('_').lower()
    if not clean_name:
        clean_name = "de_thi"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_filename = f"{clean_name}_{ts}_contribute{ext}"

    training_dir = os.path.join(BASE_DIR, "data", "training")
    os.makedirs(training_dir, exist_ok=True)
    saved_path = os.path.join(training_dir, target_filename)

    with open(saved_path, "wb") as f:
        f.write(contents)

    log_msg = f"Đã nhận tệp đóng góp: {target_filename}"
    if contributor_name:
        log_msg += f" từ {contributor_name.strip()}"
    if notes:
        log_msg += f" (Ghi chú: {notes.strip()})"

    log_collector_event(
        platform="contribute",
        status="success",
        message=log_msg,
        count=1
    )

    return {
        "success": True,
        "filename": target_filename,
        "saved_path": saved_path,
        "message": "Đóng góp đề thi thành công! Tệp đã được lưu vào hệ thống."
    }

# ----------------- Static Files Serving -----------------

# Mount media directory
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# Mount frontend
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

