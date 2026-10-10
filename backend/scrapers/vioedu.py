from __future__ import annotations
import re
import uuid
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from backend.database import insert_or_update_question, log_collector_event, bulk_insert_questions
from backend.normalizer import normalize_question_payload, is_valid_question_payload

VN_TZ = timezone(timedelta(hours=7)) # Chuẩn múi giờ Việt Nam UTC+7

VIOEDU_BASE_URL = "https://vio.edu.vn"

# Realistic User-Agent for headless requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# -------------------------------------------------------------
# 1. Direct HTTP API Authentication & Target Parsing
# -------------------------------------------------------------

def parse_vioedu_target(target: Optional[str]) -> Dict[str, Any]:
    """
    Parses user input target into action type:
    - MongoDB 24-hex ID: skill_practice
    - URL containing skill-practice/:id: skill_practice
    - URL containing skill-list or 'skill-list': skill_list
    - Digits (1, 2, 3): arena_round
    - None or empty: auto
    """
    if not target or not str(target).strip():
        return {"type": "auto"}
        
    s = str(target).strip()
    
    # 1. Check skill-practice URL: e.g. https://vio.edu.vn/skill-practice/64bf82717faf420030d20eeb
    m_skill = re.search(r'skill-practice/([0-9a-fA-F]{24})', s)
    if m_skill:
        return {"type": "skill_practice", "skill_id": m_skill.group(1)}
        
    # 2. Check direct 24-character hex ID: e.g. 64bf82717faf420030d20eeb
    if re.match(r'^[0-9a-fA-F]{24}$', s):
        return {"type": "skill_practice", "skill_id": s}
        
    # 3. Check skill-list: e.g. https://vio.edu.vn/skill-list or skill-list
    if "skill-list" in s.lower() or "danh-sach-ky-nang" in s.lower():
        return {"type": "skill_list"}
        
    # 4. Arena round number: e.g. 1, 2, 10
    if s.isdigit():
        return {"type": "arena_round", "round_id": s}
        
    # 5. Full custom URL
    if s.startswith("http://") or s.startswith("https://"):
        return {"type": "custom_url", "url": s}
        
    return {"type": "arena_round", "round_id": s}

RESET_3_DEVICES_MUTATION = """mutation resetLogin3DevicesM($username: String) {
  resetLogin3Devices(username: $username)
}"""

