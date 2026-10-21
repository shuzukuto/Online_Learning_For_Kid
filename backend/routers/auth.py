"""Auth & User Administration APIRouter."""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from backend.dependencies import (
    _auth_conn,
    _bearer_token,
    _require_admin,
    _require_session,
)
from backend.database import log_collector_event

router = APIRouter(tags=["Auth & Administration"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@router.post("/api/auth/register")
async def auth_register(payload: dict):
    from backend import auth as A
    conn = _auth_conn()
    try:
        ok, msg = A.register_user(conn, payload.get("username", ""), payload.get("password", ""))
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/api/auth/login")
async def auth_login(payload: dict):
    from backend import auth as A
    conn = _auth_conn()
    try:
        token, msg = A.login_user(conn, payload.get("username", ""), payload.get("password", ""))
        me = A.get_session_user(conn, token) if token else None
    finally:
        conn.close()
    if not token or me is None:
        raise HTTPException(status_code=401, detail=msg)
    return {"success": True, "message": msg, "token": token,
            "username": me["username"], "role": me["role"]}


@router.post("/api/auth/logout")
async def auth_logout(request: Request):
    from backend import auth as A
    conn = _auth_conn()
    try:
        A.logout_user(conn, _bearer_token(request))
    finally:
        conn.close()
    return {"success": True, "message": "Đã đăng xuất."}


@router.get("/api/auth/me")
async def auth_me(request: Request):
    return {"success": True, "user": _require_session(request)}


@router.post("/api/auth/change-password")
async def auth_change_password(request: Request, payload: dict):
    from backend import auth as A
    me = _require_session(request)
    conn = _auth_conn()
    try:
        ok, msg = A.change_password(conn, me["username"],
                                    payload.get("old_password", ""),
                                    payload.get("new_password", ""))
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.get("/api/auth/users")
async def auth_list_users(request: Request):
    from backend import auth as A
    _require_admin(request)
    conn = _auth_conn()
    try:
        users = A.list_users(conn)
    finally:
        conn.close()
    return {"success": True, "users": users}


@router.post("/api/auth/approve")
async def auth_approve_user(request: Request, payload: dict):
    from backend import auth as A
    me = _require_admin(request)
    conn = _auth_conn()
    try:
        ok, msg = A.set_user_status(conn, payload.get("username", ""),
                                    payload.get("status", "active"), by=me["username"])
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/api/auth/role")
async def auth_set_role(request: Request, payload: dict):
    """Admin grants/revokes admin role on another account."""
    from backend import auth as A
    me = _require_admin(request)
    conn = _auth_conn()
    try:
        ok, msg = A.set_user_role(conn, payload.get("username", ""),
                                  payload.get("role", "user"), by=me["username"])
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/api/auth/delete")
async def auth_delete_user(request: Request, payload: dict):
    """Admin deletes an account (sessions purged)."""
    from backend import auth as A
    me = _require_admin(request)
    conn = _auth_conn()
    try:
        ok, msg = A.delete_user(conn, payload.get("username", ""), by=me["username"])
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/api/auth/forgot")
async def auth_forgot_password(payload: dict):
    """Public (qua gate): user quên mật khẩu gửi yêu cầu, admin cấp pass tạm."""
    from backend import auth as A
    conn = _auth_conn()
    try:
        ok, msg = A.request_password_reset(conn, (payload.get("username", "")))
    finally:
        conn.close()
    return {"success": True, "message": msg}


@router.post("/api/auth/reset")
async def auth_reset_password(request: Request, payload: dict):
    """Admin cấp mật khẩu tạm cho user (1 click). Trả pass tạm để báo user."""
    from backend import auth as A
    me = _require_admin(request)
    conn = _auth_conn()
    try:
        ok, msg = A.admin_reset_password(conn, payload.get("username", ""), by=me["username"])
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.get("/api/auth/reset-requests")
async def auth_list_reset_requests(request: Request):
    """Admin xem hàng chờ quên mật khẩu (user gửi qua /forgot public)."""
    from backend import auth as A
    _require_admin(request)
    conn = _auth_conn()
    try:
        reqs = A.list_reset_requests(conn)
    finally:
        conn.close()
    pending = [r for r in reqs if (r.get("status") or "") == "pending"]
    return {"success": True, "requests": reqs, "pending": pending}


@router.post("/api/auth/reset-requests/resolve")
async def auth_resolve_reset_request(request: Request, payload: dict):
    """Admin đánh dấu yêu cầu quên MK đã xử lý (sau khi cấp pass tạm)."""
    from backend import auth as A
    me = _require_admin(request)
    conn = _auth_conn()
    try:
        try:
            req_id = int(payload.get("request_id", 0) or 0)
        except (TypeError, ValueError):
            req_id = 0
        ok, msg = A.resolve_reset_request(conn, req_id, by=me["username"])
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@router.post("/api/contribute/upload")
async def upload_contribute_file(
    request: Request,
    file: UploadFile = File(...),
    contributor_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    """Allows users/teachers to contribute exam files (PDF, Word, Image, Text) to the training pool."""
    account_name = ""
    try:
        account_name = _require_session(request)["username"]
    except HTTPException:
        account_name = ""
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

    clean_name = unicodedata.normalize('NFKD', base_name).encode('ASCII', 'ignore').decode('utf-8')
    clean_name = re.sub(r'[^\w\-]', '_', clean_name).strip('_').lower()
    if not clean_name:
        clean_name = "de_thi"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    who = re.sub(r"[^\w\-.]", "_", (account_name or "").strip().lower()).strip("_")
    if not who and contributor_name:
        who = re.sub(r"[^\w\-.]", "_", unicodedata.normalize(
            'NFKD', contributor_name.strip()).encode('ASCII', 'ignore').decode('utf-8')).strip("_").lower()
    if not who:
        who = "an_danh"
    target_filename = f"{clean_name}_{who}_{ts}_contribute{ext}"

    training_dir = os.path.join(BASE_DIR, "data", "training")
    os.makedirs(training_dir, exist_ok=True)
    saved_path = os.path.join(training_dir, target_filename)

    with open(saved_path, "wb") as f:
        f.write(contents)

    log_msg = f"Đã nhận tệp đóng góp: {target_filename}"
    if account_name:
        log_msg += f" (tài khoản: {account_name})"
    elif contributor_name:
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
