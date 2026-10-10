from __future__ import annotations
"""
EduQuest Pro — AI Vision OCR Engine
Direct connections to OpenRouter Free Vision models and OpenCode Zen models,
with automated multi-provider fallback and structured Vietnamese exam parsing.
"""

import os
import io
import re
import json
import base64
import hashlib
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

import httpx
from backend.database import get_system_config, set_system_config
from backend.ai_agent_importer import (
    normalize_options_list,
    normalize_grade,
    normalize_difficulty,
    normalize_subject,
)

# Default Vision models with high accuracy on Vietnamese exams
OPENROUTER_FREE_MODELS = [
    "openrouter/free",
    "dots-studio/dots-3-note-preview:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

OPENCODE_MODELS = [
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "claude-sonnet-4-5",
]

# In-memory LRU/hash cache for vision extractions
_VISION_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_MAX_CACHE_ENTRIES = 100


def _parse_models_list(raw_val: str, default_list: List[str]) -> List[str]:
    """Parses JSON or comma-separated list of models, falling back to default_list."""
    if not raw_val or not raw_val.strip():
        return list(default_list)
    try:
        parsed = json.loads(raw_val)
        if isinstance(parsed, list):
            clean = [str(x).strip() for x in parsed if str(x).strip()]
            if clean:
                return clean
    except Exception:
        pass
    parts = [p.strip() for p in raw_val.split(",") if p.strip()]
    return parts if parts else list(default_list)


def _mask_api_key(key) -> str:
    """Masks an API key for safe API responses (e.g. 'sk-...abcd', '***', '')."""
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= 8:
        return "***"
    return f"{k[:3]}...{k[-4:]}"


def get_ai_vision_settings(include_secrets: bool = False) -> Dict[str, Any]:
    """Retrieves current AI Vision settings from system_config and env.

    include_secrets=False (default): API keys are masked ("sk-...abcd" / "***")
    for safe API responses. Internal callers (vision pipeline) pass True.
    """
    provider = get_system_config("ai_vision_provider", os.getenv("AI_VISION_PROVIDER", "9router_first"))
    openrouter_key = get_system_config("openrouter_api_key", os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model = get_system_config("openrouter_model", os.getenv("OPENROUTER_MODEL", OPENROUTER_FREE_MODELS[0]))
    raw_or_models = get_system_config("openrouter_models", "")
    default_or = [openrouter_model] + [m for m in OPENROUTER_FREE_MODELS if m != openrouter_model]
    openrouter_models = _parse_models_list(raw_or_models, default_or)
    if openrouter_models:
        openrouter_model = openrouter_models[0]
    
    opencode_key = get_system_config("opencode_api_key", os.getenv("OPENCODE_API_KEY", ""))
    opencode_model = get_system_config("opencode_model", os.getenv("OPENCODE_MODEL", OPENCODE_MODELS[0]))
    raw_oc_models = get_system_config("opencode_models", "")
    default_oc = [opencode_model] + [m for m in OPENCODE_MODELS if m != opencode_model]
    opencode_models = _parse_models_list(raw_oc_models, default_oc)
    if opencode_models:
        opencode_model = opencode_models[0]
    
    custom_url = get_system_config("custom_vision_url", os.getenv("CUSTOM_VISION_URL", "http://127.0.0.1:20129/v1"))
    custom_key = get_system_config("custom_vision_key", os.getenv("CUSTOM_VISION_KEY", ""))
    custom_model = get_system_config("custom_vision_model", os.getenv("CUSTOM_VISION_MODEL", "openrouter/dots-studio/dots-3-note-preview:free"))
    raw_custom_models = get_system_config("custom_vision_models", "")
    default_custom = [custom_model] if custom_model else ["openrouter/dots-studio/dots-3-note-preview:free"]
    custom_vision_models = _parse_models_list(raw_custom_models, default_custom)
    if custom_vision_models:
        custom_model = custom_vision_models[0]

    return {
        "provider": provider,
        "openrouter_api_key": openrouter_key if include_secrets else _mask_api_key(openrouter_key),
        "openrouter_model": openrouter_model,
        "openrouter_models": openrouter_models,
        "openrouter_models_available": OPENROUTER_FREE_MODELS,
        "opencode_api_key": opencode_key if include_secrets else _mask_api_key(opencode_key),
        "opencode_model": opencode_model,
        "opencode_models": opencode_models,
        "opencode_models_available": OPENCODE_MODELS,
        "custom_vision_url": custom_url,
        "custom_vision_key": custom_key if include_secrets else _mask_api_key(custom_key),
        "custom_vision_model": custom_model,
        "custom_vision_models": custom_vision_models,
        "has_openrouter": bool(openrouter_key.strip()),
        "has_opencode": bool(opencode_key.strip()),
    }


async def fetch_live_vision_models(provider: str = "openrouter", api_key: str = "", base_url: str = "") -> Dict[str, Any]:
    """
    Scans and discovers currently live multimodal vision models from the provider (OpenRouter / OpenCode / 9Router / Custom).
    Returns list of model objects with id, name, pricing info (free/paid), and context length.
    """
    cfg = get_ai_vision_settings(include_secrets=True)
    key = api_key.strip() or (
        cfg["openrouter_api_key"] if provider == "openrouter" else
        cfg["opencode_api_key"] if provider == "opencode" else
        cfg.get("custom_vision_key", "")
    )
    
    if provider == "openrouter":
        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
                if res.status_code != 200:
                    return {"success": False, "models": [], "error": f"HTTP {res.status_code}: {res.text[:120]}"}
                
                raw_models = res.json().get("data", [])
                vision_models = []
                for m in raw_models:
                    mid = m.get("id", "")
                    arch = m.get("architecture", {}) or {}
                    modality = arch.get("modality", "") or ""
                    input_mods = arch.get("input_modalities", []) or []
                    
                    # Detect vision capability
                    is_vision = (
                        "image" in modality or 
                        "image" in input_mods or 
                        any(term in mid.lower() for term in ["vision", "vl", "pixtral", "omni", "flash-image"])
                    )
                    if not is_vision:
                        continue
                        
                    pricing = m.get("pricing", {}) or {}
                    prompt_price = float(pricing.get("prompt", 0) or 0)
                    is_free = ":free" in mid or prompt_price == 0.0
                    
                    vision_models.append({
                        "id": mid,
                        "name": m.get("name", mid),
                        "is_free": is_free,
                        "context_length": m.get("context_length", 0),
                        "description": m.get("description", "")[:120] if m.get("description") else "",
                        "recommended": is_free and any(term in mid.lower() for term in ["flash", "gemma", "omni", "dots", "qwen", "gemini"])
                    })
                    
                # Sort: Free models first, recommended first
                vision_models.sort(key=lambda x: (not x["is_free"], not x["recommended"], x["id"]))
                
                return {
                    "success": True,
                    "total_found": len(vision_models),
                    "free_count": sum(1 for m in vision_models if m["is_free"]),
                    "models": vision_models
                }
        except Exception as e:
            return {"success": False, "models": [], "error": str(e)}

    elif provider == "opencode":
        # Return known Zen models plus custom configured
        models = [
            {"id": "gemini-3.6-flash", "name": "Google Gemini 3.6 Flash (Zen)", "is_free": False, "recommended": True},
            {"id": "gemini-2.5-flash", "name": "Google Gemini 2.5 Flash (Zen)", "is_free": False, "recommended": True},
            {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5 Vision (Zen)", "is_free": False, "recommended": False},
        ]
        return {"success": True, "total_found": len(models), "free_count": 0, "models": models}

    elif provider in ("custom", "9router"):
        raw_base = base_url.strip() or cfg.get("custom_vision_url") or "http://127.0.0.1:20129/v1"
        base = _resolve_docker_host_url(raw_base).rstrip("/")
        models_url = f"{base}/models"
        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(models_url, headers=headers)
                if res.status_code != 200:
                    return {"success": False, "models": [], "error": f"HTTP {res.status_code}: {res.text[:120]}"}
                
                raw = res.json()
                raw_models = raw.get("data", []) if isinstance(raw, dict) else []
                vision_models = []
                for m in raw_models:
                    if isinstance(m, dict):
                        mid = m.get("id", "")
                    elif isinstance(m, str):
                        mid = m
                    else:
                        continue
                    if not mid:
                        continue
                    
                    is_free = ":free" in mid.lower() or "free" in mid.lower()
                    rec = is_free or any(term in mid.lower() for term in ["vision", "vl", "omni", "dots", "qwen", "gemini", "flash", "9router"])
                    vision_models.append({
                        "id": mid,
                        "name": mid,
                        "is_free": is_free,
                        "context_length": 0,
                        "description": "9Router local / forwarded model",
                        "recommended": rec
                    })
                
                # Sort: free first, recommended first
                vision_models.sort(key=lambda x: (not x["is_free"], not x["recommended"], x["id"]))
                return {
                    "success": True,
                    "total_found": len(vision_models),
                    "free_count": sum(1 for m in vision_models if m["is_free"]),
                    "models": vision_models
                }
        except Exception as e:
            return {"success": False, "models": [], "error": f"Không thể kết nối đến {base}: {str(e)}"}
        
    return {"success": False, "models": [], "error": f"Nền tảng {provider} không được hỗ trợ."}


def save_ai_vision_settings(settings: Dict[str, Any]) -> None:
    """Saves AI Vision configuration to database."""
    allowed_keys = [
        "ai_vision_provider",
        "openrouter_api_key",
        "openrouter_model",
        "openrouter_models",
        "opencode_api_key",
        "opencode_model",
        "opencode_models",
        "custom_vision_url",
        "custom_vision_key",
        "custom_vision_model",
        "custom_vision_models"
    ]
    for key, val in settings.items():
        if key in allowed_keys and val is not None:
            if key in ("openrouter_api_key", "opencode_api_key", "custom_vision_key"):
                # Ignore masked placeholders / empty submissions so the real stored
                # key is never overwritten by "sk-...abcd" or "***" from the UI.
                v = str(val).strip()
                if not v or "..." in v or v == "***":
                    continue
                set_system_config(key, v)
            elif key in ("openrouter_models", "opencode_models", "custom_vision_models"):
                if isinstance(val, list):
                    clean_list = [str(x).strip() for x in val if str(x).strip()]
                    set_system_config(key, json.dumps(clean_list))
                    if clean_list:
                        singular_key = key.replace("_models", "_model")
                        set_system_config(singular_key, clean_list[0])
                elif isinstance(val, str):
                    set_system_config(key, val.strip())
            else:
                set_system_config(key, str(val).strip())


def _prepare_image_payload(image_bytes: bytes) -> str:
    """
    Resizes image if too large (keeps aspect ratio) and returns base64 data URI.
    Optimizes payload size to save network bandwidth and avoid token limits.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Convert RGBA / P mode to RGB
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        max_dim = 2048
        w, h = img.size
        if w > max_dim or h > max_dim:
            ratio = min(max_dim / w, max_dim / h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        # Fallback to direct raw base64
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"


def clean_question_stem(text: str) -> str:
    """Removes question numbering prefixes and header/watermark noise from question stem."""
    if not text:
        return ""
    t = text.strip()
    # Remove leading question numbers like 'WKC 1.', '[ĐVH] 1.', 'Câu 1.', 'Question 1.', '1.'
    t = re.sub(r'^(?:\[?(?:WKC|ĐVH|DVH|TIMO)\]?\s*)?(?:Câu|Question|Problem|Bài|Q)?\s*\d{1,3}\s*[\.:\)\-]\s*', '', t, flags=re.IGNORECASE).strip()
    # Remove any stray header / watermark lines
    lines = [ln for ln in t.splitlines() if not any(w in ln.lower() for w in [
        "tài liệu & lớp học", "wkc mock test", "trẻ thông thái", "0909.698.169", "0985.074.831",
        "thầy đặng việt hùng", "ba mẹ nhắn cô hằng", "nhận video hướng dẫn"
    ])]
    return "\n".join(lines).strip()


def _build_vision_prompt() -> str:
    return (
        "Bạn là Chuyên gia Khảo thí và AI Giảng dạy hàng đầu Việt Nam. "
        "Hãy đọc toàn bộ ảnh đề thi, nhận diện từng câu hỏi, TỰ ĐỘNG GIẢI BÀI TOÁN để xác định đáp án đúng và viết lời giải chi tiết sư phạm.\n\n"
        "Xuất kết quả dưới dạng mảng JSON thuần túy:\n"
        "[\n"
        "  {\n"
        "    \"question_number\": 1,\n"
        "    \"question_text\": \"Nội dung câu hỏi đầy đủ, bao gồm dữ kiện, câu hỏi (giữ nguyên công thức toán, bảo toàn cả tiếng Anh và tiếng Việt nếu là đề song ngữ, không chứa phương án A,B,C,D vào đây)...\",\n"
        "    \"diagram_bbox\": [ymin, xmin, ymax, xmax],\n"
        "    \"options\": [\n"
        "      {\"id\": \"A\", \"content\": \"Nội dung phương án A (không ghi lại chữ 'A.' ở đầu)\"},\n"
        "      {\"id\": \"B\", \"content\": \"Nội dung phương án B (không ghi lại chữ 'B.' ở đầu)\"},\n"
        "      {\"id\": \"C\", \"content\": \"Nội dung phương án C (không ghi lại chữ 'C.' ở đầu)\"},\n"
        "      {\"id\": \"D\", \"content\": \"Nội dung phương án D (không ghi lại chữ 'D.' ở đầu)\"}\n"
        "    ],\n"
        "    \"correct_answer\": \"A\",\n"
        "    \"explanation\": \"Hướng dẫn giải chi tiết từng bước, phù hợp phương pháp sư phạm của khối lớp tương ứng...\",\n"
        "    \"grade\": 2,\n"
        "    \"difficulty\": \"medium\",\n"
        "    \"subject\": \"Toán\",\n"
        "    \"has_handwriting\": false\n"
        "  }\n"
        "]\n\n"
        "QUY TẮC BẮT BUỘC VỀ BÓC TÁCH VÀ CROP HÌNH ẢNH:\n"
        "1. ĐỐI VỚI CÂU HỎI THUẦN CHỮ (Không có hình vẽ/sơ đồ/tranh minh họa, ví dụ bài toán đố tính tuổi, phép tính số học thuần túy):\n"
        "   - BẮT BUỘC gán `diagram_bbox: null`. TUYỆT ĐỐI KHÔNG gán tọa độ toàn bộ trang giấy hay bất kỳ phần chữ nào.\n"
        "2. ĐỐI VỚI CÂU HỎI CÓ HÌNH ẢNH/SƠ ĐỒ MINH HỌA (bắt buộc phải nhìn hình mới làm được bài, như bảng lưới táo, que tính, khối lập phương, đĩa cân, đồng hồ, hình học, đồ thị...):\n"
        "   - Hãy trả về tọa độ hộp bao `diagram_bbox`: [ymin, xmin, ymax, xmax] theo tỷ lệ từ 0 đến 1000 của toàn trang ảnh.\n"
        "   - CẠNH TRÊN (ymin): BẮT BUỘC NẰM NGAY DƯỚI DÒNG CHỮ CÂU HỎI. TUYỆT ĐỐI KHÔNG chứa dòng chữ câu hỏi (cả tiếng Anh lẫn tiếng Việt).\n"
        "   - CẠNH DƯỚI (ymax): PHẢI KÉO DÀI BAO TRÙM HẾT MỌI CHI TIẾT CỦA HÌNH VẼ VÀ TẤT CẢ CÁC NHÃN/CHÚ THÍCH CỦA HÌNH (như dòng nhãn 'Group 1 / Nhóm 1', 'Group 2 / Nhóm 2', 'Group 3 / Nhóm 3' bên dưới mỗi ô hình, hoặc 'Hình 1', 'Hình 2', 'Đĩa A', 'Đĩa B'...). TUYỆT ĐỐI KHÔNG cắt cụt chân hình hoặc bỏ sót nhãn hình vẽ. TUYỆT ĐỐI KHÔNG chạm vào các phương án A, B, C, D bên dưới.\n"
        "   - CẠNH TRÁI (xmin) và CẠNH PHẢI (xmax): Bao trọn vẹn toàn bộ bề ngang của cụm hình minh họa (bao gồm tất cả các nhóm/hình thành phần).\n"
        "3. BÓC TÁCH PHƯƠNG ÁN RÕ RÀNG: Tách rời 4 lựa chọn A, B, C, D vào mảng `options` với `id` và `content`. Nội dung `content` không chứa tiền tố 'A. ', 'B. '.\n"
        "4. GIẢI TOÁN & CHỌN ĐÁP ÁN: Vận dụng tư duy logic để giải ra kết quả chính xác. Gán `correct_answer` là chữ cái đáp án đúng ('A', 'B', 'C', hoặc 'D'). Nếu trên ảnh có khoanh tròn hoặc dấu tích đáp án thì tham khảo, nhưng hãy tự giải để kiểm chứng tính chuẩn xác.\n"
        "5. LỜI GIẢI SƯ PHẠM (explanation): Viết lời giải sư phạm từng bước dễ hiểu theo khối lớp:\n"
        "   - Khối Mầm non (grade: 0) / Lớp 1 (grade: 1): Diễn đạt trực quan, so sánh, đếm đồ vật/hình ảnh cụ thể.\n"
        "   - Khối 2 - 3 (grade: 2, 3): Phân tích quy luật, lập luận logic, các phép tính rõ ràng.\n"
        "6. KHỐI LỚP (grade) & ĐỘ KHÓ (difficulty):\n"
        "   - Gán `grade: 0` nếu là đề Mầm non / Tiền tiểu học; 1 đến 12 cho các lớp tương ứng (LEVEL 1 = 1, LEVEL 2 = 2...).\n"
        "   - `difficulty`: 'easy' (Dễ), 'medium' (Trung bình), 'hard' (Khó), 'olympiad' (Toán tư duy/Olympic TIMO).\n"
        "7. NHẬN DIỆN CHỮ VIẾT TAY (has_handwriting):\n"
        "   - Gán `has_handwriting: true` nếu đề thi có vết chữ viết tay, chữ nháp của học sinh hoặc lời giải viết tay của giáo viên; gán `false` nếu là văn bản in/đánh máy hoàn toàn.\n"
        "   - TUYỆT ĐỐI KHÔNG để chữ nháp hoặc phép tính viết tay của học sinh lọt vào nội dung câu hỏi `question_text`.\n"
        "   - Nếu có lời giải hoặc nhận xét của giáo viên được viết tay, hãy tham khảo chuyển tải tinh thần đó vào trường `explanation`.\n"
        "8. LỌC NHIỄU & CÔNG THỨC TOÁN:\n"
        "   - Bỏ qua watermark, hotline, số điện thoại trung tâm ở đầu/chân trang.\n"
        "   - Sử dụng chuẩn KaTeX cho công thức toán (\\frac{a}{b}, x^2, \\sqrt{x}). Giữ nguyên ký hiệu tiền tệ ($3, $20) không biến thành khối toán.\n"
        "9. ĐỊNH DẠNG ĐẦU RA: Chỉ trả về một JSON array bắt đầu bằng `[` và kết thúc bằng `]`. Giữ nguyên tiếng Việt có dấu đầy đủ."
    )


def _clean_json_response(raw_text: str) -> List[Dict[str, Any]]:
    """Cleans code blocks, markdown wrappers, and extracts json list from model output."""
    if not raw_text or not raw_text.strip():
        return []
    text = raw_text.strip()

    # 1. Search for markdown ```json ... ``` code fence anywhere in text
    fence_matches = re.findall(r"```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```", text, re.DOTALL | re.IGNORECASE)
    for fm in fence_matches:
        try:
            data = json.loads(fm, strict=False)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass

    # 2. Strip leading/trailing markdown fences if whole text is fenced
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # 3. Search for json array bracket [ { ... } ]
    array_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if array_match:
        try:
            data = json.loads(array_match.group(0), strict=False)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass

    # 3b. Recovery for truncated JSON array (if cut off before closing ])
    partial_match = re.search(r"(\[\s*\{.*)", text, re.DOTALL)
    if partial_match:
        cand_str = partial_match.group(1).rstrip()
        last_brace = cand_str.rfind("}")
        if last_brace != -1:
            fixed_cand = cand_str[:last_brace + 1].rstrip().rstrip(",") + "\n]"
            try:
                data = json.loads(fixed_cand, strict=False)
                if isinstance(data, list) and data:
                    return data
            except Exception:
                pass

    # 4. Search for json object { "questions": [...] }
    obj_match = re.search(r"\{\s*\"(?:questions|items|data|exam)\"\s*:\s*\[.*\]\s*\}", text, re.DOTALL)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0), strict=False)
            for k in ["questions", "items", "data", "exam"]:
                if k in data and isinstance(data[k], list):
                    return data[k]
        except Exception:
            pass

    # 5. Direct json.loads fallback
    try:
        data = json.loads(text, strict=False)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            for k in ["questions", "items", "data", "exam"]:
                if k in data and isinstance(data[k], list):
                    return data[k]
            return [data]
    except Exception as e:
        print(f"[_clean_json_response] JSON parse error: {e}. Raw response snippet: {text[:200]}")
    return []


def _is_inside_docker() -> bool:
    """Detects whether current process is running inside a Docker or containerized environment."""
    return (
        os.path.exists("/.dockerenv") or 
        os.path.exists("/run/.containerenv") or 
        os.getenv("DOCKER_CONTAINER") == "1" or 
        os.getenv("RUNNING_IN_DOCKER") == "1" or
        os.getenv("CONTAINER") == "1" or
        (os.path.exists("/proc/1/cgroup") and any(
            x in open("/proc/1/cgroup", "r", errors="ignore").read()
            for x in ["docker", "containerd", "kubepods"]
        ))
    )


def _resolve_docker_host_url(url: str) -> str:
    """
    If running inside Docker container and url points to localhost/127.0.0.1,
    auto-resolves it to host.docker.internal so container can reach host services (like 9Router).
    If running outside Docker on the Windows host and url contains host.docker.internal,
    auto-resolves it to 127.0.0.1 so host tests and services work seamlessly.
    """
    if not url:
        return url
    if _is_inside_docker():
        return re.sub(r"://(?:127\.0\.0\.1|localhost)(:\d+)?", r"://host.docker.internal\1", url)
    else:
        return re.sub(r"://host\.docker\.internal(:\d+)?", r"://127.0.0.1\1", url)


def _normalize_9router_model_name(model: str) -> str:
    """
    Normalizes model names for 9Router local gateway.
    - If empty or generic '9router' / 'smart-route', defaults to 'gemini/gemini-3.7-flash'.
    - If model is a native provider route in 9Router (e.g. starts with 'gemini/', 'ds/', 'nvidia/', 'openai/'):
      kept AS IS without adding 'openrouter/' prefix, so 9Router routes to its native provider.
    - If model already starts with 'openrouter/': kept AS IS.
    - If model starts with an openrouter author (e.g. 'dots-studio/', 'google/gemma', 'thinkingmachines/'):
      prepends 'openrouter/' only if not already prefixed.
    """
    m = (model or "").strip()
    if not m or m in ("9router", "smart-route"):
        return "gemini/gemini-3.7-flash"
    if m.startswith("openrouter/"):
        return m
    if m.startswith("gemini/") or m.startswith("ds/") or m.startswith("openai/"):
        return m
    if m.startswith("nvidia/") and not m.startswith("nvidia/nemotron-3-nano") and not m.startswith("nvidia/nemotron-3.5"):
        return m
    if m.startswith("nvidia/nemotron"):
        return f"openrouter/{m}"
    if any(m.startswith(prefix) for prefix in ["dots-studio/", "google/gemma", "thinkingmachines/", "apodex/", "inclusionai/", "poolside/", "cohere/"]):
        return f"openrouter/{m}"
    return m


async def call_openai_compatible_vision(
    base_url: str,
    api_key: str,
    model: str,
    image_data_uri: str,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: float = 65.0,
    log_collector: Optional[List[str]] = None,
    provider_name: str = "AI Vision"
) -> Optional[List[Dict[str, Any]]]:
    """Generic OpenAI-compatible vision completion caller via httpx."""
    # Normalize model for 9Router if target is 9Router / custom
    norm_model = _normalize_9router_model_name(model) if ("20129" in base_url or "9router" in base_url) else model

    # Auto-resolve Docker host if running in container
    target_base = _resolve_docker_host_url(base_url)
    endpoint = f"{target_base.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": norm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _build_vision_prompt()
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_uri
                        }
                    }
                ]
            }
        ],
        "temperature": 0.0,
        "max_tokens": 8192,
        "stream": False  # Crucial for 9Router and local proxies to return clean application/json
    }

    # Alternate endpoint for bridge failover (between 127.0.0.1 and host.docker.internal)
    if "host.docker.internal" in endpoint:
        alt_endpoint = re.sub(r"://host\.docker\.internal(:\d+)?", r"://127.0.0.1\1", endpoint)
    else:
        alt_endpoint = re.sub(r"://(?:127\.0\.0\.1|localhost)(:\d+)?", r"://host.docker.internal\1", endpoint)

    async def _post_req(url_to_call: str, req_model: str):
        p = dict(payload)
        p["model"] = req_model
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await asyncio.wait_for(client.post(url_to_call, headers=headers, json=p), timeout=timeout)

    def _append_log(msg: str):
        if log_collector is not None:
            log_collector.append(msg)

    resp = None
    try:
        resp = await _post_req(endpoint, norm_model)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        # If localhost/127.0.0.1 failed, try host.docker.internal (Docker bridge on Windows)
        try:
            print(f"[call_openai_compatible_vision] Tự động chuyển hướng tới host Docker bridge: {alt_endpoint}")
            resp = await _post_req(alt_endpoint, norm_model)
        except Exception as alt_e:
            print(f"[call_openai_compatible_vision] Request failed to {endpoint} and {alt_endpoint}: {alt_e}")
            _append_log(f"❌ [{provider_name}] Lỗi kết nối tới {endpoint} và {alt_endpoint}: {str(alt_e)[:100]}")
            return None
    except Exception as e:
        print(f"[call_openai_compatible_vision] Request failed to {endpoint} ({norm_model}): {e}")
        _append_log(f"❌ [{provider_name}] Lỗi gửi yêu cầu tới {endpoint} ({norm_model}): {str(e)[:100]}")
        return None

    # Handle 410 Gone (model expired upstream on 9Router)
    if resp and resp.status_code == 410:
        print(f"[call_openai_compatible_vision] ⚠️ Model '{norm_model}' trả về HTTP 410 Gone (mô hình đã hết hạn upstream trên 9Router). Bỏ qua ngay.")
        _append_log(f"⚠️ [{provider_name}] Model '{norm_model}' trả về HTTP 410 (Mô hình đã hết hạn hỗ trợ trên nhà cung cấp).")
        return None

    # Handle 429 or 503 rate-limit
    if resp and (resp.status_code == 429 or (resp.status_code == 503 and any(k in resp.text.lower() for k in ["429", "rate limit", "free-models-per-day", "exceeded"]))):
        print(f"[call_openai_compatible_vision] ⚠️ Rate limit 429/503 from {endpoint} ({norm_model}): {resp.text[:160]}")
        _append_log(f"⚠️ [{provider_name}] Model '{norm_model}' bị từ chối (HTTP {resp.status_code}): Đã hết hạn mức yêu cầu miễn phí trong ngày (50/50 requests/ngày).")
        return None

    # Handle 404 (missing provider credentials) -> auto-retry with openrouter/ prefix if not prefixed
    if resp and resp.status_code == 404 and not norm_model.startswith("openrouter/"):
        retry_model = f"openrouter/{norm_model}"
        try:
            print(f"[call_openai_compatible_vision] Thử lại với tiền tố '{retry_model}' do 404...")
            resp = await _post_req(endpoint, retry_model)
        except Exception:
            pass

    if resp and resp.status_code == 200:
        result_json = None
        raw_body = resp.text.strip()
        cleaned_body = re.sub(r"data:\s*\[DONE\].*$", "", raw_body, flags=re.DOTALL).strip()
        try:
            result_json = json.loads(cleaned_body, strict=False)
        except Exception:
            brace_match = re.search(r"\{.*\}", cleaned_body, re.DOTALL)
            if brace_match:
                try:
                    result_json = json.loads(brace_match.group(0), strict=False)
                except Exception:
                    pass

        if not result_json:
            # Handle text/event-stream, SSE or chunked/extra JSON lines
            full_content = ""
            full_reasoning = ""
            for line in raw_body.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    continue
                if line.startswith("{") and line.endswith("}"):
                    try:
                        candidate = json.loads(line, strict=False)
                        choices = candidate.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {}) or choices[0].get("delta", {})
                            if msg:
                                full_content += (msg.get("content") or "")
                                full_reasoning += (msg.get("reasoning") or msg.get("reasoning_content") or "")
                    except Exception:
                        pass
            if full_content or full_reasoning:
                result_json = {
                    "choices": [{
                        "message": {
                            "content": full_content,
                            "reasoning": full_reasoning
                        }
                    }]
                }

        if not result_json:
            print(f"[call_openai_compatible_vision] Không thể parse JSON từ {endpoint} ({norm_model}): {raw_body[:160]}")
            _append_log(f"⚠️ [{provider_name}] Phản hồi từ '{norm_model}' không thể đọc cấu trúc JSON.")
            return None

        # Check if provider returned 200 with an error object inside
        if "error" in result_json:
            err_info = result_json.get("error", {})
            err_msg = err_info.get("message", str(err_info)) if isinstance(err_info, dict) else str(err_info)
            print(f"[call_openai_compatible_vision] Upstream error from {endpoint} ({norm_model}): {err_msg}")
            _append_log(f"❌ [{provider_name}] Lỗi upstream từ '{norm_model}': {err_msg[:120]}")
            return None

        choices = result_json.get("choices", [])
        if choices and "message" in choices[0]:
            msg_obj = choices[0]["message"]
            content = (msg_obj.get("content") or "").strip()
            reasoning = (msg_obj.get("reasoning") or msg_obj.get("reasoning_content") or "").strip()

            # 1. Try content
            parsed = _clean_json_response(content) if content else []
            # 2. Try reasoning
            if not parsed and reasoning:
                parsed = _clean_json_response(reasoning)
            # 3. Try combined
            if not parsed and content and reasoning:
                parsed = _clean_json_response(f"{content}\n{reasoning}")

            if parsed:
                _append_log(f"✅ [{provider_name}] Model '{norm_model}' trích xuất thành công {len(parsed)} câu hỏi!")
                return parsed
            else:
                _append_log(f"⚠️ [{provider_name}] Model '{norm_model}' phản hồi nhưng nội dung không chứa câu hỏi hợp lệ.")
    elif resp:
        err_snippet = resp.text[:140].replace('\n', ' ')
        print(f"[call_openai_compatible_vision] Error {resp.status_code} from {endpoint} ({norm_model}): {err_snippet}")
        if resp.status_code in (401, 403):
            _append_log(f"❌ [{provider_name}] Lỗi xác thực HTTP {resp.status_code} với '{norm_model}'. Vui lòng kiểm tra lại API Key.")
        elif resp.status_code == 404:
            _append_log(f"⚠️ [{provider_name}] Model '{norm_model}' không tìm thấy trên server (HTTP 404).")
        else:
            _append_log(f"❌ [{provider_name}] Model '{norm_model}' trả về HTTP {resp.status_code}: {err_snippet}")

    return None


async def test_ai_vision_connection(
    provider: str = "custom",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tests connection to OpenRouter, OpenCode, or custom 9Router gateway.
    Returns status, latency (ms), and friendly diagnostic message.
    """
    import time
    start_t = time.perf_counter()
    provider = (provider or "custom").lower()

    if provider == "openrouter":
        url = "https://openrouter.ai/api/v1/auth/key"
        key = (api_key or "").strip() or get_system_config("openrouter_api_key", "")
        if not key:
            return {"success": False, "message": "Chưa nhập API Key cho OpenRouter."}
        headers = {"Authorization": f"Bearer {key}"}
        try:
            async with httpx.AsyncClient(timeout=7.0) as client:
                res = await client.get(url, headers=headers)
                latency = round((time.perf_counter() - start_t) * 1000)
                if res.status_code == 200:
                    data = res.json().get("data", {})
                    free_quota = data.get("free_model_daily_requests", {})
                    rem = free_quota.get("remaining", "N/A")
                    limit = free_quota.get("limit", "N/A")
                    used = free_quota.get("used", "N/A")
                    label = data.get("label", "Key hợp lệ")
                    if isinstance(rem, (int, float)) and rem <= 0:
                        msg = f"⚠️ Kết nối OpenRouter thành công ({latency}ms) nhưng ĐÃ HẾT HẠN MỨC MIỄN PHÍ TRONG NGÀY ({used}/{limit} lượt đã dùng, còn lại {rem})! Các model :free sẽ bị từ chối 429 cho đến 00:00 UTC."
                    else:
                        msg = f"Kết nối OpenRouter thành công ({latency}ms)! Hạn mức miễn phí: còn {rem}/{limit} requests/ngày (đã dùng {used})."
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "status_code": 200,
                        "message": msg,
                        "details": data
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "status_code": res.status_code,
                        "message": f"OpenRouter trả về lỗi HTTP {res.status_code}: {res.text[:120]}"
                    }
        except Exception as e:
            latency = round((time.perf_counter() - start_t) * 1000)
            return {"success": False, "latency_ms": latency, "message": f"Lỗi kết nối tới OpenRouter: {str(e)}"}

    elif provider == "opencode":
        url = "https://opencode.ai/zen/v1/models"
        key = (api_key or "").strip() or get_system_config("opencode_api_key", "")
        if not key:
            return {"success": False, "message": "Chưa nhập API Key cho OpenCode."}
        headers = {"Authorization": f"Bearer {key}"}
        try:
            async with httpx.AsyncClient(timeout=7.0) as client:
                res = await client.get(url, headers=headers)
                latency = round((time.perf_counter() - start_t) * 1000)
                if res.status_code in (200, 204):
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "status_code": res.status_code,
                        "message": f"Kết nối OpenCode Zen thành công ({latency}ms)!"
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "status_code": res.status_code,
                        "message": f"OpenCode trả về HTTP {res.status_code}: {res.text[:120]}"
                    }
        except Exception as e:
            latency = round((time.perf_counter() - start_t) * 1000)
            return {"success": False, "latency_ms": latency, "message": f"Lỗi kết nối tới OpenCode: {str(e)}"}

    else:
        # Custom 9Router / Local Gateway
        target_url = (base_url or "").strip() or get_system_config("custom_vision_url", "http://127.0.0.1:20129/v1")
        target_key = (api_key or "").strip() or get_system_config("custom_vision_key", "")
        raw_model = (model or "").strip() or get_system_config("custom_vision_model", "openrouter/dots-studio/dots-3-note-preview:free")
        target_model = _normalize_9router_model_name(raw_model)

        headers = {}
        if target_key:
            headers["Authorization"] = f"Bearer {target_key}"

        # Test function supporting auto-retry on host.docker.internal
        async def _test_target(url_to_test: str):
            models_endpoint = f"{url_to_test.rstrip('/')}/models"
            chat_endpoint = f"{url_to_test.rstrip('/')}/chat/completions"
            async with httpx.AsyncClient(timeout=7.0) as client:
                # 1. Try GET /models
                try:
                    res = await client.get(models_endpoint, headers=headers)
                    if res.status_code == 200:
                        m_list = res.json().get("data", [])
                        count = len(m_list) if isinstance(m_list, list) else 0
                        return True, 200, f"Kết nối 9Router ({url_to_test}) thành công! Tìm thấy {count} model.", count
                except Exception:
                    pass

                # 2. Try POST /chat/completions ping
                ping_payload = {
                    "model": target_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                    "stream": False
                }
                res = await client.post(chat_endpoint, headers=headers, json=ping_payload)
                if res.status_code == 200:
                    return True, 200, f"Kết nối và gọi model '{target_model}' trên 9Router ({url_to_test}) thành công!", 1
                elif res.status_code == 410:
                    return False, 410, f"Model '{target_model}' trên 9Router báo 410 (Hết hạn upstream). Vui lòng chọn model khác.", 0
                elif res.status_code in (401, 403):
                    return False, res.status_code, f"9Router yêu cầu API Key chính xác (HTTP {res.status_code}).", 0
                elif res.status_code == 503 and ("429" in res.text or "rate limit" in res.text.lower() or "free-models-per-day" in res.text.lower()):
                    return False, 429, f"9Router kết nối tốt nhưng upstream OpenRouter hết hạn mức miễn phí trong ngày (429 Rate Limit 50/50 requests/ngày).", 0
                else:
                    return False, res.status_code, f"9Router ({url_to_test}) trả về HTTP {res.status_code}: {res.text[:120]}", 0

        # Try connection with Docker host auto-recovery
        resolved_url = _resolve_docker_host_url(target_url)
        if "host.docker.internal" in resolved_url:
            alt_url = re.sub(r"://host\.docker\.internal(:\d+)?", r"://127.0.0.1\1", resolved_url)
        else:
            alt_url = re.sub(r"://(?:127\.0\.0\.1|localhost)(:\d+)?", r"://host.docker.internal\1", resolved_url)

        try:
            ok, status, msg, count = await _test_target(resolved_url)
            latency = round((time.perf_counter() - start_t) * 1000)
            return {"success": ok, "latency_ms": latency, "status_code": status, "message": f"{msg} ({latency}ms)", "models_count": count}
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            try:
                ok, status, msg, count = await _test_target(alt_url)
                latency = round((time.perf_counter() - start_t) * 1000)
                return {
                    "success": ok,
                    "latency_ms": latency,
                    "status_code": status,
                    "message": f"[Docker Bridge] {msg} ({latency}ms).",
                    "models_count": count
                }
            except Exception:
                pass
            latency = round((time.perf_counter() - start_t) * 1000)
            return {
                "success": False,
                "latency_ms": latency,
                "message": f"Không thể kết nối tới {resolved_url} (đã thử cả {alt_url}): {str(e)}"
            }
        except Exception as e:
            latency = round((time.perf_counter() - start_t) * 1000)
            return {"success": False, "latency_ms": latency, "message": f"Lỗi kết nối tới 9Router: {str(e)}"}


async def extract_questions_with_ai_vision(
    image_bytes: bytes,
    filename: str = "exam_image.png",
    media_url: Optional[str] = None,
    log_collector: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Main entry point: tries configured Vision providers with automated fallback.
    Returns: (list_of_normalized_questions, engine_used_name)
    """
    # 1. Check Hash Cache
    img_hash = hashlib.sha256(image_bytes).hexdigest()
    if img_hash in _VISION_CACHE:
        if log_collector is not None:
            log_collector.append("⚡ [AI Vision] Sử dụng kết quả bóc tách từ bộ nhớ đệm (Cache) cho ảnh này.")
        cached_qs = _VISION_CACHE[img_hash]
        result_qs = []
        for q in cached_qs:
            q_copy = dict(q)
            if media_url:
                q_copy["source_image_url"] = media_url
            result_qs.append(q_copy)
        return result_qs, "ai_vision_cache"

    cfg = get_ai_vision_settings(include_secrets=True)
    image_data_uri = _prepare_image_payload(image_bytes)

    active_provider = cfg.get("provider", "9router_first")

    # 2. Build Candidate Execution Order across multi-models
    attempts: List[Tuple[str, str, str, str, Optional[Dict[str, str]]]] = []

    # Helper: Filter out non-vision/safety models
    def _filter_valid_vision_models(models: List[str]) -> List[str]:
        clean = []
        for m in models:
            m_clean = m.strip()
            low = m_clean.lower()
            if any(bad in low for bad in ["content-safety", "safety", "guard", "moderation", "audio", "whisper", "asr"]):
                continue
            clean.append(m_clean)
        priority_order = [
            "dots-studio/dots-3-note-preview:free",
            "google/gemma-4-26b-a4b-it:free",
            "google/gemma-4-31b-it:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "openrouter/free"
        ]
        sorted_m = []
        for p in priority_order:
            for item in clean:
                if (p in item or item in p) and item not in sorted_m:
                    sorted_m.append(item)
        for m in clean:
            if m not in sorted_m:
                sorted_m.append(m)
        return sorted_m if sorted_m else list(OPENROUTER_FREE_MODELS)

    # Helper: Build 9Router attempts
    def _build_9router_attempts():
        custom_url = cfg.get("custom_vision_url", "").strip() or "http://127.0.0.1:20129/v1"
        c_models = cfg.get("custom_vision_models", [])
        
        # Prioritize verified live high-performance vision models
        verified_live = [
            "gemini/gemini-3.8-flash",
            "gemini/gemini-3.5-flash-lite",
            "gemini/gemini-3.1-flash-lite-preview",
            "gemini/gemini-3-flash-preview",
            "gemini/gemini-2.5-flash",
            "gemini/gemini-3.6-flash",
            "nvidia/meta/llama-3.2-11b-vision-instruct"
        ]
        
        all_candidates = list(verified_live)
        if c_models:
            for m in c_models:
                norm_m = _normalize_9router_model_name(m)
                if norm_m not in all_candidates:
                    all_candidates.append(norm_m)

        built = []
        for m in all_candidates:
            built.append((
                "9Router",
                custom_url,
                cfg.get("custom_vision_key", "").strip(),
                m,
                None
            ))
        return built

    # Helper: Build OpenRouter attempts
    def _build_openrouter_attempts():
        or_key = cfg.get("openrouter_api_key", "").strip()
        if not or_key:
            return []
        raw_models = cfg.get("openrouter_models", [])
        if not raw_models:
            raw_models = [cfg["openrouter_model"]] if cfg.get("openrouter_model") else OPENROUTER_FREE_MODELS
        or_models = _filter_valid_vision_models(raw_models)
        built = []
        for m in or_models:
            built.append((
                "OpenRouter",
                "https://openrouter.ai/api/v1",
                or_key,
                m,
                {
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "EduQuest Pro OCR"
                }
            ))
        return built

    # Helper: Build OpenCode attempts
    def _build_opencode_attempts():
        oc_key = cfg.get("opencode_api_key", "").strip()
        if not oc_key:
            return []
        oc_models = cfg.get("opencode_models", [])
        if not oc_models:
            oc_models = [cfg["opencode_model"]] if cfg.get("opencode_model") else OPENCODE_MODELS
        built = []
        for m in oc_models:
            built.append((
                "OpenCode",
                "https://opencode.ai/zen/v1",
                oc_key,
                m,
                None
            ))
        return built

    # Order based on active_provider:
    if active_provider in ("9router", "custom"):
        attempts.extend(_build_9router_attempts())
    elif active_provider == "9router_first":
        attempts.extend(_build_9router_attempts())
        attempts.extend(_build_openrouter_attempts())
        attempts.extend(_build_opencode_attempts())
    elif active_provider == "openrouter":
        attempts.extend(_build_openrouter_attempts())
    elif active_provider == "opencode":
        attempts.extend(_build_opencode_attempts())
    else:
        attempts.extend(_build_9router_attempts())
        attempts.extend(_build_openrouter_attempts())
        attempts.extend(_build_opencode_attempts())

    if log_collector is not None:
        log_collector.append(f"🚀 [AI Vision] Bắt đầu chuỗi phân tích đa tầng (Thử tối đa {len(attempts)} model AI)...")

    # 3. Execute with automated multi-model fallback chain
    failed_models: List[str] = []
    for idx, (provider_name, base_url, key, model_name, extra_headers) in enumerate(attempts):
        try:
            print(f"[AI Vision] [Model {idx + 1}/{len(attempts)}] Đang thử {provider_name} :: {model_name}...")
            if log_collector is not None:
                log_collector.append(f"⏳ [AI Vision] [{idx + 1}/{len(attempts)}] Đang gửi tới {provider_name} ({model_name})...")

            per_model_timeout = 75.0 if ("20129" in base_url or "9router" in provider_name.lower()) else 32.0
            extracted = await call_openai_compatible_vision(
                base_url=base_url,
                api_key=key,
                model=model_name,
                image_data_uri=image_data_uri,
                extra_headers=extra_headers,
                timeout=per_model_timeout,
                log_collector=log_collector,
                provider_name=provider_name
            )
            if extracted:
                normalized_questions = []
                for qidx, item in enumerate(extracted):
                    q_num = item.get("question_number", qidx + 1)
                    q_text = str(
                        item.get("question_text") or
                        item.get("raw_text") or
                        item.get("question") or
                        item.get("content") or
                        item.get("text") or ""
                    ).strip()
                    raw_opts = item.get("options", [])

                    # If options were embedded in raw_text, separate them
                    if (not raw_opts or len(raw_opts) < 2) and "\n" in q_text:
                        lines = q_text.split("\n")
                        cand_opts = []
                        main_lines = []
                        for ln in lines:
                            ln_s = ln.strip()
                            if re.match(r"^\(?[A-D]\)?[\.\:\)\-]\s*", ln_s):
                                cand_opts.append(ln_s)
                            else:
                                main_lines.append(ln)
                        if cand_opts:
                            raw_opts = cand_opts
                            q_text = "\n".join(main_lines).strip()

                    clean_text = clean_question_stem(q_text)
                    if clean_text:
                        q_text = clean_text

                    corr = str(item.get("correct_answer", "")).strip().upper()
                    m_corr = re.search(r'\b([A-D])\b', corr)
                    if m_corr:
                        corr = m_corr.group(1)

                    norm_opts = normalize_options_list(raw_opts, corr)
                    if not corr and norm_opts:
                        for opt in norm_opts:
                            if opt.get("is_correct"):
                                corr = opt["id"]
                                break
                    if not corr and norm_opts:
                        corr = "A"

                    for opt in norm_opts:
                        opt["is_correct"] = (opt["id"] == corr)

                    expl = str(item.get("explanation") or item.get("solution") or item.get("loi_giai") or "").strip()
                    subj = str(item.get("subject", "Toán")).strip()
                    norm_subj = normalize_subject(subj, "math")
                    grade = normalize_grade(item.get("grade"), 5)
                    diff = normalize_difficulty(item.get("difficulty"))

                    diagram_bbox = item.get("diagram_bbox")
                    q_images = []
                    if diagram_bbox and isinstance(diagram_bbox, (list, tuple)) and len(diagram_bbox) == 4:
                        try:
                            from backend.image_cropper import crop_image_bbox
                            cropped_diag = crop_image_bbox(
                                image_bytes,
                                diagram_bbox,
                                padding_pct=0.01,
                                output_prefix=f"crop_diag_q{q_num}",
                                auto_refine=True
                            )
                            if cropped_diag:
                                q_images.append(cropped_diag)
                        except Exception as e:
                            print(f"[AI Vision] Lỗi cắt ảnh minh họa: {e}")

                    q_obj = {
                        "question_number": q_num,
                        "content_text": q_text,
                        "content_html": f"<p>{q_text}</p>",
                        "options": norm_opts,
                        "correct_answer": corr,
                        "explanation": expl,
                        "topic": f"Bóc tách AI Vision ({subj})" if subj else "Bóc tách AI Vision",
                        "grade": grade,
                        "difficulty": diff,
                        "subject": norm_subj,
                        "source_platform": "ai_vision",
                        "source_file_name": filename,
                        "ocr_engine_used": f"{provider_name}:{model_name}",
                        "has_handwriting": bool(item.get("has_handwriting", False)),
                        "images": q_images,
                        "diagram_bbox": diagram_bbox if isinstance(diagram_bbox, (list, tuple)) and len(diagram_bbox) == 4 else None,
                        "source_image_url": media_url or ""
                    }
                    normalized_questions.append(q_obj)

                # Store in Cache
                if len(_VISION_CACHE) >= _MAX_CACHE_ENTRIES:
                    _VISION_CACHE.pop(next(iter(_VISION_CACHE)))
                _VISION_CACHE[img_hash] = normalized_questions

                if failed_models:
                    engine_label = f"{provider_name}:{model_name} (sau khi {len(failed_models)} model trước lỗi)"
                else:
                    engine_label = f"{provider_name}:{model_name}"

                print(f"[AI Vision] ✅ Thành công với {engine_label}!")
                if log_collector is not None:
                    log_collector.append(f"✨ [AI Vision] Bóc tách hoàn tất ({len(normalized_questions)} câu hỏi) bằng {engine_label}!")
                return normalized_questions, engine_label
            else:
                failed_models.append(f"{model_name}")
                print(f"[AI Vision] ⚠️ Model {provider_name}:{model_name} không trả về kết quả hợp lệ. Tự động chuyển model dự phòng...")
                if log_collector is not None and idx < len(attempts) - 1:
                    log_collector.append(f"🔄 [AI Vision] Chuyển tiếp sang model dự phòng [{idx + 2}/{len(attempts)}]...")
        except Exception as e:
            failed_models.append(f"{model_name}")
            print(f"[AI Vision] ⚠️ Fallback từ {provider_name} ({model_name}) do: {e}")
            if log_collector is not None:
                log_collector.append(f"❌ [AI Vision] Ngoại lệ khi gọi {provider_name} ({model_name}): {str(e)[:100]}")
            continue

    if log_collector is not None:
        log_collector.append(f"⚠️ [AI Vision] Toàn bộ {len(attempts)} model AI đều không khả dụng. Tự động chuyển giao sang RapidOCR cục bộ...")
    fail_info = f"ai_vision_failed (đã thử qua {len(attempts)} model)"
    return [], fail_info
