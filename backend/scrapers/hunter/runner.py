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
    grade: Any = 5,
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
    # Sequential Crawling across all Grades 1 to 12 when grade is 'all'
    if str(grade).lower() in ("all", "0", "tat_ca"):
        total_new_saved = 0
        total_skipped_dupes = 0
        total_harvested = 0
        all_sources_scraped = []
        all_source_reports = []
        grade_results = {}

        for g in range(1, 13):
            res_g = await run_internet_question_hunter(
                subject=subject,
                grade=g,
                custom_url=custom_url,
                custom_urls=custom_urls,
                limit=limit
            )
            g_new = res_g.get("new_saved", 0)
            g_dupes = res_g.get("skipped_duplicates", 0)
            total_new_saved += g_new
            total_skipped_dupes += g_dupes
            total_harvested += res_g.get("total_harvested", 0)
            for s in res_g.get("sources_scraped", []):
                if s not in all_sources_scraped:
                    all_sources_scraped.append(s)
            for rep in res_g.get("sources_report", []):
                if not any(r.get("url") == rep.get("url") for r in all_source_reports):
                    all_source_reports.append(rep)
            grade_results[f"grade_{g}"] = {
                "grade": g,
                "new_saved": g_new,
                "skipped_duplicates": g_dupes,
                "total_harvested": res_g.get("total_harvested", 0)
            }
            await asyncio.sleep(0.15)

        return {
            "success": True,
            "grade": "all",
            "subject": subject,
            "total_harvested": total_harvested,
            "new_saved": total_new_saved,
            "skipped_duplicates": total_skipped_dupes,
            "sources_scraped": all_sources_scraped,
            "sources_report": all_source_reports,
            "grade_breakdown": grade_results,
            "message": f"Đã cào tuần tự từ Khối 1 đến Khối 12: Lưu {total_new_saved} câu mới ({total_skipped_dupes} câu trùng lặp)."
        }
    from backend.database import get_connection, find_duplicate_question_id, resequence_question_numbers

    collected = []
    urls_to_scrape = []
    if custom_url and custom_url.strip():
        urls_to_scrape.append(custom_url.strip())
    if custom_urls:
        for u in custom_urls:
            if u and u.strip() and u.strip() not in urls_to_scrape:
                urls_to_scrape.append(u.strip())
                
    # 0. Tự động nạp các nguồn mở uy tín theo khối lớp từ catalog nếu danh sách URL trống
    if not urls_to_scrape:
        from backend.scrapers.hunter.sources import get_grade_source_urls
        catalog = get_grade_source_urls(grade or 5)
        categories = catalog.get("categories", [])
        if subject in ("english", "vietnamese"):
            categories = sorted(categories, key=lambda c: 0 if c.get("id") == subject else 1)
        for cat in categories:
            for s in cat.get("sources", []):
                u = s.get("url")
                stype = (s.get("type") or "").strip().lower()
                if u and stype not in ("interactive",) and u not in urls_to_scrape:
                    urls_to_scrape.append(u)
                    if len(urls_to_scrape) >= 3:
                        break
            if len(urls_to_scrape) >= 4:
                break

    # 1. Scrape all targeted URLs
    from urllib.parse import urlparse
    import time as _time
    source_reports = []

    for target_url in urls_to_scrape:
        start_t = _time.perf_counter()
        parsed_host = urlparse(target_url).hostname or target_url
        try:
            web_q = await fetch_questions_from_web_url(target_url)
            dur_ms = int((_time.perf_counter() - start_t) * 1000)
            q_found = len(web_q)
            for q in web_q:
                # Chỉ điền khi parser chưa gán (URL như olm.vn/lop-9 trả grade
                # mặc định 5, k5/ixl grade-2...). Ép đè bừa làm 1887 câu lạc
                # grade (hunter_math_g2_* nằm ở grade 6/9/12).
                if grade and grade > 0 and not q.get("grade"):
                    q["grade"] = grade
                if subject and subject != "all" and not q.get("subject"):
                    q["subject"] = subject
            collected.extend(web_q)
            source_reports.append({
                "url": target_url,
                "name": parsed_host,
                "status": "success" if q_found > 0 else "empty",
                "status_code": 200,
                "latency_ms": dur_ms,
                "questions_found": q_found,
                "message": f"Thu được {q_found} câu hỏi" if q_found > 0 else "Kết nối thành công nhưng chưa tìm thấy câu hỏi"
            })
        except Exception as e:
            dur_ms = int((_time.perf_counter() - start_t) * 1000)
            source_reports.append({
                "url": target_url,
                "name": parsed_host,
                "status": "error",
                "status_code": 500,
                "latency_ms": dur_ms,
                "questions_found": 0,
                "message": f"Lỗi cào nguồn: {str(e)[:120]}"
            })
        
    # 2. Harvest from curated repository and generate dynamic curriculum/Olympiad questions
    target_subjects = ["math", "vietnamese", "english", "science", "informatics"] if subject == "all" else [subject]
    for sub in target_subjects:
        # Pull static repository items (chỉ lấy đúng grade được yêu cầu —
        # pool mở nhiều khối, ép grade bừa sẽ làm lạc grade như G2→G9).
        pool = OPEN_EXAM_REPOSITORY.get(sub, [])
        for item in pool:
            if grade and item.get("grade") not in (None, grade):
                continue
            q = dict(item)
            q["id"] = f"hunter_{sub}_{uuid.uuid4().hex[:8]}"
            q["source_platform"] = "internet_hunter"
            q["source_url"] = item.get("source_url") or "https://khoade.edu.vn"
            if not q.get("source_detail"):
                from backend.database import compute_source_detail
                q["source_detail"] = compute_source_detail(q)
            if grade and grade > 0:
                q["grade"] = grade
            q["subject"] = sub
            collected.append(q)

        # Specialized harvest for Grade 2 Math (English + Vietnamese + Olympic)
        if grade == 2 and (subject == "all" or subject == "math"):
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
        param_count = 12 if subject != "all" else 6
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
                # insert_or_update_question() trả về dupe_id khi câu đã có
                # (DB không tăng). Chỉ đếm new_saved khi id trả về trùng
                # id vừa gửi — ngược lại là đếm ảo.
                rid = insert_or_update_question(norm)
                if rid == norm.get("id"):
                    new_saved_count += 1
                else:
                    skipped_dupe_count += 1
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
        "total_harvested": new_saved_count,
        "total_found": len(collected),
        "new_saved": new_saved_count,
        "skipped_duplicates": skipped_dupe_count,
        "skipped_invalid": skipped_invalid_count,
        "sources_scraped": urls_to_scrape,
        "sources_report": source_reports,
        "questions": collected[:limit]
    }
