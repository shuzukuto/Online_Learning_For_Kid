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
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image

import httpx

from backend.database import get_system_config, set_system_config

# Default Vision models with high accuracy on Vietnamese exams
OPENROUTER_FREE_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "dots-studio/dots-3-note-preview:free",
    "thinkingmachines/inkling-small:free",
    "thinkingmachines/inkling:free",
]

OPENCODE_MODELS = [
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "claude-sonnet-4-5",
]

# In-memory LRU/hash cache for vision extractions
_VISION_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_MAX_CACHE_ENTRIES = 100


def get_ai_vision_settings() -> Dict[str, Any]:
    """Retrieves current AI Vision settings from system_config and env."""
    provider = get_system_config("ai_vision_provider", os.getenv("AI_VISION_PROVIDER", "auto"))
    openrouter_key = get_system_config("openrouter_api_key", os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model = get_system_config("openrouter_model", os.getenv("OPENROUTER_MODEL", OPENROUTER_FREE_MODELS[0]))
    
    opencode_key = get_system_config("opencode_api_key", os.getenv("OPENCODE_API_KEY", ""))
    opencode_model = get_system_config("opencode_model", os.getenv("OPENCODE_MODEL", OPENCODE_MODELS[0]))
    
    custom_url = get_system_config("custom_vision_url", os.getenv("CUSTOM_VISION_URL", "http://localhost:20128/v1"))
    custom_key = get_system_config("custom_vision_key", os.getenv("CUSTOM_VISION_KEY", ""))
    custom_model = get_system_config("custom_vision_model", os.getenv("CUSTOM_VISION_MODEL", "opencode/free"))

    return {
        "provider": provider,
        "openrouter_api_key": openrouter_key,
        "openrouter_model": openrouter_model,
        "openrouter_models_available": OPENROUTER_FREE_MODELS,
        "opencode_api_key": opencode_key,
        "opencode_model": opencode_model,
        "opencode_models_available": OPENCODE_MODELS,
        "custom_vision_url": custom_url,
        "custom_vision_key": custom_key,
        "custom_vision_model": custom_model,
        "has_openrouter": bool(openrouter_key.strip()),
        "has_opencode": bool(opencode_key.strip()),
    }


async def fetch_live_vision_models(provider: str = "openrouter", api_key: str = "") -> Dict[str, Any]:
    """
    Scans and discovers currently live multimodal vision models from the provider (OpenRouter / OpenCode).
    Returns list of model objects with id, name, pricing info (free/paid), and context length.
    """
    cfg = get_ai_vision_settings()
    key = api_key.strip() or (cfg["openrouter_api_key"] if provider == "openrouter" else cfg["opencode_api_key"])
    
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
        
    return {"success": False, "models": [], "error": f"Nền tảng {provider} không được hỗ trợ."}


def save_ai_vision_settings(settings: Dict[str, Any]) -> None:
    """Saves AI Vision configuration to database."""
    allowed_keys = [
        "ai_vision_provider",
        "openrouter_api_key",
        "openrouter_model",
        "opencode_api_key",
        "opencode_model",
        "custom_vision_url",
        "custom_vision_key",
        "custom_vision_model"
    ]
    for key, val in settings.items():
        if key in allowed_keys and val is not None:
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


def _build_vision_prompt() -> str:
    return (
        "Bạn là chuyên gia số hoá và bóc tách đề thi học sinh (Tiểu học & THCS) tại Việt Nam.\n"
        "Nhiệm vụ: Hãy phân tích kỹ hình ảnh đề thi được cung cấp và trích xuất TOÀN BỘ các câu hỏi vào định dạng JSON hợp lệ.\n\n"
        "CÁC QUY TẮC BẮT BUỘC:\n"
        "1. Trích xuất chính xác 100% tiếng Việt có đầy đủ dấu câu, tuyệt đối không làm mất dấu hay sai chính tả.\n"
        "2. Nếu câu hỏi có chứa công thức toán hoặc biểu thức, hãy viết dưới dạng LaTeX chuẩn (ví dụ: $1/2$, $\\frac{a}{b}$, $x^2$).\n"
        "3. Với câu hỏi trắc nghiệm:\n"
        "   - 'options': mảng các lựa chọn (ví dụ: ['A. 15', 'B. 20', 'C. 25', 'D. 30']).\n"
        "   - 'correct_answer': Tự động nhận diện đáp án đúng nếu trong ảnh có dấu hiệu trực quan (được tô màu xanh lá cây, có dấu tick xanh ✓, được khoanh tròn hoặc gạch chân). Nếu không thấy dấu hiệu, để rỗng \"\".\n"
        "4. Với câu hỏi tự luận / điền số:\n"
        "   - 'options': [] (để mảng rỗng)\n"
        "   - 'correct_answer': điền đáp số nếu ảnh có ghi kèm.\n"
        "5. Bỏ qua hoàn toàn các chi tiết rác giao diện chụp màn hình điện thoại: thanh pin, wifi, đồng hồ, logo không liên quan, điểm số góc màn hình.\n"
        "6. Trả về DUY NHẤT một mảng JSON với cấu trúc sau:\n"
        "[\n"
        "  {\n"
        "    \"question_number\": 1,\n"
        "    \"question_text\": \"Nội dung câu hỏi...\",\n"
        "    \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"],\n"
        "    \"correct_answer\": \"A\",\n"
        "    \"explanation\": \"Giải thích lời giải nếu có (hoặc để rỗng)\",\n"
        "    \"subject\": \"Toán\" (hoặc Tiếng Việt, Tiếng Anh, Khoa học...)\n"
        "  }\n"
        "]\n"
        "CHỈ TRẢ VỀ JSON THUẦN TÚY, KHÔNG KÈM GIẢI THÍCH THÊM NGOÀI KHỐI JSON."
    )


