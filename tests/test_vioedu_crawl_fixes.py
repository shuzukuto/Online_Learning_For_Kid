"""RED-phase: breadth must not block the HTTP worker + dedup must not
collapse distinct VioEdu questions sharing the same short stem prefix.

Bug 1: POST /api/collect/run action=breadth awaits the whole sweep inline
(100+ skills x 12 questions). The single uvicorn worker is held for many
minutes -> browser/proxy times out -> only the 'running' log survives.
Fix: run sweep in background, return immediately with a job id.

Bug 2: dedup key in vioedu.py Step 4 truncates normalized text to 80 chars.
VioEdu stems share long prefixes ("Bạn hãy chọn đáp án đúng. Cho hình..."),
so distinct questions collapse to one. Fix: key on full hash (content
+ options signature), not truncated prefix.
"""
import re


def _read_vioedu():
    with open("backend/scrapers/vioedu.py", encoding="utf-8") as f:
        return f.read()


def _read_app():
    with open("backend/app.py", encoding="utf-8") as f:
        return f.read()


def test_breadth_does_not_block_request():
    app = _read_app()
    m = re.search(r'elif req\.action == "breadth":(.*?)(?=\n        elif |\n    elif platform)', app, re.S)
    assert m, "breadth branch not found"
    body = m.group(1)
    assert "background" in body.lower() or "create_task" in body or "BackgroundTasks" in body, \
        "breadth still awaits full sweep inline (blocks single worker)"


def test_dedup_key_not_truncated():
    src = _read_vioedu()
    assert "lower()[:80]" not in src and "lower()[: 80]" not in src, \
        "dedup key still truncated to 80 chars (collapses distinct questions)"


def test_breadth_jobs_registry_exists():
    app = _read_app()
    assert "_BREADTH_JOBS" in app and "_BREADTH_JOBS[" in app, \
        "missing _BREADTH_JOBS registry for background jobs"
    assert "/api/collect/breadth-status" in app, \
        "missing breadth-status poll endpoint"
