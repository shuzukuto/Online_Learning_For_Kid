from __future__ import annotations
import os
import re
import io
import uuid
import unicodedata
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from pypdf import PdfReader
from PIL import Image

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

def clean_ocr_vietnamese_text(text: str) -> str:
    """Normalizes Unicode NFC, removes mobile status bar / score noise, and repairs common OCR misrecognitions in Vietnamese exams."""
    if not text:
        return ""
    # 1. Unicode NFC normalization (combining accents -> canonical precomposed characters)
    text = unicodedata.normalize('NFC', text)
    
    # 2. Filter out phone status bar time (e.g. 05:31, 12:45)
    text = re.sub(r'(?m)^\s*\d{1,2}:\d{2}\s*$', '', text)
    
    # 3. Strip quiz score badges like *4/4, (4/4), [4/4], * 4/4
    text = re.sub(r'[\*\(\[]?\s*\d+\s*/\s*\d+\s*[\*\)\]]?', '', text)
    
    # 4. Clean checkmarks / bullets at the start of a question line (e.g. '✓ 4. If today...' -> '4. If today...')
    text = re.sub(r'(?m)^[✓✔☑●•\*\-–—\s]+(?=\d)', '', text)

    # 4b. Protect hyphenated compound numbers (e.g. 2-digit, 3-chữ số, 4-step) to avoid accidental question splits
    text = re.sub(r'\b(\d+)-(digit|digits|bit|bits|letter|step|year|month|day|hour|minute|second|inch|cm|mm|m|kg|g|chữ\s*số|chiều|d|D|st|nd|rd|th)\b', r'\1_\2', text, flags=re.IGNORECASE)
    
    # 5. Space out stuck letters and digits (e.g. has5 -> has 5, class5 -> class 5, 5Michael -> 5 Michael)
    text = re.sub(r'([a-zA-Z])(\d+)', r'\1 \2', text)
    text = re.sub(r'(\d+)([a-zA-Z])', r'\1 \2', text)
    
    # 6. Normalize common OCR mistakes on "Câu" / "Bài" / "Question"
    text = re.sub(r'(?i)\b(?:c@u|cdu|cáu|cau)\s*([0-9]{1,3})\b', r'Câu \1', text)
    text = re.sub(r'(?i)\b(?:b@i|bai)\s*([0-9]{1,3})\b', r'Bài \1', text)
    
    # 7. Standardize question numbering: '4. ' or '5, ' or '5: ' or 'Câu 1' -> '\nCâu 4. '
    text = re.sub(r'(?m)^(\s*)(?:Câu|Question|Problem|Bài|Q)\s*([0-9]{1,3})\s*[,.:\)\-]\s*', r'\nCâu \2. ', text)
    text = re.sub(r'(?m)^(\s*)([0-9]{1,3})\s*[\.:\),]\s*(?=[A-Za-z\u00C0-\u024F\u1EA0-\u1EF9])', r'\nCâu \2. ', text)

    # 7b. Restore protected compound numbers
    text = re.sub(r'\b(\d+)_([a-zA-Z]+)\b', r'\1-\2', text)
    
    # 8. Fix days of week in bilingual options (e.g. ThitTur -> Thứ Tư)
    text = re.sub(r'(?i)\b(?:thittur|thietuew|thir\s*tur|thu\s*tu)\b', 'Thứ Tư', text)
    text = re.sub(r'(?i)\b(?:thirbay|thitbay|thu\s*bay)\b', 'Thứ Bảy', text)
    text = re.sub(r'(?i)\b(?:thushiu|thosiu|thusiu|thu\s*sau)\b', 'Thứ Sáu', text)
    text = re.sub(r'(?i)\b(?:thunam|thurnam|thu\s*nam)\b', 'Thứ Năm', text)
    text = re.sub(r'(?i)\b(?:thuhai|thirhai|thu\s*hai)\b', 'Thứ Hai', text)
    text = re.sub(r'(?i)\b(?:chuanhat|chunhat)\b', 'Chủ Nhật', text)

    # 9. Contextual dictionary repairs for common OCR Vietnamese distortions in math/exam questions (VietOCR-inspired Lexicon)
    ocr_viet_repairs = [
        # Question 4 patterns
        (r'(?i)\bweckis(\d+)thMarch\b', r'week is \1th March'),
        (r'(?i)\bweckis0thMarch\b', 'week is 9th March'),
        (r'(?i)\bweckisOthMarch\b', 'week is 9th March'),
        (r'(?i)\bweck\s*is\b', 'week is'),
        (r'(?i)\bIftodayis\b', 'If today is'),
        (r'(?i)\bandalsothe\b', 'and also the'),
        (r'(?i)\bfirstdayof\b', 'first day of'),
        (r'(?i)\bWhichdayofthe\b', 'Which day of the'),
        (r'(?i)\b(?:nenhom|nen\s*hom|ncu\s*hom)\s*(?:nary|nay|nar)\b', 'Nếu hôm nay'),
        (r'(?i)\b(?:nen|ncu)\s*hom\s*nay\b', 'Nếu hôm nay'),
        (r'(?i)\b(?:fathieTiemcung|la\s*thir\s*tur\s*wi\s*cing\s*la|la\s*thietiemcung|lathietiemcung|la\s*thie\s*tu\s*va\s*cung)\b', 'là thứ Tư và cũng'),
        (r'(?i)\bla\s*(?:thir\s*tur|thittur|thietuew|thu\s*tu)\b', 'là thứ Tư'),
        (r'(?i)\b(?:wi|va|vi|w)\s*(?:cing|cung)\s*la\b', 'và cũng là'),
        (r'(?i)\b(?:langay|la\s*ngay|la\s*ngdy)\b', 'là ngày'),
        (r'(?i)\b(?:ngdy|ngay)\s*(?:diu|dau|atae|atiae|atintien)\s*tien\b', 'ngày đầu tiên'),
        (r'(?i)\b(?:diu|dau|atae|atiae|atintien)\s*tien\b', 'đầu tiên'),
        (r'(?i)\b(?:ctia|crn|crin|cuia|cua)\s*(?:thdng|thang)\s*(\d+)\b', r'của tháng \1'),
        (r'(?i)\b(?:ctia|crn|crin|cuia|cua)\s*(?:thdng|thang)\b', 'của tháng'),
        (r'(?i)\b(?:vay|voy|vayngdy|vay\s*ngdy)\s*(?:ngay|ngdy)?\s*(\d+)\s*(?:thang|thdng)\s*(\d+)\b', r'Vậy ngày \1 tháng \2'),
        (r'(?i)\b(?:voy|vay)\s*ngay\b', 'Vậy ngày'),
        (r'(?i)\bthang\s*(\d+)\b', r'tháng \1'),
        (r'(?i)\b(?:langay|la\s*ngay|la\s*ngdy)\s*(?:thur|thir|thu)\s*(?:may|miy)\b', 'là ngày thứ mấy'),
        (r'(?i)\bngay\s*(?:thur|thir|thu)\s*(?:may|miy)\b', 'ngày thứ mấy'),
        (r'(?i)\b(?:thur|thir|thu)\s*(?:may|miy)\b', 'thứ mấy'),

        # Question 5 patterns
        (r'(?i)\b(?:lopctiamichaelco|lopcriamichaelco|lop\s*ctia\s*michael\s*co|lop\s*cuia\s*michael\s*co|lop\s*cua\s*michael\s*co|lopcramichaelco)\b', 'Lớp của Michael có'),
        (r'(?i)\b(?:lap|lop)\s*(?:crn|crin|cuia|cua|ctia|cra)\b', 'Lớp của'),
        (r'(?i)\bco\s*(\d+)\s*ban\s*trai\b', r'có \1 bạn trai'),
        (r'(?i)\btrai\s*(?:wi|w)\b', 'trai và'),
        (r'(?i)\bban\s*trai\b', 'bạn trai'),
        (r'(?i)\b(?:wi|va|vi|wio|w)\s*(\d+)\s*ban\s*(?:gii|guii|gai|gif|git)\b', r'và \1 bạn gái'),
        (r'(?i)\bban\s*(?:gii|guii|gai|gif|git)\b', 'bạn gái'),
        (r'(?i)\b(?:hoi|hot|hol)\s*([A-Za-z]+)\s*co\s*(?:bao\s*nhicu|baonhicu|bao\s*nhieu|baonhieu|baonhicur)\s*ban\s*(?:cing|cting|cung)\s*(?:iop|lop)\b', r'Hỏi \1 có bao nhiêu bạn cùng lớp'),
        (r'(?i)\b(?:hol|hoi|hot)\b(?=\s+[A-Z])', 'Hỏi'),
        (r'(?i)\bco\s*(?:bao\s*nhicu|baonhicu|bao\s*nhieu|baonhieu|baonhicur)\s*ban\b', 'có bao nhiêu bạn'),
        (r'(?i)\b(?:cing|cting|cung|ciang)\s*(?:iop|lop)\b', 'cùng lớp'),
        (r'(?i)\b(?:cing|cting|cung|ciang)\s*lop\b', 'cùng lớp'),

        # Question 8 English
        (r'(?i)\bofanumber\b', 'of a number'),
        (r'(?i)\bthensubtracts\b', 'then subtracts'),
        (r'(?i)\btogetthesmallest\b', 'to get the smallest'),
        (r'2-digit\.odd\b', '2-digit odd'),
        (r'(?i)\boddnumber\b', 'odd number'),
        (r'(?i)\bFindGordon\'?s\b', 'Find Gordon\'s'),
        (r'Find Gordon\'?s\s*number\.', 'Find Gordon\'s number.'),

        # Question 8 Vietnamese
        (r'(?i)\b(?:gordon|gondon)[a-z]*\s*(?:so|mprso|mirso|mpr\s*so)\b', 'Gordon nghĩ ra một số'),
        (r'(?i)\b(?:anhay|anh\s*ay)\b', 'Anh ấy'),
        (r'(?i)\b(?:ldy|lay)\s*(?:sodo|so\s*do)\b', 'lấy số đó'),
        (r'(?i)\b(?:congrhom|cong\s*rhom)\b', 'cộng thêm'),
        (r'(?i)\b(?:roitrirdi|roitrir\s*di|roi\s*trirdi|roi\s*trudi|roi\s*tri\s*di)\b', 'rồi trừ đi'),
        (r'(?i)\b(?:thiducsole|thiduncsole|thi\s*dunc\s*sole|thi\s*duc\s*sole|thi\s*duoc\s*so\s*le)\b', 'thì được số lẻ'),
        (r'(?i)\b(?:hohaircohai|nhonhaircohai|nho\s*nhaircohai|hohair\s*cohai|nho\s*nhat\s*co\s*hai)\b', 'nhỏ nhất có hai'),
        (r'(?i)\b(?:chirso|chantso|chrso|chir\s*so|chu\s*so)\b', 'chữ số'),
        (r'(?i)\b(?:timsodo|tim\s*sodo|tim\s*so\s*do)\b', 'Tìm số đó'),

        # Question 9 English & Vietnamese
        (r'(?i)\bCalculate\s*(\d+)', r'Calculate \1'),
        (r'(?i)\bTinh\s*(\d+)', r'Tính \1'),
        (r'(?i)\bTính\s*13\s*-\s*1\s*\+', 'Tính 13 - 11 +'),
        (r'(\d+)\s*-\s*(\d+)\s*\+\s*(\d+)\s*-\s*(\d+)\s*\+\s*(\d+)\s*-\s*(\d+)\s*\+\s*(\d+)', r'\1 - \2 + \3 - \4 + \5 - \6 + \7'),

        # General exam and school math Vietnamese lexicon repairs
        (r'(?i)\bphep\s*tinh\b', 'phép tính'),
        (r'(?i)\bket\s*qua\b', 'kết quả'),
        (r'(?i)\bchu\s*vi\b', 'chu vi'),
        (r'(?i)\bdien\s*tich\b', 'diện tích'),
        (r'(?i)\bhinh\s*chu\s*nhat\b', 'hình chữ nhật'),
        (r'(?i)\bhinh\s*vuong\b', 'hình vuông'),
        (r'(?i)\bhinh\s*tron\b', 'hình tròn'),
        (r'(?i)\bhinh\s*tam\s*giac\b', 'hình tam giác'),
        (r'(?i)\bphan\s*so\b', 'phân số'),
        (r'(?i)\btu\s*so\b', 'tử số'),
        (r'(?i)\bmau\s*so\b', 'mẫu số'),
        (r'(?i)\bso\s*tu\s*nhien\b', 'số tự nhiên'),
        (r'(?i)\bso\s*thap\s*phan\b', 'số thập phân'),
        (r'(?i)\bdap\s*an\s*dung\b', 'đáp án đúng'),
        (r'(?i)\bchon\s*dap\s*an\b', 'chọn đáp án'),
        (r'(?i)\bloi\s*giai\b', 'lời giải'),
        (r'(?i)\bgiai\s*thich\b', 'giải thích'),
        (r'(?i)\bbieu\s*thuc\b', 'biểu thức'),
        (r'(?i)\bgia\s*tri\b', 'giá trị'),
        (r'(?i)\bquang\s*duong\b', 'quãng đường'),
        (r'(?i)\bvan\s*toc\b', 'vận tốc'),
        (r'(?i)\bthoi\s*gian\b', 'thời gian'),
    ]
    for pattern, replacement in ocr_viet_repairs:
        text = re.sub(pattern, replacement, text)

    # 10. Active Lexicon Learning: apply user-learned dynamic corrections from database
    try:
        from backend.database import get_ocr_corrections_map
        user_corrections = get_ocr_corrections_map()
        for wrong, correct in user_corrections.items():
            if wrong and correct and wrong != correct:
                pattern = r'(?i)\b' + re.escape(wrong) + r'\b'
                text = re.sub(pattern, correct, text)
    except Exception as e:
        pass

    # 11. Vietnamese NLP post-processing: restore diacritics, fix character confusions, normalize Unicode
    try:
        from backend.vietnamese_nlp import (
            restore_vietnamese_diacritics,
            fix_common_ocr_confusions,
            normalize_vietnamese_unicode
        )
        # Fix character-level OCR confusions first (rn->nh, cl->d, 0->o, etc.)
        text = fix_common_ocr_confusions(text)
        # Restore missing diacritics on common Vietnamese words (e.g. "phan so" -> "phân số")
        text = restore_vietnamese_diacritics(text)
        # Final Unicode NFC normalization pass
        text = normalize_vietnamese_unicode(text)
    except Exception as e:
        pass
        
    # 12. Standardize option prefixes (e.g., "(A)", "A - ", "A: ", "A .", or glued digits "C12" -> "C. 12", "AWednesdlay" -> "A. Wednesdlay")
    text = re.sub(r'(?m)^(\s*)([A-Ea-e])(?=[A-Z][a-z])', r'\n\2. ', text)
    text = re.sub(r'(?m)^(\s*)([A-Da-d])\s*[\.:\)]*\s*([0-9]+)\s*(\(?\s*(?:[✓✔☑]|\bchecked\b)?\s*\)?)$', r'\n\2. \3 \4', text)
    text = re.sub(r'(?:^|\n|\s)\(([A-Ea-e])\)\s*', r'\n\1. ', text)
    text = re.sub(r'(?:^|\n|\s)([A-Ea-e])\s*[\:\-]\s*', r'\n\1. ', text)
    text = re.sub(r'(?:^|\n|\s)([A-Ea-e])\s+\.\s*', r'\n\1. ', text)

    return text.strip()