async def reset_vioedu_devices(username: str) -> bool:
    """
    Calls VioEdu GraphQL mutation to clear registered devices when account hits OVER_QUOTA (max 3 devices limit).
    Returns True if successfully reset.
    """
    url = f"{VIOEDU_BASE_URL}/graphql"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Origin": VIOEDU_BASE_URL,
        "Referer": f"{VIOEDU_BASE_URL}/login"
    }
    payload = {
        "operationName": "resetLogin3DevicesM",
        "variables": {"username": username.strip()},
        "query": RESET_3_DEVICES_MUTATION
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return bool(data.get("data", {}).get("resetLogin3Devices"))
    except Exception:
        pass
    return False

async def login_vioedu(username: str, password: str, log_func: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
    """
    Direct HTTP authentication with VioEdu API endpoint (https://vio.edu.vn/login).
    Retrieves user profile, fixed grade, and session cookies.
    Handles device quota limitation (OVER_QUOTA) automatically by resetting prior sessions.
    """
    url = f"{VIOEDU_BASE_URL}/login"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Referer": "https://vio.edu.vn/login",
        "Origin": "https://vio.edu.vn"
    }
    payload = {
        "username": username.strip(),
        "password": password.strip()
    }
    
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                user = data.get("user")
                
                # Auto-recovery for OVER_QUOTA (exceeded 3 concurrent devices)
                if status == "OVER_QUOTA":
                    if log_func:
                        log_func("⚠️ Tài khoản đã đăng nhập trên quá 3 thiết bị (OVER_QUOTA). Đang tự động kích hoạt giải phóng phiên cũ (resetLogin3Devices)...")
                    reset_ok = await reset_vioedu_devices(username)
                    if reset_ok:
                        if log_func:
                            log_func("✅ Đã giải phóng phiên thiết bị cũ thành công. Đang tự động đăng nhập lại...")
                        await asyncio.sleep(0.6)
                        retry_resp = await client.post(url, json=payload, headers=headers)
                        if retry_resp.status_code == 200:
                            retry_data = retry_resp.json()
                            status = retry_data.get("status")
                            user = retry_data.get("user")
                            resp = retry_resp
                    else:
                        if log_func:
                            log_func("⚠️ Không thể giải phóng phiên thiết bị qua API GraphQL. Sẽ thử xử lý qua trình duyệt...")
                
                if user and isinstance(user, dict):
                    student_grade = user.get("grade") or user.get("class")
                    student_name = user.get("fullName") or user.get("username") or username
                    token = user.get("token") or user.get("_id") or str(uuid.uuid4())
                    
                    return {
                        "success": True,
                        "user": user,
                        "student_name": student_name,
                        "grade": int(student_grade) if student_grade else 5,
                        "token": token,
                        "cookies": dict(resp.cookies)
                    }
                elif status == "WRONG_PASSWORD":
                    return {
                        "success": False,
                        "error": "Tên đăng nhập hoặc mật khẩu VioEdu không chính xác. Vui lòng kiểm tra lại."
                    }
                elif status == "WRONG_PASSWORD_LOCKED":
                    return {
                        "success": False,
                        "error": "Tài khoản VioEdu đã bị khóa do nhập sai mật khẩu quá nhiều lần!"
                    }
                elif status == "OVER_QUOTA":
                    return {
                        "success": False,
                        "error": "Tài khoản đăng nhập vượt quá 3 thiết bị đồng thời (OVER_QUOTA). Vui lòng thử lại sau giây lát."
                    }
                elif status == "IN_ACTIVE":
                    return {
                        "success": False,
                        "error": "Tài khoản VioEdu chưa được kích hoạt. Vui lòng kích hoạt tài khoản trên trang web VioEdu."
                    }
                elif status == "DELETED":
                    return {
                        "success": False,
                        "error": "Tài khoản VioEdu không tồn tại trong hệ thống hoặc đã bị vô hiệu hóa."
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Phản hồi từ VioEdu: {status or 'Chưa xác thực được người dùng'}"
                    }
            elif resp.status_code in [401, 403]:
                return {
                    "success": False,
                    "error": "Tài khoản hoặc mật khẩu VioEdu không chính xác hoặc cần xác thực Captcha."
                }
            else:
                return {
                    "success": False,
                    "error": f"Máy chủ VioEdu phản hồi HTTP {resp.status_code}"
                }
    except Exception as e:
        return {"success": False, "error": f"Lỗi kết nối máy chủ VioEdu: {str(e)}"}

# -------------------------------------------------------------
# 2. VioEdu Question Normalization & Parsing
# -------------------------------------------------------------

def clean_vioedu_stem(raw_html: str) -> str:
    """Strips leading question numbers like 'Câu hỏi số 5', 'Câu 1:' from content."""
    if not raw_html:
        return ""
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup.select(".panel-heading, .practice-question-title, .question-title, .cau-hoi-so, [class*='question-number']"):
            tag.decompose()
        cleaned = str(soup)
    except Exception:
        cleaned = raw_html
        
    cleaned = re.sub(r'^(?:<[^>]+>|\s)*(?:<[bi]>)?(?:Câu|Bài)(?:\s+hỏi)?\s*(?:số)?\s*\d+\s*[:.]?\s*(?:<\/[bi]>)?(?:\s*<\/[^>]+>)?\s*', '', cleaned, flags=re.I)
    return cleaned.strip()

def parse_vioedu_question_data(item: Dict[str, Any], exam_name: str = "Đấu trường VioEdu", grade: int = 5) -> Optional[Dict[str, Any]]:
    """
    Parses a raw VioEdu question dict into standard EduQuest question schema.
    Extracts formulas, options, correct answers, and explanations across all question types:
    - Type 1: Single Choice (Chọn 1 đáp án)
    - Type 2: Multiple Choice (Chọn tất cả đáp án đúng)
    - Type 3: Fill in the Blank (Điền vào ô trống {})
    - Type 4: Matching / Pairs (Nối tương ứng)
    """
    if not item or not isinstance(item, dict):
        return None
        
    raw_content = item.get("content") or item.get("question_content") or item.get("question_text") or item.get("stem") or item.get("title") or ""
    if not raw_content or len(str(raw_content).strip()) < 6:
        return None
        
    raw_content = clean_vioedu_stem(str(raw_content))
    raw_exp = item.get("explanation") or item.get("solution") or item.get("guide") or ""
    q_type_raw = str(item.get("questionType") or item.get("type") or "").strip()
    
    # Process options / answers
    raw_options = (
        item.get("answers") or 
        item.get("options") or 
        item.get("list_answer") or 
        item.get("list_answers") or 
        item.get("choices") or 
        []
    )
    
    options = []
    correct_ans = item.get("right_answer") or item.get("correct_answer")
    q_type = "single_choice"
    
    # 1. Matching Questions (Type 4 or leftMatching/rightMatching)
    if (item.get("leftMatching") and item.get("rightMatching")) or q_type_raw in ["match", "matching", "pair", "4"]:
        q_type = "matching"
        lm_list = item.get("leftMatching") or []
        rm_list = item.get("rightMatching") or []
        for idx, lm in enumerate(lm_list):
            rm = rm_list[idx] if idx < len(rm_list) else {}
            lt = lm.get("textContent") or lm.get("content") or lm.get("text") or "" if isinstance(lm, dict) else str(lm)
            rt = rm.get("textContent") or rm.get("content") or rm.get("text") or "" if isinstance(rm, dict) else str(rm)
            if lt or rt:
                options.append({
                    "id": chr(65 + idx),
                    "content": f"{lt} ↔ {rt}",
                    "is_correct": True
                })
        correct_ans = "Nối tương ứng"

    # 2. Fill in the blank (Type 3 or explicit fill_blank or stem has {} and answers are blanks)
    elif q_type_raw in ["3", "fill_blank"] or ("{}" in raw_content and (not raw_options or len(raw_options) <= 3 and not any(isinstance(o, dict) and (o.get("correct") or o.get("is_correct")) for o in raw_options))):
        q_type = "fill_blank"
        options = []
        blank_values = []
        if isinstance(raw_options, list):
            for a in raw_options:
                txt = ""
                if isinstance(a, dict):
                    txt = a.get("text") or a.get("content") or ""
                elif isinstance(a, str):
                    txt = a
                t_clean = BeautifulSoup(str(txt), "html.parser").get_text().strip()
                if t_clean:
                    blank_values.append(t_clean)
        if blank_values:
            correct_ans = ", ".join(blank_values)
        elif not correct_ans:
            correct_ans = ""

    # 3. Dropdown Questions
    elif not raw_options and isinstance(item.get("textDropdownAnswers"), list) and len(item["textDropdownAnswers"]) > 0:
        q_type = "single_choice"
        for dd in item["textDropdownAnswers"]:
            if isinstance(dd, dict) and isinstance(dd.get("list"), list):
                for idx, opt in enumerate(dd["list"]):
                    t = opt.get("text") or opt.get("content") if isinstance(opt, dict) else str(opt)
                    if t:
                        options.append({
                            "id": chr(65 + idx),
                            "content": str(t).strip(),
                            "is_correct": idx == 0
                        })
        if options and not correct_ans:
            correct_ans = "A"

    # 4. Standard Multiple Choice / Single Choice
    else:
        # Determine if multiple_choice (Type 2 or explicit label)
        if q_type_raw in ["2", "multiple_choice"] or "chọn tất cả" in raw_content.lower() or "các đáp án đúng" in raw_content.lower():
            q_type = "multiple_choice"
        else:
            q_type = "single_choice"
            
        correct_letters = []
        if isinstance(raw_options, list):
            for idx, opt in enumerate(raw_options):
                opt_id = chr(65 + idx)
                opt_content = ""
                is_correct = False
                
                if isinstance(opt, dict):
                    opt_content = opt.get("text") or opt.get("content") or opt.get("title") or ""
                    if opt.get("correct") is True or opt.get("is_correct") is True or opt.get("right") is True:
                        is_correct = True
                        correct_letters.append(opt_id)
                elif isinstance(opt, str):
                    opt_content = opt
                    
                opt_content = re.sub(r'^[A-D]\s*[\.\:\)]\s*', '', str(opt_content).strip())
                if opt_content:
                    options.append({
                        "id": opt_id,
                        "content": opt_content,
                        "is_correct": is_correct
                    })
                    
        if correct_letters:
            correct_ans = ", ".join(correct_letters)
            if len(correct_letters) > 1:
                q_type = "multiple_choice"
        elif not correct_ans:
            correct_ans = "A" if options else ""

    # Normalize images
    images = []
    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_content)
    for src in img_matches:
        if src not in images and not any(ic in src for ic in ["avatar", "icon", "logo", "btn", "arrow"]):
            images.append(src)

    topic = item.get("skillName") or item.get("skill_name") or item.get("topic") or f"Toán học VioEdu Lớp {grade}"
    clean_text = BeautifulSoup(raw_content, "html.parser").get_text(separator=" ").strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    qid = str(item.get("id") or item.get("_id") or item.get("question_id") or uuid.uuid4().hex[:8])
    
    return {
        "id": f"vioedu_{qid}",
        "source_platform": "vioedu",
        "source_url": "https://vio.edu.vn",
        "exam_name": exam_name,
        "grade": grade,
        "subject": "math",
        "topic": topic,
        "question_type": q_type,
        "content_html": raw_content,
        "content_text": clean_text,
        "images": images,
        "options": options,
        "correct_answer": str(correct_ans) if correct_ans else ("A" if options else ""),
        "explanation": str(raw_exp),
        "difficulty": str(item.get("level") or "medium")
    }

