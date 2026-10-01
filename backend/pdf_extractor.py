import os
import re
import uuid
from typing import List, Dict, Any
from pypdf import PdfReader
from PIL import Image
import io

MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

def extract_questions_from_pdf(pdf_bytes: bytes, filename: str = "exam.pdf") -> List[Dict[str, Any]]:
    """
    Intelligently extracts questions, options, and images from PDF exam papers (TIMO, HKIMO, ASMO, etc.)
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    questions: List[Dict[str, Any]] = []
    
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
            
    # 2. Detect competition and grade from text
    exam_name = filename.replace(".pdf", "")
    grade = 5
    source_platform = "manual"
    
    lower_full = full_text.lower()
    if "timo" in lower_full:
        source_platform = "timo"
        exam_name = "Kỳ thi Olympic Toán học Quốc tế TIMO"
    elif "hkimo" in lower_full:
        source_platform = "hkimo"
        exam_name = "Kỳ thi Olympic Toán học Quốc tế HKIMO"
    elif "asmo" in lower_full:
        source_platform = "asmo"
        exam_name = "Kỳ thi Olympic Quốc tế ASMO"
    elif "sasmo" in lower_full:
        source_platform = "sasmo"
        exam_name = "Kỳ thi Olympic Toán Singapore và Châu Á SASMO"
    elif "trạng nguyên" in lower_full or "tnmath" in lower_full:
        source_platform = "tnmath"
        exam_name = "Đề thi Trạng Nguyên Toán Học"
    elif "vioedu" in lower_full:
        source_platform = "vioedu"
        exam_name = "Đề thi VioEdu"
        
    grade_match = re.search(r'(?:lớp|grade|khối)\s*([1-9]|1[0-2])', lower_full)
    if grade_match:
        grade = int(grade_match.group(1))
        
    # 3. Pattern matching for question boundaries
    # E.g. Câu 1:, Câu 1., Question 1:, Question 1., Problem 1:, Bài 1:
    q_pattern = re.compile(
        r'(?:^|\n)\s*(?:Câu|Question|Problem|Bài)\s*([0-9]{1,3})[\s\.:\)-]+',
        re.IGNORECASE
    )
    
    splits = list(q_pattern.finditer(full_text))
    
    if not splits:
        # Fallback: simple numeric bullet "1. ... 2. ... 3. ..."
        q_pattern = re.compile(r'(?:^|\n)\s*([0-9]{1,3})\s*[\.\)]\s+', re.IGNORECASE)
        splits = list(q_pattern.finditer(full_text))
        
    if splits:
        for i, match in enumerate(splits):
            q_num = match.group(1)
            start_pos = match.end()
            end_pos = splits[i + 1].start() if i + 1 < len(splits) else len(full_text)
            
            raw_block = full_text[start_pos:end_pos].strip()
            
            # Stop if block contains "Đáp án" or "Answer Key" at the end
            if "đáp án" in raw_block.lower() or "answer key" in raw_block.lower():
                raw_block = re.split(r'(?i)(?:bảng đáp án|answer key)', raw_block)[0].strip()
                
            if not raw_block:
                continue
                
            # Extract Options: A. ... B. ... C. ... D. ... or (A) ... (B) ...
            opt_pattern = re.compile(r'(?:^|\s|\n)(?:\(?([A-Ea-e])[\.\)]|\b([A-Ea-e])\.)\s*(.*?)(?=(?:(?:\s|\n)(?:\(?[A-Ea-e][\.\)]|[A-Ea-e]\.))|$)', re.DOTALL)
            opt_matches = list(opt_pattern.finditer(raw_block))
            
            options = []
            question_content = raw_block
            
            if len(opt_matches) >= 3:  # Found multiple-choice options
                first_opt_start = opt_matches[0].start()
                question_content = raw_block[:first_opt_start].strip()
                
                for m in opt_matches:
                    opt_id = (m.group(1) or m.group(2) or "A").upper()
                    opt_text = m.group(3).strip()
                    options.append({
                        "id": opt_id,
                        "content": opt_text,
                        "is_correct": False
                    })
                    
            # Check question type
            q_type = "single_choice" if options else "fill_blank"
            
            # Clean content & normalize basic math
            # E.g. 1/2 -> \frac{1}{2}
            norm_content = re.sub(r'(\d+)/(\d+)', r'$\\frac{\1}{\2}$', question_content)
            norm_content = norm_content.replace("\n", " ").strip()
            
            # Associate images: if there are extracted images from PDF, distribute them
            imgs = []
            if page_images and (i < len(page_images.get(0, []))):
                # Attach image if available
                first_page_imgs = page_images.get(0, [])
                if i < len(first_page_imgs):
                    imgs.append(first_page_imgs[i])
                    
            questions.append({
                "id": f"{source_platform}_{uuid.uuid4().hex[:8]}",
                "source_platform": source_platform,
                "exam_name": f"{exam_name} - Câu {q_num}",
                "grade": grade,
                "subject": "math",
                "topic": "Olympic & Đề thi thử",
                "question_type": q_type,
                "content_html": f"<p>{norm_content}</p>",
                "content_text": norm_content,
                "images": imgs,
                "options": options,
                "correct_answer": None,
                "explanation": None,
                "difficulty": "olympiad" if source_platform in ["timo", "hkimo", "asmo", "sasmo"] else "medium"
            })
            
    return questions
