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
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse

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
    save_practice_history, get_practice_history, get_practice_history_by_id, get_practice_analytics,
    get_due_reviews, get_review_stats, record_review_results
)
from backend.models import (
    QuestionCreate, QuestionUpdate, BulkQuestionCreate,
    BulkDeleteRequest, BulkDeleteQuestionsRequest, BulkUpdateGradeRequest,
    ExamCreate, ScrapeRequest, VioEduPlanRequest, AutoExamGenerateRequest, CleanDuplicatesRequest,
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
    login_vioedu, fetch_vioedu_arena_questions, parse_vioedu_question_data, crawl_vioedu_rounds_headless,
    crawl_vioedu_breadth,
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
    """Enforces credential on destructive/admin endpoints.

    Accepts EITHER a valid admin Bearer session (account login) OR the
    X-API-Token header (when API_TOKEN env is set). Local default (env empty
    AND no Bearer token) keeps pass-through so the dashboard & extension keep
    working. Ingest paths (collect, sync, bulk-insert) are intentionally NOT
    gated so zero-click extension sync never breaks.
    """
    # 1. Admin session (account login) is always accepted.
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from backend import auth as A
            from backend.database import get_connection
            conn = get_connection()
            try:
                user = A.get_session_user(conn, auth[7:].strip())
            finally:
                conn.close()
            if user is not None and user["role"] == "admin" and user["status"] == "active":
                return None
        except Exception:
            pass
        # Bearer present but invalid -> fall through to token check below
    # 2. Legacy X-API-Token (only enforced when env is set).
    if not API_TOKEN:
        return None
    if request.headers.get("X-API-Token", "") != API_TOKEN:
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai credential (đăng nhập admin hoặc header X-API-Token)")
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


# Web login gate (quyết định 2026-10-12 cùng user): mọi /api/* đều yêu cầu
# Bearer session, TRỪ auth/version + 4 endpoint extension-sync relay
# (bulk, bulk-update-grade, logs/sync, stats) để zero-click sync không gãy.
# Dạng middleware nên không cần sửa ~60 endpoint; test khóa ở test_auth.py.
_AUTH_GATE_PUBLIC = frozenset({
    "/api/version",
    "/api/auth/register", "/api/auth/login", "/api/auth/logout",
    "/api/auth/forgot",
    "/api/questions/bulk", "/api/questions/bulk-update-grade",
    "/api/collect/logs/sync", "/api/stats",
})
# Subpath read-only public: healthcheck Docker gọi /api/stats/count,
# AGENTS.md smoke dùng curl -I .../api/stats/count. Exact-match sẽ 401 →
# container unhealthy nên phải prefix-match nhóm này.
_AUTH_GATE_PUBLIC_PREFIX = ("/api/stats", "/api/version")


def _is_gate_public(path: str) -> bool:
    if path in _AUTH_GATE_PUBLIC:
        return True
    return path.startswith(_AUTH_GATE_PUBLIC_PREFIX)


def _session_user_for_gate(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        from backend import auth as A
        from backend.database import get_connection
        conn = get_connection()
        try:
            return A.get_session_user(conn, auth[7:].strip())
        finally:
            conn.close()
    except Exception:
        return None


async def _auth_gate_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not _is_gate_public(path):
        user = _session_user_for_gate(request)
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"success": False, "detail": "Chưa đăng nhập hoặc phiên đã hết hạn."},
            )
        if user["status"] != "active":
            return JSONResponse(
                status_code=403,
                content={"success": False, "detail": "Tài khoản chưa được duyệt hoặc đã bị khóa."},
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
    # 24/7 VioEdu auto-crawl scheduler (honors system_config vioedu_auto_crawl)
    asyncio.create_task(_schedule_vioedu_auto_crawl())
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

from backend.routers.database import _schedule_db_backup

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
app.middleware("http")(_auth_gate_middleware)

# (Database & System Stats endpoints migrated to backend/routers/database.py)

# (Exams, Word & PDF export migrated to backend/routers/exams.py)

# (AI Vision & OCR endpoints migrated to backend/routers/ai_vision.py)

# (Collector, Hunter & Seeder endpoints migrated to backend/routers/collector.py)

# (Practice Arena endpoints migrated to backend/routers/practice.py)

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

# (Media Upload endpoint migrated to backend/routers/ai_vision.py)

from backend.dependencies import require_api_token, _require_session, _require_admin

# ----------------- Routers -----------------
from backend.routers.auth import router as auth_router
from backend.routers.questions import router as questions_router
from backend.routers.exams import router as exams_router, normalize_moet_math_symbols, build_moet_exam_html
from backend.routers.practice import router as practice_router
from backend.routers.collector import router as collector_router, _schedule_vioedu_auto_crawl, init_sample_questions
from backend.routers.ai_vision import router as ai_vision_router
from backend.routers.database import router as database_router

app.include_router(auth_router)
app.include_router(questions_router)
app.include_router(exams_router)
app.include_router(practice_router)
app.include_router(collector_router)
app.include_router(ai_vision_router)
app.include_router(database_router)

# ----------------- Static Files Serving -----------------

# Mount media directory
@app.get("/")
@app.get("/index.html")
async def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(
        index_file,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# Mount frontend
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