# -------------------------------------------------------------
# 3. Deep Question Extraction from Nested Payloads
# -------------------------------------------------------------

IGNORED_KEYS = {
    "user", "auth", "ranking", "leaderboard", "avatar", "profile",
    "news", "posts", "post", "articles", "banners", "banner",
    "notifications", "notification", "categories", "sliders", "slider",
    "events", "event", "packages", "package", "transactions", "payments"
}

def is_question_candidate(obj: Any) -> bool:
    """Determines whether a dictionary represents an educational question payload."""
    if not isinstance(obj, dict):
        return False
        
    if any(k in obj for k in ["slug", "post_type", "category_id", "news_id", "banner_url"]):
        return False
        
    content = obj.get("content") or obj.get("question_content") or obj.get("question_text") or obj.get("stem")
    if not content or not isinstance(content, str) or len(content.strip()) < 8:
        return False
        
    # Exclude system strings, UUIDs, or URLs
    if content.startswith("http://") or content.startswith("https://") or re.match(r'^[a-f0-9\-]{24,36}$', content.strip()):
        return False
        
    has_options = bool(obj.get("answers") or obj.get("options") or obj.get("choices") or obj.get("list_answer"))
    has_indicators = any(k in obj for k in [
        "questionType", "question_type", "right_answer", "correct_answer", 
        "explanation", "skill_name", "skillName", "guide", "solution", "depthOfKnowledge"
    ])
    has_math = any(kw in content for kw in ["math-tex", "$", "+", "=", "tính", "phân số", "diện tích", "chu vi", "hình", "biểu thức"])
    
    return has_options or has_indicators or has_math

