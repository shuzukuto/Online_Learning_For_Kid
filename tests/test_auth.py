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
               "/api/auth/change-password", "/api/auth/users", "/api/auth/approve"]:
        assert ep in src, f"missing endpoint {ep}"


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
const api = ['AuthStore','authHeaders','openAuthModal','closeAuthModal','doLogin','doRegister','doLogout','doChangePassword','loadAdminUsers','approve','refreshBadge'];
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
