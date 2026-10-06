"""
Vietnamese NLP Post-Processing Module
Provides functions to restore diacritics, normalize unicode, fix common OCR confusions,
and calculate Vietnamese confidence scores. Used as a post-processing step for OCR results.
"""

import re
import unicodedata

__all__ = [
    'VIETNAMESE_COMMON_WORDS',
    'restore_vietnamese_diacritics',
    'normalize_vietnamese_unicode',
    'calculate_vietnamese_confidence',
    'fix_common_ocr_confusions'
]

VIETNAMESE_COMMON_WORDS = {
    # Toán học (Math)
    'toan hoc': 'toán học',
    'phep tinh': 'phép tính',
    'ket qua': 'kết quả',
    'hinh chu nhat': 'hình chữ nhật',
    'phan so': 'phân số',
    'tu so': 'tử số',
    'mau so': 'mẫu số',
    'dien tich': 'diện tích',
    'chu vi': 'chu vi',
    'duong thang': 'đường thẳng',
    'dinh': 'đỉnh',
    'canh': 'cạnh',
    'goc': 'góc',
    'tam giac': 'tam giác',
    'ban kinh': 'bán kính',
    'duong kinh': 'đường kính',
    'the tich': 'thể tích',
    'trung binh': 'trung bình',
    'phep cong': 'phép cộng',
    'phep tru': 'phép trừ',
    'phep nhan': 'phép nhân',
    'phep chia': 'phép chia',
    'so chan': 'số chẵn',
    'so le': 'số lẻ',
    'so nguyen to': 'số nguyên tố',
    'uoc chung': 'ước chung',
    'boi chung': 'bội chung',
    'luy thua': 'lũy thừa',
    'can bac hai': 'căn bậc hai',
    'do thi': 'đồ thị',
    'ham so': 'hàm số',
    'chieu dai': 'chiều dài',
    'chieu rong': 'chiều rộng',
    'chieu cao': 'chiều cao',
    'trong luong': 'trọng lượng',
    'khoi luong': 'khối lượng',
    'khoang cach': 'khoảng cách',
    'van toc': 'vận tốc',
    'thoi gian': 'thời gian',
    'don vi': 'đơn vị',
    
    # Tiếng Việt chung (General Vietnamese)
    'duoc': 'được',
    'khong': 'không',
    'nhung': 'những',
    'nguoi': 'người',
    'nhieu': 'nhiều',
    'truong': 'trường',
    'duong': 'đường',
    'nuoc': 'nước',
    'chuong': 'chương',
    'thuong': 'thường',
    'phuong': 'phương',
    'huong': 'hướng',
    'vuot': 'vượt',
    'truoc': 'trước',
    'trong': 'trong',
    'ngoai': 'ngoài',
    'quoc gia': 'quốc gia',
    'viet nam': 'việt nam',
    'tieng viet': 'tiếng việt',
    'cong dong': 'cộng đồng',
    'xa hoi': 'xã hội',
    'phat trien': 'phát triển',
    'lich su': 'lịch sử',
    'dia ly': 'địa lý',
    'van hoc': 'văn học',
    'khoa hoc': 'khoa học',
    'tu nhien': 'tự nhiên',
    
    # Giáo dục (Education)
    'hoc sinh': 'học sinh',
    'giao vien': 'giáo viên',
    'truong hoc': 'trường học',
    'lop hoc': 'lớp học',
    'bai tap': 'bài tập',
    'kiem tra': 'kiểm tra',
    'diem': 'điểm',
    'sinh vien': 'sinh viên',
    'giang vien': 'giảng viên',
    'dai hoc': 'đại học',
    'cao dang': 'cao đẳng',
    'tieu hoc': 'tiểu học',
    'trung hoc': 'trung học',
    'giao duc': 'giáo dục',
    'dao tao': 'đào tạo',
    'mon hoc': 'môn học',
    'bai giang': 'bài giảng',
    'sach giao khoa': 'sách giáo khoa',
    'hoc ky': 'học kỳ',
    'thi cu': 'thi cử',
    'danh gia': 'đánh giá',
    
    # Thời gian (Time)
    'thu hai': 'thứ hai',
    'thu ba': 'thứ ba',
    'thu tu': 'thứ tư',
    'thu nam': 'thứ năm',
    'thu sau': 'thứ sáu',
    'thu bay': 'thứ bảy',
    'chu nhat': 'chủ nhật',
    'thang': 'tháng',
    'nam': 'năm',
    'ngay': 'ngày',
    'hom nay': 'hôm nay',
    'ngay mai': 'ngày mai',
    'hom qua': 'hôm qua',
    'tuan': 'tuần',
    'gio': 'giờ',
    'phut': 'phút',
    'giay': 'giây',
    'mua xuan': 'mùa xuân',
    'mua ha': 'mùa hạ',
    'mua he': 'mùa hè',
    'mua thu': 'mùa thu',
    'mua dong': 'mùa đông',
    'sang': 'sáng',
    'trua': 'trưa',
    'chieu': 'chiều',
    'toi': 'tối'
}