def extract_questions_deep(data: Any, max_depth: int = 5) -> List[Dict[str, Any]]:
    """Recursively walks nested JSON data to discover all question objects."""
    results = []
    if not data or max_depth <= 0:
        return results
        
    if isinstance(data, list):
        for item in data:
            if is_question_candidate(item):
                results.append(item)
            elif isinstance(item, (dict, list)):
                results.extend(extract_questions_deep(item, max_depth - 1))
    elif isinstance(data, dict):
        if is_question_candidate(data):
            results.append(data)
        for k, v in data.items():
            if k.lower() in IGNORED_KEYS:
                continue
            if isinstance(v, (dict, list)):
                results.extend(extract_questions_deep(v, max_depth - 1))
                
    return results

# -------------------------------------------------------------
# 4. Safe Read-Only GraphQL Crawlers (Skill Practice & Skill List)
# -------------------------------------------------------------

PRACTICE_QUESTION_QUERY = """query PracticeQuestionQuery($skillId: String, $user: String, $score: Int, $permission: String, $previousScore: Int, $grade: Int, $isTester: Boolean, $userHomeworkId: String, $fromSchool: Boolean, $notHomework: Boolean, $skillResultId: String, $totalQues: Int, $hwQsDone: Int, $homeworkQues: Int, $doneHwQues: Int, $currentWrongId: String, $isManual: Boolean, $afterManual: Boolean, $tokenId: String) {
  getPracticeQuestionBySkillId(skillId: $skillId, user: $user, score: $score, permission: $permission, previousScore: $previousScore, grade: $grade, isTester: $isTester, userHomeworkId: $userHomeworkId, fromSchool: $fromSchool, notHomework: $notHomework, skillResultId: $skillResultId, totalQues: $totalQues, hwQsDone: $hwQsDone, homeworkQues: $homeworkQues, doneHwQues: $doneHwQues, currentWrongId: $currentWrongId, isManual: $isManual, afterManual: $afterManual, tokenId: $tokenId) {
    _id
    skillName
    grade
    subject
    content
    depthOfKnowledge
    questionType
    explanation
    answers {
      _id
      text
      order
      correct
    }
    leftMatching {
      id
      textContent
    }
    rightMatching {
      id
      textContent
    }
    textDropdownAnswers {
      order
      list {
        text
      }
    }
    topic
    category
  }
}"""

async def fetch_vioedu_skill_practice_questions(
    skill_id: str,
    grade: int,
    cookies: Optional[Dict[str, str]] = None,
    max_questions: int = 15,
    log_func: Optional[callable] = None
) -> List[Dict[str, Any]]:
    """
    Safely retrieves practice questions for a specific skill via GraphQL in Read-Only mode.
    - Zero answer submissions (PracticeResultMutation is NEVER called).
    - Preserves student practice quota, score, and progress 100%.
    - Completely safe against bot bans.
    """
    url = f"{VIOEDU_BASE_URL}/graphql"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Referer": f"{VIOEDU_BASE_URL}/skill-practice/{skill_id}",
        "Origin": VIOEDU_BASE_URL
    }
    
    collected: List[Dict[str, Any]] = []
    seen_ids = set()
    consecutive_repeats = 0
    
    if log_func:
        log_func(f"🎯 Bắt đầu truy vấn câu hỏi thực hành an toàn (Read-Only) cho bài: {skill_id}...")
        
    try:
        async with httpx.AsyncClient(timeout=12.0, cookies=cookies or {}, follow_redirects=True) as client:
            for step in range(max_questions):
                variables = {
                    "skillId": skill_id,
                    "score": 0,
                    "userHomeworkId": "",
                    "fromSchool": False,
                    "notHomework": False,
                    "skillResultId": "",
                    "totalQues": step,
                    "hwQsDone": step,
                    "isManual": False,
                    "afterManual": False
                }
                payload = {
                    "operationName": "PracticeQuestionQuery",
                    "variables": variables,
                    "query": PRACTICE_QUESTION_QUERY
                }
                
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_q = data.get("data", {}).get("getPracticeQuestionBySkillId")
                    if raw_q and raw_q.get("_id"):
                        qid = raw_q["_id"]
                        if qid not in seen_ids:
                            seen_ids.add(qid)
                            consecutive_repeats = 0
                            collected.append(raw_q)
                            if log_func:
                                s_name = raw_q.get("skillName") or "Luyện tập"
                                raw_stem = clean_vioedu_stem(raw_q.get('content', ''))
                                clean_snippet = re.sub(r'<[^>]+>', ' ', raw_stem)
                                clean_snippet = re.sub(r'\s+', ' ', clean_snippet).strip()[:55]
                                log_func(f"  ✨ Thu thập câu hỏi #{len(collected)} [{s_name}]: {clean_snippet}...")
                        else:
                            consecutive_repeats += 1
                            if consecutive_repeats >= 4:
                                if log_func:
                                    log_func(f"  ℹ️ Đã quét hết ngân hàng câu hỏi mở của bài luyện tập này ({len(collected)} câu).")
                                break
                    else:
                        break
                else:
                    break
                    
                await asyncio.sleep(0.35)
                
    except Exception as e:
        if log_func:
            log_func(f"⚠️ Lỗi kết nối khi truy vấn bài luyện tập: {str(e)}")
            
    return collected

