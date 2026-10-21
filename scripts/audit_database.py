import sqlite3
import json
import re
from collections import defaultdict

conn = sqlite3.connect('data/questions.db')
c = conn.cursor()

c.execute("""
    SELECT id, q_number, source_platform, source_detail, source_url, 
           grade, subject, question_type, content_html, content_text, 
           images, options, correct_answer, explanation, content_hash
    FROM questions
""")
all_questions = c.fetchall()
total_count = len(all_questions)

print(f"=== TỔNG SỐ CÂU HỎI TRONG DATABASE: {total_count} ===")

# Categories of errors:
errors_empty_text = []
errors_too_short = []
errors_ui_noise = []
errors_js_object = []
errors_html_in_text = []
errors_mcq_no_options = []
errors_mcq_one_option = []
errors_mcq_bad_json = []
errors_mcq_duplicate_options = []
errors_empty_options_content = []
errors_broken_images = []
errors_vietnamese_in_math = []
errors_bare_number_dollars = []
errors_unpaired_dollars = []
errors_broken_latex = []
errors_missing_answer = []

# Keywords indicating UI noise / scraping errors
UI_NOISE_PATTERNS = [
    re.compile(r'\b(undefined|null|\[object Object\]|NaN)\b', re.IGNORECASE),
    re.compile(r'(Đang tải|Xem đáp án|Báo lỗi|Quảng cáo|Bình luận|Chia sẻ|Nộp bài|Học kỳ \d năm học)', re.IGNORECASE),
    re.compile(r'(\bfunction\s*\(|<script|\bdocument\.get|\bwindow\.)', re.IGNORECASE)
]

# Patterns for $
bare_number_pattern = re.compile(r'\$\s*(\d+(?:[.,]\d+)?\s*\.?)\s*\$')
vn_in_math_pattern = re.compile(r'\$[^$]*\b(giờ|phút|giây|ngày|tháng|năm|học sinh|bạn|lít|gam|kg|cm|dm|m|km|đáp án|đúng|sai)\b[^$]*\$', re.IGNORECASE)
html_tag_pattern = re.compile(r'<(?:div|span|p|br|table|tr|td|th|ul|li|b|i|u|strong|em)\b[^>]*>', re.IGNORECASE)

platform_errors = defaultdict(lambda: defaultdict(int))

for q in all_questions:
    (qid, q_num, platform, s_detail, s_url, grade, subject, 
     q_type, c_html, c_text, images, options, correct_ans, explanation, c_hash) = q
    
    text = (c_text or "").strip()
    html = (c_html or "").strip()
    
    # 1. Empty or too short
    if not text:
        errors_empty_text.append((qid, platform, "Empty content_text"))
        platform_errors[platform]["empty_text"] += 1
    elif len(text) < 10:
        errors_too_short.append((qid, platform, text))
        platform_errors[platform]["too_short"] += 1
        
    # 2. UI noise / JS objects
    for pat in UI_NOISE_PATTERNS:
        m = pat.search(text) or (options and pat.search(options))
        if m:
            errors_ui_noise.append((qid, platform, m.group(0), text[:120]))
            platform_errors[platform]["ui_noise"] += 1
            break
            
    # 3. HTML tags leaked into content_text
    if text and html_tag_pattern.search(text):
        errors_html_in_text.append((qid, platform, text[:120]))
        platform_errors[platform]["html_in_text"] += 1
        
    # 4. MCQ options issues
    if q_type == 'multiple_choice':
        if not options or options.strip() in ('[]', '', 'null'):
            errors_mcq_no_options.append((qid, platform, text[:120]))
            platform_errors[platform]["mcq_no_options"] += 1
        else:
            try:
                opt_data = json.loads(options)
                if not isinstance(opt_data, list):
                    errors_mcq_bad_json.append((qid, platform, options[:100]))
                    platform_errors[platform]["mcq_bad_json"] += 1
                elif len(opt_data) <= 1:
                    errors_mcq_one_option.append((qid, platform, len(opt_data), text[:120]))
                    platform_errors[platform]["mcq_one_option"] += 1
                else:
                    # check empty options inside
                    texts = []
                    has_empty = False
                    for o in opt_data:
                        t = (o.get("text", "") if isinstance(o, dict) else str(o)).strip()
                        if not t and not (isinstance(o, dict) and o.get("image")):
                            has_empty = True
                        texts.append(t)
                    if has_empty:
                        errors_empty_options_content.append((qid, platform, texts))
                        platform_errors[platform]["empty_options_content"] += 1
                    # check duplicates
                    non_empty_texts = [t for t in texts if t]
                    if len(non_empty_texts) > 1 and len(set(non_empty_texts)) == 1:
                        errors_mcq_duplicate_options.append((qid, platform, texts))
                        platform_errors[platform]["duplicate_options"] += 1
            except Exception as e:
                errors_mcq_bad_json.append((qid, platform, str(e)))
                platform_errors[platform]["mcq_bad_json"] += 1
                
    # 5. Missing correct answer
    if not correct_ans or str(correct_ans).strip() in ('', 'null', 'None', 'undefined'):
        errors_missing_answer.append((qid, platform, q_type, text[:100]))
        platform_errors[platform]["missing_answer"] += 1

    # 6. Broken images (blob: URLs)
    if images and images.strip() not in ('[]', '', 'null'):
        try:
            img_list = json.loads(images)
            for img in img_list:
                img_url = img if isinstance(img, str) else img.get("url", "")
                if img_url.startswith("blob:"):
                    errors_broken_images.append((qid, platform, img_url))
                    platform_errors[platform]["blob_images"] += 1
                    break
        except Exception:
            pass

    # 7. Dollar errors
    if text:
        # Unpaired $
        if text.count('$') % 2 != 0:
            errors_unpaired_dollars.append((qid, platform, text[:120]))
            platform_errors[platform]["unpaired_dollars"] += 1
            
        # Bare numbers in $ e.g. $2$, $ 28$, $ 32.$
        bare_matches = bare_number_pattern.findall(text)
        if bare_matches:
            errors_bare_number_dollars.append((qid, platform, bare_matches, text[:120]))
            platform_errors[platform]["bare_number_dollars"] += 1
            
        # Vietnamese text inside $...$ e.g. $3 giờ$, $15l$, $3 bạn$
        vn_matches = vn_in_math_pattern.findall(text)
        if vn_matches:
            errors_vietnamese_in_math.append((qid, platform, vn_matches, text[:120]))
            platform_errors[platform]["vietnamese_in_math"] += 1

