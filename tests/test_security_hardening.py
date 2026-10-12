"""RED/GREEN f5: XSS escapeHtml + SSRF blocklist (3 ban phan bien AI).

XSS (High, kiem toan #2): bank.js render truong DB text (content_text_preview,
source_detail, topic/exam_name) vao innerHTML ma khong escape — cau hoi doc
tu web ve co the nhu payload <script>/<img onerror>. content_html giu nguyen
(can rich text + KaTeX; normalizer da strip script luc ingest).
SSRF (Medium): hunter fetch custom_url tu user ma khong chan localhost/
169.254/10./192.168. → ke tan cong co token co the quet mang noi bo.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(os.path.join(PROJECT_ROOT, path), encoding="utf-8") as f:
        return f.read()


NODE_EXTRACT = r"""
const fs = require('fs');
const path = process.argv[2];
const fname = process.argv[3];
const src = fs.readFileSync(path, 'utf8');
const start = src.indexOf('function ' + fname + '(');
if (start < 0) { console.log(JSON.stringify({error: 'missing:' + fname})); process.exit(0); }
let depth = 0, end = -1;
for (let i = start; i < src.length; i++) {
  if (src[i] === '{') depth++;
  else if (src[i] === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
}
const code = src.slice(start, end);
const args = JSON.parse(process.argv[4]);
let fn;
eval(code + '\nfn = ' + fname + ';');
try {
  const out = fn.apply(null, args);
  console.log(JSON.stringify({ok: out}));
} catch (e) {
  console.log(JSON.stringify({error: String(e && e.message || e)}));
}
"""


def _run_js(path: str, fname: str, args) -> object:
    probe = os.path.join(PROJECT_ROOT, "tests", "_js_probe_tmp2.js")
    with open(probe, "w", encoding="utf-8") as f:
        f.write(NODE_EXTRACT)
    try:
        p = subprocess.run(
            ["node", probe, path, fname, json.dumps(args)],
            capture_output=True, text=True, timeout=30,
        )
        assert p.returncode == 0, f"node failed: {p.stderr[:300]}"
        data = json.loads(p.stdout.strip().splitlines()[-1])
    finally:
        if os.path.exists(probe):
            os.remove(probe)
    assert "error" not in data, f"JS {fname} error: {data.get('error')}"
    return data["ok"]


BANK_JS = os.path.join(PROJECT_ROOT, "frontend", "js", "bank.js")


def test_bank_has_escape_html_helper():
    src = _read("frontend/js/bank.js")
    assert "function escapeHtml(" in src, "bank.js thieu helper escapeHtml"


def test_escape_html_neutralizes_script_payload():
    out = _run_js(BANK_JS, "escapeHtml",
                  ['<script>alert(1)</script><img src=x onerror=evil()>'])
    assert "<script" not in out and "<img" not in out, f"payload song: {out!r}"
    assert "&lt;script" in out and "&lt;img" in out, f"escape sai: {out!r}"


def test_escape_html_keeps_math_readable():
    out = _run_js(BANK_JS, "escapeHtml", [r"Tính $\frac{1}{2} + 50$ đồng"])
    assert "frac" in out and "1" in out and "2" in out, f"mat cong thuc: {out!r}"


def test_bank_dupe_preview_sink_escapes():
    # Sink bank.js:808 ${grp.content_text_preview} trong innerHTML —
    # phai boc escapeHtml, khong de text tho.
    src = _read("frontend/js/bank.js")
    hits = [ln for ln in src.splitlines() if "content_text_preview" in ln]
    assert hits, "sink content_text_preview doi hinh?"
    assert any("escapeHtml" in ln for ln in hits), \
        "sink preview chua escape — cau doc tu web co the nhu <script>"


def test_bank_source_detail_sink_escapes():
    # Sink: dong gan sourceDetailHtml + span tag-topic render text DB vao
    # innerHTML — phai boc escapeHtml, khong de text tho.
    src = _read("frontend/js/bank.js")
    detail_lines = [ln for ln in src.splitlines()
                    if "sourceDetailHtml =" in ln and "span" in ln]
    topic_lines = [ln for ln in src.splitlines()
                   if "tag-topic" in ln and ("q.topic" in ln or "exam_name" in ln)]
    assert detail_lines and topic_lines, "sink source_detail/topic doi hinh?"
    for ln in detail_lines + topic_lines:
        assert "escapeHtml" in ln, f"sink chua escape: {ln.strip()[:100]}"


def test_ssrf_blocklist_helper_exists():
    from backend.scrapers.hunter import fetch as F
    assert hasattr(F, "is_url_fetch_allowed"), \
        "fetch.py thieu is_url_fetch_allowed(url)"


def test_ssrf_blocks_private_and_metadata():
    from backend.scrapers.hunter import fetch as F
    blocked = [
        "http://localhost:8000/api/questions",
        "http://127.0.0.1:8000/x",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "ftp://internal.local/x",
    ]
    for u in blocked:
        assert F.is_url_fetch_allowed(u) is False, f"lot SSRF: {u}"


def test_ssrf_allows_public_edu_sources():
    from backend.scrapers.hunter import fetch as F
    allowed = [
        "https://loigiaihay.com/toan-lop-9-c1968.html",
        "https://vndoc.com/de-thi-toan-lop-5.jsp",
    ]
    for u in allowed:
        assert F.is_url_fetch_allowed(u) is True, f"chan nham public: {u}"


def test_fetch_entry_rejects_blocked_url_without_network():
    from backend.scrapers.hunter import fetch as F
    out = asyncio.run(F.fetch_questions_from_web_url("http://127.0.0.1:9/x"))
    assert out == [], f"van fetch URL bi chan: {out!r}"
