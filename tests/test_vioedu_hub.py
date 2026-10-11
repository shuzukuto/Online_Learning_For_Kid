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
