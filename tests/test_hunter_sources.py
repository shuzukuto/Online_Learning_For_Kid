"""RED-phase: hunter upgrade — new live-verified sources + fixes.

1. get_grade_source_urls(grade) must include the newly verified slug families:
   loigiaihay (toan/tieng-viet/tieng-anh per grade), ioe.vn (english),
   tienganh123, mathplayground, education.com (EN worksheets).
2. Must NOT contain dead URLs verified 404 today:
   vietjack toan-{1,2}-kn, vndoc.com/toan-lop-{grade} (400), thivietnamese (DNS),
   tuyensinh247 hoc-lop-2, splashlearn grade-2.
3. fetch_questions_from_web_url has a handler for loigiaihay (not just generic).
4. run_internet_question_hunter passes grade into parametric gen per subject
   (no silent grade=5 default that mis-tags questions).
"""
from __future__ import annotations

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(os.path.join(PROJECT_ROOT, path), encoding="utf-8") as f:
        return f.read()


def test_hunter_has_new_verified_sources():
    src = _read("backend/scrapers/hunter/sources.py")
    for needle in ["loigiaihay.com", "ioe.vn", "tienganh123", "mathplayground", "education.com"]:
        assert needle in src, f"missing new verified source: {needle}"


def test_hunter_no_dead_urls():
    src = _read("backend/scrapers/hunter/sources.py")
    for dead in ["toan-{grade}-kn", "vndoc.com/toan-lop-", "thivietnamese", "hoc-lop-2", "splashlearn"]:
        assert dead not in src, f"dead URL family still present: {dead}"


def test_hunter_loigiaihay_handler():
    src = _read("backend/scrapers/hunter/fetch.py")
    assert "loigiaihay" in src.lower(), "no dedicated loigiaihay handler in fetch.py"


def test_runner_grades_parametric_per_subject():
    src = _read("backend/scrapers/hunter/runner.py")
    assert "generate_parametric_questions" in src
    # parametric must receive the requested grade, not a hardcoded fallback
    assert "grade=grade" in src or "grade = grade" in src or ", grade" in src, \
        "parametric generator not given the requested grade"


def test_parametric_math_covers_all_grades():
    src = _read("backend/scrapers/hunter/parametric.py")
    for g in range(1, 12):
        assert f"grade == {g}" in src, f"parametric math missing grade {g}"
    # Grade 12 is the final else branch (see asymptote/logarithm/integral modes)
    assert "Grade 12" in src, "parametric math missing grade 12 branch"


# Behavior tests: loigiaihay EXAM-listing URLs (de-thi-...-cNNN.html) must use
# the IDs verified live (urllib HTTP 200, 2026-10-11). The old chapter-listing
# pages (toan-lop-2-c122.html) list 2062/2064 doc-hieu van links — NOT math
# exams — so the crawler targets exam listings instead.
def test_build_loigiaihay_url_uses_verified_ids():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import build_loigiaihay_url
    assert build_loigiaihay_url("math", 2) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-toan-lop-2-ket-noi-tri-thuc-c1212.html"
    assert build_loigiaihay_url("math", 5) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-toan-lop-5-ket-noi-tri-thuc-c1990.html"
    assert build_loigiaihay_url("vietnamese", 2) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-tieng-viet-lop-2-ket-noi-tri-thuc-c1213.html"
    assert build_loigiaihay_url("vietnamese", 5) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-tieng-viet-lop-5-ket-noi-tri-thuc-c1994.html"
    assert build_loigiaihay_url("english", 3) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-tieng-anh-lop-3-global-success-c1218.html"
    assert build_loigiaihay_url("english", 2) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-tieng-anh-lop-2-ket-noi-tri-thuc-c1217.html"
    assert build_loigiaihay_url("vietnamese", 1) is None  # no TV grade-1 section on site
    assert build_loigiaihay_url("english", 1) is None  # no EN grade-1 exam listing


def test_grade_source_urls_use_verified_loigiaihay():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import get_grade_source_urls
    got = get_grade_source_urls(2)
    urls = [s["url"] for cat in got["categories"] for s in cat["sources"]]
    assert "https://loigiaihay.com/de-thi-de-kiem-tra-toan-lop-2-ket-noi-tri-thuc-c1212.html" in urls
    assert "https://loigiaihay.com/de-thi-de-kiem-tra-tieng-viet-lop-2-ket-noi-tri-thuc-c1213.html" in urls


