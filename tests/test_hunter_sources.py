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


def test_vietjack_filter_matches_toan_grade_slug_and_trac_nghiem():
    # Upper-grade trac-nghiem links use toan-{grade}-kn/... (no "lop-12"),
    # e.g. ../toan-12-kn/trac-nghiem-bai-1-....jsp (verified live 2026-10-12).
    src = _read("backend/scrapers/hunter/fetch.py")
    assert "toan-{grade}" in src, "grade pattern misses toan-{grade} slug family"
    assert "trac-nghiem" in src, "link filter misses bare trac-nghiem pages"
    assert r"(?:/|\.\./)" in src or "../" in src, \
        "link regex misses relative ../ sibling links used by upper-grade hubs"


def test_vietjack_relative_parent_link_resolves_one_level_up():
    # "../de-kiem-tra-lop-12/x.jsp" seen from
    # https://vietjack.com/toan-12-kn/trac-nghiem-toan-lop-12.jsp must resolve
    # to https://vietjack.com/de-kiem-tra-lop-12/x.jsp (urljoin semantics) —
    # naive base_dir + "/" + e[3:] lands in /toan-12-kn/... (404).
    from urllib.parse import urljoin
    base = "https://vietjack.com/toan-12-kn/trac-nghiem-toan-lop-12.jsp"
    assert urljoin(base, "../de-kiem-tra-lop-12/de-kiem-tra-toan-12.jsp") == \
        "https://vietjack.com/de-kiem-tra-lop-12/de-kiem-tra-toan-12.jsp"
    src = _read("backend/scrapers/hunter/fetch.py")
    assert "urljoin" in src, "vietjack handler must use urljoin for ../ links"


def test_vietjack_same_grade_prefers_same_subject():
    # VJ12 trac hub lists 60 same-grade links incl. de-cuong hoa/van; the
    # 8-URL budget was eaten by wrong subjects (E2E TOTAL 0, 2026-10-12).
    # Hub/listing pages (de-cuong/de-thi tong-hop) have stems but NO key;
    # leaf trac-nghiem-bai-N pages carry "Đáp án đúng là: X" — rank them first.
    src = _read("backend/scrapers/hunter/fetch.py")
    assert "same_grade.sort" in src or "same-subject" in src or \
        "subj" in src, "same-grade links must prefer the hub subject"
    assert "trac-nghiem-(bai|chuong|tuan)" in src, \
        "leaf trac-nghiem pages (with answer keys) must rank before hub pages"


# Grade 6-12 exam pages use a NEW layout (verified DOM 2026-10-12, a120884):
# stem+options inline in one <p> ("Câu 1: ... A. ... B. ... C. ... D. ..."),
# key in a <table> of "<N>. <X>" cells, solutions as "<p><strong>Câu N</strong></p>
# ... <p><strong>Chọn X.</strong></p>". The old div.question parser yields 0.
LOIGIAIHAY_UPPER_HTML = (
    '<div class="box-question" id="sub-question-1">'
    '<p><strong>Câu 1</strong><strong>:</strong> Cho tập hợp M các tháng có 31 ngày. '
    'Phần tử không thuộc M là</p>'
    '<p><strong>A.</strong> Tháng 5 <strong>B.</strong> Tháng 6 '
    '<strong>C.</strong> Tháng 7 <strong>D.</strong> Tháng 8.</p>'
    '<p><strong>Câu 2</strong><strong>:</strong> Tập hợp các chữ cái trong từ TOÁN 6 là</p>'
    '<p><strong>A.</strong> {T;O;A;N;6} <strong>B.</strong> {T;O;A;N} '
    '<strong>C.</strong> {T;A;N} <strong>D.</strong> {T;O;A;N;S;U}.</p>'
    '</div>'
    '<div class="box-question" id="sub-question-2">'
    '<p id="question-title-idx-2"><strong>Lời giải</strong></p>'
    '<table><tbody><tr><td><p><strong>1. B</strong></p></td>'
    '<td><p><strong>2. B</strong></p></td></tr></tbody></table>'
    '<p><strong>Câu 1</strong></p><p><strong>Phương pháp:</strong></p>'
    '<p>Dùng quy ước bàn tay.</p><p><strong>Cách giải:</strong></p>'
    '<p>Tháng 6 có 30 ngày.</p><p><strong>Chọn B.</strong></p>'
    '<p><strong>Câu 2</strong></p><p><strong>Phương pháp:</strong></p>'
    '<p>Liệt kê duy nhất 1 lần.</p><p><strong>Cách giải:</strong></p>'
    '<p>Số 6 không phải chữ cái.</p><p><strong>Chọn B.</strong></p>'
    '</div>'
)


