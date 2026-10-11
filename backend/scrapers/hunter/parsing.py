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
from backend.scrapers.hunter.sources import extract_grade_from_url


def parse_unstructured_questions(text: str, source_url: str = "") -> List[Dict[str, Any]]:
    """
    Parses questions and multiple choice options from raw text commonly pasted
    from Facebook educational groups, online forums, or unformatted blogs.
    Strips HTML tags, removes header/footer/sidebar/contact boilerplate,
    and strictly rejects non-question text (blog posts, articles, contact info).
    """
    results = []
    if not text:
        return results

    # 1. Clean HTML tags safely first using BeautifulSoup
    if "<" in text and ">" in text:
        try:
            soup = BeautifulSoup(text, "html.parser")
            # Decompose technical and layout tags
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "form", "button", "iframe", "meta", "link", "aside"]):
                tag.decompose()
            # Decompose common blog/page sidebar and footer widgets
            for el in soup.find_all(attrs={"class": re.compile(r'(?:footer|header|sidebar|widget|menu|nav|author|share|social|comment|relat)', re.I)}):
                el.decompose()
            clean_str = soup.get_text(separator="\n")
        except Exception:
            clean_str = text
    else:
        clean_str = text

    # 2. Filter out raw CSS, JS, contact info, and boilerplate lines
    filtered_lines = []
    contact_junk_pattern = re.compile(
        r'(?:liên hệ|hotline|sđt|điện thoại:|zalo|facebook cô hà|fanpage|inbox|học phí|đăng ký khóa học|'
        r'ba mẹ|phụ huynh|tải đề thi|tải tài liệu|video chữa đề|tặng miễn phí|hướng dẫn dự thi|'
        r'lịch thi, giờ thi|địa điểm thi|chuẩn bị trước ngày thi|chúc mừng, bạn vừa|bạn đã cố gắng rồi|'
        r'bản quyền thuộc về|all rights reserved|tin liên quan|bài viết liên quan|chia sẻ bài viết)',
        re.IGNORECASE
    )

    for line in clean_str.split("\n"):
        ln = line.strip()
        if not ln:
            continue
        ln_lower = ln.lower()
        if any(bad in ln_lower for bad in ["<!doctype", "<html", "xmlns=", "css_layout", "display:none", "position:static", "var ", "function()", "const ", "{opacity:", "png'/>", "tailwind", "keenthemes"]):
            continue
        # Skip isolated lines that are pure contact, advertisement, or phone numbers
        if re.search(r'\b0[1-9]\d{1,2}[\.\s\-]?\d{3}[\.\s\-]?\d{3,4}\b', ln):
            continue
        if contact_junk_pattern.search(ln) and len(ln) < 150:
            continue
        filtered_lines.append(ln)

    full_text = "\n".join(filtered_lines)

    # 3. Split by Question markers (Câu 1, Bài 1, Question 1, 1., 1))
    blocks = re.split(r'\n(?=(?:Câu|Bài|Question|\b\d+[\.\)])\s*\d+[\.:\)])', full_text, flags=re.IGNORECASE)
    
    for idx, block in enumerate(blocks):
        block = block.strip()
        if not block or len(block) < 15:
            continue

        # Strip any trailing contact/footer section that might have bled into the block
        block = re.split(r'(?i)\n\s*(?:LIÊN HỆ|Hotline|SĐT|Điện thoại|Facebook|Fanpage|Website|Ba mẹ|Phụ huynh|Tải đề|Download|Lưu ý quan trọng|Bản quyền).*', block)[0].strip()
        if len(block) < 15:
            continue

        # A valid block MUST either start with a question marker OR have at least 2 distinct multiple choice options
        has_marker = bool(re.match(r'^(?:Câu|Bài|Question|\b\d+[\.\)])\s*\d+[\.:\)]', block, re.IGNORECASE))

        # Check for multiple choice options (A., B., C., D.)
        opt_matches = re.findall(r'(?:^|\s|\n)([A-D])[\.\:\)]\s*(.*?)(?=(?:(?:^|\s|\n)[A-D][\.\:\)]|\n|$))', block, flags=re.DOTALL)
        options = []
        seen_letters = set()
        if opt_matches:
            for letter, opt_text in opt_matches:
                let_upper = letter.upper()
                if let_upper in seen_letters:
                    continue
                clean_opt = opt_text.strip().replace("\n", " ")
                # Strip out trailing option markers or CSS
                clean_opt = re.sub(r'\s+', ' ', clean_opt).strip()
                if clean_opt and len(clean_opt) < 200:
                    seen_letters.add(let_upper)
                    options.append({
                        "id": let_upper,
                        "content": clean_opt,
                        "is_correct": False
                    })

        # Discard spurious options if less than 2 distinct options
        if len(options) < 2:
            options = []

        # If this is blocks[0] (or any block) without marker AND without valid options:
        # It's an article title, intro description, or page header -> DISCARD IT!
        if not has_marker and not options:
            continue

        stem_match = re.split(r'\n?[A-D][\.\:\)]', block)
        q_stem = stem_match[0].strip() if stem_match else block[:120]
        q_text = re.sub(r'^(Câu|Bài|Question|\d+)[\s\d\.:\)]+', '', q_stem, flags=re.IGNORECASE).strip()
        if not q_text:
            q_text = q_stem

        # Re-check stem length: If no options, stem shouldn't exceed 450 chars (avoiding article summaries)
        if not options and len(q_text) > 450:
            continue

        ans_match = re.search(r'(?:Đáp án|Chọn|Key|Answer)[\s\:\-]+([A-D])\b', block, flags=re.IGNORECASE)
        correct_ans = ans_match.group(1).upper() if ans_match else (options[0]["id"] if options else None)
        if correct_ans and options:
            for o in options:
                if o["id"] == correct_ans:
                    o["is_correct"] = True

        if len(q_text) >= 10:
            subject = classify_subject(q_text)
            candidate = {
                "id": f"parsed_{uuid.uuid4().hex[:10]}",
                "source_platform": "internet_hunter",
                "source_url": source_url or "https://khoade.edu.vn",
                "exam_name": "Kho bài tập & Đề thi trực tuyến",
                "grade": extract_grade_from_url(source_url, default_grade=5),
                "subject": subject,
                "topic": "Bóc tách tự động",
                "question_type": "single_choice" if options else "fill_blank",
                "content_html": f"<p>{q_text}</p>",
                "content_text": q_text,
                "images": [],
                "options": options,
                "correct_answer": correct_ans,
                "explanation": "",
                "difficulty": "medium"
            }
            is_valid, _ = is_valid_question_payload(candidate)
            if is_valid:
                results.append(candidate)
    return results


