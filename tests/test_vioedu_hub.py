"""RED-phase: unified crawl hub + skill ledger (7-day re-crawl).

1. Skill ledger: record_skill_crawl() / get_stale_skills() exist in vioedu.py.
   - A skill crawled now is NOT stale again within 7 days.
   - crawl_vioedu_breadth() skips fresh skills unless force=True, and records
     each visited skill.
2. Scheduler: backend has a 24/7 background crawl scheduler honoring
   system_config vioedu_auto_crawl (lifespan starts it).
3. Unified API: /api/collect/vioedu-plan validates mode in
   {once, auto, breadth} (no login needed for breadth), and action=breadth
   is only reachable via the unified path (old direct branch removed or
   delegates to the same background job runner).
"""
import re


def _read_vioedu():
    with open("backend/scrapers/vioedu.py", encoding="utf-8") as f:
        return f.read()


def _read_app():
    with open("backend/app.py", encoding="utf-8") as f:
        return f.read()


def test_skill_ledger_exists():
    src = _read_vioedu()
    assert "def record_skill_crawl" in src, "missing record_skill_crawl()"
    assert "def get_stale_skills" in src, "missing get_stale_skills()"


def test_breadth_skips_fresh_skills():
    src = _read_vioedu()
    i = src.find("async def crawl_vioedu_breadth(")
    assert i >= 0, "crawl_vioedu_breadth not found"
    j = src.find("async def crawl_vioedu_rounds_headless(", i)
    body = src[i:j if j > 0 else len(src)]
    assert "get_stale_skills" in body, \
        "breadth does not consult the skill ledger (re-crawls everything)"
    assert "record_skill_crawl" in body, \
        "breadth does not record visited skills"


def test_scheduler_exists():
    app = _read_app()
    assert "vioedu_auto_crawl" in app, "missing vioedu_auto_crawl config key"
    assert "schedule_vioedu" in app.lower() or "auto_crawl" in app.lower(), \
        "missing background crawl scheduler"


def test_unified_plan_endpoint():
    app = _read_app()
    assert "/api/collect/vioedu-plan" in app, "missing unified /api/collect/vioedu-plan"


def test_scheduler_records_heartbeat():
    # 24/7 bot must leave a liveness trace: scheduler loop updates a
    # heartbeat record every iteration (even when disabled or skipping),
    # so the UI can tell "alive but idle" apart from "dead".
    app = _read_app()
    i = app.find("async def _schedule_vioedu_auto_crawl(")
    assert i >= 0, "scheduler not found"
    j = app.find("@app.post(\"/api/collect/run\")", i)
    body = app[i:j if j > 0 else len(app)]
    assert "heartbeat" in body.lower(), \
        "scheduler loop never records a heartbeat tick"


def test_plan_endpoint_exposes_heartbeat():
    app = _read_app()
    i = app.find("async def vioedu_plan_status(")
    assert i >= 0, "vioedu_plan_status not found"
    j = app.find("@app.get(\"/api/collect/logs\")", i)
    body = app[i:j if j > 0 else len(app)]
    assert "heartbeat" in body.lower(), \
        "GET /api/collect/vioedu-plan does not expose scheduler heartbeat"


def test_hub_ui_renders_heartbeat():
    with open("frontend/js/collector.js", encoding="utf-8") as f:
        js = f.read()
    assert "heartbeat" in js.lower(), \
        "hub status UI never renders scheduler heartbeat"


# Auth-gate (quyết định 2026-10-12): mọi /api/* trừ auth/version + 4 endpoint
# extension-sync đều 401 khi thiếu Bearer. Hub/bot VioEdu từng dùng fetch
# trần → sau khi bật tường login, nút "Bắt đầu cào", "Cào diện rộng",
# toggle 24/7, trạng thái hub và nhật ký chết lặng với 401. Mọi điểm gọi
# /collect/* trong collector.js PHẢI đi qua EduAuth.apiFetch (tự gắn token
# + mở tường khi 401), cấm fetch trần tới /collect/.
_HUB_BOT_CALLERS = [
    "runAutoScraper",         # POST /collect/run (bot đăng nhập cào vòng thi)
    "runVioEduBreadth",       # POST /collect/vioedu-plan (cào diện rộng)
    "refreshVioEduHubStatus",  # GET  /collect/vioedu-plan (trạng thái hub)
    "pollBreadthStatus",      # GET  /collect/breadth-status (poll job nền)
    "loadCollectorLogs",      # GET  /collect/logs
    "copyCollectorLogs",      # GET  /collect/logs
    "clearAllCollectorLogs",  # DELETE /collect/logs
    "toggleBotAutoCrawl",     # POST /collect/vioedu-plan (toggle 24/7)
    "saveVioEduSession",      # POST /collect/vioedu-login (luu phien TK)
]


