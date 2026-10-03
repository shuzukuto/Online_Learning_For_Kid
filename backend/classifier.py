from __future__ import annotations
import re
from typing import List, Dict, Any, Optional

# Keywords & patterns for classification
VIETNAMESE_KEYWORDS = [
    # Mẫu câu & Kiểu câu (GDPT 2018 Tiểu học & THCS)
    r'ai là gì', r'ai làm gì', r'ai thế nào', r'câu nêu đặc điểm', r'câu nêu hoạt động', r'câu giới thiệu',
    r'câu khiến', r'câu cảm', r'câu hỏi', r'câu kể', r'kiểu câu', r'mẫu câu',
    # Dấu câu
    r'dấu câu', r'dấu phẩy', r'dấu chấm', r'dấu chấm hỏi', r'dấu chấm than', r'dấu hai chấm', r'dấu ngoặc kép', r'dấu gạch ngang',
    # Ngữ âm & Cấu tạo từ
    r'điền âm', r'điền vần', r'chọn từ', r'từ có vần', r'vần nào', r'âm đầu', r'tiếng bắt đầu', r'tiếng có âm',
    r'từ chỉ sự vật', r'từ chỉ hoạt động', r'từ chỉ đặc điểm',
    r'từ đồng nghĩa', r'từ trái nghĩa', r'từ nhiều nghĩa', r'từ ghép', r'từ láy',
    r'chủ ngữ', r'vị ngữ', r'trạng ngữ', r'câu ghép', r'câu đơn',
    r'nhân hóa', r'so sánh', r'ẩn dụ', r'hoán dụ', r'thành ngữ', r'tục ngữ', r'ca dao',
    r'chính tả', r'vần', r'từ loại', r'danh từ', r'động từ', r'tính từ',
    r'đại từ', r'quan hệ từ', r'phụ ngữ', r'điền từ vào chỗ trống', r'điền vào chỗ chấm',
    r'từ nào viết sai', r'bài thơ', r'nhà thơ', r'tác giả', r'tiếng mẹ đẻ',
    # Đọc hiểu & Tập làm văn
    r'tập làm văn', r'bài văn', r'đoạn văn', r'tiếng việt', r'trạng nguyên tiếng việt',
    r'bài đọc', r'câu chuyện', r'nhân vật', r'chi tiết', r'nội dung bài', r'cho thấy điều gì',
    r'ý nghĩa', r'tình bạn', r'lời khuyên', r'đọc hiểu', r'sắp xếp các câu', r'thành đoạn văn',
    r'chăm sóc cây', r'giúp đỡ gia đình', r'bạn thân', r'lớp học'
]

ENGLISH_KEYWORDS = [
    r'\bthe\b', r'\bwhich\b', r'\bwhat\b', r'\bwhere\b', r'\bwhen\b', r'\bwho\b',
    r'\bchoose\b', r'\bcorrect\b', r'\bblank\b', r'\bread\b',
    r'\bsentence\b', r'\bword\b', r'\bpassage\b', r'\bfollowing\b', r'\bopposite\b',
    r'\bsynonym\b', r'\bantonym\b', r'\bmeaning\b', r'\bfill in\b', r'\benglish\b',
    r'\bgrammar\b', r'\btense\b', r'\bverb\b', r'\bnoun\b', r'\badjective\b',
    r'\bvocabulary\b', r'\bpronunciation\b', r'\bconversations?\b', r'\bcomplete the sentence\b'
]

MATH_KEYWORDS = [
    # LaTeX & math symbols
    r'\\frac', r'\\sqrt', r'\\times', r'\\div', r'\\le', r'\\ge', r'\\pm',
    r'\bcm\b', r'\bm\b', r'\bkm\b', r'\bkg\b', r'km/h',
    # Vietnamese math concepts
    r'phân số', r'hỗn số', r'số thập phân', r'tính giá trị', r'biểu thức',
    r'hình vuông', r'hình chữ nhật', r'hình thang', r'hình tròn', r'tam giác', r'hình thoi',
    r'diện tích', r'chu vi', r'thể tích', r'vận tốc', r'quãng đường', r'thời gian',
    r'số tự nhiên', r'chữ số tận cùng', r'chia hết cho', r'bội chung', r'ước chung',
    r'tổ hợp', r'xác suất', r'phương trình', r'bất đẳng thức', r'đáy lớn', r'đáy bé', r'chiều cao',
    r'bán kính', r'đường kính', r'tổng các số', r'chữ số', r'hàng đơn vị', r'hàng chục',
    r'hàng trăm', r'hàng nghìn', r'hàng triệu', r'lớn hơn', r'nhỏ hơn', r'bằng nhau',
    r'số liền trước', r'số liền sau', r'phép tính', r'phép cộng', r'phép trừ', r'phép nhân', r'phép chia',
    r'tìm x', r'chẵn', r'lẻ', r'tổng', r'hiệu', r'tích', r'thương', r'tỉ số',
    # English Olympic & Primary Math terms (TIMO, HKIMO, ASMO, K5 Learning, IXL, Common Core)
    r'\bhow many\b', r'\bdigits?\b', r'\bnumbers?\b', r'\barea\b', r'\bperimeter\b',
    r'\bside length\b', r'\bsum of\b', r'\bdivisible\b', r'\bremainder\b', r'\bequation\b',
    r'\bfactor\b', r'\bmultiple\b', r'\bprime\b', r'\bconsecutive\b', r'\bratio\b',
    r'\bplace value\b', r'\btens and ones\b', r'\bhundreds\b', r'\bregrouping\b',
    r'\bword problem\b', r'\beven or odd\b', r'\bskip counting\b', r'\bexpanded form\b',
    r'\bvertices\b', r'\bvertex\b', r'\bshapes?\b', r'\bcoins?\b', r'\bcents?\b',
    r'\bdimes?\b', r'\bnickels?\b', r'\bquarters?\b', r'\bk5 learning\b', r'\bixl\b',
    r'\bmath worksheet\b', r'\bnumber line\b'
]

