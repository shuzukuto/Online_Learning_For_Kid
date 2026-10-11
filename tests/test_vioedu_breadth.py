"""RED-phase tests for VioEdu breadth expansion (Toan + TV + Anh, grade focus 2).

Covers:
1. VIOEDU_SUBJECTS maps all 3 subjects with verified subjectIds.
2. parse_vioedu_question_data honors subject + topic params (no hard-coded math).
3. Crawler iterates the FULL discovered skill list (not [:3]/[:4]).
4. Explanation/solution merging helper keeps loi giai from GraphQL result packet.
"""
import re


def _read_vioedu():
    with open("backend/scrapers/vioedu.py", encoding="utf-8") as f:
        return f.read()


def test_subject_map_has_all_three():
    src = _read_vioedu()
    assert "61e520ada47228001dfedb6b" in src, "missing Tieng Viet subjectId"
    assert "66b96da2a1d5fb632d7aedab" in src, "missing Tieng Anh subjectId"
    assert "5b59371949ce6e0015c74cd9" in src, "missing Toan subjectId"


def test_parse_honors_subject_param():
    src = _read_vioedu()
    m = re.search(r"def parse_vioedu_question_data\((.*?)\)", src)
    assert m, "parse_vioedu_question_data not found"
    assert "subject" in m.group(1), "parse must accept a subject parameter"


def test_no_hardcoded_math_subject():
    src = _read_vioedu()
    m = re.search(r"def parse_vioedu_question_data\(.*?\):(.*?)(?=\n# -{10,}|\ndef |\nasync def )", src, re.S)
    assert m, "parse body not found"
    assert '"subject": "math"' not in m.group(1) and "'subject': 'math'" not in m.group(1), \
        "subject still hard-coded to math inside parse"


def test_crawler_covers_full_skill_list():
    src = _read_vioedu()
    assert "discovered[:4]" not in src and "discovered[:3]" not in src, \
        "crawler still truncates skill list to first 3-4 skills"


def test_explanation_merge_helper_exists():
    src = _read_vioedu()
    assert "def merge_vioedu_explanation" in src, "missing merge_vioedu_explanation helper"