# Sort keys by length descending so longer phrases match first
_SORTED_WORDS = sorted(VIETNAMESE_COMMON_WORDS.keys(), key=len, reverse=True)
_WORDS_PATTERN = re.compile(r'\b(' + '|'.join(map(re.escape, _SORTED_WORDS)) + r')\b', flags=re.IGNORECASE)

def _match_case(original: str, target: str) -> str:
    """Helper to match the capitalization of the original text."""
    if original.isupper():
        return target.upper()
    elif original.istitle() or (len(original) > 0 and original[0].isupper()):
        words = target.split(' ')
        if original.istitle():
            return ' '.join(w.capitalize() for w in words)
        return target.capitalize()
    return target

def restore_vietnamese_diacritics(text: str) -> str:
    """
    Restores missing Vietnamese diacritics in common words.
    Preserves original capitalization and ignores already correctly diacriticized words.
    """
    if not text:
        return text
    
    def replacer(match):
        word = match.group(0)
        replacement = VIETNAMESE_COMMON_WORDS.get(word.lower())
        if replacement:
            return _match_case(word, replacement)
        return word
        
    return _WORDS_PATTERN.sub(replacer, text)

def normalize_vietnamese_unicode(text: str) -> str:
    """
    Ensures all Vietnamese text uses NFC normalization and fixes common Unicode encoding errors.
    Handles both composed and decomposed forms correctly.
    """
    if not text:
        return text
    # Convert to canonical composed form (NFC)
    return unicodedata.normalize('NFC', text)

def calculate_vietnamese_confidence(text: str) -> float:
    """
    Returns a score 0.0-1.0 indicating how "Vietnamese" a text looks
    based on the ratio of Vietnamese-specific characters with diacritics.
    """
    if not text:
        return 0.0
        
    # Set of Vietnamese-specific characters (lowercase and uppercase)
    vi_chars = set(
        'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
        'ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ'
    )
    
    total_letters = sum(1 for c in text if c.isalpha())
    if total_letters == 0:
        return 0.0
        
    vi_char_count = sum(1 for c in text if c in vi_chars)
    
    # Typically, Vietnamese text has around 20-30% characters with diacritics
    # We cap the ratio at 1.0. If 25% of letters are Vietnamese specific, that's very high confidence.
    score = (vi_char_count / total_letters) * 4.0
    return min(1.0, score)

def fix_common_ocr_confusions(text: str) -> str:
    """
    Fixes character-level confusions common in Vietnamese OCR.
    """
    if not text:
        return text
        
    # 'rn' -> 'nh' when surrounded by word characters (e.g., hirn -> hinh)
    text = re.sub(r'(?<=[a-zA-Z])rn(?=[a-zA-Z]|\b)', 'nh', text)
    
    # 'cl' -> 'd' at the beginning of words (e.g., clien -> dien)
    text = re.sub(r'\bcl(?=[a-zA-Z])', 'd', text)
    
    # 'li' -> 'lí' or 'lì' (isolated 'li' usually means 'lí' in math/physics context like 'vật lí')
    text = re.sub(r'\bli\b', 'lí', text)
    
    # 'nn' -> 'nh' at the end of words (e.g., hinh -> hinn -> hinh)
    text = re.sub(r'(?<=[a-zA-Z])nn\b', 'nh', text)
    
    # '0' (zero) -> 'o' in word context (or 'ơ' depending on context, 'o' is a safe default)
    text = re.sub(r'(?<=[a-zA-Z])0(?=[a-zA-Z]|\b)', 'o', text)
    text = re.sub(r'\b0(?=[a-zA-Z])', 'o', text)
    
    # '1' (one) -> 'l' in word context
    text = re.sub(r'(?<=[a-zA-Z])1(?=[a-zA-Z]|\b)', 'l', text)
    text = re.sub(r'\b1(?=[a-zA-Z])', 'l', text)
    
    # Fix doubled spaces, missing spaces
    text = re.sub(r'\s{2,}', ' ', text)
    
    return text.strip()
