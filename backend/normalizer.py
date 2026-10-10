from __future__ import annotations
import os
import re
import json
import hashlib
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Tuple

MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

QUESTION_NUMBER_REGEX = re.compile(
    r'^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*(?:tập)?\s*\d+)[\s\.\:\-_]*',
    re.IGNORECASE
)

def clean_html_and_math(html_str: str) -> Tuple[str, str]:
    """
    Cleans raw HTML, normalizes LaTeX/MathJax formulas, removes question numbering prefixes
    (e.g., 'Câu hỏi số 5', 'Câu 7:', 'Bài 1.'), and returns (clean_html, clean_text).
    """
    if not html_str:
        return "", ""
        
    text = html_str
    
    # 1. Normalize MathJax tags / spans: e.g. <span class="math-tex">\( x^2 \)</span> -> $x^2$
    text = re.sub(r'<span[^>]*class="[^"]*math-tex[^"]*"[^>]*>\\?\((.*?)\\?\)</span>', lambda m: f"${m.group(1).strip()}$", text, flags=re.DOTALL)
    text = re.sub(r'<span[^>]*class="[^"]*math-tex[^"]*"[^>]*>\\?\[(.*?)\\?\]</span>', lambda m: f"$${m.group(1).strip()}$$", text, flags=re.DOTALL)
    text = re.sub(r'<span[^>]*class="[^"]*math-tex[^"]*"[^>]*>(.*?)</span>', lambda m: f"${m.group(1).strip()}$", text, flags=re.DOTALL)
    
    # 2. Convert standard \( ... \) to $ ... $ and \[ ... \] to $$ ... $$
    text = re.sub(r'\\\((.*?)\\\)', lambda m: f"${m.group(1).strip()}$", text, flags=re.DOTALL)
    text = re.sub(r'\\\[(.*?)\\\]', lambda m: f"$${m.group(1).strip()}$$", text, flags=re.DOTALL)
    
    # 3. Clean common HTML entities
    soup = BeautifulSoup(text, "html.parser")
    
    # Remove script, style, iframe, object tags
    for tag in soup(["script", "style", "iframe", "object"]):
        tag.decompose()

    # 4. Remove question header tags containing question index/number (e.g., .panel-heading, .question-title)
    heading_selectors = [
        ".panel-heading", ".practice-question-title", ".question-title",
        ".title-question", ".box-question-title", ".cau-hoi-so",
        ".question-number", ".question-index", ".stt-cau-hoi"
    ]
    for sel in heading_selectors:
        for tag in soup.select(sel):
            tag_text = tag.get_text().strip()
            # If tag text is purely question number indicator or short header
            if QUESTION_NUMBER_REGEX.match(tag_text) or len(tag_text) <= 25:
                tag.decompose()

    # Also decompose any top-level tag whose text strictly starts with question number pattern and is short
    for child in list(soup.children):
        if hasattr(child, 'get_text'):
            t = child.get_text().strip()
            if QUESTION_NUMBER_REGEX.match(t) and len(t) <= 25:
                child.decompose()

    # 5. Strip leading question number from first text node in clean_html
    from bs4 import NavigableString
    for desc in soup.descendants:
        if isinstance(desc, NavigableString):
            stripped = desc.strip()
            if stripped:
                match = QUESTION_NUMBER_REGEX.match(desc)
                if match:
                    new_val = desc[match.end():].lstrip()
                    desc.replace_with(new_val)
                break

    clean_html = str(soup).strip()
    clean_text = soup.get_text(separator=" ").strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    clean_text = QUESTION_NUMBER_REGEX.sub('', clean_text).strip()
    
    return clean_html, clean_text

async def download_and_localize_image(url: str, referer: str = None) -> str:
    """
    Downloads remote image and saves it to local data/media folder.
    Returns the local URL path: /media/<filename>
    """
    if not url or url.startswith("/media/") or url.startswith("data:image"):
        return url
        
    try:
        # Generate stable filename from URL hash
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        ext = ".png"
        clean_url = url.split("?")[0]
        for candidate_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
            if clean_url.lower().endswith(candidate_ext):
                ext = candidate_ext
                break
                
        local_filename = f"img_{url_hash[:16]}{ext}"
        local_filepath = os.path.join(MEDIA_DIR, local_filename)
        
        # If already cached, reuse
        if os.path.exists(local_filepath) and os.path.getsize(local_filepath) > 0:
            return f"/media/{local_filename}"
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        if referer:
            headers["Referer"] = referer
            
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                with open(local_filepath, "wb") as f:
                    f.write(resp.content)
                return f"/media/{local_filename}"
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        
    return url