def _collector_func_body(src: str, name: str) -> str:
    i = src.find(f"async function {name}(")
    if i < 0:
        i = src.find(f"function {name}(")
    assert i >= 0, f"{name}() missing from collector.js"
    m = re.search(r"\n(?:async )?function \w+\(", src[i + 1:])
    return src[i:i + 1 + m.start() if m else len(src)]


def test_hub_bot_fetches_carry_auth_token():
    with open("frontend/js/collector.js", encoding="utf-8") as f:
        src = f.read()
    bad = []
    for name in _HUB_BOT_CALLERS:
        body = _collector_func_body(src, name)
        if "apiFetch" not in body or "fetch(`${API_BASE}/collect/" in body:
            bad.append(name)
    # Khối init đồng bộ toggle lúc nạp trang (không nằm trong function).
    i = src.find("Hub VioEdu: đồng bộ toggle")
    assert i >= 0, "hub init sync block missing from collector.js"
    init_slice = src[i:i + 1200]
    if "apiFetch" not in init_slice or "fetch(`${API_BASE}/collect/" in init_slice:
        bad.append("<hub-init-sync>")
    assert not bad, (
        "hub/bot vẫn fetch trần (dính gate 401 sau khi bật login): "
        + ", ".join(bad) + " — phải qua EduAuth.apiFetch"
    )


def test_breadth_poll_stops_on_auth_error():
    # Poll job nền mỗi 15s × 80 lần: khi mất phiên (401) phải dừng ngay,
    # không retry mù 20 phút (mỗi lần retry lại mở tường login).
    with open("frontend/js/collector.js", encoding="utf-8") as f:
        src = f.read()
    body = _collector_func_body(src, "pollBreadthStatus")
    assert "apiFetch" in body, "pollBreadthStatus chưa qua EduAuth.apiFetch"
    assert re.search(r"401|đăng nhập|hết hạn", body), \
        "pollBreadthStatus không có guard dừng retry khi mất phiên"


def test_vioedu_login_endpoint_exists():
    # User 2026-10-14: xoay khoi 1-12 dung "tai khoan dang nhap cao du lieu".
    # Admin nhap TK VioEdu 1 lan → server login, luu cookies vao system_config
    # (key vioedu_session_cookies) de scheduler dung. Endpoint chi admin.
    with open("backend/app.py", encoding="utf-8") as f:
        src = f.read()
    assert "vioedu-login" in src or "vioedu_login" in src, \
        "chua co endpoint luu phien dang nhap VioEdu (admin nhap TK 1 lan)"
    assert "vioedu_session_cookies" in src, \
        "chua luu cookies phien VioEdu vao system_config"


def test_scheduler_uses_saved_vioedu_session():
    # Scheduler 24/7 phai doc cookies da luu (neu co) va truyen vao ham cao,
    # fallback anonymous khi chua co — khong doi hanh vi hien tai.
    with open("backend/app.py", encoding="utf-8") as f:
        src = f.read()
    assert "vioedu_session_cookies" in src, \
        "scheduler chua doc phien VioEdu da luu"
    with open("backend/scrapers/vioedu.py", encoding="utf-8") as f:
        vsrc = f.read()
    assert "cookies" in vsrc, \
        "ham cao VioEdu chua nhan cookies (khong dung duoc TK dang nhap)"


def test_vioedu_login_requires_admin_not_passthrough():
    # POST /api/collect/vioedu-login luu phien TK → user thuong KHONG duoc
    # goi (ke ca local pass-through): phai _require_admin, khong phai
    # require_api_token (rong = cho qua o local).
    with open("backend/app.py", encoding="utf-8") as f:
        src = f.read()
    i = src.find('"/api/collect/vioedu-login"')
    assert i >= 0, "endpoint vioedu-login missing"
    post_i = src.rfind("@app.post(", 0, i)
    assert post_i >= 0
    body = src[post_i:src.find("\n@app.", i)]
    assert "_require_admin" in body, \
        "POST vioedu-login chua _require_admin (user thuong luu phien TK tuy y)"
    assert "require_api_token" not in body or "_require_admin" in body
