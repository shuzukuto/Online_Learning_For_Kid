"""Database Diagnostics, Backup & Restore, Stats, and App Version APIRouter."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends

from backend.dependencies import require_api_token
from backend.version import APP_VERSION, APP_VERSION_NUMBER, CACHE_BUSTER, EXT_VERSION
from backend.database import (
    DB_PATH,
    init_db,
    invalidate_stats_cache,
    get_stats,
    get_stats_count,
    run_database_diagnostics,
    fix_database_issues,
    log_collector_event,
)

VN_TZ = timezone(timedelta(hours=7))
logger = logging.getLogger("eduquest.database")

router = APIRouter(tags=["Database & System Stats"])

DB_BACKUP_KEEP_DAILY = int(os.environ.get("DB_BACKUP_KEEP", "7"))
DB_BACKUP_INTERVAL_SEC = 24 * 60 * 60  # 24 hours


def _get_db_backup_dir() -> str:
    d = os.path.join(os.path.dirname(DB_PATH), "backup")
    os.makedirs(d, exist_ok=True)
    return d


def _do_db_backup(tag: str = "auto") -> Optional[str]:
    """Copies questions.db via sqlite3 online backup API. Returns filename or None."""
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


# ----------------- Version (single source of truth) -----------------

@router.get("/api/version")
async def get_app_version():
    """Returns canonical app/extension versions + cache buster (from backend/version.py)."""
    return {
        "app_version": APP_VERSION,
        "app_version_number": APP_VERSION_NUMBER,
        "cache_buster": CACHE_BUSTER,
        "ext_version": EXT_VERSION,
    }


# ----------------- Question Bank Endpoints -----------------

@router.get("/api/stats")
async def get_dashboard_stats():
    return get_stats()


@router.api_route("/api/stats/count", methods=["GET", "HEAD"])
async def get_question_count():
    """Lightweight endpoint for heartbeat polling — single COUNT query, no cache needed."""
    return {"total_questions": get_stats_count()}


@router.get("/api/database/diagnostics")
async def get_db_diagnostics():
    """Runs a complete diagnostic health check on SQLite database."""
    return run_database_diagnostics()


@router.get("/api/database/backups")
async def list_db_backups(_auth=Depends(require_api_token)):
    """Lists SQLite backup snapshots in data/backup (newest first)."""
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


@router.post("/api/database/backup")
async def create_db_backup_now(_auth=Depends(require_api_token)):
    """Creates an immediate manual SQLite backup snapshot."""
    fname = await asyncio.to_thread(_do_db_backup, "manual")
    if not fname:
        raise HTTPException(status_code=500, detail="Sao lưu CSDL thất bại")
    return {"success": True, "filename": fname, "message": f"Đã sao lưu CSDL: {fname}"}


@router.post("/api/database/restore")
async def restore_db_backup(payload: dict, _auth=Depends(require_api_token)):
    """Restores questions.db from a backup snapshot (auto pre-restore snapshot first)."""
    filename = str((payload or {}).get("filename", "")).strip()
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Tên file backup không hợp lệ")
    if not filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file .db")
    src = os.path.join(_get_db_backup_dir(), filename)
    if not os.path.isfile(src):
        raise HTTPException(status_code=404, detail="Không tìm thấy file backup")
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


@router.post("/api/database/diagnostics/fix")
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
