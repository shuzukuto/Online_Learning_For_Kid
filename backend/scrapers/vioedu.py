import httpx
import re
import uuid
from typing import List, Dict, Any, Optional

VIOEDU_BASE_URL = "https://vio.edu.vn"

async def login_vioedu(username: str, password: str) -> Dict[str, Any]:
    """
    Attempts to authenticate with VioEdu API across current known endpoints.
    Provides clear fallback guidance if Cloudflare/Captcha prevents headless login.
    """
    candidate_urls = [
        "https://api.vio.edu.vn/api/v1/users/login",
        "https://api.vio.edu.vn/api/v2/auth/login",
        "https://api.vio.edu.vn/v1/auth/login",
        "https://vio.edu.vn/api/v1/auth/login",
        "https://vio.edu.vn/api/v1/user/login"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": "https://vio.edu.vn/login",
        "Origin": "https://vio.edu.vn"
    }
    payload = {
        "username": username,
        "password": password
    }
    
    last_error = ""
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for url in candidate_urls:
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        token = data.get("data", {}).get("token") or data.get("token")
                        if token:
                            return {"success": True, "token": token, "data": data}
                    elif resp.status_code in [401, 403]:
                        last_error = "Tài khoản hoặc mật khẩu không chính xác, hoặc cần xác thực Captcha."
                    else:
                        last_error = f"Máy chủ VioEdu phản hồi HTTP {resp.status_code}"
                except Exception as inner_e:
                    last_error = str(inner_e)
                    
        return {
            "success": False,
            "error": f"VioEdu áp dụng bảo mật Captcha/Cloudflare ({last_error}). Vui lòng đăng nhập trên trình duyệt Chrome/Edge và sử dụng Tiện ích EduQuest Collector để tự động thu thập 100% đề thi an toàn."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def parse_vioedu_question_data(item: Dict[str, Any], exam_name: str = "VioEdu Luyện tập", grade: int = 5) -> Dict[str, Any]:
    """
    Parses VioEdu JSON payload into EduQuest standard question schema.
    VioEdu returns fields like:
    - content / question_content
    - answers / options
    - right_answer / correct_answer
    - explanation
    """
    raw_content = item.get("content") or item.get("question_content") or item.get("title") or ""
    raw_exp = item.get("explanation") or item.get("guide") or ""
    
    # Process options
    raw_options = item.get("answers") or item.get("options") or []
    options = []
    correct_ans = item.get("right_answer") or item.get("correct_answer")
    
    if isinstance(raw_options, list):
        for idx, opt in enumerate(raw_options):
            opt_id = chr(65 + idx)  # A, B, C, D
            opt_content = ""
            is_correct = False
            
            if isinstance(opt, dict):
                opt_content = opt.get("content") or opt.get("text") or ""
                if opt.get("is_correct") or opt.get("correct"):
                    is_correct = True
                    correct_ans = opt_id
            elif isinstance(opt, str):
                opt_content = opt
                
            options.append({
                "id": opt_id,
                "content": opt_content,
                "is_correct": is_correct
            })
            
    # Normalize images
    images = []
    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_content)
    for src in img_matches:
        if src not in images:
            images.append(src)
            
    # Determine question type
    q_type = "single_choice"
    if not options or len(options) == 0:
        q_type = "fill_blank"
    elif item.get("type") in ["match", "matching", "pair"]:
        q_type = "matching"
        
    topic = item.get("skill_name") or item.get("topic") or "Toán học VioEdu"
    
    return {
        "id": f"vioedu_{item.get('id') or uuid.uuid4().hex[:8]}",
        "source_platform": "vioedu",
        "source_url": "https://vio.edu.vn",
        "exam_name": exam_name,
        "grade": grade,
        "subject": "math",
        "topic": topic,
        "question_type": q_type,
        "content_html": raw_content,
        "content_text": re.sub(r'<[^>]+>', '', raw_content),
        "images": images,
        "options": options,
        "correct_answer": str(correct_ans) if correct_ans else "A",
        "explanation": raw_exp,
        "difficulty": item.get("level") or "medium"
    }

async def fetch_vioedu_arena_questions(token: str, arena_id: str, grade: int = 5) -> List[Dict[str, Any]]:
    """
    Fetches questions from an active/past VioEdu arena.
    """
    url = f"{VIOEDU_BASE_URL}/api/v1/arena/{arena_id}/questions"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw_items = data.get("data", []) or []
                return [parse_vioedu_question_data(it, exam_name=f"Đấu trường VioEdu #{arena_id}", grade=grade) for it in raw_items]
    except Exception as e:
        print(f"Error fetching VioEdu arena questions: {e}")
        
    return []
