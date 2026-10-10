from __future__ import annotations
import re
import random
import hashlib
import json
from typing import List, Dict, Any, Tuple, Optional, Set

__all__ = [
    'extract_template_signature',
    'normalize_problem_text',
    'calculate_text_similarity',
    'classify_problem_archetype',
    'select_diverse_exam_questions',
    'analyze_exam_diversity',
    'deduplicate_and_diversify_exam',
    'swap_exam_question',
    'shuffle_exam_smart'
]

# Common units of measurement
UNITS_REGEX = re.compile(
    r'\b(?:m|cm|dm|mm|km|kg|g|tạ|tấn|yến|lít|ml|giây|phút|giờ|ngày|tháng|năm|đồng|đ|'
    r'km/h|km/g|m/s|m²|cm²|dm²|km²|mm²|m2|cm2|dm2|km2|mm2|m³|cm³|dm³|m3|cm3|dm3|'
    r'học sinh|em|bạn|người|trang|cuốn|quyển|lần|phần trăm|%)\b',
    re.IGNORECASE
)

# Common person names in school word problems (Vietnamese & English)
NAME_REGEX = re.compile(
    r'\b(?:Bạn\s+)?(Minh|Hoa|Nam|Mai|Hà|Đức|Lan|An|Bình|Linh|Hùng|Trang|Tuấn|Hương|'
    r'Phương|Cường|Hải|Dũng|Thu|Thảo|Thành|Khoa|Long|Nga|Ngọc|Quân|Sơn|Tâm|Tú|Vân|Việt|'
    r'Liam|Noah|Emma|Olivia|Lucas|Lily|Tom|Michael|Jack|Sophia|James|Benjamin|Mia|'
    r'Charlotte|Amelia|Oliver|Henry|Alexander|William|Daniel|Matthew|David|Joseph)\b',
    re.IGNORECASE
)

# Common objects/items in elementary word problems
ITEM_REGEX = re.compile(
    r'\b(viên bi|viên kẹo|cái kẹo|kẹo|quả táo|quả cam|quả bưởi|bông hoa|nhãn vở|'
    r'bút chì|bút mực|quyển vở|trang sách|con tem|gói bánh|hộp bánh|thước kẻ|'
    r'cây xanh|cây cam|cây chuối|pencils?|crayons?|apples?|stickers?|marbles?|'
    r'candies|candy|books?|erasers?|markers?|stamps?|balloons?|chocolates?)\b',
    re.IGNORECASE
)

