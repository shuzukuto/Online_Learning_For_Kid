"""EduQuest Pro — account auth (login/register/change-password + admin approval).

Passwords are NEVER stored in plaintext: PBKDF2-HMAC-SHA256 with a per-user
salt, format ``$pbkdf2$sha256$<iter>$<salt_hex>$<hash_hex>``.
New registrations are PENDING until the admin approves them; only active
accounts can log in. Sessions are opaque Bearer tokens (7-day expiry).
Seed admin username is ``luanpt``; its initial password comes from the
ADMIN_SEED_PASSWORD env var (default "1122" per operator request — change it
after first login via change-password).
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

VN_TZ = timezone(timedelta(hours=7))

ADMIN_USERNAME = "luanpt"
ADMIN_SEED_PASSWORD = os.environ.get("ADMIN_SEED_PASSWORD", "1122")

_PBKDF2_ITERATIONS = 200_000
# User 2026-10-13: phien 7 ngay het → ngan hang bao 0 cau du DB con nguyen.
# Tang len 30 ngay de giao vien/phu huynh do phai dang nhap lai.
_SESSION_TTL_DAYS = 30


def _now_iso() -> str:
    return datetime.now(VN_TZ).isoformat()


def hash_password(password: str) -> str:
    """Hash a plaintext password with PBKDF2 (never store plaintext)."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"$pbkdf2$sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        if not stored or not stored.startswith("$pbkdf2$"):
            return False
        _, _, algo, iter_s, salt_hex, hash_hex = stored.split("$")
        if algo != "sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iter_s))
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def init_auth_tables(conn: sqlite3.Connection) -> None:
    """Creates users/sessions tables and seeds the admin account (idempotent)."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT,
        approved_by TEXT,
        approved_at TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        created_at TEXT,
        expires_at TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions (username);")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reset_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT,
        resolved_by TEXT,
        resolved_at TEXT
    );
    """)
    row = cur.execute("SELECT username FROM users WHERE username = ?",
                      (ADMIN_USERNAME,)).fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, status, created_at, approved_by, approved_at)"
            " VALUES (?, ?, 'admin', 'active', ?, 'system', ?)",
            (ADMIN_USERNAME, hash_password(ADMIN_SEED_PASSWORD), _now_iso(), _now_iso()),
        )
    conn.commit()


def get_user(conn: sqlite3.Connection, username: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE username = ?",
                        (username or "",)).fetchone()


def _valid_username(username: str) -> bool:
    u = (username or "").strip()
    return 3 <= len(u) <= 32 and all(c.isalnum() or c in "_-." for c in u)


def register_user(conn: sqlite3.Connection, username: str,
                  password: str) -> Tuple[bool, str]:
    """Registers a PENDING account (username + password only)."""
    u = (username or "").strip()
    if not _valid_username(u):
        return False, "Tên đăng nhập 3–32 ký tự (chữ, số, _, -, .)."
    if not password or len(password) < 4:
        return False, "Mật khẩu tối thiểu 4 ký tự."
    if get_user(conn, u) is not None:
        return False, "Tên đăng nhập đã tồn tại."
    conn.execute(
        "INSERT INTO users (username, password_hash, role, status, created_at)"
        " VALUES (?, ?, 'user', 'pending', ?)",
        (u, hash_password(password), _now_iso()),
    )
    conn.commit()
    return True, "Đăng ký thành công! Tài khoản đang chờ admin phê duyệt."


def login_user(conn: sqlite3.Connection, username: str,
               password: str) -> Tuple[Optional[str], str]:
    """Returns (token, message). Only ACTIVE accounts can log in."""
    u = get_user(conn, (username or "").strip())
    if u is None or not verify_password(password or "", u["password_hash"] or ""):
        return None, "Sai tên đăng nhập hoặc mật khẩu."
    if u["status"] == "pending":
        return None, "Tài khoản đang chờ admin phê duyệt."
    if u["status"] != "active":
        return None, "Tài khoản đã bị khóa."
    token = secrets.token_urlsafe(32)
    exp = (datetime.now(VN_TZ) + timedelta(days=_SESSION_TTL_DAYS)).isoformat()
    conn.execute("INSERT INTO sessions (token, username, created_at, expires_at)"
                 " VALUES (?, ?, ?, ?)",
                 (token, u["username"], _now_iso(), exp))
    conn.commit()
    return token, "Đăng nhập thành công."


def get_session_user(conn: sqlite3.Connection, token: str) -> Optional[sqlite3.Row]:
    """Returns the user row for a valid non-expired session token."""
    if not token:
        return None
    row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if row is None:
        return None
    try:
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(VN_TZ):
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None
    except Exception:
        return None
    return get_user(conn, row["username"])


def logout_user(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token or "",))
    conn.commit()


def change_password(conn: sqlite3.Connection, username: str, old_password: str,
                    new_password: str) -> Tuple[bool, str]:
    u = get_user(conn, username or "")
    if u is None:
        return False, "Tài khoản không tồn tại."
    if not verify_password(old_password or "", u["password_hash"] or ""):
        return False, "Mật khẩu cũ không đúng."
    if not new_password or len(new_password) < 4:
        return False, "Mật khẩu mới tối thiểu 4 ký tự."
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                 (hash_password(new_password), u["username"]))
    conn.execute("DELETE FROM sessions WHERE username = ?", (u["username"],))
    conn.commit()
    return True, "Đổi mật khẩu thành công. Vui lòng đăng nhập lại."