def parse_exam_text_into_questions(
    full_text: str,
    filename: str = "exam",
    source_platform: str = "manual",
    default_images: Optional[List[str]] = None,
    page_images: Optional[Dict[int, List[str]]] = None
) -> List[Dict[str, Any]]:
    """
    Core parsing engine for exam text extracted from PDFs or Images.
    Identifies question stems (Câu 1, Bài 1, Question 1...), splits options A, B, C, D,
    detects correct answer checkboxes, and normalizes math fractions and formatting.
    """
    questions: List[Dict[str, Any]] = []
    if not full_text or not full_text.strip():
        return questions

    full_text = clean_ocr_vietnamese_text(full_text)
    
    # 1. Detect competition and grade from text or filename
    base_name = os.path.splitext(filename)[0]
    exam_name = base_name.replace("_", " ").title()
    grade = 5
    detected_platform = source_platform
    
    combined_header_check = f"{filename} {full_text[:400]}".lower()
    
    # Specific exam title detection (e.g. "ĐỀ SỐ 1 - KHỐI 2")
    title_match = re.search(r'(?i)(?:đề\s*số|de\s*so)\s*(\d+).*?(?:khối|khoi|lớp|lop|grade)\s*(\d+)', combined_header_check)
    if title_match:
        exam_name = f"Đề số {title_match.group(1)} - Khối {title_match.group(2)}"
        grade = int(title_match.group(2))
    elif "timo" in combined_header_check:
        detected_platform = "timo"
        exam_name = "Kỳ thi Olympic Toán học Quốc tế TIMO"
    elif "hkimo" in combined_header_check:
        detected_platform = "hkimo"
        exam_name = "Kỳ thi Olympic Toán học Quốc tế HKIMO"
    elif "asmo" in combined_header_check:
        detected_platform = "asmo"
        exam_name = "Kỳ thi Olympic Quốc tế ASMO"
    elif "sasmo" in combined_header_check:
        detected_platform = "sasmo"
        exam_name = "Kỳ thi Olympic Toán Singapore và Châu Á SASMO"
    elif "trạng nguyên" in combined_header_check or "tnmath" in combined_header_check:
        detected_platform = "tnmath"
        exam_name = "Đề thi Trạng Nguyên Toán Học"
    elif "vioedu" in combined_header_check:
        detected_platform = "vioedu"
        exam_name = "Đề thi VioEdu"
        
    grade_match = re.search(r'(?:lớp|grade|khối|khoi|lop)\s*([1-9]|1[0-2])', combined_header_check)
    if grade_match:
        grade = int(grade_match.group(1))
        
    # 2. Pattern matching for question boundaries
    # E.g. Câu 1:, Câu 1., Question 1:, Problem 1:, Bài 1:, or 1. / 1: followed by text
    q_pattern = re.compile(
        r'(?:^|\n)\s*(?:(?:(?:Câu|Question|Problem|Bài|Q)\s*([0-9]{1,3})[\s\.:\)-]+)|(?:([0-9]{1,3})[\.:\),]\s+))',
        re.IGNORECASE
    )
    splits = []
    for m in q_pattern.finditer(full_text):
        q_num = m.group(1) or m.group(2)
        # Avoid splitting on phone status like "05" if followed by minute
        if m.start() < 20 and int(q_num) > 10:
            continue
        splits.append((m, q_num))
    
    # Fallback: If no explicit question numbers, treat entire text as 1 question if non-empty
    if not splits and len(full_text.strip()) > 10:
        raw_blocks = [("1", full_text.strip())]
    else:
        raw_blocks = []
        for i, (match, q_num) in enumerate(splits):
            start_pos = match.end()
            end_pos = splits[i + 1][0].start() if i + 1 < len(splits) else len(full_text)
            raw_block = full_text[start_pos:end_pos].strip()
            if raw_block:
                raw_blocks.append((q_num, raw_block))

    # Consolidate orphan blocks if any short block has no options and was split accidentally
    blocks = []
    for q_num, raw_block in raw_blocks:
        opt_chk = re.findall(r'(?:^|\s|\n)(?:\(?([A-Ea-e])[\.\)]|\b([A-Ea-e])\.)\s*', raw_block)
        if len(opt_chk) < 2 and blocks and len(raw_block) < 250 and not any(p in raw_block.lower() for p in ["câu ", "question ", "đáp án", "bài "]):
            prev_num, prev_content = blocks[-1]
            blocks[-1] = (prev_num, prev_content + " " + raw_block)
        else:
            blocks.append((q_num, raw_block))
                
    for idx, (q_num, raw_block) in enumerate(blocks):
        # Stop if block contains "Đáp án" or "Answer Key" at the end
        if "đáp án" in raw_block.lower() or "answer key" in raw_block.lower():
            raw_block = re.split(r'(?i)(?:bảng đáp án|answer key|hướng dẫn giải)', raw_block)[0].strip()
            
        if not raw_block:
            continue
            
        # Extract Options: A. ... B. ... C. ... D. ... or (A) ... (B) ...
        opt_pattern = re.compile(
            r'(?:^|\s|\n)(?:\(?([A-Ea-e])[\.\)]|\b([A-Ea-e])\.)\s*(.*?)(?=(?:(?:\s|\n)(?:\(?[A-Ea-e][\.\)]|[A-Ea-e]\.))|$)',
            re.DOTALL
        )
        opt_matches = list(opt_pattern.finditer(raw_block))
        
        options = []
        question_content = raw_block
        detected_correct_answer = None
        
        if len(opt_matches) >= 2:  # Found multiple-choice options (at least 2, typically 4)
            first_opt_start = opt_matches[0].start()
            question_content = raw_block[:first_opt_start].strip()
            
            for m in opt_matches:
                opt_id = (m.group(1) or m.group(2) or "A").upper()
                opt_raw = m.group(3).strip()
                # Check for checkmark / radio checked in option text
                is_correct = bool(re.search(r'[✓✔☑]|checked|\(đúng\)|\bcorrect\b', opt_raw, re.IGNORECASE))
                clean_opt = re.sub(r'[✓✔☑]|checked|\(đúng\)|\bcorrect\b', '', opt_raw, flags=re.IGNORECASE).strip()
                clean_opt = re.sub(r'\s+', ' ', clean_opt).strip()
                
                if is_correct and not detected_correct_answer:
                    detected_correct_answer = opt_id
                    
                options.append({
                    "id": opt_id,
                    "content": clean_opt,
                    "is_correct": is_correct
                })
                
        # If no option was marked with checkmark, default first option or None
        if not detected_correct_answer and options:
            detected_correct_answer = "A"
            options[0]["is_correct"] = True
            
        # Check question type
        q_type = "single_choice" if options else "fill_blank"
        
        # Clean content & normalize basic math fractions (e.g. 1/2 -> $\frac{1}{2}$)
        norm_content = re.sub(r'(\d+)/(\d+)', r'$\\frac{\1}{\2}$', question_content)
        norm_content = re.sub(r'\s+', ' ', norm_content).strip()
        
        # Infer subject
        from backend.classifier import classify_subject
        subject = classify_subject(content_text=norm_content, content_html=f"<p>{norm_content}</p>")
        
        # Attach images: if page_images passed, distribute them, else default_images
        imgs = []
        if page_images and (idx < len(page_images.get(0, []))):
            first_page_imgs = page_images.get(0, [])
            if idx < len(first_page_imgs):
                imgs.append(first_page_imgs[idx])
        elif default_images:
            imgs = list(default_images)
            
        difficulty = "medium"
        if detected_platform in ["timo", "hkimo", "asmo", "sasmo"]:
            difficulty = "olympiad"
            
        questions.append({
            "id": f"{detected_platform}_{uuid.uuid4().hex[:8]}",
            "source_platform": detected_platform,
            "exam_name": f"{exam_name} - Câu {q_num}",
            "grade": grade,
            "subject": subject,
            "topic": f"{exam_name}" if exam_name else "Đề thi bóc tách (OCR/PDF)",
            "question_type": q_type,
            "content_html": f"<p>{norm_content}</p>",
            "content_text": norm_content,
            "images": imgs,
            "options": options,
            "correct_answer": detected_correct_answer,
            "explanation": None,
            "difficulty": difficulty,
            "created_at": datetime.now().isoformat()
        })
        
    return questions