def normalize_problem_text(text: str) -> str:
    """
    Produces the core conceptual skeleton of a question by normalizing:
    - Numbers, decimals, negative numbers, fractions
    - Person names and common objects/items
    - Units of measurement
    - LaTeX formatting and math wrappers
    """
    if not text:
        return ""
    
    s = text.lower()
    
    # 1. Remove HTML tags
    s = re.sub(r'<[^>]+>', ' ', s)
    
    # 2. Remove leading question numbering (e.g. 'Câu 10:', 'Bài 2.')
    s = re.sub(r'^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*(?:tập)?\s*\d+)[\s\.\:\-_]*', '', s)
    
    # 3. Handle LaTeX text environments: \text{ m} -> m
    s = re.sub(r'\\text\{([^}]*)\}', r' \1 ', s)
    
    # 4. Handle LaTeX math fractions, roots, powers
    s = re.sub(r'\\frac\{[^{}]*\}\{[^{}]*\}', ' <NUM> ', s)
    s = re.sub(r'\\sqrt\{[^{}]*\}', ' <NUM> ', s)
    s = re.sub(r'\^[0-9]+', '', s)
    
    # 5. Remove remaining LaTeX command words (\times, \div, \pm, etc.)
    s = re.sub(r'\\[a-zA-Z]+', ' ', s)
    
    # 6. Remove math markers $ ... $
    s = s.replace('$', ' ')
    
    # 7. Normalize entity names and counting items
    s = NAME_REGEX.sub(' <PERSON> ', s)
    s = ITEM_REGEX.sub(' <ITEM> ', s)
    
    # 8. Replace all numerical values (integers, floats, negative numbers)
    s = re.sub(r'[-+]?\d+(?:[.,]\d+)?', ' <NUM> ', s)
    
    # 9. Normalize unit words
    s = UNITS_REGEX.sub(' <UNIT> ', s)
    
    # 10. Normalize variable assignments (e.g. AB =, r =)
    s = re.sub(r'\b[a-z]{1,4}\s*=\s*<NUM>', ' <VAR_VAL> ', s)
    
    # 11. Clean punctuation and collapse whitespace
    s = re.sub(r'[^\w\s<>]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def extract_template_signature(text: str) -> str:
    """
    Computes a stable hash key representing the exact structure/template of the question.
    Two questions with identical phrasing that differ only by numbers or names
    will return the exact same template signature.
    """
    normalized = normalize_problem_text(text)
    if not normalized:
        return "empty_template"
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculates semantic token similarity (Jaccard on 1-grams and 2-grams)
    between two normalized problem skeletons.
    """
    norm1 = normalize_problem_text(text1)
    norm2 = normalize_problem_text(text2)
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0
        
    words1 = norm1.split()
    words2 = norm2.split()
    
    if not words1 or not words2:
        return 0.0
        
    set1 = set(words1)
    set2 = set(words2)
    
    # 1-gram Jaccard
    jaccard_1 = len(set1 & set2) / max(1, len(set1 | set2))
    
    # 2-grams (phrases)
    bigrams1 = set(zip(words1[:-1], words1[1:])) if len(words1) > 1 else set()
    bigrams2 = set(zip(words2[:-1], words2[1:])) if len(words2) > 1 else set()
    
    jaccard_2 = 0.0
    if bigrams1 and bigrams2:
        jaccard_2 = len(bigrams1 & bigrams2) / max(1, len(bigrams1 | bigrams2))
    elif not bigrams1 and not bigrams2:
        jaccard_2 = jaccard_1
        
    return 0.4 * jaccard_1 + 0.6 * jaccard_2

# =========================================================================
# Pedagogical Problem Archetypes (Dạng bài & Phương pháp giải)
# =========================================================================
ARCHETYPE_PATTERNS: List[Tuple[str, str, str, List[str]]] = [
    # (archetype_key, display_name, subject, regex_patterns)
    # --- MATH: Geometry ---
    ("math_geo_trapezoid_area", "Hình học: Diện tích hình thang", "math", [
        r"hình thang.*(diện tích|đáy lớn|đáy bé|chiều cao)",
        r"thửa ruộng hình thang",
        r"mảnh đất hình thang"
    ]),
    ("math_geo_triangle", "Hình học: Tam giác (Diện tích & Cạnh)", "math", [
        r"tam giác.*(diện tích|chiều cao|cạnh đáy|chu vi)",
        r"hình tam giác"
    ]),
    ("math_geo_circle", "Hình học: Hình tròn (Chu vi & Diện tích)", "math", [
        r"hình tròn.*(bán kính|đường kính|chu vi|diện tích)",
        r"bán kính.*r\s*=",
        r"đường kính.*d\s*="
    ]),
    ("math_geo_rect_square", "Hình học: Hình chữ nhật & Hình vuông", "math", [
        r"hình chữ nhật.*(chiều dài|chiều rộng|chu vi|diện tích)",
        r"hình vuông.*(cạnh|chu vi|diện tích)"
    ]),
    ("math_geo_parallelogram_rhombus", "Hình học: Hình bình hành & Hình thoi", "math", [
        r"hình bình hành",
        r"hình thoi"
    ]),
    ("math_geo_3d_box", "Hình học: Thể tích & Hình khối", "math", [
        r"hình hộp chữ nhật",
        r"hình lập phương",
        r"thể tích.*(hình hộp|hình lập phương|bể nước|khối)"
    ]),
    ("math_geo_broken_line", "Hình học: Đoạn thẳng & Đường gấp khúc", "math", [
        r"đường gấp khúc",
        r"đoạn thẳng.*độ dài",
        r"điểm nằm giữa",
        r"tia số"
    ]),
    ("math_geo_3d_coordinates", "Hình học Oxyz: Mặt cầu & Không gian", "math", [
        r"mặt cầu\s*\(\s*s\s*\)",
        r"không gian tọa độ.*oxyz",
        r"phương trình mặt cầu",
        r"mặt phẳng\s*\(\s*p\s*\)"
    ]),

    # --- MATH: Word Problems ---
    ("math_word_motion", "Toán chuyển động: Vận tốc, Quãng đường, Thời gian", "math", [
        r"vận tốc.*(km/h|m/s|quãng đường)",
        r"người đi (xe máy|ô tô|xe đạp|tàu hỏa|ca nô)",
        r"đuổi kịp|ngược chiều|cùng chiều"
    ]),
    ("math_word_item_give_take", "Toán có lời văn: Thêm bớt & So sánh số lượng", "math", [
        r"gives.*to.*friend",
        r"how many.*does.*have left",
        r"nhiều hơn.*ít hơn",
        r"cho bạn.*còn lại",
        r"mua thêm.*bán đi"
    ]),
    ("math_word_sum_ratio", "Toán có lời văn: Tổng-hiệu & Tỉ lệ", "math", [
        r"tổng số.*nhiều hơn",
        r"học sinh là nữ.*số học sinh",
        r"gấp.*lần",
        r"tỉ số giữa",
        r"tìm hai số khi biết"
    ]),
    ("math_word_age_work", "Toán có lời văn: Tính tuổi & Năng suất", "math", [
        r"tuổi của (bố|mẹ|con|ông|bà)",
        r"cùng làm một công việc",
        r"vòi nước.*chảy vào bể"
    ]),

    # --- MATH: Fractions, Decimals & Percentages ---
    ("math_fraction_calc", "Phân số: Phép tính & Hỗn số", "math", [
        r"\\frac",
        r"phân số",
        r"hỗn số",
        r"tử số.*mẫu số"
    ]),
    ("math_decimal_percentage", "Số học: Số thập phân & Tỉ số phần trăm", "math", [
        r"số thập phân",
        r"tỉ số phần trăm",
        r"phần trăm.*của",
        r"lãi suất.*%"
    ]),

    # --- MATH: Number Theory & Arithmetic ---
    ("math_number_structure", "Số học: Cấu tạo số & Giá trị chữ số", "math", [
        r"place value of the digit",
        r"chữ số hàng (đơn vị|chục|trăm|nghìn|triệu)",
        r"giá trị của chữ số",
        r"số lớn nhất.*số bé nhất",
        r"số liền sau|số liền trước",
        r"số có.*chữ số"
    ]),
    ("math_arith_gcd_lcm", "Số học: Ước chung, Bội chung & Số nguyên tố", "math", [
        r"ước chung lớn nhất|ưcln",
        r"bội chung nhỏ nhất|bcnn",
        r"số nguyên tố|hợp số",
        r"chia hết cho|số dư khi chia"
    ]),
    ("math_arith_integers", "Số học: Phép tính số nguyên & Biểu thức", "math", [
        r"phép tính số nguyên",
        r"thứ tự thực hiện.*phép tính",
        r"tính giá trị của biểu thức",
        r"biểu thức:.*[-+*/]"
    ]),
    ("math_arith_basic", "Số học: Phép cộng, trừ, nhân, chia", "math", [
        r"kết quả của phép (cộng|trừ|nhân|chia)",
        r"tính nhẩm kết quả",
        r"đặt tính rồi tính"
    ]),
    ("math_algebra_asymptote_function", "Giải tích: Khảo sát hàm số & Tiệm cận", "math", [
        r"đường tiệm cận (đứng|ngang)",
        r"đồ thị hàm số",
        r"cực trị|đồng biến|nghịch biến"
    ]),
    ("math_algebra_equation", "Đại số: Phương trình & Tìm x", "math", [
        r"tìm x",
        r"nghiệm của phương trình",
        r"phương trình bậc"
    ]),

    # --- VIETNAMESE ---
    ("vn_spelling", "Tiếng Việt: Chính tả & Âm vần", "vietnamese", [
        r"điền (âm|vần|tiếng|từ)",
        r"viết đúng chính tả",
        r"từ nào viết sai"
    ]),
    ("vn_parts_of_speech", "Tiếng Việt: Từ loại & Mở rộng vốn từ", "vietnamese", [
        r"từ chỉ (sự vật|hoạt động|đặc điểm)",
        r"danh từ|động từ|tính từ",
        r"từ đồng nghĩa|từ trái nghĩa|từ ghép|từ láy"
    ]),
    ("vn_sentence_syntax", "Tiếng Việt: Kiểu câu & Dấu câu", "vietnamese", [
        r"ai là gì|ai làm gì|ai thế nào",
        r"câu kể|câu hỏi|câu cảm|câu khiến",
        r"chủ ngữ|vị ngữ|trạng ngữ",
        r"dấu (chấm|phẩy|hai chấm|chấm than)"
    ]),
    ("vn_idioms_reading", "Tiếng Việt: Thành ngữ, Tục ngữ & Đọc hiểu", "vietnamese", [
        r"thành ngữ|tục ngữ|ca dao",
        r"đoạn văn|bài đọc|nội dung bài",
        r"ý nghĩa của"
    ]),

    # --- ENGLISH ---
    ("en_grammar_tense", "Tiếng Anh: Ngữ pháp & Thì động từ", "english", [
        r"verb form|tense|past simple|present continuous",
        r"correct form of the verb"
    ]),
    ("en_vocabulary", "Tiếng Anh: Từ vựng & Điền từ", "english", [
        r"opposite meaning|synonym|antonym",
        r"choose the word|fill in the blank"
    ]),
    ("en_reading", "Tiếng Anh: Đọc hiểu văn bản", "english", [
        r"read the passage|according to the text"
    ])
]

def classify_problem_archetype(q: Dict[str, Any]) -> Tuple[str, str]:
    """
    Identifies the pedagogical archetype (dạng bài toán / kỹ năng giải)
    of a question to ensure diverse coverage across concepts.
    Returns (archetype_key, display_name).
    """
    text = (q.get("content_text") or q.get("content_html") or "").lower()
    subject = (q.get("subject") or "math").lower()
    topic = (q.get("topic") or "").lower()
    combined = f"{text} {topic}"
    
    for arch_key, disp_name, arch_subj, patterns in ARCHETYPE_PATTERNS:
        if arch_subj == subject or subject == "math":
            for pat in patterns:
                if re.search(pat, combined, re.IGNORECASE):
                    return arch_key, disp_name
                    
    norm = normalize_problem_text(text)
    words = norm.split()
    lead_phrase = "_".join(words[:4]) if words else "unknown"
    return f"{subject}_{lead_phrase}", f"{subject.capitalize()}: Dạng bài tổng hợp"

# =========================================================================
# Diverse Exam Generation Algorithm
# =========================================================================
def select_diverse_exam_questions(
    candidates: List[Dict[str, Any]],
    count: int,
    already_selected: Optional[List[Dict[str, Any]]] = None,
    allow_cross_grade: bool = True,
    fallback_fetcher: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Selects 'count' questions from 'candidates' guaranteeing:
    1. ZERO isomorphic duplicate questions (strictly distinct template signatures).
    2. Maximal archetype and pedagogical diversity (khác nhau về nội dung lẫn cách làm).
    3. Similarity between any two questions remains below the duplicate threshold.
    """
    if count <= 0:
        return []
        
    selected: List[Dict[str, Any]] = []
    used_templates: Set[str] = set()
    used_archetypes_count: Dict[str, int] = {}
    
    # Register already selected questions
    if already_selected:
        for sq in already_selected:
            txt = sq.get("content_text") or sq.get("content_html") or ""
            sig = extract_template_signature(txt)
            used_templates.add(sig)
            arch, _ = classify_problem_archetype(sq)
            used_archetypes_count[arch] = used_archetypes_count.get(arch, 0) + 1

    # Shuffle candidates to ensure fresh random selection across runs
    shuffled_candidates = list(candidates)
    random.shuffle(shuffled_candidates)
    
    # Group candidates by archetype
    archetype_buckets: Dict[str, List[Dict[str, Any]]] = {}
    for c in shuffled_candidates:
        txt = c.get("content_text") or c.get("content_html") or ""
        sig = extract_template_signature(txt)
        if sig in used_templates:
            continue
            
        arch, _ = classify_problem_archetype(c)
        archetype_buckets.setdefault(arch, []).append(c)

    # Round-Robin through archetypes to maximize problem diversity
    # Round 1: Take 1 question per archetype
    # Round 2+: If still needed, take additional questions with strict template uniqueness & similarity < 0.65
    max_rounds = 4
    for round_num in range(1, max_rounds + 1):
        if len(selected) >= count:
            break
            
        sorted_archs = sorted(
            archetype_buckets.keys(),
            key=lambda a: (used_archetypes_count.get(a, 0), random.random())
        )
        
        for arch in sorted_archs:
            if len(selected) >= count:
                break
                
            bucket = archetype_buckets[arch]
            chosen_cand = None
            for cand in bucket:
                txt = cand.get("content_text") or cand.get("content_html") or ""
                sig = extract_template_signature(txt)
                if sig in used_templates:
                    continue
                    
                is_too_similar = False
                for s in (already_selected or []) + selected:
                    s_txt = s.get("content_text") or s.get("content_html") or ""
                    sim = calculate_text_similarity(txt, s_txt)
                    if sim >= 0.65:
                        is_too_similar = True
                        break
                        
                if not is_too_similar:
                    chosen_cand = cand
                    break
                    
            if chosen_cand:
                selected.append(chosen_cand)
                sig = extract_template_signature(chosen_cand.get("content_text") or "")
                used_templates.add(sig)
                used_archetypes_count[arch] = used_archetypes_count.get(arch, 0) + 1
                bucket.remove(chosen_cand)

    # If still not enough and fallback_fetcher is provided, fetch extra diverse questions
    if len(selected) < count and fallback_fetcher:
        needed_more = count - len(selected)
        extra_candidates = fallback_fetcher(exclude_templates=used_templates, needed=needed_more * 3)
        if extra_candidates:
            extra_selected = select_diverse_exam_questions(
                candidates=extra_candidates,
                count=needed_more,
                already_selected=(already_selected or []) + selected,
                allow_cross_grade=False,
                fallback_fetcher=None
            )
            selected.extend(extra_selected)

    return selected

# =========================================================================
# Exam Diversity Analysis & Deduplication Utilities
# =========================================================================
def analyze_exam_diversity(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Examines an exam question list and reports:
    - Number of duplicate isomorphic question clusters (e.g. trapezoid clones)
    - Diversity score (0% to 100%)
    - Breakdown of problem archetypes
    - Specific duplicate question IDs that should be replaced
    """
    total = len(questions)
    if total == 0:
        return {
            "total_questions": 0,
            "unique_templates_count": 0,
            "duplicate_count": 0,
            "diversity_score": 100.0,
            "duplicate_clusters": [],
            "duplicate_question_ids": [],
            "archetypes": {},
            "status": "empty",
            "message": "Chưa có câu hỏi trong đề"
        }

    template_map: Dict[str, List[Dict[str, Any]]] = {}
    archetypes_map: Dict[str, int] = {}
    
    for idx, q in enumerate(questions):
        txt = q.get("content_text") or q.get("content_html") or ""
        sig = extract_template_signature(txt)
        arch_key, arch_name = classify_problem_archetype(q)
        
        archetypes_map[arch_name] = archetypes_map.get(arch_name, 0) + 1
        template_map.setdefault(sig, []).append({
            "id": q.get("id"),
            "index": idx + 1,
            "q_number": q.get("q_number"),
            "archetype": arch_name,
            "snippet": txt[:75] + ("..." if len(txt) > 75 else "")
        })

    duplicate_clusters = []
    duplicate_ids: List[str] = []
    
    for sig, group in template_map.items():
        if len(group) > 1:
            duplicate_clusters.append({
                "template_hash": sig,
                "count": len(group),
                "archetype": group[0]["archetype"],
                "sample_text": group[0]["snippet"],
                "questions": group
            })
            for dup_item in group[1:]:
                duplicate_ids.append(dup_item["id"])

    # Also check fuzzy similarity for questions with different template hashes
    checked_pairs = set()
    for i in range(total):
        q1_id = questions[i].get("id")
        if q1_id in duplicate_ids:
            continue
        txt1 = questions[i].get("content_text") or ""
        for j in range(i + 1, total):
            q2_id = questions[j].get("id")
            if q2_id in duplicate_ids:
                continue
            pair_key = (min(str(q1_id), str(q2_id)), max(str(q1_id), str(q2_id)))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)
            
            txt2 = questions[j].get("content_text") or ""
            sim = calculate_text_similarity(txt1, txt2)
            if sim >= 0.72:
                duplicate_ids.append(q2_id)
                duplicate_clusters.append({
                    "template_hash": f"fuzzy_{q1_id}",
                    "count": 2,
                    "archetype": classify_problem_archetype(questions[i])[1],
                    "sample_text": txt1[:75],
                    "questions": [
                        {"id": q1_id, "index": i + 1, "snippet": txt1[:75]},
                        {"id": q2_id, "index": j + 1, "snippet": txt2[:75]}
                    ]
                })

    unique_count = total - len(duplicate_ids)
    diversity_score = round((unique_count / max(1, total)) * 100, 1)

    if len(duplicate_ids) == 0:
        msg = f"Đề thi đạt độ đa dạng hoàn hảo {diversity_score}%! Không có câu hỏi nào bị trùng dạng hay lặp lại số liệu."
        status = "excellent"
    elif diversity_score >= 80:
        msg = f"Độ đa dạng khá tốt ({diversity_score}%). Phát hiện {len(duplicate_ids)} câu trùng dạng bài."
        status = "good"
    else:
        msg = f"Cảnh báo: Đề thi có {len(duplicate_ids)} câu hỏi bị trùng dạng / chỉ khác số liệu (Độ đa dạng: {diversity_score}%)."
        status = "warning"

    return {
        "total_questions": total,
        "unique_templates_count": unique_count,
        "duplicate_count": len(duplicate_ids),
        "diversity_score": diversity_score,
        "duplicate_clusters": duplicate_clusters,
        "duplicate_question_ids": duplicate_ids,
        "archetypes": archetypes_map,
        "status": status,
        "message": msg
    }

def deduplicate_and_diversify_exam(
    questions: List[Dict[str, Any]],
    replacement_fetcher: Any
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    One-click smart exam deduplication and diversification.
    Keeps 1 question from each duplicate cluster and replaces all redundant ones
    with fresh diverse questions matching the same difficulty and grade.
    """
    analysis = analyze_exam_diversity(questions)
    dup_ids = set(analysis["duplicate_question_ids"])
    
    if not dup_ids:
        return questions, []
        
    kept_questions = [q for q in questions if q.get("id") not in dup_ids]
    used_templates = {extract_template_signature(q.get("content_text") or "") for q in kept_questions}
    
    replacements_made = []
    final_questions = list(questions)
    
    for idx, q in enumerate(questions):
        qid = q.get("id")
        if qid in dup_ids:
            grade = q.get("grade") or 5
            diff = q.get("difficulty") or "medium"
            subj = q.get("subject") or "math"
            
            new_q = replacement_fetcher(
                subject=subj,
                grade=grade,
                difficulty=diff,
                exclude_templates=used_templates,
                exclude_ids={x.get("id") for x in final_questions if x.get("id")}
            )
            
            if new_q:
                new_sig = extract_template_signature(new_q.get("content_text") or "")
                used_templates.add(new_sig)
                final_questions[idx] = new_q
                replacements_made.append({
                    "old_id": qid,
                    "new_id": new_q.get("id"),
                    "index": idx + 1,
                    "difficulty": diff
                })
                
    return final_questions, replacements_made

def swap_exam_question(
    target_id: str,
    all_questions: List[Dict[str, Any]],
    candidate_fetcher: Any
) -> Optional[Dict[str, Any]]:
    """
    Swaps a single question with a new question of the same difficulty/grade
    that is guaranteed to have a completely DIFFERENT archetype and template.
    """
    target_q = next((q for q in all_questions if q.get("id") == target_id), None)
    if not target_q:
        return None
        
    grade = target_q.get("grade") or 5
    diff = target_q.get("difficulty") or "medium"
    subj = target_q.get("subject") or "math"
    
    other_questions = [q for q in all_questions if q.get("id") != target_id]
    used_templates = {extract_template_signature(q.get("content_text") or "") for q in other_questions}
    target_sig = extract_template_signature(target_q.get("content_text") or "")
    used_templates.add(target_sig)
    
    used_ids = {q.get("id") for q in all_questions if q.get("id")}
    
    return candidate_fetcher(
        subject=subj,
        grade=grade,
        difficulty=diff,
        exclude_templates=used_templates,
        exclude_ids=used_ids
    )

# =========================================================================
# Smart Exam Shuffling (Trộn Đề Thi & Xáo Trộn Đáp Án Chuẩn)
# =========================================================================
def shuffle_exam_smart(
    questions: List[Dict[str, Any]],
    shuffle_order: bool = True,
    shuffle_options: bool = True
) -> List[Dict[str, Any]]:
    """
    Shuffles exam questions and/or scrambles multiple choice options (A, B, C, D)
    while strictly keeping the correct_answer key in perfect sync!
    """
    result = []
    
    for q in questions:
        q_copy = dict(q)
        
        options = q.get("options")
        if shuffle_options and options and isinstance(options, list) and len(options) >= 2:
            orig_correct = q.get("correct_answer")
            
            opts_with_correct = []
            for opt in options:
                is_correct = opt.get("is_correct", False)
                if orig_correct and str(opt.get("id")).upper() == str(orig_correct).upper():
                    is_correct = True
                opts_with_correct.append({
                    "content": opt.get("content", ""),
                    "is_correct": is_correct
                })
                
            random.shuffle(opts_with_correct)
            
            labels = ["A", "B", "C", "D", "E", "F"]
            new_options = []
            new_correct_label = "A"
            
            for idx, item in enumerate(opts_with_correct):
                lbl = labels[idx] if idx < len(labels) else f"Opt{idx+1}"
                new_options.append({
                    "id": lbl,
                    "content": item["content"],
                    "is_correct": item["is_correct"]
                })
                if item["is_correct"]:
                    new_correct_label = lbl
                    
            q_copy["options"] = new_options
            q_copy["correct_answer"] = new_correct_label
            
        result.append(q_copy)
        
    if shuffle_order:
        random.shuffle(result)
        
    return result