SCIENCE_KEYWORDS = [
    r'quang hợp', r'động vật', r'thực vật', r'hệ thần kinh', r'hệ tiêu hóa',
    r'tuần hoàn', r'không khí', r'nước', r'nhiệt độ', r'chất rắn', r'chất lỏng',
    r'khí quyển', r'môi trường', r'năng lượng', r'nam châm', r'trọng lực',
    r'khoa học', r'tự nhiên và xã hội', r'sinh sản', r'thụ phấn', r'nhụy hoa', r'nhị hoa'
]

VN_DIACRITICS_REGEX = re.compile(r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', re.IGNORECASE)

def classify_subject(
    content_text: str = "",
    content_html: str = "",
    topic: str = "",
    source_platform: str = "",
    options: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Intelligently classifies a question into its subject:
    'math' | 'vietnamese' | 'english' | 'science' | 'history_geo' | 'informatics'
    """
    raw_text = content_text or ""
    topic_str = topic or ""
    combined = f"{raw_text} {topic_str} {source_platform or ''}".lower()
    has_vn_diacritics = bool(VN_DIACRITICS_REGEX.search(raw_text))
    platform_clean = (source_platform or "").lower().strip()

    # 1. Explicit Subject Clues in Topic or Content
    if "trạng nguyên tiếng việt" in combined or "môn tiếng việt" in combined or "tiếng việt" in topic_str.lower():
        return "vietnamese"
    if "tiếng anh" in topic_str.lower() or "english contest" in combined or "grammar" in topic_str.lower():
        return "english"
    if "khoa học" in topic_str.lower() or "tự nhiên và xã hội" in topic_str.lower():
        return "science"
    if "lịch sử" in topic_str.lower() or "địa lý" in topic_str.lower():
        return "history_geo"
    if "tin học" in topic_str.lower() or "informatics" in topic_str.lower():
        return "informatics"

    # 2. Check Strong Math Signals (Formulas, Math Symbols, Numbers in Context)
    has_math_formula = bool(
        "$" in content_html or 
        "\\frac" in content_html or 
        "\\sqrt" in content_html or 
        "\\times" in content_html or
        "\\div" in content_html or
        "math-tex" in content_html or
        re.search(r'\$\s*\d+', content_html)
    )
    has_math_operator = bool(re.search(r'[\$\=><%]|\d+\s*[\+\-\*/×÷=]\s*\d+', raw_text))

    # 3. Calculate Keyword Matches
    vn_score = sum(1 for kw in VIETNAMESE_KEYWORDS if re.search(kw, combined))
    math_score = sum(1 for kw in MATH_KEYWORDS if re.search(kw, combined))
    sci_score = sum(1 for kw in SCIENCE_KEYWORDS if re.search(kw, combined))
    en_score = sum(1 for kw in ENGLISH_KEYWORDS if re.search(kw, combined))

    # 4. Science Questions (Khoa học)
    if sci_score > 0 and sci_score >= math_score and sci_score >= vn_score:
        return "science"

    # 5. If Vietnamese Linguistic Clues are dominant
    if vn_score > 0 and vn_score > math_score and not has_math_formula:
        return "vietnamese"

    # Reading passage heuristic: Substantial Vietnamese text with no math operators or formulas
    if has_vn_diacritics and not has_math_formula and not has_math_operator and math_score == 0 and sci_score == 0:
        if vn_score > 0 or len(raw_text) >= 50:
            return "vietnamese"

    # 6. If Math formulas or Math concepts are present
    if has_math_formula or math_score > 0 or has_math_operator:
        return "math"

    # 7. Platform-Specific Strong Clues
    # Olympic Math competitions (TIMO, HKIMO, ASMO, SASMO) are ALWAYS Math
    if platform_clean in ["timo", "hkimo", "asmo", "sasmo"]:
        return "math"

    # IOE platform is English
    if re.search(r'\bioe\b', platform_clean) or "ioe.vn" in combined:
        return "english"

    # 8. English Questions (Tiếng Anh)
    # If text is predominantly English words with zero Vietnamese diacritics
    if not has_vn_diacritics:
        en_words = re.findall(r'\b[a-zA-Z]{2,}\b', raw_text)
        if len(en_words) >= 5 and en_score >= 1:
            return "english"

    # 9. VioEdu & Trạng Nguyên default
    if "vioedu" in platform_clean or "tnmath" in platform_clean:
        if has_vn_diacritics and vn_score > 0:
            return "vietnamese"
        return "math"

    # Fallback
    if has_vn_diacritics and vn_score > 0:
        return "vietnamese"
    return "math"