def test_parse_loigiaihay_upper_layout_extracts_key_and_explanation():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.parsing import parse_loigiaihay_questions
    out = parse_loigiaihay_questions(
        LOIGIAIHAY_UPPER_HTML,
        source_url="https://loigiaihay.com/de-kiem-tra-giua-hoc-ki-1-toan-6-de-so-1-a120884.html",
    )
    assert len(out) == 2, f"expected 2 questions, got {len(out)}"
    by_num = {q["content_text"][:20]: q for q in out}
    q1 = next(q for q in out if "31 ngày" in q["content_text"])
    assert len(q1["options"]) == 4
    assert q1["correct_answer"] == "B", f"got {q1['correct_answer']}"
    assert "bàn tay" in q1["explanation"], f"got {q1['explanation'][:60]!r}"
    q2 = next(q for q in out if "TOÁN 6" in q["content_text"])
    assert q2["correct_answer"] == "B"
    assert q1["grade"] == 6


def test_hunter_package_exports_loigiaihay_parser():
    src = _read("backend/scrapers/hunter/__init__.py")
    assert "parse_loigiaihay_questions" in src


# EN grade 6-12 exercise pages (verified DOM 2026-10-12, a154048): no
# div.question blocks — "Exercise N|instruction|1. stem|A. a B. b C. c D. d|
# ...|Đáp án: |1. X|2. Y|..." with numbered inline options and a
# "Đáp án: |<num>. <letter>|" key per exercise.
LOIGIAIHAY_EN_EXERCISE_HTML = (
    '<div class="box-question" id="sub-question-2">'
    '<p id="question-title-idx-2"><strong>Lời giải</strong></p>'
    '<p>Exercise 3|Choose the correct preposition.|'
    '1. There is a clock _______ the wall in class.|'
    'A. near B. across C. on D. at|'
    '2. Where is Susan? She is sitting _______ Jim.|'
    'A. on B. under C. between D. next to|'
    'Đáp án: | | |1. C| |2. D| | |</p>'
    '</div>'
)


def test_parse_loigiaihay_english_exercise_layout():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.parsing import parse_loigiaihay_questions
    out = parse_loigiaihay_questions(
        LOIGIAIHAY_EN_EXERCISE_HTML,
        source_url="https://loigiaihay.com/de-cuong-on-tap-hk1-tieng-anh-6-a154048.html",
    )
    assert len(out) == 2, f"expected 2 questions, got {len(out)}"
    q1 = next(q for q in out if "clock" in q["content_text"])
    assert len(q1["options"]) == 4
    assert q1["correct_answer"] == "C", f"got {q1['correct_answer']}"
    q2 = next(q for q in out if "Susan" in q["content_text"])
    assert q2["correct_answer"] == "D"
    assert q1["grade"] == 6
    assert "anh" in q1["subject"] or "english" in q1["subject"], q1["subject"]


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


# Upper-grade trac-nghiem pages (verified DOM 2026-10-12,
# toan-12-kn/trac-nghiem-bai-1...): NO key table; the key lives inline as
# "Đáp án đúng là: X" inside the solution text after "Hiển thị đáp án".
VIETJACK_SOLUTION_KEY_HTML = (
    '<p><strong><span>Câu 1. </span></strong>'
    '<span>Cho hàm số y = f(x). Hàm số đã cho đồng biến trên khoảng nào?</span></p>'
    '<p>A. (-2; 2).</p><p>B. (0; 2).</p><p>C. (-1; 1).</p><p>D. (1; 2).</p>'
    '<section>Hiển thị đáp án Đáp án đúng là: D - Xét đáp án A, trên khoảng '
    '(-2; 2) có đoạn đi xuống nên loại. Xét đáp án D, đồ thị đi lên nên chọn.</section>'
)


def test_parse_vietjack_reads_inline_solution_key():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.parsing import parse_vietjack_questions
    out = parse_vietjack_questions(
        VIETJACK_SOLUTION_KEY_HTML,
        source_url="https://vietjack.com/toan-12-kn/trac-nghiem-bai-1-tinh-don-dieu.jsp")
    assert len(out) == 1, out
    assert out[0]["correct_answer"] == "D", out[0]


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


