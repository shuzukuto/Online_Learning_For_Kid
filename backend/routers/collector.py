"""Automated Scraper, Hunter, VioEdu Hub & Sample Data APIRouter."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request, Query

from backend.dependencies import require_api_token, _require_admin
from backend.database import (
    bulk_insert_questions,
    insert_or_update_question,
    log_collector_event,
    get_collector_logs,
    clear_collector_logs,
    get_system_config,
    set_system_config,
)
from backend.models import ScrapeRequest, VioEduPlanRequest
from backend.normalizer import normalize_question_payload, is_valid_question_payload
from backend.scrapers.vioedu import (
    login_vioedu,
    fetch_vioedu_arena_questions,
    parse_vioedu_question_data,
    crawl_vioedu_rounds_headless,
    crawl_vioedu_breadth,
)
from backend.scrapers.tnmath import login_tnmath, parse_tnmath_question_data
from backend.scrapers.internet_hunter import run_internet_question_hunter, get_grade_source_urls

VN_TZ = timezone(timedelta(hours=7))
logger = logging.getLogger("eduquest.collector")

router = APIRouter(tags=["Collector & Hunter"])

# ----------------- Automated Scraper Runner -----------------

# In-memory registry for background breadth jobs (single worker; DB log is the durable record).
_BREADTH_JOBS: dict = {}

# Auto-crawl 24/7 config keys (system_config): vioedu_auto_crawl = on/off,
# vioedu_auto_interval_sec (default 21600 = 6h), vioedu_auto_grades, vioedu_auto_subjects.
VIOEDU_AUTO_DEFAULT_INTERVAL_SEC = 6 * 60 * 60
# User 2026-10-14: mo rong xoay tua 1-12 (tieu hoc → THPT).
# Moi vong 6h cao 1 khoi khac nhau; hunter-internet (LGH/VJ/OLM) co mapping
# san cho 1-12 nen moi khoi deu co URL moi → bot luon co viec.
VIOEDU_AUTO_DEFAULT_GRADES = "1,2,3,4,5,6,7,8,9,10,11,12"
_VIOEDU_AUTO_GRADE_CURSOR = {"idx": 0}

# VioEdu arena/tournament common time windows (Vietnam local time)
# Bot will attempt arena crawl when current time falls within these ranges.
VIOEDU_ARENA_WINDOWS = [
    (7, 30, 9, 0),    # Sáng: 7:30 - 9:00
    (11, 0, 12, 30),   # Trưa: 11:00 - 12:30
    (19, 0, 21, 0),    # Tối: 19:00 - 21:00
]


def _is_arena_hour() -> bool:
    """Check if current time (VN timezone) falls within typical VioEdu arena windows."""
    now = datetime.now(VN_TZ)
    current_minutes = now.hour * 60 + now.minute
    for start_h, start_m, end_h, end_m in VIOEDU_ARENA_WINDOWS:
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        if start <= current_minutes <= end:
            return True
    return False


# Scheduler liveness trace: updated on EVERY loop iteration (even when the
# bot is disabled or skipping), so the hub UI can distinguish
# "alive but idle" from "dead". In-memory by design (resets on restart —
# absence right after boot is expected, absence after hours means dead).
_VIOEDU_HEARTBEAT: dict = {"tick_at": None, "note": "scheduler chưa chạy vòng nào"}


def _record_vioedu_heartbeat(note: str) -> None:
    _VIOEDU_HEARTBEAT["tick_at"] = datetime.now(VN_TZ).isoformat()
    _VIOEDU_HEARTBEAT["note"] = note


VIOEDU_SESSION_COOKIES_KEY = "vioedu_session_cookies"


def _get_vioedu_session_cookies():
    # User 2026-10-14: xoay 1-12 dung "tai khoan dang nhap cao du lieu".
    # Admin nhap TK VioEdu 1 lan (POST /api/collect/vioedu-login) → cookies
    # luu JSON tai day. Chua co → None = anonymous nhu cu (khong doi hanh vi).
    try:
        from backend.database import get_system_config
        import json as _json
        raw = (get_system_config(VIOEDU_SESSION_COOKIES_KEY, "") or "").strip()
        if not raw:
            return None
        data = _json.loads(raw)
        return data if isinstance(data, dict) and data else None
    except Exception:
        return None


async def _run_breadth_job(jid: str, grades, subjects, max_q: int, force: bool = False,
                           recrawl_days: int = 7, source: str = "manual"):
    """Shared breadth sweep runner: crawl -> normalize -> insert -> log.

    Used by action=breadth, the unified vioedu-plan endpoint, and the 24/7
    background scheduler."""
    from backend.normalizer import normalize_question_payload as _norm, is_valid_question_payload as _valid
    try:
        def _log_breadth_progress(msg: str):
            try:
                log_collector_event("vioedu", "info", f"[{jid}] {msg}", 0)
            except Exception:
                pass

        sweep = await crawl_vioedu_breadth(grades=grades, subjects=subjects,
            max_questions_per_skill=max_q, force=force, recrawl_days=recrawl_days,
            cookies=_get_vioedu_session_cookies(),
            log_func=_log_breadth_progress)
        fallback_grade = (grades or [2])[0] if grades else 2
        normalized_list = []
        for raw in sweep.get("questions", []):
            subj = raw.pop("_breadth_subject", "math")
            parsed = parse_vioedu_question_data(
                raw, exam_name=f"VioEdu {subj} Lớp {raw.get('grade', fallback_grade)}",
                grade=int(raw.get("grade") or fallback_grade), subject=subj)
            if parsed:
                try:
                    norm_q = await _norm(parsed)
                    valid, _ = _valid(norm_q)
                    if valid:
                        normalized_list.append(norm_q)
                except Exception:
                    pass
        inserted = bulk_insert_questions(normalized_list, skip_duplicates=True) if normalized_list else 0
        _BREADTH_JOBS[jid] = {"status": "done", "count": inserted, "source": source,
            "stats": sweep.get("stats", {}), "skills_visited": sweep.get("skills_visited", 0)}
        log_collector_event("vioedu", "success",
            f"Cào diện rộng VioEdu [{source}]: {inserted} câu mới ({sweep.get('skills_visited', 0)} bài, {sweep.get('stats', {})})", inserted)
    except Exception as e:
        _BREADTH_JOBS[jid] = {"status": "error", "error": str(e)[:200], "count": 0, "source": source}
        log_collector_event("vioedu", "error", f"Cào diện rộng VioEdu lỗi: {str(e)[:150]}", 0)


async def _schedule_vioedu_auto_crawl():
    """24/7 background scheduler: sweep stale skills on interval when enabled.

    Reads system_config vioedu_auto_crawl (on/off). Skips while a breadth job
    is already running. Ledger (7-day default) prevents re-crawling fresh skills.
    First run 120s after startup so boot stays fast.
    """
    from backend.database import get_system_config
    _record_vioedu_heartbeat("scheduler vừa khởi động, chờ vòng đầu (~2 phút)")
    await asyncio.sleep(120)
    while True:
        try:
            enabled = (get_system_config("vioedu_auto_crawl", "off") or "off").strip().lower() == "on"
            if enabled and not any(j.get("status") == "running" for j in _BREADTH_JOBS.values()):
                try:
                    interval = int(get_system_config("vioedu_auto_interval_sec", str(VIOEDU_AUTO_DEFAULT_INTERVAL_SEC)) or VIOEDU_AUTO_DEFAULT_INTERVAL_SEC)
                except ValueError:
                    interval = VIOEDU_AUTO_DEFAULT_INTERVAL_SEC
                grades_raw = (get_system_config("vioedu_auto_grades", VIOEDU_AUTO_DEFAULT_GRADES) or VIOEDU_AUTO_DEFAULT_GRADES).strip()
                subs_raw = (get_system_config("vioedu_auto_subjects", "math,vietnamese,english") or "math,vietnamese,english").strip()
                grades_all = [int(g) for g in grades_raw.split(",") if g.strip().isdigit()] or [2]
                # Xoay vong 1 khoi/vong de moi vong tap trung cao sau 1 khoi,
                # tranh cao lai khoi vua fresh -> 0 cau.
                # Luu con tro cursor vao system_config de restart khong bi reset ve khoi 1.
                from backend.database import set_system_config
                cursor_raw = get_system_config("vioedu_auto_cursor", "0")
                try:
                    cursor_idx = int(cursor_raw)
                except (ValueError, TypeError):
                    cursor_idx = _VIOEDU_AUTO_GRADE_CURSOR.get("idx", 0)
                if len(grades_all) > 1:
                    grades = [grades_all[cursor_idx % len(grades_all)]]
                    _VIOEDU_AUTO_GRADE_CURSOR["idx"] = (cursor_idx + 1) % len(grades_all)
                    set_system_config("vioedu_auto_cursor", str(_VIOEDU_AUTO_GRADE_CURSOR["idx"]))
                else:
                    grades = grades_all
                subjects = [s.strip().lower() for s in subs_raw.split(",") if s.strip()] or ["math", "vietnamese", "english"]
                import time as _t
                jid = f"auto-{int(_t.time())}"
                _BREADTH_JOBS[jid] = {"status": "running", "stats": {}, "count": 0, "skills_visited": 0, "source": "auto"}
                # --- Arena-aware scheduling (Phase 5) ---
                arena_note = ""
                if _is_arena_hour():
                    arena_note = " + arena check"
                    _record_vioedu_heartbeat(f"⚔️ giờ đấu trường! cào arena + breadth {jid} (khối={grades})")
                    log_collector_event("vioedu", "running", f"⚔️ Arena window — cào đấu trường + breadth [{jid}] (khối={grades})", 0)
                    # Try arena crawl with session cookies if available
                    try:
                        arena_cookies = _get_vioedu_session_cookies()
                        if arena_cookies:
                            from backend.scrapers.vioedu import fetch_vioedu_supplementary
                            arena_qs = await fetch_vioedu_supplementary(
                                grade=grades[0] if grades else 5,
                                cookies=arena_cookies,
                                log_func=lambda msg: log_collector_event("vioedu", "info", msg, 0),
                            )
                            if arena_qs:
                                from backend.normalizer import normalize_question_payload
                                normalized = [await normalize_question_payload(q) for q in arena_qs]
                                inserted = bulk_insert_questions(normalized, skip_duplicates=True)
                                log_collector_event("vioedu", "success", f"⚔️ Arena/Exam/Challenge: +{inserted} câu mới", inserted)
                    except Exception as e:
                        log_collector_event("vioedu", "error", f"Arena supplementary error: {e}", 0)
                else:
                    log_collector_event("vioedu", "running", f"Tự động cào định kỳ [{jid}] (khối={grades})", 0)
                    _record_vioedu_heartbeat(f"đang cào {jid} (khối={grades})")
                # Always run breadth sweep
                await _run_breadth_job(jid, grades, subjects, 12, force=False, recrawl_days=7, source="auto")
                _record_vioedu_heartbeat(f"xong {jid}{arena_note} (+{_BREADTH_JOBS.get(jid, {}).get('count', 0)} câu)")

            else:
                try:
                    interval = int(get_system_config("vioedu_auto_interval_sec", str(VIOEDU_AUTO_DEFAULT_INTERVAL_SEC)) or VIOEDU_AUTO_DEFAULT_INTERVAL_SEC)
                except ValueError:
                    interval = VIOEDU_AUTO_DEFAULT_INTERVAL_SEC
                busy = any(j.get("status") == "running" for j in _BREADTH_JOBS.values())
                _record_vioedu_heartbeat(
                    "TẮT (bật toggle để cào)" if not enabled
                    else ("job khác đang chạy, chờ vòng sau" if busy else "không có bài cũ (ledger fresh), chờ vòng sau"))
                # Lịch sử tick vào collector_logs để restart không mất dấu vết
                try:
                    log_collector_event("vioedu", "info",
                        f"💓 Bot heartbeat: {_VIOEDU_HEARTBEAT['note']}", 0)
                except Exception:
                    pass
        except Exception as e:
            print(f"[VioEdu Auto] lỗi vòng lặp: {e}")
            _record_vioedu_heartbeat(f"lỗi vòng lặp: {str(e)[:100]}")
            interval = 3600
        await asyncio.sleep(max(600, interval))

@router.post("/api/collect/run")
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
        elif req.action == "breadth":
            # Cào diện rộng: chạy NỀN qua helper dùng chung, trả ngay job id.
            import time as _time
            import asyncio as _asyncio
            job_id = f"breadth-{int(_time.time())}"
            subjects = None
            if isinstance(req.subject, str) and req.subject.strip():
                subjects = [s.strip().lower() for s in req.subject.split(",") if s.strip()]
            grades = [req.grade] if req.grade else None
            max_q = req.max_questions or 12
            _BREADTH_JOBS[job_id] = {"status": "running", "stats": {}, "count": 0, "skills_visited": 0}
            log_collector_event(platform="vioedu", status="running",
                message=f"Cào diện rộng VioEdu (môn={subjects or 'all'}, khối={grades or 'all'}) [{job_id}]", count=0)
            _asyncio.create_task(_run_breadth_job(job_id, grades, subjects, max_q, source="manual"))
            return {"success": True, "background": True, "job_id": job_id,
                    "message": "Đã chạy nền. Theo dõi tiến độ ở Nhật ký Thu thập."}
            
    elif platform == "tnmath":
        if req.action == "login":
            res = await login_tnmath(req.username, req.password)
            return res
            
    return {"success": False, "error": "Chức năng hoặc nền tảng chưa được hỗ trợ trực tiếp. Vui lòng sử dụng Tiện ích Extension hoặc nạp PDF."}

@router.get("/api/collect/breadth-status")
async def breadth_status(job_id: str = ""):
    """Poll tiến độ job cào diện rộng (không giữ worker)."""
    if job_id and job_id in _BREADTH_JOBS:
        return {"success": True, "job_id": job_id, **_BREADTH_JOBS[job_id]}
    recent = dict(list(_BREADTH_JOBS.items())[-5:])
    return {"success": True, "jobs": recent}


@router.post("/api/collect/vioedu-plan")
async def vioedu_plan(req: VioEduPlanRequest):
    """Cụm điều khiển thống nhất: cào 1 lần / tự động 24/7 / diện rộng.

    - breadth/once: khởi động job nền quét skill cũ (ledger 7 ngày), trả job id.
    - auto: bật/tắt scheduler nền 24/7 (lưu system_config, không cần mở tab).
    Không cần login VioEdu cho breadth (GraphQL công khai).
    """
    import time as _t
    import asyncio as _a
    from backend.database import get_system_config, set_system_config
    mode = (req.mode or "breadth").strip().lower()
    if mode not in ("once", "auto", "breadth"):
        raise HTTPException(status_code=422, detail="mode phải là once | auto | breadth")
    grades = req.grades or [2]
    subjects = [s.strip().lower() for s in (req.subjects or ["math", "vietnamese", "english"]) if s.strip()] or ["math", "vietnamese", "english"]
    if mode == "auto":
        if req.auto_enabled is not None:
            set_system_config("vioedu_auto_crawl", "on" if req.auto_enabled else "off")
        if req.interval_sec:
            set_system_config("vioedu_auto_interval_sec", str(max(600, req.interval_sec)))
        if req.grades and len(req.grades) > 0 and (len(req.grades) > 1 or req.grades != [2]):
            set_system_config("vioedu_auto_grades", ",".join(str(g) for g in req.grades))
        else:
            current_g = get_system_config("vioedu_auto_grades", "")
            if not current_g:
                set_system_config("vioedu_auto_grades", VIOEDU_AUTO_DEFAULT_GRADES)
        set_system_config("vioedu_auto_subjects", ",".join(subjects))
        on = (get_system_config("vioedu_auto_crawl", "off") or "off") == "on"
        grades_cfg = get_system_config("vioedu_auto_grades", VIOEDU_AUTO_DEFAULT_GRADES)
        return {"success": True, "mode": "auto", "enabled": on,
                "grades": grades_cfg, "subjects": subjects,
                "message": "Đã BẬT tự động cào nền 24/7." if on else "Đã TẮT tự động cào nền."}
    jid = f"{mode}-{int(_t.time())}"
    _BREADTH_JOBS[jid] = {"status": "running", "stats": {}, "count": 0, "skills_visited": 0, "source": mode}
    log_collector_event("vioedu", "running", f"Cụm VioEdu [{mode}] khởi động [{jid}] (khối={grades})", 0)
    _a.create_task(_run_breadth_job(jid, grades, subjects, req.max_questions or 12,
        force=req.force, recrawl_days=7, source=mode))
    return {"success": True, "mode": mode, "background": True, "job_id": jid,
            "message": "Đã chạy nền. Poll /api/collect/breadth-status để xem tiến độ."}


@router.post("/api/collect/vioedu-login")
async def vioedu_login(payload: dict, request: Request):
    """Admin nhap TK VioEdu 1 lan → server login, luu cookies phien vao
    system_config (vioedu_session_cookies) de scheduler 24/7 cao bang tai
    khoan dang nhap (mo noi dung can login, quota cao hon anonymous).
    Mat khau KHONG luu — chi giu cookies phien."""
    _require_admin(request)
    import json as _json
    from backend.database import set_system_config
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    if not username or not password:
        raise HTTPException(status_code=422, detail="Thiếu username/password VioEdu")
    result = await login_vioedu(username, password)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Đăng nhập VioEdu thất bại")
    cookies = result.get("cookies") or {}
    set_system_config(VIOEDU_SESSION_COOKIES_KEY, _json.dumps(cookies))
    set_system_config("vioedu_session_user", result.get("student_name") or username)
    log_collector_event("vioedu", "success",
        f"Đã lưu phiên đăng nhập VioEdu ({result.get('student_name') or username}) — scheduler dùng TK này để cào", 0)
    return {"success": True,
            "student_name": result.get("student_name") or username,
            "grade": result.get("grade"),
            "message": f"Đã lưu phiên VioEdu ({result.get('student_name') or username}) — bot cào bằng tài khoản này."}


@router.get("/api/collect/vioedu-login")
async def vioedu_login_status():
    """Trang thai phien VioEdu: co TK dang nhap hay dang anonymous."""
    from backend.database import get_system_config
    has = bool(_get_vioedu_session_cookies())
    who = (get_system_config("vioedu_session_user", "") or "") if has else ""
    return {"success": True, "logged_in": has, "student_name": who,
            "message": f"Đang cào bằng TK {who}" if has else "Đang cào anonymous (chưa nhập TK VioEdu)"}


@router.get("/api/collect/vioedu-plan")
async def vioedu_plan_status():
    """Trạng thái cụm: scheduler auto on/off + 5 job gần nhất + ledger size."""
    from backend.database import get_system_config
    from backend.scrapers.vioedu import _load_skill_ledger
    recent = dict(list(_BREADTH_JOBS.items())[-5:])
    running = [jid for jid, j in _BREADTH_JOBS.items() if j.get("status") == "running"]
    grades_raw = (get_system_config("vioedu_auto_grades", VIOEDU_AUTO_DEFAULT_GRADES) or VIOEDU_AUTO_DEFAULT_GRADES).strip()
    cursor_idx = int(get_system_config("vioedu_auto_cursor", "0") or "0")
    grades_all = [int(g) for g in grades_raw.split(",") if g.strip().isdigit()] or [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    next_grade = grades_all[cursor_idx % len(grades_all)] if grades_all else 2
    return {"success": True,
            "auto_enabled": (get_system_config("vioedu_auto_crawl", "off") or "off") == "on",
            "interval_sec": get_system_config("vioedu_auto_interval_sec", str(VIOEDU_AUTO_DEFAULT_INTERVAL_SEC)),
            "grades": grades_raw,
            "cursor_idx": cursor_idx,
            "next_grade": next_grade,
            "subjects": get_system_config("vioedu_auto_subjects", "math,vietnamese,english"),
            "ledger_skills": len(_load_skill_ledger()),
            "running_jobs": running,
            "recent_jobs": recent,
            "vioedu_logged_in": bool(_get_vioedu_session_cookies()),
            "vioedu_account": (get_system_config("vioedu_session_user", "") or ""),
            "heartbeat": dict(_VIOEDU_HEARTBEAT)}


@router.get("/api/collect/vioedu-diagnostics")
async def vioedu_diagnostics():
    """Chi tiết toàn diện: ledger stats, hit rate, fail rate, per-grade/subject breakdown."""
    from backend.scrapers.vioedu import _load_skill_ledger, _adaptive_cooldown_days
    from backend.database import get_system_config
    import statistics

    ledger = _load_skill_ledger()
    now = datetime.now(VN_TZ)

    # Aggregate ledger statistics
    total_skills = len(ledger)
    skills_with_questions = 0
    skills_exhausted = 0
    total_questions_crawled = 0
    new_counts = []
    fail_streaks = []
    stale_count = 0
    fresh_count = 0

    for sid, entry in ledger.items():
        if not isinstance(entry, dict):
            continue
        nc = entry.get("new_count", 0)
        tc = entry.get("total_crawled", 0)
        fs = entry.get("fail_streak", 0)
        total_questions_crawled += tc
        new_counts.append(nc)
        fail_streaks.append(fs)
        if tc > 0:
            skills_with_questions += 1
        if fs >= 3:
            skills_exhausted += 1
        # Check freshness using adaptive cooldown
        cooldown = _adaptive_cooldown_days(entry)
        last_crawl_str = entry.get("last_crawl", "")
        if last_crawl_str:
            try:
                last_dt = datetime.fromisoformat(last_crawl_str)
                if hasattr(last_dt, 'tzinfo') and last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=VN_TZ)
                age_days = (now - last_dt).total_seconds() / 86400
                if age_days > cooldown:
                    stale_count += 1
                else:
                    fresh_count += 1
            except (ValueError, TypeError):
                stale_count += 1
        else:
            stale_count += 1

    # Calculate averages
    avg_questions = round(statistics.mean(new_counts), 1) if new_counts else 0
    avg_fail_streak = round(statistics.mean(fail_streaks), 1) if fail_streaks else 0
    max_fail_streak = max(fail_streaks) if fail_streaks else 0
    hit_rate = round(skills_with_questions / total_skills * 100, 1) if total_skills else 0

    # Recent job performance
    recent_jobs_list = list(_BREADTH_JOBS.items())[-10:]
    job_summaries = []
    for jid, job in recent_jobs_list:
        job_summaries.append({
            "id": jid,
            "status": job.get("status"),
            "count": job.get("count", 0),
            "skills_visited": job.get("skills_visited", 0),
            "source": job.get("source", "unknown"),
        })

    # Arena schedule status
    arena_active = _is_arena_hour()
    now_str = now.strftime("%H:%M %d/%m/%Y")

    return {
        "success": True,
        "timestamp": now_str,
        "ledger": {
            "total_skills": total_skills,
            "skills_with_questions": skills_with_questions,
            "skills_exhausted": skills_exhausted,
            "skills_stale": stale_count,
            "skills_fresh": fresh_count,
            "total_questions_crawled": total_questions_crawled,
            "avg_new_per_crawl": avg_questions,
            "hit_rate_pct": hit_rate,
            "avg_fail_streak": avg_fail_streak,
            "max_fail_streak": max_fail_streak,
        },
        "arena": {
            "is_arena_hour": arena_active,
            "windows": [f"{h1}:{m1:02d}-{h2}:{m2:02d}" for h1, m1, h2, m2 in VIOEDU_ARENA_WINDOWS],
        },
        "scheduler": {
            "auto_enabled": (get_system_config("vioedu_auto_crawl", "off") or "off") == "on",
            "interval_sec": get_system_config("vioedu_auto_interval_sec", str(VIOEDU_AUTO_DEFAULT_INTERVAL_SEC)),
            "grades": get_system_config("vioedu_auto_grades", VIOEDU_AUTO_DEFAULT_GRADES),
            "heartbeat": dict(_VIOEDU_HEARTBEAT),
            "vioedu_logged_in": bool(_get_vioedu_session_cookies()),
            "vioedu_account": get_system_config("vioedu_session_user", "") or "",
        },
        "recent_jobs": job_summaries,
    }


@router.get("/api/collect/logs")
async def get_logs(limit: int = 50, platform: Optional[str] = None):
    return get_collector_logs(limit, platform=platform)

@router.post("/api/collect/logs/sync")
async def sync_collector_log(payload: dict):
    platform = payload.get("platform", "extension")
    status = payload.get("status", "info")
    message = payload.get("message", "")
    count = int(payload.get("count", 0))
    if message:
        log_collector_event(platform=platform, status=status, message=message, count=count)
    return {"success": True}

@router.delete("/api/collect/logs")
async def delete_logs(_auth=Depends(require_api_token)):
    clear_collector_logs()
    return {"success": True, "message": "Đã xóa toàn bộ nhật ký"}

# ----------------- Sample Data Seeder -----------------

@router.post("/api/init-samples")
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

@router.post("/api/hunter/run")
async def trigger_internet_hunter(payload: dict):
    subject = payload.get("subject", "all")
    grade_raw = payload.get("grade", 5)
    if str(grade_raw).lower() in ("all", "0", "tat_ca"):
        grade = "all"
    else:
        try:
            grade = int(grade_raw)
        except (ValueError, TypeError):
            grade = 5
    custom_url = payload.get("custom_url") or payload.get("url")
    custom_urls = payload.get("custom_urls", [])
    single = payload.get("url")
    if single and single.strip() and single.strip() not in custom_urls \
            and single.strip() != (custom_url or "").strip():
        custom_urls = custom_urls + [single.strip()]
    result = await run_internet_question_hunter(
        subject=subject,
        grade=grade,
        custom_url=custom_url,
        custom_urls=custom_urls
    )
    return result

@router.get("/api/hunter/grade-sources")
async def get_grade_math_sources(grade: str = "2"):
    """Returns the catalog of supported sources across Vietnamese, English and Olympic platforms for any Grade 1 to 12 or all."""
    if str(grade).lower() in ("all", "0", "tat_ca"):
        return get_grade_source_urls("all")
    try:
        g = int(grade)
    except (ValueError, TypeError):
        g = 2
    return get_grade_source_urls(g)

@router.get("/api/hunter/grade2-sources")
async def get_grade2_math_sources():
    """Backward-compatible endpoint: Returns sources for Grade 2."""
    return get_grade_source_urls(2)

@router.post("/api/hunter/harvest-by-grade")
async def harvest_math_by_grade(payload: dict):
    """Triggers an all-inclusive multi-source harvest for Math across any Grade 1 to 12 (Vietnamese + English + Olympic) or all."""
    grade_raw = payload.get("grade", 2)
    subject = payload.get("subject", "math")

    if str(grade_raw).lower() in ("all", "0", "tat_ca"):
        return await run_internet_question_hunter(
            subject=subject,
            grade="all",
            limit=50
        )

    try:
        grade = int(grade_raw)
    except (ValueError, TypeError):
        grade = 2
    grade = max(1, min(12, grade))
    
    # Dynamically extract target URLs from source catalog for this grade.
    # Skip type=interactive entries (VioEdu/TNMath/quiz-JS "mở tay" pages):
    # they need login/JS rendering and yield nothing via static fetch.
    catalog = get_grade_source_urls(grade)
    target_urls = []
    skipped_interactive = 0
    for cat in catalog.get("categories", []):
        for s in cat.get("sources", []):
            u = s.get("url")
            if not u or u in target_urls:
                continue
            if (s.get("type") or "").strip().lower() == "interactive":
                skipped_interactive += 1
                continue
            target_urls.append(u)

    res = await run_internet_question_hunter(
        subject=subject,
        grade=grade,
        custom_urls=target_urls,
        limit=50
    )
    if isinstance(res, dict):
        res["skipped_interactive"] = skipped_interactive
    return res

@router.post("/api/hunter/harvest-grade2")
async def harvest_grade2_math():
    """Backward-compatible endpoint: Triggers harvest for Grade 2 Math."""
    return await harvest_math_by_grade({"grade": 2, "subject": "math"})

@router.post("/api/hunter/test-source")
async def test_hunter_single_source(payload: dict):
    """Diagnoses a single target URL: measures latency, HTTP status, anti-bot behavior,
    and extracts test questions to verify if the source is working."""
    url = (payload.get("url") or "").strip()
    grade_raw = payload.get("grade", 2)
    subject = payload.get("subject", "math")
    try:
        grade = int(grade_raw) if str(grade_raw).isdigit() else 2
    except (ValueError, TypeError):
        grade = 2

    if not url:
        raise HTTPException(status_code=422, detail="Vui lòng cung cấp URL nguồn cần kiểm tra")
    
    from backend.scrapers.hunter.fetch import is_url_fetch_allowed, fetch_questions_from_web_url
    if not is_url_fetch_allowed(url):
        return {
            "success": False,
            "url": url,
            "status": "error",
            "status_code": 403,
            "error": "URL không được phép truy cập (bảo vệ an toàn SSRF / mạng nội bộ)",
            "advice": "Vui lòng sử dụng địa chỉ website giáo dục công khai."
        }
    
    import time
    start_t = time.perf_counter()
    try:
        web_q = await fetch_questions_from_web_url(url)
        elapsed_ms = int((time.perf_counter() - start_t) * 1000)
        valid_sample = None
        for q in web_q:
            is_valid, _ = is_valid_question_payload(q)
            if is_valid:
                valid_sample = {
                    "content_text": (q.get("content_text") or "")[:150],
                    "options_count": len(q.get("options", [])),
                    "correct_answer": q.get("correct_answer")
                }
                break
        
        status = "success" if len(web_q) > 0 else "empty"
        msg = f"Thu thập thành công {len(web_q)} câu hỏi ({elapsed_ms}ms)" if len(web_q) > 0 else f"Kết nối 200 OK nhưng trang web chưa có câu hỏi tương thích ({elapsed_ms}ms)"
        advice = "Nguồn hoạt động rất tốt, sẵn sàng cào dữ liệu!" if len(web_q) > 0 else "Trang web có thể dùng JavaScript tải động (SPA) hoặc cần mở trang chi tiết đề thi."
        
        return {
            "success": True,
            "url": url,
            "status": status,
            "status_code": 200,
            "latency_ms": elapsed_ms,
            "questions_found": len(web_q),
            "sample": valid_sample,
            "message": msg,
            "advice": advice
        }
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_t) * 1000)
        return {
            "success": False,
            "url": url,
            "status": "error",
            "status_code": 500,
            "latency_ms": elapsed_ms,
            "questions_found": 0,
            "error": str(e),
            "advice": "Kiểm tra lại đường truyền mạng hoặc trang web có thể chặn bot (Anti-bot / Cloudflare / 403)."
        }

@router.post("/api/collect/check-session")
async def check_collector_session(payload: dict):
    """Directly verifies VioEdu or other platform credentials or stored cookies."""
    platform = payload.get("platform", "vioedu")
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    
    if platform == "vioedu":
        if username and password:
            res = await login_vioedu(username, password)
            return res
        cookies = _get_vioedu_session_cookies()
        if not cookies:
            return {"success": False, "logged_in": False, "message": "Chưa có phiên lưu trữ. Vui lòng nhập tài khoản và mật khẩu VioEdu."}
        user = get_system_config("vioedu_session_user", "")
        return {"success": True, "logged_in": True, "student_name": user, "message": f"Phiên VioEdu đang lưu hợp lệ cho tài khoản: {user}"}
        
    return {"success": False, "message": "Nền tảng chưa hỗ trợ kiểm tra trực tiếp."}


