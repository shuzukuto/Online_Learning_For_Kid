"""RED tests: frontend display logic (mastery + KaTeX currency) via node.

Extracts pure helper functions from frontend/js/*.js and asserts:
1. resolveMasteryDisplay: 0 attempts -> hasData False, no fake 75%, status 'Chua luyen tap'.
2. escapeCurrencyForKatex: currency $50000$ -> placeholder (no stray backslash);
   real formulas ($\\frac, $\\text, $12 + 34$) untouched.
3. unescape/restore brings the currency text back byte-identical.
"""
from __future__ import annotations

import json
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
const argJson = process.argv[4];
const args = JSON.parse(argJson);
let fn;
const preamble = "const CURRENCY_TOKEN_OPEN = '';\nconst CURRENCY_TOKEN_CLOSE = '';\n";
eval(preamble + code + '\nfn = ' + fname + ';');
try {
  const out = fn.apply(null, args);
  console.log(JSON.stringify({ok: out}));
} catch (e) {
  console.log(JSON.stringify({error: String(e && e.message || e)}));
}
"""


def _run_js(path: str, fname: str, args) -> object:
    probe = os.path.join(PROJECT_ROOT, "tests", "_js_probe_tmp.js")
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


APP_JS = os.path.join(PROJECT_ROOT, "frontend", "js", "app.js")
PRACTICE_JS = os.path.join(PROJECT_ROOT, "frontend", "js", "practice.js")


def test_mastery_no_data_not_fake_75():
    out = _run_js(PRACTICE_JS, "resolveMasteryDisplay", [None, []])
    assert out["hasData"] is False
    assert out["accuracy"] is None
    assert out["attempts"] == 0
    assert "75" not in str(out)


def test_mastery_no_data_status_not_pass():
    out = _run_js(PRACTICE_JS, "resolveMasteryDisplay", [None, []])
    assert out["statusText"] != "Đạt yêu cầu"


def test_mastery_with_server_stat():
    sub = {"accuracy_rate": 82.5, "attempts": 12}
    out = _run_js(PRACTICE_JS, "resolveMasteryDisplay", [sub, []])
    assert out["hasData"] is True
    assert out["accuracy"] == 83 or out["accuracy"] == 82
    assert out["attempts"] == 12


def test_currency_escaped_no_backslash():
    s = "Mẹ mua gạo giá $50000$ đồng, trả $100000$ đồng."
    out = _run_js(APP_JS, "escapeCurrencyForKatex", [s])
    assert "\\" not in out, f"stray backslash in escaped: {out!r}"
    assert "$50000$" not in out  # must be protected from KaTeX


def test_currency_roundtrip_identical():
    s = "Mẹ mua gạo giá $50000$ đồng, trả $100000$ đồng."
    esc = _run_js(APP_JS, "escapeCurrencyForKatex", [s])
    back = _run_js(APP_JS, "restoreCurrencyAfterKatex", [esc])
    assert back == s


def test_real_formulas_untouched_by_escape():
    cases = [
        "Cách nhau $165\\text{ km}$ lúc 7 giờ.",
        "Đáy lớn $120\\text{ m}$, đáy bé $\\frac{2}{3}$.",
        "Tính $A = \\frac{1}{2} + \\frac{1}{6}$.",
        "Kết quả $12 + 34$ là bao nhiêu?",
    ]
    for s in cases:
        out = _run_js(APP_JS, "escapeCurrencyForKatex", [s])
        assert out == s, f"formula modified: {s!r} -> {out!r}"


def test_tts_short_text_single_chunk():
    out = _run_js(PRACTICE_JS, "splitIntoSpeechChunks", ["Câu 1. Hai cộng ba bằng mấy?", 180])
    assert out == ["Câu 1. Hai cộng ba bằng mấy?"]


def test_tts_long_text_splits_all_under_limit():
    long_text = " ".join([f"Câu {i}. Đáp án A là {i}, đáp án B là {i + 1}." for i in range(1, 12)])
    out = _run_js(PRACTICE_JS, "splitIntoSpeechChunks", [long_text, 180])
    assert isinstance(out, list) and len(out) > 1
    for ch in out:
        assert len(ch) <= 180, f"chunk too long ({len(ch)}): {ch[:60]!r}"
    joined = " ".join(out)
    for i in (1, 5, 11):
        assert f"Câu {i}." in joined


def test_tts_empty_text_no_chunks():
    assert _run_js(PRACTICE_JS, "splitIntoSpeechChunks", ["   ", 180]) == []
