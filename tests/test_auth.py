"""RED-phase: account auth (login/register/change-password, admin approval).

Requirements (user, 2026-10-11):
1. Register takes username + password only; new account is PENDING until
   admin approves — login before approval must fail.
2. Admin seed: username 'luanpt' with full rights, always active.
3. Passwords stored as PBKDF2 hash (never plaintext).
4. Session token model: login returns token, logout invalidates it.
5. change-password requires old password + valid session.
6. Only admin can list/approve/reject users.
"""
from __future__ import annotations

import os
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(os.path.join(PROJECT_ROOT, path), encoding="utf-8") as f:
        return f.read()


def test_auth_module_exists_with_pbkdf2():
    src = _read("backend/auth.py")
    assert "pbkdf2_hmac" in src, "passwords must use PBKDF2"
    assert "plaintext" not in src.lower() or "never" in src.lower()


def test_schema_has_users_table():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    import sqlite3
    from backend import auth as A
    conn = sqlite3.connect(":memory:")
    A.init_auth_tables(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "users" in tables and "sessions" in tables
    conn.close()


def test_auth_flow_register_pending_approve_login():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend import auth as A

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    A.init_auth_tables(conn)

    # seed admin exists and is active admin
    admin = A.get_user(conn, "luanpt")
    assert admin is not None and admin["role"] == "admin" and admin["status"] == "active"

    # register pending
    ok, msg = A.register_user(conn, "hs_moi", "secret1")
    assert ok, msg
    u = A.get_user(conn, "hs_moi")
    assert u["status"] == "pending"

    # login before approval fails
    tok, _ = A.login_user(conn, "hs_moi", "secret1")
    assert tok is None

    # wrong password fails
    tok, _ = A.login_user(conn, "luanpt", "sai-pass")
    assert tok is None

    # admin approves -> login works -> session valid
    assert A.set_user_status(conn, "hs_moi", "active", by="luanpt")[0]
    tok, _ = A.login_user(conn, "hs_moi", "secret1")
    assert tok
    assert A.get_session_user(conn, tok)["username"] == "hs_moi"

    # change password needs old password
    assert not A.change_password(conn, "hs_moi", "sai-cu", "moi123")[0]
    assert A.change_password(conn, "hs_moi", "secret1", "moi123")[0]
    tok2, _ = A.login_user(conn, "hs_moi", "moi123")
    assert tok2

    # logout invalidates
    A.logout_user(conn, tok2)
    assert A.get_session_user(conn, tok2) is None

    # non-admin cannot approve
    assert not A.set_user_status(conn, "hs_moi", "banned", by="hs_moi")[0]
    conn.close()


def test_password_not_plaintext():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend import auth as A
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    A.init_auth_tables(conn)
    A.register_user(conn, "kiem_tra", "matkhau123")
    row = conn.execute("SELECT password_hash FROM users WHERE username='kiem_tra'").fetchone()
    assert "matkhau123" not in (row["password_hash"] or "")
    assert "$pbkdf2$" in (row["password_hash"] or "")
    conn.close()


def test_app_has_auth_endpoints():
    src = _read("backend/app.py")
    for ep in ["/api/auth/register", "/api/auth/login", "/api/auth/logout",
               "/api/auth/change-password", "/api/auth/users", "/api/auth/approve",
               "/api/auth/forgot", "/api/auth/reset"]:
        assert ep in src, f"missing endpoint {ep}"


def test_password_reset_flow_admin_only():
    # Quên mật khẩu (không có hạ tầng gửi mail): user gửi yêu cầu public,
    # admin cấp mật khẩu tạm 1 click; user đăng nhập rồi đổi ngay.
    import re
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend import auth as A
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    A.init_auth_tables(conn)
    A.register_user(conn, "quen_mk", "matkhau-cu")
    A.set_user_status(conn, "quen_mk", "active", by="luanpt")
    A.register_user(conn, "ke_la", "pass1234")
    A.set_user_status(conn, "ke_la", "active", by="luanpt")
    # user thường không reset được cho người khác
    ok, _ = A.admin_reset_password(conn, "quen_mk", by="ke_la")
    assert not ok
    # admin reset → trả mật khẩu tạm, pass cũ chết, pass tạm sống
    ok, msg = A.admin_reset_password(conn, "quen_mk", by="luanpt")
    assert ok, msg
    m = re.search(r": (\S+) \(", msg)
    assert m, f"khong tim thay mat khau tam trong: {msg}"
    temp = m.group(1)
    tok, _ = A.login_user(conn, "quen_mk", "matkhau-cu")
    assert tok is None, "mat khau cu van song sau reset"
    tok, _ = A.login_user(conn, "quen_mk", temp)
    assert tok, "mat khau tam khong dang nhap duoc"
    # user không tồn tại → báo rõ, không crash
    ok, _ = A.admin_reset_password(conn, "khong_co_ai", by="luanpt")
    assert not ok
    conn.close()


def test_contribute_filename_embeds_account():
    src = _read("backend/app.py")
    assert "account_name" in src
    assert "_contribute" in src
    # filename pattern includes the account segment before timestamp
    assert "{who}_{ts}_contribute" in src or "{who}_" in src


def test_ui_wires_auth_modal_and_admin_panel():
    html = _read("frontend/index.html")
    assert "js/auth.js" in html
    assert 'id="modal-auth"' in html
    assert 'id="auth-user-badge"' in html
    assert 'id="admin-users-panel"' in html
    assert "EduAuth.openAuthModal" in html


def test_destructive_gate_accepts_admin_session():
    """Destructive/admin gate (require_api_token) must accept a valid admin
    Bearer session as credential — without breaking pass-through when
    API_TOKEN is unset (dashboard + extension keep working)."""
    import re
    src = _read("backend/app.py")
    m = re.search(r"def require_api_token\(request: Request\):(.*?)(?=\n(?:def |@app\.|class )|\Z)",
                  src, re.S)
    assert m, "require_api_token missing"
    body = m.group(1)
    assert "session" in body.lower() or "Bearer" in body, \
        "destructive gate must consult the session layer (admin Bearer token)"


AUTH_UI_HARNESS = r"""
const fs = require('fs');
const els = {};
function mkEl(id){ return { id, style:{display:''}, textContent:'', title:'', value:'', innerHTML:'' }; }
global.document = { getElementById: (id) => els[id] || null, addEventListener: () => {} };
['auth-user-badge','btn-open-auth-modal','btn-open-admin-users','admin-users-panel'].forEach(id => els[id] = mkEl(id));
const store = {};
global.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k,v) => { store[k]=String(v); },
  removeItem: (k) => { delete store[k]; },
};
global.window = global;
global.fetch = async () => ({ ok:false, status:401, json: async () => ({detail:'x'}) });
eval(fs.readFileSync(process.argv[2],'utf8'));
const api = ['AuthStore','authHeaders','apiFetch','requireLogin','showLoginWall','hideLoginWall','openAdminView','setRole','deleteUser','openAuthModal','closeAuthModal','doLogin','doRegister','doLogout','doChangePassword','doForgotPassword','adminResetPassword','loadAdminUsers','approve','refreshBadge'];
const missing = api.filter(k => typeof EduAuth[k] === 'undefined');
if (missing.length) { console.log('MISSING: '+missing.join(',')); process.exit(1); }
EduAuth.AuthStore.save('tok123',{username:'luanpt',role:'admin'});
if (EduAuth.AuthStore.token()!=='tok123') { console.log('TOKEN-FAIL'); process.exit(1); }
if (EduAuth.AuthStore.user().username!=='luanpt') { console.log('USER-FAIL'); process.exit(1); }
if (EduAuth.authHeaders().Authorization!=='Bearer tok123') { console.log('HEADER-FAIL'); process.exit(1); }
EduAuth.AuthStore.clear();
EduAuth.refreshBadge().then(()=>{
  if (els['auth-user-badge'].style.display!=='none') { console.log('BADGE-FAIL'); process.exit(1); }
  console.log('AUTH-UI-OK');
});
"""


def test_auth_js_wiring_live_via_node():
    import subprocess
    probe = os.path.join(PROJECT_ROOT, "tests", "_auth_probe_tmp.js")
    with open(probe, "w", encoding="utf-8") as f:
        f.write(AUTH_UI_HARNESS)
    try:
        p = subprocess.run(
            ["node", probe, os.path.join(PROJECT_ROOT, "frontend", "js", "auth.js")],
            capture_output=True, text=True, timeout=30,
        )
    finally:
        if os.path.exists(probe):
            os.remove(probe)
    assert p.returncode == 0, f"node auth harness failed: {p.stderr[:300]}"
    assert "AUTH-UI-OK" in p.stdout, f"unexpected harness output: {p.stdout[:300]}"


def test_auth_js_never_doubles_api_prefix():
    # E2E 2026-10-12: login/register failed via browser with
    # "Method Not Allowed" because auth.js built /api/api/auth/...
    # (API_BASE already ends with /api, paths start with /api/).
    # Runtime check: evaluate the real apiBase() from auth.js in node.
    import re
    import subprocess
    src = _read("frontend/js/auth.js")
    m = re.search(r"function apiBase\(\) \{(.*?)\n  \}", src, re.S)
    assert m, "apiBase() missing from auth.js"
    js = ("var API_BASE='https://demo.ngrok-free.dev/api';\n"
          "function apiBase(){" + m.group(1) + "\n}\n"
          "var out=[apiBase(),apiBase()+\"/api/auth/me\",apiBase()+\"/api/auth/login\"];\n"
          "if(out.some(function(u){return u.indexOf('/api/api/')>=0;})){console.log('DOUBLE:'+JSON.stringify(out));process.exit(1);}\n"
          "console.log('URL-OK:'+JSON.stringify(out));")
    probe = os.path.join(PROJECT_ROOT, "tests", "_apibase_probe_tmp.js")
    with open(probe, "w", encoding="utf-8") as f:
        f.write(js)
    try:
        p = subprocess.run(["node", probe], capture_output=True, text=True, timeout=30)
    finally:
        if os.path.exists(probe):
            os.remove(probe)
    assert p.returncode == 0, f"apiBase() still doubles /api: {p.stdout[:300]}{p.stderr[:200]}"
    assert "URL-OK" in p.stdout


# Gate đăng nhập web (quyết định 2026-10-12 cùng user):
# - Mọi /api/* (trừ auth/version + 4 endpoint extension-sync) PHẢI qua
#   _require_session (401 khi không Bearer token).
# - Extension sync KHÔNG cần login: /api/questions/bulk,
#   /api/questions/bulk-update-grade, /api/collect/logs/sync, /api/stats
#   giữ public để zero-click sync không gãy.
# - Trang Quản trị riêng trong sidebar (view admin-users), chỉ admin thấy.
_AUTH_PUBLIC_PATHS = {
    "/api/version",
    "/api/auth/register", "/api/auth/login", "/api/auth/logout",
    "/api/auth/forgot",
    # extension-sync relay (không token, không session):
    "/api/questions/bulk", "/api/questions/bulk-update-grade",
    "/api/collect/logs/sync", "/api/stats",
}
# /api/auth/reset CỐ Ý KHÔNG public — chỉ admin (Bearer) được gọi,
# middleware gate mặc định 401 khi không token. Không cho vào tập trên
# để test_web_api_requires_login_session bắt đúng.


def test_forgot_reset_contract_html_js_endpoints():
    # Cross-layer contract: HTML ids/functions mà auth.js đọc/gọi phải
    # tồn tại ở cả 2 phía (drift câm: caller gửi mà handler không đọc).
    html = _read("frontend/index.html")
    js = _read("frontend/js/auth.js")
    app = _read("backend/app.py")
    assert 'id="auth-forgot-user"' in html, "thieu o nhap quen MK"
    assert "EduAuth.doForgotPassword" in html, "nut quen MK chua goi EduAuth"
    assert "doForgotPassword" in js and "/api/auth/forgot" in js
    assert "adminResetPassword" in js and "/api/auth/reset" in js
    assert '"/api/auth/forgot"' in app and '"/api/auth/reset"' in app
    assert '"/api/auth/forgot"' in app.split("_AUTH_GATE_PUBLIC")[1].split("})")[0], \
        "forgot phai public qua gate (user chua login van gui duoc)"


def test_auth_role_and_delete_guards():
    import sqlite3
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend import auth as A
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    A.init_auth_tables(conn)
    A.register_user(conn, "nv_a", "pass1234")
    A.register_user(conn, "nv_b", "pass1234")
    A.set_user_status(conn, "nv_a", "active", by="luanpt")
    A.set_user_status(conn, "nv_b", "active", by="luanpt")
    # user thường không phân quyền được
    ok, _ = A.set_user_role(conn, "nv_b", "admin", by="nv_a")
    assert not ok
    # admin nâng nv_a lên admin
    ok, _ = A.set_user_role(conn, "nv_a", "admin", by="luanpt")
    assert ok
    assert conn.execute("SELECT role FROM users WHERE username='nv_a'").fetchone()[0] == "admin"
    # không tự đổi quyền chính mình / không đụng admin gốc
    ok, _ = A.set_user_role(conn, "nv_a", "user", by="nv_a")
    assert not ok
    ok, _ = A.set_user_role(conn, "luanpt", "user", by="nv_a")
    assert not ok
    # admin hạ quyền + xóa
    ok, _ = A.set_user_role(conn, "nv_a", "user", by="luanpt")
    assert ok
    ok, _ = A.delete_user(conn, "nv_b", by="luanpt")
    assert ok
    assert conn.execute("SELECT COUNT(*) FROM users WHERE username='nv_b'").fetchone()[0] == 0
    # không tự xóa / không xóa admin gốc
    ok, _ = A.delete_user(conn, "nv_a", by="nv_a")
    assert not ok
    ok, _ = A.delete_user(conn, "luanpt", by="nv_a")
    assert not ok
    conn.close()


def test_app_has_role_delete_endpoints():
    src = _read("backend/app.py")
    assert '"/api/auth/role"' in src, "missing /api/auth/role"
    assert '"/api/auth/delete"' in src, "missing /api/auth/delete"


def _route_guarded(src: str, path_literal: str) -> bool:
    # Gate là middleware (_auth_gate_middleware + _AUTH_GATE_PUBLIC +
    # _AUTH_GATE_PUBLIC_PREFIX), không phải _require_session trong từng
    # hàm — nên check tập public (exact + prefix).
    import re as _re
    m = _re.search(
        r"_AUTH_GATE_PUBLIC\s*=\s*frozenset\(\{([^}]*)\}\)", src)
    public = m.group(1) if m else ""
    mp = _re.search(r"_AUTH_GATE_PUBLIC_PREFIX\s*=\s*\(([^)]*)\)", src)
    prefixes = mp.group(1) if mp else ""
    if f'"{path_literal}"' in public:
        return False  # cố ý public (exact)
    for pq in _re.findall(r'"([^"]+)"', prefixes):
        if path_literal == pq or path_literal.startswith(pq + "/") or pq.startswith(path_literal + "/"):
            return False  # cố ý public (prefix, cả 2 chiều: route con/cha)
    i = src.find(f'"{path_literal}"')
    if i < 0:
        return True  # route lạ không liệt kê → middleware gate mặc định
    fn = src.find("async def ", i)
    if fn < 0:
        return True
    nxt = src.find("@app.", i)
    body = src[fn:nxt if nxt > fn else len(src)]
    if "_require_session" in body or "_require_admin" in body:
        return True
    # middleware gate mọi /api/ còn lại
    return "_auth_gate_middleware" in src


def test_web_api_requires_login_session():
    import re
    src = _read("backend/app.py")
    paths = re.findall(r'@app\.(?:get|post|put|delete|patch)\("(/api/[^"{]+)"', src)
    unguarded = [p for p in dict.fromkeys(paths)
                 if p not in _AUTH_PUBLIC_PATHS and not _route_guarded(src, p)]
    assert not unguarded, f"web API chua khoa dang nhap: {unguarded[:8]}"


def test_extension_sync_stays_public():
    src = _read("backend/app.py")
    for p in ["/api/questions/bulk", "/api/questions/bulk-update-grade",
              "/api/collect/logs/sync", "/api/stats"]:
        assert not _route_guarded(src, p), f"{p} bi gate se gay extension sync"


def test_gate_public_covers_subpaths_and_healthcheck():
    # Healthcheck Docker gọi /api/stats/count (subpath của /api/stats public).
    # Gate exact-match (`path not in _AUTH_GATE_PUBLIC`) trả 401 → container
    # unhealthy. Middleware phải dùng helper prefix-match.
    src = _read("backend/app.py")
    assert "def _is_gate_public" in src, \
        "thieu helper public-prefix: /api/stats/count (healthcheck) se bi 401"
    body = src[src.find("async def _auth_gate_middleware"):]
    nxt = body.find("\nasync def ", 1)
    body = body[:nxt if nxt > 0 else len(body)]
    assert "_is_gate_public(path)" in body, \
        "middleware chua dung helper prefix-match cho public paths"


def test_auth_gate_middleware_registered():
    src = _read("backend/app.py")
    assert "async def _auth_gate_middleware" in src, "thieu middleware gate"
    assert 'app.middleware("http")(_auth_gate_middleware)' in src, \
        "middleware gate chua duoc gan vao app"


def test_sidebar_has_admin_view_and_login_wall():
    html = _read("frontend/index.html")
    assert 'data-view="admin-users"' in html or 'id="view-admin-users"' in html, \
        "thieu view Quan tri rieng trong sidebar"
    js = _read("frontend/js/auth.js")
    assert "admin-users" in js, "auth.js chua dieu huong view Quan tri"
    appjs = _read("frontend/js/app.js")
    assert "login-wall" in appjs or "requireLogin" in appjs or "auth-wall" in appjs, \
        "thieu tuong login chan dashboard khi chua dang nhap"


def test_auth_modal_above_login_wall():
    # Bug 2026-10-12 (user + ảnh): bấm "Đăng nhập / Đăng ký" trên tường
    # login nhưng modal-auth mở ra nằm DƯỚI tường (z 9999 < 10000) nên
    # tường như không biến mất, che khuất form đăng nhập.
    import re
    html = _read("frontend/index.html")
    js = _read("frontend/js/auth.js")
    m = re.search(r'id="modal-auth"[^>]*z-index:\s*(\d+)', html)
    assert m, "modal-auth missing z-index"
    modal_z = int(m.group(1))
    wall_fn = js[js.find("function showLoginWall()"):]
    w = re.search(r'z-index:(\d+)', wall_fn)
    assert w, "login-wall missing z-index"
    wall_z = int(w.group(1))
    assert modal_z > wall_z, \
        f"modal-auth (z={modal_z}) bi login-wall (z={wall_z}) de"


def test_js_version_fallback_matches_backend():
    import re
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.version import APP_VERSION_NUMBER
    appjs = _read("frontend/js/app.js")
    m = re.search(r'(?:let|const|var)\s+APP_VERSION\s*=\s*"v([\d.]+)"', appjs)
    assert m, "APP_VERSION fallback missing in app.js"
    assert m.group(1) == APP_VERSION_NUMBER, \
        f"fallback v{m.group(1)} != backend v{APP_VERSION_NUMBER}"
