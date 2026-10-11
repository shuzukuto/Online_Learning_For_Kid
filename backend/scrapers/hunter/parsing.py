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
    if not html:
        return results
    has_classic = "question-content" in html
    has_upper = "sub-question-" in html or "box-question" in html
    if not has_classic and not has_upper:
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
    if results:
        return results
    # Fallback: grade 6-12 layout (verified DOM 2026-10-12, a120884).
    # No div.question blocks: stems+options inline in <p> ("Câu N: ... A. ...
    # B. ... C. ... D. ..."), key in a <table> of "<N>. <X>" cells, and
    # solutions as "<p><strong>Câu N</strong></p> ... Phương pháp/Cách giải ...
    # <p><strong>Chọn X.</strong></p>".
    return _parse_loigiaihay_upper_layout(soup, source_url)


def _parse_loigiaihay_upper_layout(soup: "BeautifulSoup", source_url: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        grade = extract_grade_from_url(source_url, default_grade=5)
        # 0. EN exercise layout (a154048): numbered items + "Đáp án: |N. X|" keys.
        # Try it first when the page has Exercise markers; it shares no
        # structure with the Câu-N layouts below.
        page_text = soup.get_text(" ", strip=True)
        if re.search(r"\bExercise\s*\d+", page_text, re.I):
            ex_out = _parse_loigiaihay_exercise_layout(soup, source_url, grade)
            if ex_out:
                return ex_out
        # 1. Answer-key table: cells like "1. B" / "12. A".
        answer_key: Dict[int, str] = {}
        for table in soup.find_all("table"):
            for cell in table.find_all(["td", "th"]):
                m = re.match(r"^\s*(\d{1,2})\s*[.\):]\s*([A-D])\b",
                             cell.get_text(" ", strip=True), re.I)
                if m and int(m.group(1)) not in answer_key:
                    answer_key[int(m.group(1))] = m.group(2).upper()
            if len(answer_key) >= 5:
                break

        # 2. Solutions: "Câu N" header -> text until "Chọn X.".
        solutions: Dict[int, str] = {}
        chosen: Dict[int, str] = {}
        paras = [p for p in soup.find_all("p")
                 if not p.find_parent("table")]
        current: Optional[int] = None
        buf: List[str] = []
        for p in paras:
            t = p.get_text(" ", strip=True)
            m_head = re.match(r"^(Câu|Bài)\s*(\d{1,2})\s*$", t, re.I)
            if m_head:
                if current is not None and buf:
                    solutions[current] = re.sub(r"\s+", " ", " ".join(buf)).strip()
                current = int(m_head.group(2))
                buf = []
                continue
            m_pick = re.match(r"^Chọn\s+([A-D])\s*[.\!]?\s*$", t, re.I)
            if m_pick and current is not None:
                chosen[current] = m_pick.group(1).upper()
                if buf:
                    solutions[current] = re.sub(r"\s+", " ", " ".join(buf)).strip()
                current = None
                buf = []
                continue
            if current is not None and t and len(t) < 600:
                if not re.match(r"^(Phương pháp|Cách giải)\s*:?\s*$", t, re.I):
                    buf.append(t)
        if current is not None and buf:
            solutions[current] = re.sub(r"\s+", " ", " ".join(buf)).strip()

        # 3. Stems: <p> starting "Câu N:" — options inline OR in following <p>.
        seen_nums = set()
        for p in soup.find_all("p"):
            t = p.get_text(" ", strip=True)
            m_stem = re.match(r"^(Câu|Bài)\s*(\d{1,2})\s*[:.]\s*(.+)$", t, re.I | re.S)
            if not m_stem:
                continue
            q_num = int(m_stem.group(2))
            if q_num in seen_nums:
                continue
            seen_nums.add(q_num)
            rest = m_stem.group(3).strip()
            # Split inline options at "A. / B. / C. / D." markers.
            marks = list(re.finditer(r"\b([A-D])\s*[.\):]\s*", rest))
            options = []
            if len(marks) >= 2 and [m.group(1).upper() for m in marks[:2]] == ["A", "B"]:
                stem = rest[:marks[0].start()].strip()
                for i, m in enumerate(marks):
                    end = marks[i + 1].start() if i + 1 < len(marks) else len(rest)
                    opt_text = re.sub(r"\s+", " ", rest[m.end():end].strip())
                    if opt_text and len(opt_text) < 300:
                        options.append({"id": m.group(1).upper(), "content": opt_text,
                                        "is_correct": False})
            else:
                # Options live in the following sibling <p> (a120884 layout).
                stem = rest
                node = p.find_next_sibling()
                hops = 0
                while node is not None and hops < 4 and len(options) < 2:
                    hops += 1
                    if getattr(node, "get_text", None) is None:
                        node = node.find_next_sibling()
                        continue
                    n_text = node.get_text(" ", strip=True)
                    if re.match(r"^(Câu|Bài)\s*\d{1,2}\s*[:.]", n_text, re.I):
                        break
                    n_marks = list(re.finditer(r"\b([A-D])\s*[.\):]\s*", n_text))
                    if len(n_marks) >= 2 and [m.group(1).upper() for m in n_marks[:2]] == ["A", "B"]:
                        for i, m in enumerate(n_marks):
                            end = n_marks[i + 1].start() if i + 1 < len(n_marks) else len(n_text)
                            opt_text = re.sub(r"\s+", " ", n_text[m.end():end].strip())
                            if opt_text and len(opt_text) < 300:
                                options.append({"id": m.group(1).upper(), "content": opt_text,
                                                "is_correct": False})
                        break
                    node = node.find_next_sibling()
            if len(stem) < 5 or len(options) < 2:
                continue
            correct_ans = (answer_key.get(q_num) or chosen.get(q_num)
                           or options[0]["id"])
            if correct_ans not in [o["id"] for o in options]:
                correct_ans = options[0]["id"]
            for o in options:
                if o["id"] == correct_ans:
                    o["is_correct"] = True
            q_text = stem
            candidate = {
                "id": f"lgh_{uuid.uuid4().hex[:10]}",
                "source_platform": "loigiaihay",
                "source_url": source_url or "https://loigiaihay.com/",
                "exam_name": "Lời Giải Hay - Đề thi có lời giải chi tiết",
                "grade": grade,
                "subject": classify_subject(q_text),
                "topic": "Đề thi Lời Giải Hay",
                "question_type": "single_choice",
                "content_html": f"<p>{q_text}</p>",
                "content_text": q_text,
                "images": [],
                "options": options,
                "correct_answer": correct_ans,
                "explanation": solutions.get(q_num, ""),
                "difficulty": "medium",
            }
            is_valid, _ = is_valid_question_payload(candidate)
            if is_valid:
                results.append(candidate)
                if len(results) >= 30:
                    break
    except Exception:
        return results
    return results


def parse_vietjack_questions(html: str, source_url: str = "") -> List[Dict[str, Any]]:
    """Parses vietjack.com .jsp exam pages (verified DOM 2026-10-12).

    Stems live in ``<p><strong>Câu N:</strong> ...</p>``, options in following
    sibling ``<p>A. ...</p>`` paragraphs, and the answer key in a ``<table>``
    whose header row holds ``Câu 1..N`` with the letters in the second row.
    Returns validated payloads tagged ``source_platform="vietjack"``.
    """
    results: List[Dict[str, Any]] = []
    if not html or "Câu" not in html:
        return results
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return results
    for tag in soup(["script", "style", "noscript", "header", "footer",
                     "nav", "aside", "form", "iframe"]):
        tag.decompose()

    # 1. Answer-key tables: header row "Câu 1..N" -> second row letters.
    answer_key: Dict[int, str] = {}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = [c.get_text(" ", strip=True) for c in rows[0].find_all(["td", "th"])]
        header_nums = []
        for c in header_cells:
            m = re.search(r"Câu\s*(\d+)", c, re.I)
            if m:
                header_nums.append(int(m.group(1)))
        if len(header_nums) < 2:
            continue
        key_cells = [c.get_text(" ", strip=True) for c in rows[1].find_all(["td", "th"])]
        for num, cell in zip(header_nums, key_cells):
            m = re.match(r"^([A-D])\b", cell.strip().upper())
            if m and num not in answer_key:
                answer_key[num] = m.group(1)
        table.decompose()  # keep key rows out of the option walk

    # 2. Stems: <p>/<div>/<li> starting with "Câu N:" / "Bài N:".
    stem_tags = [t for t in soup.find_all(["p", "div", "li"])
                 if re.match(r"^(Câu|Bài)\s*\d+\s*[:.]", t.get_text(strip=True), re.I)]
    for stem_tag in stem_tags[:30]:
        try:
            stem_raw = stem_tag.get_text(" ", strip=True)
            m_num = re.match(r"^(Câu|Bài)\s*(\d+)\s*[:.]\s*(.*)$", stem_raw, re.I | re.S)
            if not m_num:
                continue
            q_num = int(m_num.group(2))
            stem = m_num.group(3).strip()
            if len(stem) < 5 or len(stem) > 500:
                continue
            # 3. Options: following siblings "A. ...", stop at next stem/section.
            # The solution lives in a sibling <section> ("Hiển thị đáp án /
            # Đáp án đúng là: X") — collect it, don't stop at it.
            options = []
            node = stem_tag.find_next_sibling()
            sol_section_texts = []
            # NOTE: keep walking until the next stem (not just until 4 options)
            # so the trailing <section> holding "Đáp án đúng là: X" is seen.
            while node is not None:
                if getattr(node, "get_text", None) is None:
                    node = node.find_next_sibling()
                    continue
                n_text = node.get_text(" ", strip=True)
                if re.match(r"^(Câu|Bài)\s*\d+\s*[:.]", n_text, re.I):
                    break
                if node.name == "section" and re.search(
                        r"Đáp án|Hiển thị đáp án|Lời giải", n_text, re.I):
                    sol_section_texts.append(n_text)
                    node = node.find_next_sibling()
                    continue
                if len(options) >= 4 and not re.search(
                        r"Đáp án|Hiển thị đáp án|Lời giải", n_text, re.I):
                    node = node.find_next_sibling()
                    continue
                if (re.search(r"Đáp án|Tự luận|Quảng cáo", n_text, re.I)
                        and not re.match(r"^[A-D][\.\)\:]", n_text)):
                    break
                om = re.match(r"^([A-D])[\.\)\:]\s*(.+)$", n_text, re.S)
                if om and len(om.group(2).strip()) < 300:
                    options.append({"id": om.group(1).upper(),
                                    "content": re.sub(r"\s+", " ", om.group(2).strip()),
                                    "is_correct": False})
                node = node.find_next_sibling()
            if len(options) < 2:
                continue
            # 3b. Inline key: "Đáp án đúng là: X" — solution <section> first,
            # then remaining siblings. Capture solution text as explanation.
            explanation = ""
            inline_key = None
            sol_parts = list(sol_section_texts)
            for _sp in sol_section_texts:
                km0 = re.search(r"Đáp án đúng là:\s*([A-D])\b", _sp, re.I)
                if km0:
                    inline_key = km0.group(1).upper()
                    break
            node2 = node
            while node2 is not None:
                if getattr(node2, "get_text", None) is None:
                    node2 = node2.find_next_sibling()
                    continue
                s_text = node2.get_text(" ", strip=True)
                if re.match(r"^(Câu|Bài)\s*\d+\s*[:.]", s_text, re.I):
                    break
                km = re.search(r"Đáp án đúng là:\s*([A-D])\b", s_text, re.I)
                if km and inline_key is None:
                    inline_key = km.group(1).upper()
                if re.search(r"Đáp án|Hiển thị đáp án|Lời giải", s_text, re.I):
                    sol_parts.append(s_text)
                node2 = node2.find_next_sibling()
                if len(sol_parts) > 6:
                    break
            if sol_parts:
                explanation = re.sub(r"\s+", " ", " ".join(sol_parts))[:600]
            correct_ans = inline_key or answer_key.get(q_num, options[0]["id"])
            if correct_ans not in [o["id"] for o in options]:
                correct_ans = options[0]["id"]
            for o in options:
                if o["id"] == correct_ans:
                    o["is_correct"] = True
            q_text = stem
            candidate = {
                "id": f"vj_{uuid.uuid4().hex[:10]}",
                "source_platform": "vietjack",
                "source_url": source_url or "https://vietjack.com/",
                "exam_name": "VietJack - Đề thi có đáp án",
                "grade": extract_grade_from_url(source_url, default_grade=5),
                "subject": classify_subject(q_text),
                "topic": "Đề thi VietJack",
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
                results.append(candidate)
        except Exception:
            continue
    return results


def _parse_loigiaihay_exercise_layout(soup: "BeautifulSoup", source_url: str,
                                     grade: int) -> List[Dict[str, Any]]:
    """Parses EN exercise pages (verified DOM 2026-10-12, a154048).

    Items are numbered ``1. stem|A. a B. b C. c D. d|2. ...`` inside <p>
    blocks; each exercise's key follows a ``Đáp án:`` marker as
    ``|<num>. <letter>|`` cells (letters only for MCQ items — written-answer
    keys like ``1. is`` are skipped). Subject is forced to ``english``
    from the URL slug (stems alone often miss the classifier's keywords).
    """
    results: List[Dict[str, Any]] = []
    try:
        full = soup.get_text("|", strip=True)
        # Split into Exercise sections — numbering restarts per exercise, so
        # keys MUST stay scoped to their own section (a154048: Ex3 key is
        # 1.C 2.D..., later exercises reuse 1-5 with different letters).
        ex_marks = list(re.finditer(r"\bExercise\s*(\d+)", full, re.I))
        sections = []
        for i, m in enumerate(ex_marks):
            end = ex_marks[i + 1].start() if i + 1 < len(ex_marks) else len(full)
            sections.append((int(m.group(1)), full[m.start():end]))
        subj = "english" if re.search(r"tieng-anh|english|anh-\d", source_url, re.I) \
            else classify_subject(source_url)
        seen_stems = set()
        for _ex_num, sec in sections:
            # Key within THIS section only: after "Đáp án:" in the section.
            key_map: Dict[int, str] = {}
            dm = re.search(r"Đáp án\s*:", sec, re.I)
            if dm:
                key_seg = sec[dm.end():]
                for km in re.finditer(r"\|\s*(\d{1,2})\s*[.\):]\s*([A-D])(?=\s*\||\s|$)",
                                      key_seg, re.I):
                    num = int(km.group(1))
                    if num not in key_map:
                        key_map[num] = km.group(2).upper()
            # Items: only the part BEFORE "Đáp án:" (the solution half repeats
            # the same items with numbering that would double-count stems).
            item_seg = sec[:dm.start()] if dm else sec
            for m in re.finditer(
                    r"(?:^|\|)\s*(\d{1,2})\s*[.\):]\s*([^|]+?)\|\s*"
                    r"A\s*[.\):]\s*(.+?)(?=(?:^|\|)\s*\d{1,2}\s*[.\):]|\|\s*Đáp án|$)",
                    item_seg, re.S):
                num = int(m.group(1))
                body = m.group(2).strip() + " A. " + m.group(3).strip()
                m_a = re.search(r"\bA\s*[.\):]\s*", body)
                if not m_a:
                    continue
                stem = re.sub(r"\s+", " ", body[:m_a.start()].strip())
                opt_run = body[m_a.end():]
                _emit_exercise_item(results, seen_stems, key_map, subj,
                                    source_url, grade, num, stem, opt_run)
                if len(results) >= 30:
                    return results
        # Lone shape (b): each <p> is "N. stem", options in the NEXT <p>.
        # (Handled below on the raw <p> list.)
        for p in soup.find_all("p"):
            t = p.get_text("|", strip=True)
            if "Đáp án" in t or re.match(r"^\s*Exercise\s*\d+", t, re.I):
                continue
            # Two live shapes:
            #  (a) one <p> holds "1. stem|A. a B. b C. c D. d|2. ..." (multi-item);
            #  (b) each <p> is a lone "N. stem" and options sit in the NEXT <p>
            #      as "A. ... B. ... C. ... D. ..." (a154048 Exercise 3+).
            lone = re.match(r"^\s*(\d{1,2})\s*[.\):]\s*(.+?)\s*$", t, re.S)
            if lone and "A." not in t and len(lone.group(2).strip()) >= 5:
                num = int(lone.group(1))
                stem = re.sub(r"\s+", " ", lone.group(2).strip())
                opt_run = ""
                node = p.find_next_sibling()
                hops = 0
                while node is not None and hops < 3:
                    hops += 1
                    if getattr(node, "get_text", None) is None:
                        node = node.find_next_sibling()
                        continue
                    n_text = node.get_text(" ", strip=True)
                    if re.match(r"^\s*\d{1,2}\s*[.\):]", n_text):
                        break
                    if re.search(r"\bA\s*[.\):]", n_text):
                        opt_run = n_text
                        break
                    node = node.find_next_sibling()
                if opt_run:
                    # Lone items share their exercise's key: find nearest
                    # preceding "Đáp án:"-scoped map via section lookup.
                    _emit_exercise_item(results, seen_stems, _section_key_for(
                        full, p, sections), subj,
                        source_url, grade, num, stem, opt_run)
                continue
    except Exception:
        return results
    return results


def _section_key_for(full: str, p, sections: list) -> Dict[int, str]:
    """Key map of the Exercise section containing paragraph *p* (best effort).

    Falls back to {} when the paragraph sits outside any keyed section.
    """
    try:
        anchor = p.get_text("|", strip=True)[:40]
        pos = full.find(anchor)
        best: Dict[int, str] = {}
        for _ex_num, sec in sections:
            start = full.find(sec[:60])
            if start != -1 and start <= pos < start + len(sec):
                dm = re.search(r"Đáp án\s*:", sec, re.I)
                if dm:
                    for km in re.finditer(
                            r"\|\s*(\d{1,2})\s*[.\):]\s*([A-D])(?=\s*\||\s|$)",
                            sec[dm.end():], re.I):
                        num = int(km.group(1))
                        if num not in best:
                            best[num] = km.group(2).upper()
                break
        return best
    except Exception:
        return {}


def _emit_exercise_item(results: List[Dict[str, Any]], seen_stems: set,
                        key_map: Dict[int, str], subj: str, source_url: str,
                        grade: int, num: int, stem: str, opt_run: str) -> None:
    """Builds one MCQ payload from a stem + option-run string."""
    opt_parts = re.split(r"\b([B-D])\s*[.\):]\s*", opt_run)
    # opt_parts: [A_text, B, B_text, C, C_text, D, D_text]
    if len(opt_parts) < 7:
        return
    opts_raw = [opt_parts[0], opt_parts[2], opt_parts[4], opt_parts[6]]
    if len(stem) < 5 or len(stem) > 400:
        return
    options = []
    for lid, oc in zip("ABCD", opts_raw):
        oc = re.sub(r"[\s\xa0]+", " ", oc.strip())
        if oc and len(oc) < 200:
            options.append({"id": lid, "content": oc, "is_correct": False})
    if len(options) < 2:
        return
    skey = re.sub(r"\s+", " ", stem.lower()).strip()
    if skey in seen_stems:
        return
    seen_stems.add(skey)
    correct_ans = key_map.get(num, options[0]["id"])
    if correct_ans not in [o["id"] for o in options]:
        correct_ans = options[0]["id"]
    for o in options:
        if o["id"] == correct_ans:
            o["is_correct"] = True
    candidate = {
        "id": f"lgh_{uuid.uuid4().hex[:10]}",
        "source_platform": "loigiaihay",
        "source_url": source_url or "https://loigiaihay.com/",
        "exam_name": "Lời Giải Hay - Bài tập Tiếng Anh có đáp án",
        "grade": grade,
        "subject": subj,
        "topic": "Bài tập Lời Giải Hay",
        "question_type": "single_choice",
        "content_html": f"<p>{stem}</p>",
        "content_text": stem,
        "images": [],
        "options": options,
        "correct_answer": correct_ans,
        "explanation": "",
        "difficulty": "medium",
    }
    is_valid, _ = is_valid_question_payload(candidate)
    if is_valid:
        results.append(candidate)
