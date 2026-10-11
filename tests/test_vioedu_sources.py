"""RED tests: VioEdu/hunter source URLs must not contain known-dead patterns.

Verified live (2026-10-11, urllib HEAD/GET):
- https://vio.edu.vn/luyen-tap            -> 404 (alive: /skill-list, /arena, /login)
- https://tnmath.edu.vn/luyen-tap       -> 404 (alive: / root)
- https://olm.vn/chu-de/toan-lop-{grade} -> 404 (alive: /lop-{grade})
- https://vietjack.com/toan-lop-{g}/index.jsp -> 404 (alive: /toan-{g}/index.jsp)
"""
from __future__ import annotations

import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEAD_PATTERNS = [
    "vio.edu.vn/luyen-tap",
    "tnmath.edu.vn/luyen-tap",
    "olm.vn/chu-de/toan-lop-",
    "vietjack.com/toan-lop-",
]

SEARCH_FILES = [
    "backend/scrapers/hunter/sources.py",
    "frontend/js/collector.js",
]


def _read(rel: str) -> str:
    with open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_no_dead_source_urls_in_hunter_catalog():
    src = _read("backend/scrapers/hunter/sources.py")
    for pat in DEAD_PATTERNS:
        assert pat not in src, f"sources.py still contains dead URL pattern: {pat}"


def test_no_dead_source_urls_in_collector_presets():
    src = _read("frontend/js/collector.js")
    for pat in DEAD_PATTERNS:
        assert pat not in src, f"collector.js still contains dead URL pattern: {pat}"


def test_vioedu_skill_list_url_present():
    src = _read("backend/scrapers/hunter/sources.py")
    assert "vio.edu.vn/skill-list" in src


def test_olm_grade_url_shape():
    src = _read("backend/scrapers/hunter/sources.py")
    assert re.search(r"olm\.vn/lop-\{grade\}|\{'grade'\}", src) or "olm.vn/lop-" in src