VALID_SUBJECTS = {"math", "vietnamese", "english", "science", "informatics", "history_geo"}

SUBJECT_CANONICAL_MAP = {
    "toán": "math",
    "toan": "math",
    "toán học": "math",
    "math": "math",
    "mathematics": "math",
    "tiếng việt": "vietnamese",
    "tieng viet": "vietnamese",
    "vietnamese": "vietnamese",
    "văn": "vietnamese",
    "tiếng anh": "english",
    "tieng anh": "english",
    "english": "english",
    "khoa học": "science",
    "khoa hoc": "science",
    "science": "science",
    "tnxh": "science",
    "tin học": "informatics",
    "tin hoc": "informatics",
    "informatics": "informatics",
    "lịch sử": "history_geo",
    "địa lý": "history_geo",
    "history_geo": "history_geo"
}

from backend.classifier import classify_subject

async def normalize_question_payload(q: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes a raw question dict, cleans HTML, normalizes LaTeX, downloads images, and prepares it for DB.
    """
    content = q.get("content_html") or q.get("content_text") or ""
    clean_html, clean_text = clean_html_and_math(content)
    
    q["content_html"] = clean_html
    q["content_text"] = QUESTION_NUMBER_REGEX.sub('', clean_text or q.get("content_text", "")).strip()

    # Subject handling:
    # Nếu câu hỏi đến từ source_platform in ["ai_agent_import", "manual"] hoặc current_sub đã được chỉ định rõ ràng và hợp lệ,
    # TUYỆT ĐỐI KHÔNG tự ý ghi đè q["subject"] bằng classify_subject(). Chỉ phân loại tự động nếu q.get("subject") hoàn toàn rỗng.
    current_sub = q.get("subject")
    if current_sub and isinstance(current_sub, str):
        sub_key = current_sub.strip().lower()
        if sub_key in SUBJECT_CANONICAL_MAP:
            current_sub = SUBJECT_CANONICAL_MAP[sub_key]
            q["subject"] = current_sub

    source_platform = str(q.get("source_platform") or "").strip().lower()
    is_protected_source = source_platform in ["ai_agent_import", "manual"]
    is_valid_subject = current_sub in VALID_SUBJECTS

    from backend.classifier import VN_DIACRITICS_REGEX
    has_vn = bool(VN_DIACRITICS_REGEX.search(q["content_text"]))

    should_classify = False
    if not current_sub or not str(current_sub).strip():
        # Chỉ phân loại tự động nếu q.get("subject") hoàn toàn rỗng
        should_classify = True
    elif not is_protected_source:
        if not is_valid_subject:
            should_classify = True
        elif current_sub == "english" and has_vn:
            # Phát hiện câu hỏi crawler bị gán nhầm 'english' nhưng toàn văn tiếng Việt
            should_classify = True

    if should_classify:
        detected_sub = classify_subject(
            content_text=q["content_text"],
            content_html=q["content_html"],
            topic=q.get("topic", ""),
            source_platform=q.get("source_platform", ""),
            options=q.get("options", [])
        )
        q["subject"] = detected_sub
    
    # Process images list
    images = q.get("images", [])
    localized_images = []
    referer = q.get("source_url") or "https://vio.edu.vn"
    
    for img_url in images:
        if isinstance(img_url, str):
            loc_url = await download_and_localize_image(img_url, referer)
            localized_images.append(loc_url)
            # Replace in content_html if present
            if loc_url != img_url and img_url in q["content_html"]:
                q["content_html"] = q["content_html"].replace(img_url, loc_url)
                
    # Also extract any img tags inside content_html
    soup = BeautifulSoup(q["content_html"], "html.parser")
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")
        if src and not src.startswith("/media/"):
            loc = await download_and_localize_image(src, referer)
            img_tag["src"] = loc
            if loc not in localized_images:
                localized_images.append(loc)
    q["content_html"] = str(soup)
    q["images"] = localized_images
    
    # Process options
    options = q.get("options", [])
    for opt in options:
        if isinstance(opt, dict) and "content" in opt:
            c_html, c_txt = clean_html_and_math(opt["content"])
            opt["content"] = c_html
            
    # Process explanation
    if q.get("explanation"):
        exp_html, _ = clean_html_and_math(q["explanation"])
        q["explanation"] = exp_html
        
    return q

import unicodedata

def remove_vietnamese_accents(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').replace('đ', 'd').replace('Đ', 'D')

def is_valid_question_payload(q: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates that a question has meaningful, clean educational content
    and rejects web scrap noise (Doctype, CSS classes, script tags, empty text,
    blog descriptions, news announcements, contact info, headers/footers, arena match dialogs).
    Supports accent-insensitive detection for robustness.
    """
    if not isinstance(q, dict):
        return False, "Dữ liệu không phải là định dạng JSON hợp lệ"

    content_text = (q.get("content_text") or "").strip()
    content_html = (q.get("content_html") or "").strip()
    combined = (content_text + " " + content_html).lower()
    combined_no_accents = remove_vietnamese_accents(combined)

    # 1. Reject if too short or excessively long (blog post / article dump)
    if len(content_text) < 8:
        return False, f"Nội dung quá ngắn ({len(content_text)} ký tự)"
    if len(content_text) > 3000:
        return False, f"Nội dung quá dài ({len(content_text)} ký tự), có thể là bài viết blog hoặc tài liệu toàn bài"

    # 1.1. Reject UUID strings, hex hashes, or single-word token IDs
    if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', content_text, re.I):
        return False, "Nội dung chỉ là chuỗi mã UUID tham chiếu ID, không phải câu hỏi giáo dục"
    if re.match(r'^[0-9a-f]{16,64}$', content_text, re.I):
        return False, "Nội dung chỉ là chuỗi mã băm Hex, không phải câu hỏi"
    if ' ' not in content_text and len(content_text) > 20:
        return False, "Nội dung là một chuỗi mã liền không có khoảng trắng"
    if content_text.isdigit():
        return False, "Nội dung chỉ là một dãy số ID thuần túy"

    # 1.2. Reject extension debug logs, telemetry, timestamps, extension UI strings, and LMS resume popups
    if re.search(r'\[(?:dom|mạng|lưu csdl|tương tác|thông báo|bỏ qua|dom bỏ qua|dom bắt được|mạng bắt được|mạng gói tin|info|ok|skip|net|error|warn)\]', combined, re.I):
        return False, "Chứa thẻ nhật ký log của Extension ([DOM...], [MẠNG...])"
    if re.search(r'^\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\s*\[', content_text, re.I):
        return False, "Chứa thời gian timestamp nhật ký log của Extension"
    if any(k in combined for k in [
        "danh sách câu hỏi đã quét", "xem các câu hỏi đã quét", "cào tất cả câu hỏi",
        "quét nhanh màn hình", "tự động lưu (zero-click)", "nhật ký hoạt động (debug log)",
        "bạn đang làm bài kiểm tra này", "tiếp tục từ phần đã làm trước đó", "thẻ #1 trùng câu hỏi", "trùng câu hỏi đã có"
    ]):
        return False, "Chứa văn bản giao diện tiện ích hoặc hộp thoại tiếp tục bài làm hệ thống"

    # 1.3. Reject progress bars, completion percentage, steppers, and loading states
    if re.search(r'\bbạn đã hoàn thành\b', combined, re.I):
        return False, "Chứa thông báo tiến độ 'Bạn đã hoàn thành'"
    if re.search(r'\bhoàn thành\s*\d+\s*(?:/\s*\d+)?\s*(?:câu|%)?', combined, re.I):
        return False, "Chứa thanh tiến độ làm bài hoàn thành số câu / phần trăm"
    if re.search(r'\b\d+\s*/\s*\d+\s*câu\b', combined, re.I):
        return False, "Chứa chỉ số tiến độ số câu (ví dụ: 5/20 câu)"
    if re.search(r'\b\d+%\s*$', content_text, re.I):
        return False, "Kết thúc bằng phần trăm tiến độ"
    if any(k in combined for k in [
        "cách tính điểm khi trả lời", "tổng điểm <", "score-hint-popup", "star_practice",
        "đúng cộng 10 điểm", "đúng cộng 9 điểm", "sai trừ 1 điểm", "sai trừ 2 điểm", "sai trừ 3 điểm",
        "đang lấy thông tin câu hỏi", "viogpt-loading", "đang tải dữ liệu",
        "tiến độ làm bài", "vui lòng chờ trong giây lát"
    ]):
        return False, "Chứa trạng thái đang tải câu hỏi, tiến độ, hoặc popup cách tính điểm VioEdu"
    if re.search(r'\b\d+\s*/\s*100\b', combined) and ("tính điểm" in combined or "điểm" in combined):
        return False, "Chứa tiến độ điểm số trên thang 100 của VioEdu"

    # 1.4. Reject login / auth forms and password prompts
    login_keywords = ["tên đăng nhập", "mật khẩu", "nhập tên đăng nhập", "nhập mật khẩu",
                      "quên mật khẩu", "vui lòng nhập mật khẩu", "login-username", "login-password"]
    if any(k in combined for k in login_keywords):
        return False, "Chứa biểu mẫu đăng nhập / mật khẩu, không phải câu hỏi giáo dục"

    # 1.5. Reject welcome / onboarding popups
    if re.search(r'chào mừng.*đến vioedu|chào mừng.*đến với', combined, re.I):
        return False, "Chứa popup chào mừng / onboarding VioEdu"
    if any(k in combined for k in ["mỗi bạn nhỏ đều có", "vioedu giúp bạn tìm ra", "popup-onboard", "robot-popup-onboard"]):
        return False, "Chứa nội dung popup chào mừng / onboarding VioEdu"

    # 1.6. Reject arena gate / lobby UI and battle schedule displays
    arena_lobby_keywords = ["diễn ra hàng ngày", "hãy bắt đầu thách đấu ngay",
                            "vươn lên vị trí cao", "chưa có trận đấu",
                            "hãy tham gia thách đấu ngay", "challenge_gate", "arena-mass", "mass_thachdau"]
    if any(k in combined for k in arena_lobby_keywords):
        return False, "Chứa giao diện cổng đấu trường / lobby VioEdu, không phải câu hỏi"
    if re.search(r'bạn còn \d+/\d+ lượt thi đấu', combined, re.I):
        return False, "Chứa thông tin lượt thi đấu còn lại"

    # 1.7. Reject battle scoreboard with player names, timers, correct/wrong counts
    if any(k in combined for k in ["correct_icon", "wrong_icon", "countdown_icon"]):
        if re.search(r'\b\d{2}:\d{2}\b', content_text):
            return False, "Chứa bảng điểm trận đấu với bộ đếm thời gian và biểu tượng đúng/sai"
    if re.search(r'ôi tiếc quá.*sai mất rồi', combined, re.I):
        return False, "Chứa thông báo phản hồi trận đấu 'sai mất rồi'"
    if re.search(r'bạn hãy đọc kĩ câu hỏi.*để có thể trả lời đúng', combined, re.I):
        return False, "Chứa thông báo gợi ý trận đấu, không phải câu hỏi thực"
    if "robot_false" in combined or "robot_think" in combined:
        # If the text is mostly player usernames, timer and score data, reject
        if re.search(r'[a-z0-9]+-\d{4}', content_text) and re.search(r'\b\d{2}:\d{2}\b', content_text):
            return False, "Chứa bảng điểm trận đấu với tên người chơi và phản hồi robot"

    # 1.8. Reject answer-hint UI instructions (not actual questions)
    if re.search(r'click vào đáp án phía dưới', combined, re.I):
        return False, "Chứa hướng dẫn UI điền đáp án, không phải câu hỏi giáo dục"

    # 1.9. Reject from non-educational source URLs (login, profile, settings pages)
    source_url = (q.get("source_url") or "").lower()
    non_edu_paths = ["/login", "/forgot-password", "/register", "/signup", "/profile", "/settings", "/account"]
    if any(source_url.endswith(p) or (p + "/") in source_url or (p + "?") in source_url for p in non_edu_paths):
        return False, f"Nguồn URL là trang không giáo dục: {source_url}"

    # 2. Reject HTML source dumps, doctype, scripts, CSS stylesheets
    if "<!doctype" in combined or "<html" in combined or "xmlns=" in combined:
        return False, "Chứa mã nguồn HTML/Doctype của trang web"

    if any(s in combined for s in ["<script", "window.datalayer", "document.getelement", "document.createelement", "cf-beacon"]):
        return False, "Chứa mã JavaScript hoặc thẻ script"

    if any(s in combined for s in ["css_layout", "display:none !important", "position:static !important", "scroll-smooth text-base"]):
        return False, "Chứa mã định dạng CSS / layout web"

    # 3. Reject general web template boilerplate
    boilerplate = ["tailwind react template", "keenthemes", "metronic", "challenge-platform", "cloudflareinsights"]
    for bp in boilerplate:
        if bp in combined:
            return False, f"Chứa boilerplate trang web: {bp}"

    # 4. Reject contact info, phone numbers, and tutoring marketing
    phone_match = re.search(r'\b0[1-9]\d{1,2}[\.\s\-]?\d{3}[\.\s\-]?\d{3,4}\b', content_text)
    if phone_match:
        return False, f"Chứa số điện thoại liên hệ: {phone_match.group(0)}"

    # Strict regex check for commercial course/tutoring marketing with required diacritics on "khóa/khoá",
    # ensuring legitimate educational reading passages with "khoa học" (Science) are NEVER falsely rejected.
    if re.search(r'\b(?:đăng\s+ký\s+|mua\s+|bán\s+|tư\s+vấn\s+)?(?:khóa|khoá)\s+học\b', combined, re.I):
        return False, "Chứa thông tin quảng cáo / liên hệ / khóa học (khóa học)"

    contact_keywords = [
        "liên hệ", "hotline", "sđt", "điện thoại:", "zalo", "facebook", "fanpage",
        "fan page", "inbox", "học phí", "đăng ký học",
        "lớp học thêm", "tư vấn tuyển sinh",
        "tuyển sinh", "website:", "email:", "bản quyền thuộc về", "all rights reserved"
    ]
    for ck in contact_keywords:
        ck_no = remove_vietnamese_accents(ck)
        if ck in combined or ck_no in combined_no_accents:
            return False, f"Chứa thông tin quảng cáo / liên hệ / khóa học ({ck})"

    # 5. Reject blog descriptions, article headers/footers, news announcements, and download promos
    blog_promo_keywords = [
        "ba mẹ", "phụ huynh", "tải đề thi", "tải tài liệu", "tải tại đây", "link tải",
        "download tại", "xem và tải", "video chữa đề", "lịch thi", "giờ thi", "địa điểm thi",
        "hướng dẫn dự thi", "chuẩn bị trước ngày thi", "thí sinh asmo", "tặng miễn phí",
        "nhận miễn phí", "fermat education", "kỳ thi fmo", "vòng quốc gia đã diễn ra",
        "đối chiếu đáp án", "tham khảo sau kỳ thi", "tài liệu tham khảo", "tài liệu hữu ích",
        "dành cho học sinh đang chuẩn bị", "đề vòng loại", "vòng loại bbb", "vòng loại timo",
        "bài viết liên quan", "tin liên quan", "chia sẻ bài viết", "bình luận", "trang chủ >", "home >",
        "hướng dẫn học sinh tham gia", "hướng dẫn tham gia", "bài thi thử khám phá", "thi thử khám phá",
        "thông báo mở bài thi", "thông báo mở", "thông báo v/v", "thông báo số", "thông báo kết quả", "thông báo tổ chức",
        "rộn ràng đón", "trăng rằm", "tựu trường", "bứt phá", "khám phá combo", "combo đồng hành",
        "ưu đãi", "khuyến mại", "thể lệ giải đấu", "cơ cấu giải thưởng",
        "danh sách nhận thưởng", "chúc mừng các thí sinh", "lễ vinh danh", "lễ trao giải",
        "tin tức & sự kiện", "tin nổi bật", "bài viết mới nhất", "hướng dẫn phụ huynh",
        "điều khoản sử dụng", "chính sách bảo mật", "quy định thi", "thể lệ cuộc thi", "vnmf",
        "video mở đầu", "video bài đọc", "dự án bữa ăn", "bố cục trong tranh",
        "học online toán", "học online tiếng việt", "học online luyện từ", "kh luyện từ",
        "tìm bài trong mục này", "tất cả chân trời kết nối cánh diều", "tài liệu, đề thi, trắc nghiệm"
    ]
    for bk in blog_promo_keywords:
        bk_no = remove_vietnamese_accents(bk)
        if bk in combined or bk_no in combined_no_accents:
            return False, f"Chứa bài viết mô tả / thông báo / chia sẻ tài liệu ({bk})"

    # 6. Reject arena game match celebration or system dialogs
    arena_dialogs = [
        "chúc mừng, bạn vừa chiến thắng", "bạn vừa chiến thắng 1 trận đấu",
        "bạn đã cố gắng rồi, hãy", "chúc mừng bạn đã hoàn thành",
        "kết quả trận đấu", "bảng xếp hạng trận đấu", "rời khỏi phòng thi", "đấu sĩ"
    ]
    for ad in arena_dialogs:
        ad_no = remove_vietnamese_accents(ad)
        if ad in combined or ad_no in combined_no_accents:
            return False, f"Chứa hộp thoại chúc mừng trận đấu / thông báo hệ thống ({ad})"

    # 7. Validate options if choice type
    q_type = q.get("question_type")
    options = q.get("options") or []
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except Exception:
            return False, "Định dạng phương án không hợp lệ"
    if q_type in ("single_choice", "multiple_choice") and options:
        if len(options) < 2:
            return False, f"Phương án trắc nghiệm không hợp lệ (ít hơn 2 lựa chọn)"
        opt_ids = set()
        for opt in options:
            if not isinstance(opt, dict):
                return False, "Định dạng phương án không hợp lệ"
            oid = str(opt.get("id") or "").upper().strip()
            if oid:
                if oid in opt_ids:
                    return False, f"Phương án trắc nghiệm bị lặp ký tự nhận diện ({oid})"
                opt_ids.add(oid)
            opt_c = str(opt.get("content") or "").strip()
            opt_lower = opt_c.lower()
            if any(x in opt_lower for x in ["opacity:", "first-child", "png'/>", "<style", "{opacity", "display:"]):
                return False, f"Phương án chứa mã CSS hoặc HTML lỗi: {opt_c[:40]}"
        if len(opt_ids) < 2:
            return False, "Phương án trắc nghiệm không hợp lệ (ít hơn 2 phương án phân biệt)"

    # 8. Educational intent check: Must look like an educational question
    has_math = bool(re.search(r'[\$\\\+\*\/=><%]|\\frac|\\sqrt|\b(?:tính|phép tính|biểu thức|phân số|hỗn số|chu vi|diện tích|thể tích|vận tốc|quãng đường|tỉ số|phần trăm|hình chữ nhật|hình vuông|hình thang|hình tam giác)\b', combined, re.I)) or "math-tex" in content_html
    has_question_prompt = bool(re.search(
        r'\?|câu\s*\d+|bài\s*\d+|hoạt động|luyện tập|\bbài tập khám phá\b|\bkhám phá\s*:|vận dụng|hãy chọn|chọn đáp án|em hãy|chọn từ|từ có|vần|tiếng|từ nào|từ ghép|đoạn văn|đoạn thơ|bài đọc|\btính\b|\btìm\b|\bđiền\b|\b(?:cho\s+(?:biết|hình|số|tam giác|đoạn|hai|ba|bốn|mỗi|một|\$|[a-z0-9])|hãy\s+cho\s+biết)\b|trong các|\bhỏi\b|sau đây|biết rằng|hình vẽ|khoanh|đặt tính|ghép|nối|đúng ghi|sai ghi|kết quả|giá trị|số nào',
        combined
    ))
    has_english_quiz = bool(re.search(
        r'\b(choose|which|what|where|when|who|why|how|correct|fill|opposite|meaning|sentence|solve|calculate|find)\b',
        combined
    ))

    # 9. Check for excessively long text without options (non-reading question article dump)
    if not options or len(options) == 0:
        is_reading_text = any(rm in combined for rm in ["đọc đoạn văn", "bài đọc", "reading passage", "read the following", "đoạn thơ"])
        if len(content_text) > 450 and not is_reading_text:
            return False, f"Câu hỏi điền khuyết quá dài ({len(content_text)} ký tự), không phải câu hỏi chuẩn"
        # Bắt buộc phải có dấu hỏi hoặc từ khóa nghi vấn / chỉ thị bài toán nếu câu ngắn
        has_direct_question = bool(re.search(r'\?|\b(?:hỏi|tính|tìm|điền|bao nhiêu|mấy|kết quả|giá trị|đúng ghi|sai ghi)\b', combined, re.I))
        if len(content_text) < 70 and not has_direct_question and not has_math:
            return False, "Câu ngắn không có lựa chọn và không chứa câu hỏi hoặc lệnh tính toán hợp lệ"

    if not (has_math or has_question_prompt or has_english_quiz or (options and len(options) >= 2)):
        return False, "Nội dung không chứa công thức, câu hỏi, hoặc phương án trả lời mang tính giáo dục"

    return True, "Hợp lệ"

