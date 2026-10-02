import os
import re
import io
import uuid
import unicodedata
from typing import List, Dict, Any, Optional
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
    """Normalizes Unicode NFC and fixes frequent OCR misrecognitions in Vietnamese exam papers."""
    if not text:
        return ""
    # 1. Unicode NFC normalization (combining accents -> canonical precomposed characters)
    text = unicodedata.normalize('NFC', text)
    
    # 2. Fix common OCR mistakes on "Câu" / "Bài"
    # E.g. C@u 1, Cdu 1, Cáu 1, Cau 1 -> Câu 1
    text = re.sub(r'(?i)\b(?:c@u|cdu|cáu|cau)\s*([0-9]{1,3})\b', r'Câu \1', text)
    text = re.sub(r'(?i)\b(?:b@i|bai)\s*([0-9]{1,3})\b', r'Bài \1', text)
    
    # 3. Standardize option prefixes (e.g., "(A)", "A - ", "A: ", "A .") -> "\nA. "
    text = re.sub(r'(?:^|\n|\s)\(([A-Ea-e])\)\s*', r'\n\1. ', text)
    text = re.sub(r'(?:^|\n|\s)([A-Ea-e])\s*[\:\-]\s*', r'\n\1. ', text)
    text = re.sub(r'(?:^|\n|\s)([A-Ea-e])\s+\.\s*', r'\n\1. ', text)

    return text

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
    and normalizes math fractions and formatting.
    """
    questions: List[Dict[str, Any]] = []
    if not full_text or not full_text.strip():
        return questions

    full_text = clean_ocr_vietnamese_text(full_text)
    
    # 1. Detect competition and grade from text
    base_name = os.path.splitext(filename)[0]
    exam_name = base_name
    grade = 5
    detected_platform = source_platform
    
    lower_full = full_text.lower()
    if "timo" in lower_full:
        detected_platform = "timo"
        exam_name = "Kỳ thi Olympic Toán học Quốc tế TIMO"
    elif "hkimo" in lower_full:
        detected_platform = "hkimo"
        exam_name = "Kỳ thi Olympic Toán học Quốc tế HKIMO"
    elif "asmo" in lower_full:
        detected_platform = "asmo"
        exam_name = "Kỳ thi Olympic Quốc tế ASMO"
    elif "sasmo" in lower_full:
        detected_platform = "sasmo"
        exam_name = "Kỳ thi Olympic Toán Singapore và Châu Á SASMO"
    elif "trạng nguyên" in lower_full or "tnmath" in lower_full:
        detected_platform = "tnmath"
        exam_name = "Đề thi Trạng Nguyên Toán Học"
    elif "vioedu" in lower_full:
        detected_platform = "vioedu"
        exam_name = "Đề thi VioEdu"
        
    grade_match = re.search(r'(?:lớp|grade|khối)\s*([1-9]|1[0-2])', lower_full)
    if grade_match:
        grade = int(grade_match.group(1))
        
    # 2. Pattern matching for question boundaries
    # E.g. Câu 1:, Câu 1., Question 1:, Problem 1:, Bài 1:
    q_pattern = re.compile(
        r'(?:^|\n)\s*(?:Câu|Question|Problem|Bài)\s*([0-9]{1,3})[\s\.:\)-]+',
        re.IGNORECASE
    )
    splits = list(q_pattern.finditer(full_text))
    
    if not splits:
        # Fallback: simple numeric bullet "1. ... 2. ... 3. ..."
        q_pattern = re.compile(r'(?:^|\n)\s*([0-9]{1,3})\s*[\.\)]\s+', re.IGNORECASE)
        splits = list(q_pattern.finditer(full_text))
        
    # Fallback: If no explicit question numbers, treat entire text as 1 question if non-empty
    if not splits and len(full_text.strip()) > 10:
        blocks = [("1", full_text.strip())]
    else:
        blocks = []
        for i, match in enumerate(splits):
            q_num = match.group(1)
            start_pos = match.end()
            end_pos = splits[i + 1].start() if i + 1 < len(splits) else len(full_text)
            raw_block = full_text[start_pos:end_pos].strip()
            if raw_block:
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
        
        if len(opt_matches) >= 2:  # Found multiple-choice options (at least 2, typically 4)
            first_opt_start = opt_matches[0].start()
            question_content = raw_block[:first_opt_start].strip()
            
            for m in opt_matches:
                opt_id = (m.group(1) or m.group(2) or "A").upper()
                opt_text = m.group(3).strip()
                opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                options.append({
                    "id": opt_id,
                    "content": opt_text,
                    "is_correct": False
                })
                
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
            "topic": "Olympic & Đề thi thử" if detected_platform in ["timo", "hkimo", "asmo", "sasmo"] else "Đề thi bóc tách (OCR/PDF)",
            "question_type": q_type,
            "content_html": f"<p>{norm_content}</p>",
            "content_text": norm_content,
            "images": imgs,
            "options": options,
            "correct_answer": None,
            "explanation": None,
            "difficulty": difficulty
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
    """Applies grayscale conversion, CLAHE contrast enhancement, and bilateral denoising for sharp OCR."""
    if cv2 is None or np is None:
        return None
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        denoised = cv2.bilateralFilter(contrast, 9, 75, 75)
        return denoised
    except Exception as e:
        print(f"[preprocess_image_for_ocr] Error: {e}")
        return None

def extract_questions_from_image(image_bytes: bytes, filename: str = "exam_image.png") -> List[Dict[str, Any]]:
    """
    Extracts exam questions from image formats (.png, .jpg, .jpeg, .webp, .bmp).
    Performs preprocessing, OCR text extraction, question boundary splitting,
    MCQ (A/B/C/D) option identification, and saves preview image into data/media/.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        ext = ".png"
        
    img_id = uuid.uuid4().hex[:12]
    saved_filename = f"ocr_{img_id}{ext}"
    saved_filepath = os.path.join(MEDIA_DIR, saved_filename)
    
    # 1. Save original image to media directory for web preview
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
    
    # Engine A: RapidOCR (PaddleOCR ONNX, fast, highly accurate, pre-bundled)
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        res, _ = engine(ocr_target_path)
        if res:
            ocr_lines = [r[1] for r in res]
    except Exception as e:
        pass
        
    # Engine B: EasyOCR (Deep Learning, native Vietnamese + English)
    if not ocr_lines:
        try:
            import easyocr
            reader = easyocr.Reader(['vi', 'en'], gpu=False)
            ocr_results = reader.readtext(ocr_target_path, detail=0)
            if ocr_results:
                ocr_lines = ocr_results
        except Exception as e:
            pass
            
    # Engine C: pytesseract fallback
    if not ocr_lines:
        try:
            import pytesseract
            img_pil = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img_pil, lang="vie+eng")
            if text:
                ocr_lines = text.split("\n")
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
    
    return questions
