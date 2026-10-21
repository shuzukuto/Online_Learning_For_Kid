"""Common dependencies and auth guards for EduQuest Pro APIRouters."""
from __future__ import annotations
import os
from fastapi import Request, HTTPException
from backend.database import get_connection

API_TOKEN = os.environ.get("API_TOKEN", "")

def _auth_conn():
    return get_connection()

def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return ""

def _require_session(request: Request):
    from backend import auth as A
    conn = _auth_conn()
    try:
        user = A.get_session_user(conn, _bearer_token(request))
    finally:
        conn.close()
    if user is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên đã hết hạn.")
    return {"username": user["username"], "role": user["role"], "status": user["status"]}

def _require_admin(request: Request):
    me = _require_session(request)
    if me["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được thực hiện.")
    return me

def require_api_token(request: Request):
    """Enforces credential on destructive/admin endpoints."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from backend import auth as A
            conn = get_connection()
            try:
                user = A.get_session_user(conn, auth[7:].strip())
            finally:
                conn.close()
            if user is not None and user["role"] == "admin" and user["status"] == "active":
                return None
        except Exception:
            pass
    if not API_TOKEN:
        return None
    if request.headers.get("X-API-Token", "") != API_TOKEN:
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai credential (đăng nhập admin hoặc header X-API-Token)")
    return None