def parse_loigiaihay_questions(html: str, source_url: str = "") -> List[Dict[str, Any]]:
    """Parses loigiaihay.com exam pages (verified DOM 2026-10-11).

    Each item is ``div.question`` containing ``.question-content-inner``
    (stem), ``ul.dapan > li`` (``span.span-answer`` letter + ``div`` text)
    and ``.loigiai`` (``b`` "Dap an : X" + ``.solution-detail`` text).
    Returns validated payloads tagged ``source_platform="loigiaihay"``.
    """
    results: List[Dict[str, Any]] = []
    if not html or "question-content" not in html:
        return results
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return results
    # Live pages repeat the exam twice (first pass lacks .loigiai answer keys).
    # Dedup by stem, preferring the copy that carries a real answer key.
    seen: Dict[str, int] = {}

    for block in soup.find_all("div", class_=re.compile(r"^question(\s|$)")):
        try:
            inner = block.find(class_="question-content-inner")
            if inner is None:
                continue
            idx_tag = inner.find("strong")
            q_num = idx_tag.get_text(strip=True) if idx_tag else ""
            stem_parts = [p.get_text(" ", strip=True) for p in inner.find_all("p")]
            stem = " ".join(s for s in stem_parts if s).strip()
            if not stem:
                stem = inner.get_text(" ", strip=True).replace(q_num, "", 1).strip()
            if len(stem) < 5:
                continue

            options = []
            dapan = block.find("ul", class_=re.compile(r"dapan"))
            if dapan is not None:
                for li in dapan.find_all("li"):
                    letter_tag = li.find("span", class_=re.compile(r"span-answer"))
                    letter_raw = letter_tag.get_text(strip=True) if letter_tag else ""
                    letter = re.sub(r"[^A-Da-d]", "", letter_raw).upper()
                    opt_div = li.find("div")
                    opt_text = opt_div.get_text(" ", strip=True) if opt_div else ""
                    if letter and opt_text and len(opt_text) < 300:
                        options.append({"id": letter, "content": opt_text, "is_correct": False})
            if len(options) < 2:
                continue

            loigiai = block.find(class_="loigiai")
            loigiai_text = loigiai.get_text(" ", strip=True) if loigiai else ""
            ans_match = re.search(r"[Đđ]áp án\s*:\s*([A-D])\b", loigiai_text)
            correct_ans = ans_match.group(1).upper() if ans_match else options[0]["id"]
            for o in options:
                if o["id"] == correct_ans:
                    o["is_correct"] = True

            explanation = ""
            sol_detail = block.find(class_="solution-detail")
            if sol_detail is not None:
                explanation = re.sub(
                    r"^\s*Lời giải chi tiết\s*:\s*", "",
                    sol_detail.get_text(" ", strip=True),
                ).strip()

            q_text = re.sub(r"^(Câu|Bài)\s*\d+\s*[:.]\s*", "", stem, flags=re.IGNORECASE).strip() or stem
            candidate = {
                "id": f"lgh_{uuid.uuid4().hex[:10]}",
                "source_platform": "loigiaihay",
                "source_url": source_url or "https://loigiaihay.com/",
                "exam_name": "Lời Giải Hay - Đề thi có lời giải chi tiết",
                "grade": extract_grade_from_url(source_url, default_grade=5),
                "subject": classify_subject(q_text),
                "topic": "Đề thi Lời Giải Hay",
                "question_type": "single_choice",
                "content_html": f"<p>{q_text}</p>",
                "content_text": q_text,
                "images": [],
                "options": options,
                "correct_answer": correct_ans,
                "explanation": explanation,
                "difficulty": "medium",
            }
            is_valid, _ = is_valid_question_payload(candidate)
            if is_valid:
                key = re.sub(r"\s+", " ", q_text.lower()).strip()
                has_key = bool(ans_match)
                if key in seen:
                    if has_key and not results[seen[key]].get("_lgh_has_key"):
                        results[seen[key]] = candidate
                        candidate["_lgh_has_key"] = True
                else:
                    candidate["_lgh_has_key"] = has_key
                    seen[key] = len(results)
                    results.append(candidate)
        except Exception:
            continue
    for r in results:
        r.pop("_lgh_has_key", None)
    return results
