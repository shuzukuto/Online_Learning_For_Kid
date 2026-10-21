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


def test_facebook_question_payload_valid_in_normalizer():
    from backend.normalizer import is_valid_question_payload

    # Payload scanned from Facebook should NOT be rejected just because it has "facebook" in topic, exam_name, or content
    fb_q = {
        "id": "fb_123",
        "source_platform": "facebook",
        "source_url": "https://www.facebook.com/groups/toantieuhoc/posts/123456",
        "exam_name": "Facebook - Nhóm Toán Tiểu Học",
        "grade": 3,
        "subject": "math",
        "topic": "Facebook Nhóm học tập (TIMO/HKIMO/ASMO)",
        "question_type": "fill_blank",
        "content_text": "Đề thi thử TIMO lớp 3 vòng 1: Câu 1: Tìm x biết x + 25 = 50. Chia sẻ từ facebook nhóm học tập.",
        "content_html": "Đề thi thử TIMO lớp 3 vòng 1: Câu 1: Tìm x biết x + 25 = 50.<br>Chia sẻ từ facebook nhóm học tập.",
        "options": [],
        "correct_answer": "25",
        "difficulty": "medium"
    }
    valid, reason = is_valid_question_payload(fb_q)
    assert valid is True, f"Câu hỏi Facebook bị từ chối sai: {reason}"

    # Non-facebook source with spam contact facebook should still be rejected
    spam_q = {
        "id": "spam_456",
        "source_platform": "vndoc",
        "source_url": "https://vndoc.com/test",
        "exam_name": "Đề thi",
        "grade": 3,
        "subject": "math",
        "topic": "Đề kiểm tra",
        "question_type": "fill_blank",
        "content_text": "Câu 1: 1 + 1 = 2. Mọi thắc mắc nhắn qua facebook cá nhân để được hỗ trợ.",
        "content_html": "Câu 1: 1 + 1 = 2. Mọi thắc mắc nhắn qua facebook cá nhân để được hỗ trợ.",
        "options": []
    }
    spam_valid, spam_reason = is_valid_question_payload(spam_q)
    assert spam_valid is False, "Spam liên hệ facebook từ nguồn khác phải bị loại"
    assert "facebook" in spam_reason.lower()


def test_extension_facebook_formatting_and_image_filters():
    with open(CONTENT_JS, encoding="utf-8") as f:
        src = f.read()
    # Check that extractImagesFromElement filters out emoji, rsrc.php, static.xx.fbcdn.net
    assert "rsrc.php" in src or "rsrc\\.php" in src, "extractImagesFromElement phai loc rsrc.php"
    assert "emoji" in src, "extractImagesFromElement phai loc emoji"
    # Check that scanFacebookPosts replaces \n with <br>
    assert "text.replace(/\\n/g, \"<br>\")" in src or "text.replace(/\\n/g, '<br>')" in src, \
        "scanFacebookPosts phai giu ngat dong bang <br>"
    # Check that scanFacebookPosts defaults to fill_blank when options is empty
    assert 'question_type: "fill_blank"' in src or "question_type: 'fill_blank'" in src, \
        "scanFacebookPosts phai co question_type fill_blank khi options rong"


def test_facebook_detector_with_images_short_caption():
    cases = [
        {"fn": "isFacebookEduPost", "input": "caption with image",
         "args": ["Đề thi học kì 1 môn Toán khối 3", True]},
        {"fn": "isFacebookEduPost", "input": "spam with image",
         "args": ["Giảm giá túi xách hàng hiệu", True]},
        {"fn": "isFacebookEduPost", "input": "caption without image",
         "args": ["Đề thi học kì 1 môn Toán khối 3", False]},
    ]
    out = _run_fb(cases)
    by = {r["input"]: r for r in out}
    assert by["caption with image"].get("ok") is True, "de thi kem anh phai match"
    assert by["spam with image"].get("ok") is False, "spam du co anh van phai loai"
    assert by["caption without image"].get("ok") is False, "caption ngan khong anh khong dau hieu cau hoi phai bo qua"


def test_facebook_social_keywords_allowed_in_normalizer():
    from backend.normalizer import is_valid_question_payload
    fb_social_q = {
        "id": "fb_img_post_789",
        "source_platform": "facebook",
        "source_url": "https://www.facebook.com/groups/toantieuhoc/posts/789",
        "exam_name": "Facebook - Nhóm Chia Sẻ Đề Thi",
        "grade": 4,
        "subject": "math",
        "topic": "Facebook Nhóm học tập (TIMO/HKIMO/ASMO)",
        "question_type": "fill_blank",
        "content_text": "Chia sẻ cho ba mẹ và phụ huynh đề kiểm tra giữa kì 1 môn Toán lớp 4 cho các con ôn tập. Mọi người để lại bình luận nhận đáp án chi tiết nhé.",
        "content_html": "Chia sẻ cho ba mẹ và phụ huynh đề kiểm tra giữa kì 1 môn Toán lớp 4 cho các con ôn tập.<br>Mọi người để lại bình luận nhận đáp án chi tiết nhé.",
        "images": ["https://scontent.fhan.fbcdn.net/v/test_exam_sheet.jpg"],
        "options": [],
        "correct_answer": None,
        "difficulty": "medium"
    }
    valid, reason = is_valid_question_payload(fb_social_q)
    assert valid is True, f"Bài post Facebook có ảnh đề thi bị từ chối sai: {reason}"


def test_facebook_button_injection_and_image_extractor_exist():
    with open(CONTENT_JS, encoding="utf-8") as f:
        src = f.read()
    assert "function extractFacebookImages(" in src, "Thiếu hàm extractFacebookImages trong content.js"
    assert "function injectFacebookPostButtons(" in src, "Thiếu hàm injectFacebookPostButtons trong content.js"
    assert "eduquest-fb-save-btn" in src, "Thiếu nút lưu đề thi Facebook 1-click trong content.js"
