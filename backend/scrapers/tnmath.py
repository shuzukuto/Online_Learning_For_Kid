import httpx
import re
import uuid
import json
from typing import List, Dict, Any, Optional

TNMATH_BASE_URL = "https://tnmath.edu.vn"

async def login_tnmath(username: str, password: str) -> Dict[str, Any]:
    """
    Login endpoint for Trạng Nguyên Toán Học.
    """
    login_url = f"{TNMATH_BASE_URL}/api/user/login"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Referer": "https://tnmath.edu.vn"
    }
    payload = {
        "username": username,
        "password": password
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(login_url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token") or data.get("data", {}).get("token")
                return {"success": True, "token": token, "data": data}
            else:
                return {"success": False, "error": f"Lỗi đăng nhập Trạng Nguyên: HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def parse_tnmath_question_data(item: Dict[str, Any], exam_name: str = "Trạng Nguyên Toán Học", grade: int = 5) -> Dict[str, Any]:
    """
    Parses a Trạng Nguyên question.
    Handles types:
    - multiple choice (10 câu trắc nghiệm)
    - fill in (Chuột vàng điền số)
    - matching (Mèo con ghép cặp)
    """
    raw_content = item.get("content") or item.get("question") or item.get("title") or ""
    q_type_raw = str(item.get("type", "")).lower()
    
    q_type = "single_choice"
    options = []
    correct_ans = item.get("answer") or item.get("correct_answer")
    
    if "match" in q_type_raw or "pair" in q_type_raw:
        q_type = "matching"
        pairs = item.get("pairs") or item.get("options") or []
        options = []
        for idx, p in enumerate(pairs):
            if isinstance(p, dict):
                options.append({
                    "id": f"pair_{idx+1}",
                    "content": f"{p.get('left', '')} ↔ {p.get('right', '')}",
                    "is_correct": True
                })
    elif "fill" in q_type_raw or "blank" in q_type_raw:
        q_type = "fill_blank"
    else:
        # Standard choice options
        raw_opts = item.get("options") or item.get("answers") or []
        for idx, opt in enumerate(raw_opts):
            opt_id = chr(65 + idx)
            opt_val = opt if isinstance(opt, str) else opt.get("content", "")
            is_c = False
            if str(correct_ans).strip().upper() == opt_id or str(correct_ans).strip() == str(opt_val).strip():
                is_c = True
            options.append({
                "id": opt_id,
                "content": opt_val,
                "is_correct": is_c
            })
            
    images = []
    img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw_content)
    for src in img_matches:
        if src not in images:
            images.append(src)
    if item.get("image"):
        images.append(item.get("image"))
        
    return {
        "id": f"tnmath_{item.get('id') or uuid.uuid4().hex[:8]}",
        "source_platform": "tnmath",
        "source_url": "https://tnmath.edu.vn",
        "exam_name": exam_name,
        "grade": grade,
        "subject": "math",
        "topic": item.get("topic") or "Trạng Nguyên Toán",
        "question_type": q_type,
        "content_html": raw_content,
        "content_text": re.sub(r'<[^>]+>', '', raw_content),
        "images": images,
        "options": options,
        "correct_answer": str(correct_ans) if correct_ans else "A",
        "explanation": item.get("explanation") or "",
        "difficulty": item.get("level") or "medium"
    }
