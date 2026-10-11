from __future__ import annotations
import asyncio
import httpx
import math
import random
import re
import uuid
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from backend.classifier import classify_subject
from backend.database import insert_or_update_question, log_collector_event
from backend.normalizer import is_valid_question_payload, normalize_question_payload
from backend.scrapers.hunter import (
    OPEN_EXAM_REPOSITORY,
    HANHTRANGSO_CURRICULUM_POOLS,
    CODEMATH_OLYMPIAD_POOLS,
    GRADE2_MATH_VN_POOLS,
    GRADE2_MATH_EN_POOLS,
    GRADE2_MATH_OLYMPIAD_POOLS,
    extract_grade_from_url,
    get_grade_source_urls,
    _make_choice_question,
    generate_parametric_questions,
    parse_unstructured_questions,
    fetch_questions_from_web_url,
    run_internet_question_hunter,
)