def set_user_status(conn: sqlite3.Connection, username: str, status: str,
                    by: str) -> Tuple[bool, str]:
    """Admin approves/rejects/bans. Only admins; admin cannot ban itself."""
    actor = get_user(conn, by or "")
    if actor is None or actor["role"] != "admin" or actor["status"] != "active":
        return False, "Chỉ tài khoản admin đang hoạt động mới được duyệt."
    if status not in ("active", "pending", "banned"):
        return False, "Trạng thái không hợp lệ."
    target = get_user(conn, username or "")
    if target is None:
        return False, "Tài khoản không tồn tại."
    if target["username"] == ADMIN_USERNAME and status != "active":
        return False, "Không thể khóa tài khoản admin gốc."
    conn.execute("UPDATE users SET status = ?, approved_by = ?, approved_at = ?"
                 " WHERE username = ?",
                 (status, actor["username"], _now_iso(), target["username"]))
    if status != "active":
        conn.execute("DELETE FROM sessions WHERE username = ?", (target["username"],))
    conn.commit()
    labels = {"active": "đã phê duyệt/kích hoạt", "pending": "chuyển về chờ duyệt",
              "banned": "đã khóa"}
    return True, f"Tài khoản {target['username']} {labels[status]}."


def list_users(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT username, role, status, created_at, approved_by, approved_at"
        " FROM users ORDER BY created_at ASC").fetchall()
    return [dict(r) for r in rows]


def set_user_role(conn: sqlite3.Connection, username: str, role: str,
                  by: str) -> Tuple[bool, str]:
    """Admin changes another account's role. Cannot change own role or the
    seed admin's role (safety against self-demotion lockout)."""
    actor = get_user(conn, by or "")
    if actor is None or actor["role"] != "admin" or actor["status"] != "active":
        return False, "Chỉ tài khoản admin đang hoạt động mới được phân quyền."
    if role not in ("admin", "user"):
        return False, "Quyền không hợp lệ (admin/user)."
    target = get_user(conn, username or "")
    if target is None:
        return False, "Tài khoản không tồn tại."
    if target["username"] == (by or ""):
        return False, "Không thể tự đổi quyền của chính mình."
    if target["username"] == ADMIN_USERNAME:
        return False, "Không thể đổi quyền tài khoản admin gốc."
    conn.execute("UPDATE users SET role = ? WHERE username = ?",
                 (role, target["username"]))
    if role != "admin":
        # Demoted sessions keep working as user; admin sessions must re-login
        # only when the account is banned (handled by set_user_status).
        pass
    conn.commit()
    return True, f"Tài khoản {target['username']} giờ là {role}."


def delete_user(conn: sqlite3.Connection, username: str,
                by: str) -> Tuple[bool, str]:
    """Admin deletes an account (sessions purged). Cannot delete self or the
    seed admin."""
    actor = get_user(conn, by or "")
    if actor is None or actor["role"] != "admin" or actor["status"] != "active":
        return False, "Chỉ tài khoản admin đang hoạt động mới được xóa tài khoản."
    target = get_user(conn, username or "")
    if target is None:
        return False, "Tài khoản không tồn tại."
    if target["username"] == (by or ""):
        return False, "Không thể tự xóa chính mình."
    if target["username"] == ADMIN_USERNAME:
        return False, "Không thể xóa tài khoản admin gốc."
    conn.execute("DELETE FROM sessions WHERE username = ?", (target["username"],))
    conn.execute("DELETE FROM users WHERE username = ?", (target["username"],))
    conn.commit()
    return True, f"Đã xóa tài khoản {target['username']}."


def admin_reset_password(conn: sqlite3.Connection, username: str,
                         by: str) -> Tuple[bool, str]:
    """Admin resets a user's password to a random temporary one (forgot-password
    flow without mail infra). Sessions purged; user changes it after login."""
    actor = get_user(conn, by or "")
    if actor is None or actor["role"] != "admin" or actor["status"] != "active":
        return False, "Chỉ tài khoản admin đang hoạt động mới được đặt lại mật khẩu."
    target = get_user(conn, username or "")
    if target is None:
        return False, "Tài khoản không tồn tại."
    temp = secrets.token_urlsafe(6)[:8]
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                 (hash_password(temp), target["username"]))
    conn.execute("DELETE FROM sessions WHERE username = ?", (target["username"],))
    conn.commit()
    return True, f"Mật khẩu tạm của {target['username']}: {temp} (đăng nhập rồi đổi ngay)."


def request_password_reset(conn: sqlite3.Connection, username: str) -> Tuple[bool, str]:
    """Public: user quên mật khẩu gửi yêu cầu (không cần login).
    Trả lời chung chung để không lộ tài khoản nào tồn tại."""
    u = get_user(conn, username or "")
    if u is not None:
        conn.execute("INSERT INTO reset_requests (username, status, created_at)"
                     " VALUES (?, 'pending', ?)", (u["username"], _now_iso()))
        conn.commit()
    return True, "Đã gửi yêu cầu. Admin duyệt sẽ cấp mật khẩu tạm cho bạn."


def list_reset_requests(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, username, status, created_at, resolved_by, resolved_at"
        " FROM reset_requests ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def resolve_reset_request(conn: sqlite3.Connection, req_id: int, by: str) -> Tuple[bool, str]:
    """Admin đánh dấu yêu cầu đã xử lý (sau khi cấp mật khẩu tạm)."""
    actor = get_user(conn, by or "")
    if actor is None or actor["role"] != "admin" or actor["status"] != "active":
        return False, "Chỉ admin mới được xử lý yêu cầu."
    row = conn.execute("SELECT * FROM reset_requests WHERE id = ?",
                       (req_id,)).fetchone()
    if row is None:
        return False, "Yêu cầu không tồn tại."
    conn.execute("UPDATE reset_requests SET status='done', resolved_by=?, resolved_at=?"
                 " WHERE id = ?", (actor["username"], _now_iso(), req_id))
    conn.commit()
    return True, f"Đã xử lý yêu cầu #{req_id}."
