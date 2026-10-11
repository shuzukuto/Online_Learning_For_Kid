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
from backend.scrapers.hunter.fetch import fetch_questions_from_web_url
from backend.scrapers.hunter.parametric import generate_parametric_questions
from backend.scrapers.hunter.sources import (
    GRADE2_MATH_EN_POOLS, GRADE2_MATH_OLYMPIAD_POOLS, GRADE2_MATH_VN_POOLS,
    OPEN_EXAM_REPOSITORY,
)


async def run_internet_question_hunter(
    subject: str = "all",
    grade: int = 5,
    custom_url: Optional[str] = None,
    custom_urls: Optional[List[str]] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Automated Internet Question Hunter:
    Fetches open questions across Internet sources by subject and grade,
    supporting custom target URLs, generating fresh parametric items,
    classifying questions, and saving clean, non-duplicate questions into the database.
    """
    from backend.database import get_connection, find_duplicate_question_id, resequence_question_numbers

    collected = []
    urls_to_scrape = []
    if custom_url and custom_url.strip():
        urls_to_scrape.append(custom_url.strip())
    if custom_urls:
        for u in custom_urls:
            if u and u.strip() and u.strip() not in urls_to_scrape:
                urls_to_scrape.append(u.strip())
                
    # 1. Scrape all targeted URLs
    for target_url in urls_to_scrape:
        web_q = await fetch_questions_from_web_url(target_url)
        for q in web_q:
            if grade and grade > 0:
                q["grade"] = grade
            if subject and subject != "all":
                q["subject"] = subject
        collected.extend(web_q)
        
    # 2. Harvest from curated repository and generate dynamic curriculum/Olympiad questions
    target_subjects = ["math", "vietnamese", "english", "science", "informatics"] if subject == "all" else [subject]
    for sub in target_subjects:
        # Pull static repository items
        pool = OPEN_EXAM_REPOSITORY.get(sub, [])
        for item in pool:
            if not grade or item.get("grade") == grade or subject != "all":
                q = dict(item)
                q["id"] = f"hunter_{sub}_{uuid.uuid4().hex[:8]}"
                q["source_platform"] = "internet_hunter"
                q["source_url"] = item.get("source_url") or "https://khoade.edu.vn"
                if not q.get("source_detail"):
                    from backend.database import compute_source_detail
                    q["source_detail"] = compute_source_detail(q)
                if grade and grade > 0:
                    q["grade"] = grade
                collected.append(q)

        # Specialized harvest for Grade 2 Math (English + Vietnamese + Olympic)
        if sub == "math" and grade == 2:
            for g2_pool, def_detail, def_plat in [
                (GRADE2_MATH_VN_POOLS, "VioEdu (FPT)", "vioedu"),
                (GRADE2_MATH_EN_POOLS, "K5 Learning (US Math)", "k5learning"),
                (GRADE2_MATH_OLYMPIAD_POOLS, "Olympic Kangaroo (IKMC)", "kangaroo")
            ]:
                for item in g2_pool:
                    q = dict(item)
                    q["id"] = f"g2_math_{uuid.uuid4().hex[:8]}"
                    q["source_platform"] = def_plat
                    q["source_detail"] = item.get("source_detail") or def_detail
                    q["source_url"] = item.get("source_url") or "https://k5learning.com"
                    q["grade"] = 2
                    q["subject"] = "math"
                    collected.append(q)
                
        # Generate fresh parametric questions to guarantee non-empty harvest
        param_count = 6 if subject != "all" else 3
        generated = generate_parametric_questions(subject=sub, grade=grade or 5, count=param_count)
        collected.extend(generated)
            
    # 3. Normalize and Save into Database with cross-check against DB
    new_saved_count = 0
    skipped_dupe_count = 0
    skipped_invalid_count = 0
    
    conn = get_connection()
    cursor = conn.cursor()
    for q_data in collected:
        # Strict validation before even touching DB
        is_valid, reason = is_valid_question_payload(q_data)
        if not is_valid:
            skipped_invalid_count += 1
            continue

        content_text = (q_data.get("content_text") or "").strip()
        is_dupe = bool(find_duplicate_question_id(cursor, content_text))
        if is_dupe:
            skipped_dupe_count += 1
        else:
            norm = await normalize_question_payload(q_data)
            # Re-verify after normalization
            is_valid_norm, _ = is_valid_question_payload(norm)
            if is_valid_norm:
                insert_or_update_question(norm)
                new_saved_count += 1
            else:
                skipped_invalid_count += 1

    # Resequence question numbers so IDs 1..N remain consecutive
    if new_saved_count > 0:
        resequence_question_numbers(cursor)
        conn.commit()
    conn.close()
        
    msg = f"Tự động săn câu hỏi Internet: Đã lưu {new_saved_count} câu mới"
    if skipped_dupe_count > 0:
        msg += f" (Bỏ qua {skipped_dupe_count} câu đã có trong CSDL)"
    if skipped_invalid_count > 0:
        msg += f" (Loại bỏ {skipped_invalid_count} câu không đạt chuẩn)"
    msg += f" [Môn: {subject.upper()}, Lớp {grade}]"

    log_collector_event(
        platform="internet_hunter",
        status="success",
        message=msg,
        count=new_saved_count
    )
    
    return {
        "success": True,
        "subject": subject,
        "grade": grade,
        "total_harvested": len(collected),
        "new_saved": new_saved_count,
        "skipped_duplicates": skipped_dupe_count,
        "skipped_invalid": skipped_invalid_count,
        "questions": collected[:limit]
    }
