"""RED tests: Facebook post detector (extension thu text truoc, anh sau).

User 2026-10-14: mo rong quet tren Facebook — nhom/page cong khai ve hoc tap
(TIMO, HKIMO, ASMO, Trang Nguyen, VioEdu...). Bot server khong cao duoc FB
(314: probe mbasic/page/oEmbed/Graph deu chan request khong-login) → lam qua
extension (chay trong phien dang nhap san cua user): detector loc post co
tu khoa ky thi + dau hieu cau hoi, tai dung pipeline capture co san.
Phase 1: TEXT only (anh OCR sau).
"""
from __future__ import annotations

import json
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_JS = os.path.join(PROJECT_ROOT, "extension", "content.js")

# Trich 2 pure helpers tu content.js (khong can DOM): kiem tra text post co
# phai de/cau hoi ky thi + tach grade tu text. Chay that qua node.
NODE_EXTRACT = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
function sliceFn(name) {
  const start = src.indexOf('function ' + name + '(');
  if (start < 0) return null;
  let depth = 0, end = -1;
  for (let i = start; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return src.slice(start, end);
}
const names = JSON.parse(process.argv[3]);
let code = '';
for (const n of names) { const s = sliceFn(n); if (!s) { console.log(JSON.stringify({error: 'missing:' + n})); process.exit(0); } code += s + '\n'; }
const cases = JSON.parse(process.argv[4]);
eval(code);
const out = [];
for (const c of cases) {
  try { out.push({fn: c.fn, input: c.input, ok: eval(c.fn).apply(null, c.args)}); }
  catch (e) { out.push({fn: c.fn, input: c.input, error: String(e && e.message || e)}); }
}
console.log(JSON.stringify(out));
"""


def _run_fb(cases) -> list:
    probe = os.path.join(PROJECT_ROOT, "tests", "_fb_probe_tmp.js")
    with open(probe, "w", encoding="utf-8") as f:
        f.write(NODE_EXTRACT)
    try:
        p = subprocess.run(
            ["node", probe, CONTENT_JS,
             json.dumps(["isFacebookEduPost", "extractGradeFromText"]),
             json.dumps(cases)],
            capture_output=True, text=True, timeout=30,
        )
        assert p.returncode == 0, f"node failed: {p.stderr[:300]}"
        data = json.loads(p.stdout.strip().splitlines()[-1])
    finally:
        if os.path.exists(probe):
            os.remove(probe)
    assert not (isinstance(data, dict) and "error" in data), f"JS missing helper: {data}"
    return data


def test_facebook_edu_post_detector_exists():
    # Detector pure: text post → co phai de/cau hoi ky thi (TIMO/HKIMO/ASMO/
    # Trang Nguyen/VioEdu/Olympic) + dau hieu cau hoi (Câu N, ?, tính, đáp án).
    with open(CONTENT_JS, encoding="utf-8") as f:
        src = f.read()
    assert "function isFacebookEduPost(" in src, \
        "thieu isFacebookEduPost(text) — extension chua loc duoc post de thi FB"
    assert "function extractGradeFromText(" in src, \
        "thieu extractGradeFromText(text) — chua tach khoi tu text post FB"


def test_facebook_detector_matches_competition_posts():
    cases = [
        {"fn": "isFacebookEduPost", "input": "TIMO mock",
         "args": ["🔥 Đề luyện TIMO khối 3 — Vòng 1. Câu 1: Tính 25 + 17 = ? A. 32 B. 42 C. 52 Đáp án comment nhé các con!"]},
        {"fn": "isFacebookEduPost", "input": "ads spam",
         "args": ["🔥 SALE SỐC giảm 50% giày sneaker, inbox shop ngay, free ship toàn quốc, hàng auth 100%"]},
        {"fn": "isFacebookEduPost", "input": "Trang Nguyen TV",
         "args": ["Trạng Nguyên Tiếng Việt lớp 2: Câu 2: Từ nào viết đúng chính tả? a) xinh xắn b) sinh sắn"]},
        {"fn": "extractGradeFromText", "input": "khoi 3",
         "args": ["Đề luyện TIMO khối 3 vòng 1, câu 1 tính 25+17"]},
        {"fn": "extractGradeFromText", "input": "lop 2",
         "args": ["Trạng Nguyên Tiếng Việt lớp 2 vòng 5"]},
    ]
    out = _run_fb(cases)
    by = {r["input"]: r for r in out}
    assert by["TIMO mock"].get("ok") is True, "post de TIMO phai match"
    assert by["ads spam"].get("ok") is False, "spam ban hang phai loai"
    assert by["Trang Nguyen TV"].get("ok") is True, "post Trang Nguyen phai match"
    assert by["khoi 3"].get("ok") == 3, f"khoi 3 → 3, got {by['khoi 3']}"
    assert by["lop 2"].get("ok") == 2, f"lop 2 → 2, got {by['lop 2']}"


def test_facebook_platform_wired():
    # content.js nhan dien facebook.com + manifest cho phep chay tren FB.
    with open(CONTENT_JS, encoding="utf-8") as f:
        src = f.read()
    assert "facebook" in src.lower(), "content.js chua co nhan dien facebook"
    with open(os.path.join(PROJECT_ROOT, "extension", "manifest.json"), encoding="utf-8") as f:
        mf = f.read()
    assert "facebook.com" in mf, "manifest chua cho phep chay tren facebook.com"