LOIGIAIHAY_EXAM_HTML = (
    '<div class="question c690326572c93bf862d7fbdc3">'
    '<div class="question-content"><div class="question-content-inner">'
    '<strong class="question-index-number">Câu 1 : </strong>'
    '<p>Số gồm 6 chục và 7 đơn vị được viết là:</p></div></div>'
    '<ul class="dapan rows-4">'
    '<li><span class="span-answer">A.</span><div>76</div></li>'
    '<li><span class="span-answer">B.</span><div>67</div></li>'
    '<li><span class="span-answer">C.</span><div>70</div></li>'
    '<li><span class="span-answer">D.</span><div>60</div></li></ul>'
    '<div class="loigiai"><p><b>Đáp án : B</b></p>'
    '<div class="solution-detail"><div class="solution-detail-title">Lời giải chi tiết : </div>'
    '<div><p>Số gồm 6 chục và 7 đơn vị được viết là: 67</p></div></div></div>'
    '</div>'
)


def test_parse_loigiaihay_extracts_question_answer_explanation():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.parsing import parse_loigiaihay_questions
    out = parse_loigiaihay_questions(LOIGIAIHAY_EXAM_HTML, source_url="https://loigiaihay.com/x-a1.html")
    assert len(out) == 1
    q = out[0]
    assert "6 chục" in q["content_text"]
    assert len(q["options"]) == 4
    assert q["correct_answer"] == "B"
    assert "67" in q["explanation"]
    assert q["source_platform"] == "loigiaihay"


def test_fetch_dispatches_loigiaihay_to_dedicated_parser():
    src = _read("backend/scrapers/hunter/fetch.py")
    assert "parse_loigiaihay_questions" in src, \
        "fetch.py must route loigiaihay URLs to parse_loigiaihay_questions (not generic crawler)"


def test_hunter_package_exports_loigiaihay_parser():
    src = _read("backend/scrapers/hunter/__init__.py")
    assert "parse_loigiaihay_questions" in src


def test_filter_loigiaihay_prefers_same_subject_grade_links():
    # Category toan-lop-2 lists exams of MANY grades + sidebar junk.
    # The crawler must prefer links matching the category's own subject+grade.
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.fetch import filter_loigiaihay_detail_urls
    urls = [
        "/doc-hieu-10-quy-luat-cuoc-song-a194873.html",
        "/de-kiem-tra-giua-hoc-ki-1-toan-2-ket-noi-tri-thuc-de-so-2-a188977.html",
        "/de-thi-de-kiem-tra-toan-lop-11-ket-noi-tri-thuc-c1623.html",
        "/de-kiem-tra-giua-hoc-ki-1-toan-2-ket-noi-tri-thuc-de-so-1-a188976.html",
    ]
    out = filter_loigiaihay_detail_urls(
        urls, "https://loigiaihay.com/toan-lop-2-c122.html")
    assert out[0].endswith("toan-2-ket-noi-tri-thuc-de-so-1-a188976.html")
    assert out[1].endswith("toan-2-ket-noi-tri-thuc-de-so-2-a188977.html")
    assert all("doc-hieu" not in u and "lop-11" not in u for u in out[:2])


def test_filter_loigiaihay_rejects_other_grade_markers():
    # '-2-' inside 'doan-2-luyen' must NOT count as grade-2 evidence;
    # a van-12 link must rank below a toan-2 link for the toan-lop-2 category.
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.fetch import filter_loigiaihay_detail_urls
    urls = [
        "/doc-hieu-21-bai-hoc-cua-the-ki-21-doan-2-luyen-de-doc-hieu-van-12-a192379.html",
        "/de-kiem-tra-giua-hoc-ki-1-toan-2-ket-noi-tri-thuc-de-so-1-a188976.html",
    ]
    out = filter_loigiaihay_detail_urls(
        urls, "https://loigiaihay.com/toan-lop-2-c122.html")
    assert out[0].endswith("toan-2-ket-noi-tri-thuc-de-so-1-a188976.html"), out