print("\n--- BẢNG THỐNG KÊ LỖI THEO NGUỒN (PLATFORM) ---")
for plat, errs in sorted(platform_errors.items()):
    print(f"Platform: {plat:15} | Tổng lỗi: {sum(errs.values())}")
    for ek, ev in errs.items():
        print(f"   - {ek:25}: {ev}")

print("\n--- CHI TIẾT TỪNG LOẠI LỖI ---")
print(f"1. Câu hỏi rỗng text: {len(errors_empty_text)}")
for s in errors_empty_text[:3]:
    print("   ", s)

print(f"\n2. Câu hỏi quá ngắn (<10 ký tự): {len(errors_too_short)}")
for s in errors_too_short[:5]:
    print("   ", s)

print(f"\n3. Chứa chuỗi rác UI / Javascript / undefined: {len(errors_ui_noise)}")
for s in errors_ui_noise[:5]:
    print("   ", s)

print(f"\n4. Bị lọt thẻ HTML thô vào content_text: {len(errors_html_in_text)}")
for s in errors_html_in_text[:5]:
    print("   ", s)

print(f"\n5. Trắc nghiệm (MCQ) KHÔNG CÓ OPTIONS: {len(errors_mcq_no_options)}")
for s in errors_mcq_no_options[:5]:
    print("   ", s)

print(f"\n6. Trắc nghiệm chỉ có 1 option: {len(errors_mcq_one_option)}")
for s in errors_mcq_one_option[:5]:
    print("   ", s)

print(f"\n7. Trắc nghiệm chứa options rỗng / trùng lặp: {len(errors_empty_options_content)} rỗng, {len(errors_mcq_duplicate_options)} trùng")
for s in errors_empty_options_content[:3]:
    print("   Rỗng:", s)
for s in errors_mcq_duplicate_options[:3]:
    print("   Trùng:", s)

print(f"\n8. Ảnh bị lỗi blob: (không hiển thị được): {len(errors_broken_images)}")
for s in errors_broken_images[:5]:
    print("   ", s)

print(f"\n9. Thiếu đáp án (missing answer): {len(errors_missing_answer)}")
for s in errors_missing_answer[:5]:
    print("   ", s)

print(f"\n10. Ký tự $ không đúng - Số thuần trong $ ($2$, $ 28$, $ 32.$): {len(errors_bare_number_dollars)}")
for s in errors_bare_number_dollars[:5]:
    print("   ", s)

print(f"\n11. Ký tự $ không đúng - Tiếng Việt bị kẹp trong math ($3 giờ$, $15 lít$): {len(errors_vietnamese_in_math)}")
for s in errors_vietnamese_in_math[:5]:
    print("   ", s)

print(f"\n12. Số lượng dấu $ bị lẻ (unpaired $): {len(errors_unpaired_dollars)}")
for s in errors_unpaired_dollars[:5]:
    print("   ", s)