def _clean_json_response(raw_text: str) -> List[Dict[str, Any]]:
    """Cleans code blocks and extracts json list from model output."""
    text = raw_text.strip()
    # Strip markdown ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Search for json array bracket if wrapped with conversational filler
    array_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if array_match:
        text = array_match.group(0)

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Sometimes model wraps list in {"questions": [...]}
            for k in ["questions", "items", "data", "exam"]:
                if k in data and isinstance(data[k], list):
                    return data[k]
            return [data]
    except Exception as e:
        print(f"[_clean_json_response] JSON parse error: {e}. Raw response snippet: {text[:200]}")
    return []


async def call_openai_compatible_vision(
    base_url: str,
    api_key: str,
    model: str,
    image_data_uri: str,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: float = 45.0
) -> Optional[List[Dict[str, Any]]]:
    """Generic OpenAI-compatible vision completion caller via httpx."""
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": model,
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
        "temperature": 0.1,
        "max_tokens": 4096
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code == 200:
                result_json = resp.json()
                choices = result_json.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    parsed = _clean_json_response(content)
                    if parsed:
                        return parsed
            else:
                print(f"[call_openai_compatible_vision] Error {resp.status_code} from {endpoint} ({model}): {resp.text[:200]}")
        except Exception as e:
            print(f"[call_openai_compatible_vision] Request failed to {endpoint} ({model}): {e}")
            
    return None


async def extract_questions_with_ai_vision(
    image_bytes: bytes,
    filename: str = "exam_image.png",
    media_url: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Main entry point: tries configured Vision providers with automated fallback.
    Returns: (list_of_normalized_questions, engine_used_name)
    """
    # 1. Check Hash Cache
    img_hash = hashlib.sha256(image_bytes).hexdigest()
    if img_hash in _VISION_CACHE:
        return _VISION_CACHE[img_hash], "ai_vision_cache"

    cfg = get_ai_vision_settings()
    image_data_uri = _prepare_image_payload(image_bytes)

    # 2. Build Candidate Execution Order
    attempts: List[Tuple[str, str, str, str, Optional[Dict[str, str]]]] = []
    
    # Provider 1: OpenRouter (Direct)
    or_key = cfg["openrouter_api_key"]
    if or_key:
        or_models = [cfg["openrouter_model"]] + [m for m in OPENROUTER_FREE_MODELS if m != cfg["openrouter_model"]]
        for m in or_models:
            attempts.append((
                "openrouter",
                "https://openrouter.ai/api/v1",
                or_key,
                m,
                {
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "EduQuest Pro OCR"
                }
            ))

    # Provider 2: OpenCode Zen (Direct)
    oc_key = cfg["opencode_api_key"]
    if oc_key:
        oc_models = [cfg["opencode_model"]] + [m for m in OPENCODE_MODELS if m != cfg["opencode_model"]]
        for m in oc_models:
            attempts.append((
                "opencode",
                "https://opencode.ai/zen/v1",
                oc_key,
                m,
                None
            ))

    # Provider 3: Custom / Local endpoint (e.g. 9Router or Ollama if configured)
    custom_url = cfg["custom_vision_url"]
    custom_model = cfg["custom_vision_model"]
    if custom_url and cfg.get("provider") in ("custom", "auto"):
        attempts.append((
            "custom_gateway",
            custom_url,
            cfg["custom_vision_key"],
            custom_model,
            None
        ))

    # 3. Execute with automated fallback
    for provider_name, base_url, key, model_name, extra_headers in attempts:
        try:
            extracted = await call_openai_compatible_vision(
                base_url=base_url,
                api_key=key,
                model=model_name,
                image_data_uri=image_data_uri,
                extra_headers=extra_headers,
                timeout=40.0
            )
            if extracted:
                normalized_questions = []
                for idx, item in enumerate(extracted):
                    q_num = item.get("question_number", idx + 1)
                    q_text = str(item.get("question_text", "")).strip()
                    options = item.get("options", [])
                    if not isinstance(options, list):
                        options = []
                    options = [str(opt).strip() for opt in options if str(opt).strip()]

                    corr = str(item.get("correct_answer", "")).strip()
                    expl = str(item.get("explanation", "")).strip()
                    subj = str(item.get("subject", "Toán")).strip()

                    q_obj = {
                        "question_number": q_num,
                        "content_text": q_text,
                        "options": options,
                        "correct_answer": corr,
                        "explanation": expl,
                        "topic": f"Bóc tách AI Vision ({subj})" if subj else "Bóc tách AI Vision",
                        "grade": 1,
                        "difficulty": "medium",
                        "source_platform": "ai_vision",
                        "source_file_name": filename,
                        "ocr_engine_used": f"{provider_name}:{model_name}",
                        "images": [media_url] if media_url else []
                    }
                    normalized_questions.append(q_obj)

                # Store in Cache
                if len(_VISION_CACHE) >= _MAX_CACHE_ENTRIES:
                    _VISION_CACHE.pop(next(iter(_VISION_CACHE)))
                _VISION_CACHE[img_hash] = normalized_questions

                return normalized_questions, f"{provider_name}:{model_name}"
        except Exception as e:
            print(f"[extract_questions_with_ai_vision] Fallback from {provider_name} ({model_name}) due to: {e}")
            continue

    return [], "ai_vision_failed"