def test_parse_loigiaihay_dedups_repeated_blocks_prefers_answer_key():
    # Live pages repeat the exam twice: first pass has no .loigiai, second does.
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.parsing import parse_loigiaihay_questions
    no_key = LOIGIAIHAY_EXAM_HTML.replace(
        '<div class="loigiai"><p><b>Đáp án : B</b></p>', '<div class="loigiai"><p><b>Đề bài</b></p>')
    out = parse_loigiaihay_questions(no_key + LOIGIAIHAY_EXAM_HTML,
                                     source_url="https://loigiaihay.com/x-a1.html")
    assert len(out) == 1
    assert out[0]["correct_answer"] == "B"


# Expansion 2026-10-12 — verified live (urllib HTTP 200):
# - vietjack bo-de-thi / bai-tap trac-nghiem toan 1-5 (.jsp, 43 cau + dap an)
# - loigiaihay TV2-c2270 + TA2-c1327 (song song voi c1213/c1217: de ket-noi vs
#   global-success — 2 bo sach khac nhau, ca 2 deu song)
def test_grade_source_urls_include_vietjack_exam_packs():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import get_grade_source_urls
    for grade in (1, 2, 3, 4, 5):
        got = get_grade_source_urls(grade)
        urls = [s["url"] for cat in got["categories"] for s in cat["sources"]]
        assert any("vietjack.com" in u and f"lop-{grade}" in u for u in urls), \
            f"grade {grade} missing vietjack exam-pack URL"


def test_build_loigiaihay_url_covers_both_textbook_sets():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import build_loigiaihay_url
    # grade 2 has TWO live listings (ket-noi c1213/c1217 + alternates c2270/c1327)
    assert build_loigiaihay_url("vietnamese", 2) is not None
    assert build_loigiaihay_url("english", 2) is not None


# VietJack .jsp fixture (verbatim structure from live page
# de-thi-giua-ki-1-toan-lop-2-chan-troi-sang-tao.jsp, 2026-10-12):
# stem in <p><strong>Cau N:</strong>...</p>, options in sibling <p>A/B/C/D.</p>,
# answer key in a <table> (header row Cau 1..N, second row letters).
VIETJACK_EXAM_HTML = (
    '<p><strong>Câu 1:</strong> Số gồm 6 chục và 7 đơn vị được viết là:</p>'
    '<p>A. 76</p><p>B. 67</p><p>C. 70</p><p>D. 60</p>'
    '<p><strong>Câu 2:</strong> Điền số thích hợp vào chỗ chấm: 54 = 50 + .....</p>'
    '<p>A. 4</p><p>B. 5</p><p>C. 50</p><p>D. 40</p>'
    '<h3><strong>I. Trắc nghiệm: 4 điểm (mỗi câu đúng được 0,5 điểm)</strong></h3>'
    '<table border="1" cellpadding="5" cellspacing="0" class="table table-bordered"><tbody>'
    '<tr><td><strong>Câu 1</strong></td><td><strong>Câu 2</strong></td></tr>'
    '<tr><td><strong>B</strong></td><td><strong>A</strong></td></tr>'
    '</tbody></table>'
)


def test_parse_vietjack_extracts_question_answer_key():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.parsing import parse_vietjack_questions
    out = parse_vietjack_questions(
        VIETJACK_EXAM_HTML,
        source_url="https://vietjack.com/de-kiem-tra-lop-2/de-thi-giua-ki-1-toan-lop-2-chan-troi-sang-tao.jsp")
    assert len(out) == 2, out
    assert "6 chục" in out[0]["content_text"]
    assert len(out[0]["options"]) == 4
    assert out[0]["correct_answer"] == "B"
    assert out[1]["correct_answer"] == "A"
    assert out[0]["source_platform"] == "vietjack"


def test_fetch_dispatches_vietjack_to_dedicated_parser():
    src = _read("backend/scrapers/hunter/fetch.py")
    assert "parse_vietjack_questions" in src, \
        "fetch.py must route vietjack URLs to parse_vietjack_questions (not generic crawler)"


def test_hunter_package_exports_vietjack_parser():
    src = _read("backend/scrapers/hunter/__init__.py")
    assert "parse_vietjack_questions" in src