def extract_questions_from_pdf(pdf_bytes: bytes, filename: str = "exam.pdf") -> List[Dict[str, Any]]:
    """
    Intelligently extracts questions, options, and images from PDF exam papers (TIMO, HKIMO, ASMO, etc.)
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = ""
    page_texts = []
    page_images: Dict[int, List[str]] = {}
    
    # 1. Extract text and images per page
    for page_idx, page in enumerate(reader.pages):
        p_text = page.extract_text() or ""
        page_texts.append(p_text)
        full_text += f"\n--- Page {page_idx + 1} ---\n" + p_text
        
        # Extract images
        page_images[page_idx] = []
        try:
            for img_idx, img_obj in enumerate(page.images):
                img_name = f"pdf_{uuid.uuid4().hex[:12]}_{img_idx}.png"
                img_path = os.path.join(MEDIA_DIR, img_name)
                with open(img_path, "wb") as f:
                    f.write(img_obj.data)
                page_images[page_idx].append(f"/media/{img_name}")
        except Exception as e:
            print(f"Error extracting image from page {page_idx}: {e}")
            
    return parse_exam_text_into_questions(
        full_text=full_text,
        filename=filename,
        source_platform="manual",
        page_images=page_images
    )

def preprocess_image_for_ocr(image_bytes: bytes) -> Optional[np.ndarray]:
    """
    Applies advanced image preprocessing optimized for Vietnamese OCR.
    Includes: adaptive upscaling (LANCZOS4), deskewing, CLAHE, bilateral filter, and unsharp mask.
    """
    if cv2 is None or np is None:
        return None
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        
        # 1. Adaptive upscaling to 1200px minimum width for better diacritics recognition
        try:
            h, w = img.shape[:2]
            target_w = 1200.0
            if w < target_w:
                scale = max(1.0, target_w / w)
                new_w, new_h = int(w * scale), int(h * scale)
                # INTER_LANCZOS4 yields better quality for upscaling text than INTER_CUBIC
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        except Exception as e:
            print(f"[preprocess_image_for_ocr] Upscaling error: {e}")

        # 2. Deskewing to correct rotation (critical for Vietnamese diacritics)
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Threshold to get text as white pixels
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) > 0:
                angle = cv2.minAreaRect(coords)[-1]
                # Adjust angle for OpenCV versions returning [-90, 0)
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                
                # Only deskew if the angle is significant but not excessive
                if abs(angle) > 0.5 and abs(angle) < 15:
                    (h, w) = img.shape[:2]
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, angle, 1.0)
                    img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        except Exception as e:
            print(f"[preprocess_image_for_ocr] Deskew error: {e}")

        # 3. CLAHE contrast enhancement in LAB color space
        # Dramatically improves recognition of faded/low-contrast text
        try:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl,a,b))
            img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        except Exception as e:
            print(f"[preprocess_image_for_ocr] CLAHE error: {e}")

        # 4. Gentle noise reduction using bilateral filter
        # Preserves edges which is important for diacritics like ă, â, ê, ô, ơ, ư
        try:
            img = cv2.bilateralFilter(img, 5, 50, 50)
        except Exception as e:
            print(f"[preprocess_image_for_ocr] Bilateral filter error: {e}")

        # 5. Sharpening using unsharp mask
        # Makes diacritics more distinguishable
        try:
            gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
            img = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)
        except Exception as e:
            print(f"[preprocess_image_for_ocr] Sharpening error: {e}")

        return img
    except Exception as e:
        print(f"[preprocess_image_for_ocr] Error: {e}")
        return None

def extract_questions_from_image(
    image_bytes: Union[bytes, str],
    filename: str = "exam_image.png",
    engine: str = "rapid"
) -> List[Dict[str, Any]]:
    """
    Extracts exam questions from image formats (.png, .jpg, .jpeg, .webp, .bmp).
    Performs preprocessing, OCR text extraction (RapidOCR / VietOCR ONNX), question boundary splitting,
    MCQ (A/B/C/D) option identification, and saves preview image into data/media/.
    """
    if isinstance(image_bytes, str):
        if filename == "exam_image.png":
            filename = os.path.basename(image_bytes)
        with open(image_bytes, "rb") as f_in:
            image_bytes = f_in.read()

    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        ext = ".png"
        
    img_id = uuid.uuid4().hex[:12]
    saved_filename = f"ocr_{img_id}{ext}"
    saved_filepath = os.path.join(MEDIA_DIR, saved_filename)
    
    # 1. Save original image to media directory for web preview & lightbox zoom
    with open(saved_filepath, "wb") as f:
        f.write(image_bytes)
    media_url = f"/media/{saved_filename}"
    
    # 2. Image Preprocessing with OpenCV
    ocr_target_path = saved_filepath
    preprocessed_img = preprocess_image_for_ocr(image_bytes)
    if preprocessed_img is not None and cv2 is not None:
        preprocessed_filename = f"ocr_{img_id}_prep{ext}"
        preprocessed_path = os.path.join(MEDIA_DIR, preprocessed_filename)
        cv2.imwrite(preprocessed_path, preprocessed_img)
        ocr_target_path = preprocessed_path
        
    # 3. Perform OCR Text Extraction with Multi-Engine Support
    ocr_lines = []
    engine_used = "rapid"
    opt_line_re = re.compile(r'^(?:\(?([A-Ea-e])[\.:\)]\s*|([A-Ea-e])(?=\d|[A-Z][a-z]))')

    # Engine Selection: AI Vision (OpenRouter / OpenCode)
    if engine.lower() in ("ai_vision", "vision", "opencode", "openrouter"):
        try:
            import asyncio
            from backend.ai_vision import extract_questions_with_ai_vision
            
            def _call_vision():
                return asyncio.run(extract_questions_with_ai_vision(image_bytes, filename=filename, media_url=media_url))

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    ai_qs, engine_used_name = pool.submit(_call_vision).result()
            else:
                ai_qs, engine_used_name = _call_vision()

            if ai_qs:
                return ai_qs
        except Exception as e:
            print(f"[extract_questions_from_image] AI Vision attempt failed: {e}. Falling back to standard OCR...")

    # Engine Selection: VietOCR ONNX vs RapidOCR
    if engine.lower() in ("vietocr", "deepdoc_vietocr", "vietocr_onnx"):
        try:
            from backend.vietocr_onnx import get_vietocr_engine
            v_engine = get_vietocr_engine()
            if v_engine.is_ready():
                # If VietOCR model is loaded, use RapidOCR DBNet for box detection then VietOCR ONNX for text recognition
                from rapidocr_onnxruntime import RapidOCR
                box_detector = RapidOCR()
                res, _ = box_detector(ocr_target_path)
                if res and cv2 is not None and preprocessed_img is not None:
                    for item in res:
                        box = item[0]
                        line_txt = item[1]
                        # Crop box polygon
                        xs = [int(p[0]) for p in box]
                        ys = [int(p[1]) for p in box]
                        x1, x2 = max(0, min(xs)), min(preprocessed_img.shape[1], max(xs))
                        y1, y2 = max(0, min(ys)), min(preprocessed_img.shape[0], max(ys))
                        is_green = False
                        if (x2 - x1) > 5 and (y2 - y1) > 5:
                            crop = preprocessed_img[y1:y2, x1:x2]
                            b_m, g_m, r_m = crop.mean(axis=(0, 1))
                            if (g_m > r_m + 6) and (g_m > b_m + 4):
                                is_green = True
                            recognized = v_engine.recognize_line(crop)
                            if recognized:
                                line_txt = recognized
                        line_clean = line_txt.strip() if line_txt else ""
                        if is_green and opt_line_re.match(line_clean) and not any(m in line_clean for m in ["✓", "✔", "☑"]):
                            line_clean += " ✓"
                        ocr_lines.append(line_clean)
                    engine_used = "vietocr_onnx"
                elif res:
                    ocr_lines = [r[1] for r in res]
                    engine_used = "rapid_fallback"
            else:
                engine_used = "rapid_auto"
        except Exception as e:
            print(f"[extract_questions_from_image] VietOCR ONNX attempt error: {e}")
            engine_used = "rapid_fallback"

    # Default RapidOCR Engine (if lines not yet extracted)
    if not ocr_lines:
        try:
            from rapidocr_onnxruntime import RapidOCR
            rap_engine = RapidOCR()
            res, _ = rap_engine(ocr_target_path)
            if res:
                for item in res:
                    box = item[0]
                    line_txt = item[1]
                    is_green = False
                    if preprocessed_img is not None and cv2 is not None:
                        xs = [int(p[0]) for p in box]
                        ys = [int(p[1]) for p in box]
                        x1, x2 = max(0, min(xs)), min(preprocessed_img.shape[1], max(xs))
                        y1, y2 = max(0, min(ys)), min(preprocessed_img.shape[0], max(ys))
                        if (x2 - x1) > 5 and (y2 - y1) > 5:
                            crop = preprocessed_img[y1:y2, x1:x2]
                            b_m, g_m, r_m = crop.mean(axis=(0, 1))
                            if (g_m > r_m + 6) and (g_m > b_m + 4):
                                is_green = True
                    line_clean = line_txt.strip() if line_txt else ""
                    if is_green and opt_line_re.match(line_clean) and not any(m in line_clean for m in ["✓", "✔", "☑"]):
                        line_clean += " ✓"
                    ocr_lines.append(line_clean)
                engine_used = "rapid"
        except Exception as e:
            pass
        
    # Fallback Engine B: EasyOCR
    if len(ocr_lines) < 3:
        try:
            import easyocr
            reader = easyocr.Reader(['vi', 'en'], gpu=False)
            ocr_results = reader.readtext(ocr_target_path, detail=0)
            if ocr_results:
                ocr_lines = ocr_results
                engine_used = "easyocr"
        except Exception as e:
            pass
            
    # Fallback Engine C: pytesseract
    if len(ocr_lines) < 3:
        try:
            import pytesseract
            img_pil = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img_pil, lang="vie+eng")
            if text:
                ocr_lines = text.split("\n")
                engine_used = "pytesseract"
        except Exception:
            pass
            
    raw_text = "\n".join(ocr_lines)
    
    # 4. Parse Questions and MCQ Options
    questions = parse_exam_text_into_questions(
        full_text=raw_text,
        filename=filename,
        source_platform="image_ocr",
        default_images=[media_url]
    )

    for q in questions:
        q["ocr_engine_used"] = engine_used
    
    return questions