LIST_TOPIC_SKILL_QUERY = """query getListTopicSkill($grade: Int, $subjectId: String, $semester: Int, $topicClass: String, $bookId: String) {
  getListTopicSkill(grade: $grade, subjectId: $subjectId, semester: $semester, topicClass: $topicClass, bookId: $bookId)
}"""

GET_SKILL_LIST_QUERY = """query getSkillListQuery($idSubject: String, $idCategory: String, $bookId: String, $grade: Int, $unit: Int, $useForMobile: Boolean) {
  getSkillList(idSubject: $idSubject, idCategory: $idCategory, grade: $grade, unit: $unit, useForMobile: $useForMobile, bookId: $bookId) {
    _id
    name
  }
}"""

async def fetch_vioedu_skills_in_grade(
    grade: int,
    cookies: Optional[Dict[str, str]] = None,
    subject_id: str = "5b59371949ce6e0015c74cd9",
    log_func: Optional[callable] = None
) -> List[Dict[str, Any]]:
    """
    Discovers skill categories and practice skill IDs for a specific grade on VioEdu.
    """
    url = f"{VIOEDU_BASE_URL}/graphql"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Referer": f"{VIOEDU_BASE_URL}/skill-list",
        "Origin": VIOEDU_BASE_URL
    }
    
    discovered_skills: List[Dict[str, Any]] = []
    
    try:
        async with httpx.AsyncClient(timeout=12.0, cookies=cookies or {}, follow_redirects=True) as client:
            for sem in [1, 2]:
                payload = {
                    "operationName": "getListTopicSkill",
                    "variables": {"grade": grade, "subjectId": subject_id, "semester": sem, "topicClass": "all", "bookId": ""},
                    "query": LIST_TOPIC_SKILL_QUERY
                }
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    cats = data.get("data", {}).get("getListTopicSkill", {}).get("listCategory", [])
                    for cat in cats:
                        cat_id = cat.get("_id")
                        cat_name = cat.get("name")
                        if not cat_id:
                            continue
                        # Query skills in this category
                        s_payload = {
                            "operationName": "getSkillListQuery",
                            "variables": {"idSubject": subject_id, "idCategory": cat_id, "grade": grade, "bookId": "", "useForMobile": False},
                            "query": GET_SKILL_LIST_QUERY
                        }
                        s_resp = await client.post(url, json=s_payload, headers=headers)
                        if s_resp.status_code == 200:
                            s_data = s_resp.json()
                            skills = s_data.get("data", {}).get("getSkillList", [])
                            for s in skills:
                                if s.get("_id"):
                                    discovered_skills.append({
                                        "skill_id": s["_id"],
                                        "skill_name": s.get("name", "Bài luyện tập"),
                                        "category_name": cat_name,
                                        "grade": grade,
                                        "semester": sem
                                    })
                        await asyncio.sleep(0.15)
    except Exception as e:
        if log_func:
            log_func(f"⚠️ Không thể duyệt toàn bộ danh mục kỹ năng: {str(e)}")
            
    return discovered_skills

# -------------------------------------------------------------
# 5. Automated Headless Bot Crawler (Playwright Engine)
# -------------------------------------------------------------