# Expansion 2026-10-12b — LGH exam listings grades 6-12 + VietJack 6/9
# (all verified urllib HTTP 200; homepage hrefs harvested, no guessing).
def test_build_loigiaihay_url_covers_grades_6_to_12():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import build_loigiaihay_url
    assert build_loigiaihay_url("math", 6) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-toan-lop-6-ket-noi-tri-thuc-c1022.html"
    assert build_loigiaihay_url("math", 9) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-toan-lop-9-ket-noi-tri-thuc-c1984.html"
    assert build_loigiaihay_url("math", 12) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-toan-lop-12-ket-noi-tri-thuc-c1964.html"
    assert build_loigiaihay_url("english", 6) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-tieng-anh-lop-6-global-success-c1160.html"
    assert build_loigiaihay_url("english", 10) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-tieng-anh-lop-10-global-success-c1192.html"
    assert build_loigiaihay_url("math", 10) is not None  # trac-nghiem set
    assert build_loigiaihay_url("vietnamese", 6) is None  # no verified VN-6 listing


def test_grade_source_urls_include_vietjack_upper_grades():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import get_grade_source_urls
    for grade in (6, 9):
        got = get_grade_source_urls(grade)
        urls = [s["url"] for cat in got["categories"] for s in cat["sources"]]
        assert any("vietjack.com" in u for u in urls), \
            f"grade {grade} missing vietjack URL"


def test_grade_source_urls_6_to_12_have_lgh_listings():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import get_grade_source_urls
    for grade in (6, 7, 8, 9, 11, 12):
        got = get_grade_source_urls(grade)
        urls = [s["url"] for cat in got["categories"] for s in cat["sources"]]
        assert any("loigiaihay.com" in u for u in urls), \
            f"grade {grade} missing loigiaihay listing URL"


# Expansion 2026-10-12c — Van trac-nghiem hubs 6/7/8/10/11, Van 12 de-thi,
# EN trac-nghiem 12 (all verified urllib HTTP 200 with matching titles).
def test_van_and_en_upper_grades_have_verified_listings():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import (
        build_loigiaihay_url, get_grade_source_urls,
        LOIGIAIHAY_VN_TRACNGHIEM,
    )
    assert build_loigiaihay_url("vietnamese", 12) == \
        "https://loigiaihay.com/de-thi-de-kiem-tra-van-12-ket-noi-tri-thuc-c1972.html"
    assert build_loigiaihay_url("english", 12) == \
        "https://loigiaihay.com/v2/tu-luyen-trac-nghiem-tieng-anh-12-global-success-c1907.html"
    assert set(LOIGIAIHAY_VN_TRACNGHIEM) == {6, 7, 8, 10, 11}
    for grade in (6, 7, 8, 10, 11, 12):
        got = get_grade_source_urls(grade)
        vn_urls = [s["url"] for cat in got["categories"]
                   for s in cat["sources"] if cat["id"] == "vietnamese"]
        assert any("loigiaihay.com" in u for u in vn_urls), \
            f"grade {grade} vietnamese missing loigiaihay URL"
    got12 = get_grade_source_urls(12)
    en_urls = [s["url"] for cat in got12["categories"]
               for s in cat["sources"] if cat["id"] == "english"]
    assert any("c1907" in u for u in en_urls), "grade 12 english missing trac-nghiem URL"


# Expansion 2026-10-12d — VietJack exam-pack + trac-nghiem 7/8/10/11/12,
# OLM lop-{7,8,10,11,12} (all verified urllib HTTP 200).
def test_vietjack_and_olm_cover_upper_grades():
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from backend.scrapers.hunter.sources import (
        get_grade_source_urls, VIETJACK_EXAM_PACKS_UPPER, VIETJACK_TRACNGHIEM,
    )
    assert VIETJACK_EXAM_PACKS_UPPER[7] == \
        "https://vietjack.com/de-kiem-tra-lop-7/de-kiem-tra-toan-7.jsp"
    assert VIETJACK_EXAM_PACKS_UPPER[12] == \
        "https://vietjack.com/de-kiem-tra-lop-12/de-kiem-tra-toan-12.jsp"
    assert VIETJACK_TRACNGHIEM[10] == \
        "https://vietjack.com/toan-10-kn/trac-nghiem-toan-lop-10-ket-noi.jsp"
    assert VIETJACK_TRACNGHIEM[12] == \
        "https://vietjack.com/toan-12-kn/trac-nghiem-toan-lop-12.jsp"
    for grade in (7, 8, 10, 11, 12):
        got = get_grade_source_urls(grade)
        urls = [s["url"] for cat in got["categories"] for s in cat["sources"]]
        assert any("vietjack.com" in u for u in urls), \
            f"grade {grade} missing vietjack URL"
        assert f"https://olm.vn/lop-{grade}" in urls, \
            f"grade {grade} missing verified OLM url"
