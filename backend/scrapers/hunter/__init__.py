"""EduQuest Pro — internet_hunter package (tach tu backend/scrapers/internet_hunter.py, P1.1).
Giu nguyen import cu: backend/scrapers/internet_hunter.py la shim re-export tu day."""
from __future__ import annotations

from backend.scrapers.hunter.sources import (
    OPEN_EXAM_REPOSITORY,
    HANHTRANGSO_CURRICULUM_POOLS,
    CODEMATH_OLYMPIAD_POOLS,
    GRADE2_MATH_VN_POOLS,
    GRADE2_MATH_EN_POOLS,
    GRADE2_MATH_OLYMPIAD_POOLS,
    extract_grade_from_url,
    get_grade_source_urls,
)

from backend.scrapers.hunter.parametric import (
    _make_choice_question,
    generate_parametric_questions,
)

from backend.scrapers.hunter.parsing import (
    parse_unstructured_questions,
)

from backend.scrapers.hunter.fetch import (
    fetch_questions_from_web_url,
)

from backend.scrapers.hunter.runner import (
    run_internet_question_hunter,
)