async def crawl_vioedu_rounds_headless(
    username: str,
    password: str,
    round_id: Optional[str] = None,
    grade: Optional[int] = None
) -> Dict[str, Any]:
    """
    Automated Headless Bot for VioEdu:
    1. Logs in headlessly via Playwright Chromium.
    2. Extracts authenticated student profile and detects the FIXED GRADE of the account.
    3. Identifies target: Skill Practice (ID / URL), Skill List, Arena Round, or Auto.
    4. Safely retrieves practice questions via non-mutating GraphQL and DOM parsing.
    5. Normalizes, validates, and persists questions directly into SQLite data/questions.db.
    6. Emits structured real-time activity logs.
    """
    from playwright.async_api import async_playwright
    
    live_logs: List[str] = []
    
    def log_step(message: str, status: str = "info"):
        formatted = f"[{datetime.now(VN_TZ).strftime('%H:%M:%S')}] {message}"
        live_logs.append(formatted)
        print(f"[VioEdu Bot] {formatted}")
        
    log_step(f"🚀 Khởi động Bot Đăng nhập Ngầm VioEdu cho tài khoản: {username}...")
    
    if not username or not password:
        err = "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu tài khoản VioEdu."
        log_step(f"❌ Lỗi: {err}", "error")
        return {"success": False, "error": err, "logs": live_logs}
        
    effective_grade: int = int(grade) if grade else 5
    captured_questions_raw: List[Dict[str, Any]] = []
    student_profile = {"fullName": "", "grade": None, "username": username}
    login_error_detail = ""

    # Parse target type early
    target_info = parse_vioedu_target(round_id)
    log_step(f"🎯 Phân tích mục tiêu cào dữ liệu: Kiểu '{target_info['type'].upper()}'")

    # Step 1: Check credentials directly with VioEdu API
    log_step("🔑 Đang kiểm tra xác thực tài khoản VioEdu...")
    auth_check = await login_vioedu(username, password, log_func=log_step)
    if not auth_check.get("success"):
        err_msg = auth_check.get("error", "Tài khoản hoặc mật khẩu VioEdu không chính xác. Vui lòng kiểm tra lại.")
        log_step(f"❌ {err_msg}", "error")
        return {"success": False, "error": err_msg, "logs": live_logs}

    session_cookies = auth_check.get("cookies", {})
    student_profile["fullName"] = auth_check.get("student_name") or username
    if auth_check.get("grade"):
        student_profile["grade"] = auth_check["grade"]
        effective_grade = int(auth_check["grade"])
        log_step(f"✅ Xác thực tài khoản thành công! Học sinh: {student_profile['fullName']}")
        log_step(f"📌 QUAN TRỌNG: Tài khoản VioEdu có KHỐI LỚP CỐ ĐỊNH: Lớp {effective_grade}. Bot áp dụng tự động cho mọi câu hỏi và vòng thi!")

    target_exam_name = f"VioEdu Luyện tập - Khối {effective_grade}"

    try:
        async with async_playwright() as p:
            log_step("🌐 Đang khởi tạo trình duyệt Chromium không đầu (Headless)...")
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True
            )
            page = await context.new_page()
            
            # --- Network Interception Hook ---
            async def on_response(response):
                url = response.url
                try:
                    c_type = response.headers.get("content-type", "").lower()
                    if "vio.edu.vn" in url and ("json" in c_type or "graphql" in url or "api" in url):
                        data = await response.json()
                        extracted = extract_questions_deep(data)
                        if extracted:
                            captured_questions_raw.extend(extracted)
                            log_step(f"🎯 Bắt được {len(extracted)} câu hỏi từ gói mạng: {url.split('?')[0].split('/')[-1]}")
                except Exception:
                    pass
                    
            page.on("response", on_response)
            
            # --- Browser Login & Session Sync ---
            log_step("🔑 Đang mở trang đăng nhập VioEdu để đồng bộ phiên làm việc...")
            await page.goto(f"{VIOEDU_BASE_URL}/login", timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            
            user_input = page.locator("#login-username")
            pass_input = page.locator("#login-password")
            
            if not await user_input.is_visible(timeout=4000):
                user_input = page.locator("input[placeholder*='tên đăng nhập'], input[type='text']").first
                pass_input = page.locator("input[placeholder*='mật khẩu'], input[type='password']").first
                
            await user_input.fill(username)
            await pass_input.fill(password)
            
            try:
                btn_login = page.locator("button", has_text="Đăng nhập").first
                if await btn_login.is_visible(timeout=2000):
                    await btn_login.click(timeout=3000)
                else:
                    await pass_input.press("Enter")
            except Exception:
                await pass_input.press("Enter")
            
            await page.wait_for_timeout(2500)
            
            # Check if VioEdu displayed "Đăng xuất toàn bộ thiết bị" (status 289 OVER_QUOTA on browser UI)
            try:
                btn_reset_device = page.locator("button", has_text="Đăng xuất toàn bộ thiết bị").first
                if await btn_reset_device.is_visible(timeout=2000):
                    log_step("🔄 Trình duyệt phát hiện nút 'Đăng xuất toàn bộ thiết bị'. Đang tự động giải phóng phiên...")
                    await btn_reset_device.click(timeout=3000)
                    await page.wait_for_timeout(1500)
                    btn_relogin = page.locator("button", has_text="Đăng nhập").first
                    if await btn_relogin.is_visible(timeout=2000):
                        await btn_relogin.click(timeout=3000)
                        await page.wait_for_timeout(2500)
            except Exception:
                pass
            
            # Extract updated cookies from browser context
            browser_cookies = await context.cookies()
            for c in browser_cookies:
                session_cookies[c["name"]] = c["value"]

            # --- Target Dispatching ---
            
            # Case 1: Targeted Skill Practice (by ID or URL)
            if target_info["type"] == "skill_practice":
                skill_id = target_info["skill_id"]
                practice_url = f"{VIOEDU_BASE_URL}/skill-practice/{skill_id}"
                log_step(f"📖 Bot truy cập bài luyện tập thực hành: {practice_url}...")
                
                try:
                    await page.goto(practice_url, timeout=20000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    log_step(f"ℹ️ Truy cập trang bài luyện tập: {str(e)[:50]}...")
                    
                # Safe Read-Only retrieval via GraphQL
                skill_questions = await fetch_vioedu_skill_practice_questions(
                    skill_id=skill_id,
                    grade=effective_grade,
                    cookies=session_cookies,
                    max_questions=15,
                    log_func=log_step
                )
                if skill_questions:
                    captured_questions_raw.extend(skill_questions)
                    target_exam_name = f"VioEdu Luyện tập - {skill_questions[0].get('skillName') or 'Kỹ năng'} (Lớp {effective_grade})"

            # Case 2: Skill List (Full Curriculum by Grade)
            elif target_info["type"] == "skill_list":
                skill_list_url = f"{VIOEDU_BASE_URL}/skill-list"
                log_step(f"📚 Bot truy cập danh sách kỹ năng: {skill_list_url}...")
                try:
                    await page.goto(skill_list_url, timeout=20000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass
                    
                log_step(f"🔍 Đang truy vấn danh mục các bài luyện tập Khối {effective_grade}...")
                discovered = await fetch_vioedu_skills_in_grade(
                    grade=effective_grade,
                    cookies=session_cookies,
                    log_func=log_step
                )
                log_step(f"📋 Tìm thấy {len(discovered)} bài luyện tập Khối {effective_grade}. Đang cào các bài tiêu biểu...")
                
                for s in discovered[:4]:
                    s_id = s["skill_id"]
                    s_name = s["skill_name"]
                    log_step(f"  👉 Cào bài: {s_name} ({s_id})...")
                    sqs = await fetch_vioedu_skill_practice_questions(
                        skill_id=s_id,
                        grade=effective_grade,
                        cookies=session_cookies,
                        max_questions=8,
                        log_func=log_step
                    )
                    captured_questions_raw.extend(sqs)
                    await asyncio.sleep(0.5)

            # Case 3: Arena Rounds / Matches
            elif target_info["type"] == "arena_round":
                r_id = target_info["round_id"]
                target_exam_name = f"Đấu trường VioEdu Vòng {r_id} - Khối {effective_grade}"
                routes = [
                    f"{VIOEDU_BASE_URL}/arena-zone/{r_id}",
                    f"{VIOEDU_BASE_URL}/arena-hero-battle/{r_id}",
                    f"{VIOEDU_BASE_URL}/arena-school",
                    f"{VIOEDU_BASE_URL}/arena"
                ]
                for route_url in routes:
                    try:
                        log_step(f"🔍 Bot đang truy cập tìm vòng thi tại: {route_url.replace(VIOEDU_BASE_URL, '')}...")
                        await page.goto(route_url, timeout=20000, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2500)
                        
                        # Step through questions if stepper exists
                        nav_buttons = await page.query_selector_all(
                            ".nav-question button, .step-item, .pagination-question button, .list-step > div, button:has-text('Tiếp theo'), button:has-text('Câu sau')"
                        )
                        if nav_buttons:
                            log_step(f"⚡ Phát hiện {len(nav_buttons)} bước/câu hỏi trên giao diện, bot đang tự động duyệt...")
                            for btn in nav_buttons[:20]:
                                try:
                                    await btn.click(timeout=1000)
                                    await page.wait_for_timeout(300)
                                except Exception:
                                    pass
                        if len(captured_questions_raw) >= 20:
                            break
                    except Exception as err:
                        log_step(f"ℹ️ Kiểm tra nhánh {route_url.split('/')[-1]}: {str(err)[:50]}...")

            # Case 4: Auto Mode (Scan active arena first, fallback to skill-practice if closed)
            else:
                routes = [
                    f"{VIOEDU_BASE_URL}/arena",
                    f"{VIOEDU_BASE_URL}/arena-school",
                    f"{VIOEDU_BASE_URL}/arena-zone",
                    f"{VIOEDU_BASE_URL}/student-exam"
                ]
                for route_url in routes:
                    try:
                        log_step(f"🔍 Bot đang tìm vòng thi đang mở tại: {route_url.replace(VIOEDU_BASE_URL, '')}...")
                        await page.goto(route_url, timeout=20000, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2000)
                        if len(captured_questions_raw) >= 15:
                            break
                    except Exception:
                        pass
                        
                # Smart fallback: If outside match hours, auto-fetch skill practices for the student's grade
                if len(captured_questions_raw) < 5:
                    log_step(f"ℹ️ Đấu trường chính thức hiện ngoài khung giờ thi đấu. Bot tự động chuyển sang thu thập bài luyện tập Toán Khối {effective_grade}...")
                    discovered = await fetch_vioedu_skills_in_grade(grade=effective_grade, cookies=session_cookies, log_func=log_step)
                    if discovered:
                        log_step(f"📋 Tìm thấy {len(discovered)} bài thực hành. Bắt đầu thu thập các bài trọng tâm...")
                        for s in discovered[:3]:
                            log_step(f"  👉 Thu thập bài: {s['skill_name']}...")
                            sqs = await fetch_vioedu_skill_practice_questions(
                                skill_id=s["skill_id"],
                                grade=effective_grade,
                                cookies=session_cookies,
                                max_questions=8,
                                log_func=log_step
                            )
                            captured_questions_raw.extend(sqs)
                            await asyncio.sleep(0.4)

            # In-Page DOM Question Extractor (supplementary fallback)
            try:
                dom_extracted = await page.evaluate(f"""() => {{
                    const list = [];
                    const cards = document.querySelectorAll(
                        "div[class*='question'], .question-box, .panel-body-question, .arena-question, [id^='MathjaxArea']"
                    );
                    cards.forEach((card, idx) => {{
                        const stemEl = card.querySelector(".question-text, .panel-body, .math-tex, .stem") || card;
                        const stemHtml = stemEl.innerHTML ? stemEl.innerHTML.trim() : "";
                        const stemText = stemEl.innerText ? stemEl.innerText.trim() : "";
                        if (stemText.length < 8) return;
                        
                        const opts = [];
                        const optNodes = card.querySelectorAll("._2UU-q, .choice-answer-grid-2026 div[role='button'], label[class*='answer'], .answer-item");
                        optNodes.forEach((on, oIdx) => {{
                            const oId = String.fromCharCode(65 + oIdx);
                            const oContent = on.innerText ? on.innerText.trim() : "";
                            if (oContent) opts.push({{ id: oId, content: oContent, is_correct: false }});
                        }});
                        list.push({{
                            id: 'dom_' + Date.now() + '_' + idx,
                            content: stemHtml,
                            question_text: stemText,
                            options: opts,
                            exam_name: '{target_exam_name}',
                            grade: {effective_grade}
                        }});
                    }});
                    return list;
                }}""")
                if dom_extracted and isinstance(dom_extracted, list):
                    captured_questions_raw.extend(dom_extracted)
            except Exception:
                pass
                
            await browser.close()
            log_step("🔒 Đã đóng phiên trình duyệt ngầm.")
            
    except Exception as e:
        log_step(f"⚠️ Ngoại lệ trong tiến trình Bot: {str(e)}", "warn")
        
    # --- Step 4: Normalize, Filter & Save to SQLite Database ---
    log_step(f"🔄 Đang tiến hành làm sạch & chuẩn hóa toàn bộ {len(captured_questions_raw)} dữ liệu thu thập được...")
    
    unique_candidates: Dict[str, Dict[str, Any]] = {}
    for raw_q in captured_questions_raw:
        raw_grade = raw_q.get("grade")
        item_grade = int(raw_grade) if (raw_grade and str(raw_grade).isdigit()) else effective_grade
        item_exam = target_exam_name
        if target_info["type"] == "skill_practice" and raw_q.get("skillName"):
            item_exam = f"VioEdu Luyện tập - {raw_q['skillName']} (Lớp {item_grade})"
            
        parsed = parse_vioedu_question_data(raw_q, exam_name=item_exam, grade=item_grade)
        if parsed:
            parsed["grade"] = item_grade
            key = re.sub(r'\s+', '', parsed["content_text"] or "").lower()[:80]
            if key and key not in unique_candidates:
                unique_candidates[key] = parsed
                
    valid_normalized_list: List[Dict[str, Any]] = []
    for q in unique_candidates.values():
        try:
            norm_q = await normalize_question_payload(q)
            valid, reason = is_valid_question_payload(norm_q)
            if valid:
                valid_normalized_list.append(norm_q)
        except Exception:
            pass
            
    inserted_count = 0
    if valid_normalized_list:
        inserted_count = bulk_insert_questions(valid_normalized_list, skip_duplicates=True)
        log_collector_event(
            platform="vioedu",
            status="success",
            message=f"Bot VioEdu cào thành công: {inserted_count} câu hỏi mới (Khối {effective_grade} - {student_profile.get('fullName') or username})",
            count=inserted_count
        )
        log_step(f"💾 CƠ SỞ DỮ LIỆU: Đã lưu thành công {inserted_count} câu hỏi mới vào Ngân hàng EduQuest Pro!", "success")
    else:
        log_step(f"ℹ️ Đợt quét hoàn tất: Không có câu hỏi mới hoặc câu hỏi đã tồn tại trong CSDL.", "info")
        log_step(f"💡 Gợi ý: Hãy nhập link bài luyện tập (vd: https://vio.edu.vn/skill-practice/...) hoặc mã vòng thi cụ thể.")
        
    log_step(f"🎉 Hoàn thành tiến trình Bot Cào Dữ liệu VioEdu!")
    
    return {
        "success": True,
        "student_name": student_profile.get("fullName") or username,
        "account_grade": effective_grade,
        "total_found": len(valid_normalized_list),
        "inserted_count": inserted_count,
        "exam_name": target_exam_name,
        "logs": live_logs
    }

# -------------------------------------------------------------
# 6. Fetch Arena Questions by ID / Token (Legacy & Direct)
# -------------------------------------------------------------

async def fetch_vioedu_arena_questions(token: str, arena_id: str, grade: int = 5) -> List[Dict[str, Any]]:
    """Direct API retrieval of questions for a specific arena round."""
    url = f"{VIOEDU_BASE_URL}/api/v1/arena/{arena_id}/questions"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw_items = data.get("data", []) or []
                questions = []
                for it in raw_items:
                    parsed = parse_vioedu_question_data(it, exam_name=f"Đấu trường VioEdu #{arena_id}", grade=grade)
                    if parsed:
                        questions.append(parsed)
                return questions
    except Exception as e:
        print(f"Error fetching VioEdu arena questions: {e}")
        
    return []
