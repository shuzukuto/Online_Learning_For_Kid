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


def get_ai_vision_settings() -> Dict[str, Any]:
    """Retrieves current AI Vision settings from system_config and env."""
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
        "openrouter_api_key": openrouter_key,
        "openrouter_model": openrouter_model,
        "openrouter_models": openrouter_models,
        "openrouter_models_available": OPENROUTER_FREE_MODELS,
        "opencode_api_key": opencode_key,
        "opencode_model": opencode_model,
        "opencode_models": opencode_models,
        "opencode_models_available": OPENCODE_MODELS,
        "custom_vision_url": custom_url,
        "custom_vision_key": custom_key,
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
    cfg = get_ai_vision_settings()
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
            if key in ("openrouter_models", "opencode_models", "custom_vision_models"):
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


def _build_vision_prompt() -> str:
    return (
        "Bóc tách toàn bộ các câu hỏi và phương án trắc nghiệm A, B, C, D trong ảnh đề thi thành mảng JSON:\n"
        "[\n"
        "  {\n"
        "    \"question_number\": 1,\n"
        "    \"question_text\": \"Nội dung câu hỏi...\",\n"
        "    \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"],\n"
        "    \"correct_answer\": \"\"\n"
        "  }\n"
        "]\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. Bạn là công cụ OCR đọc chữ. TUYỆT ĐỐI KHÔNG GIẢI TOÁN, KHÔNG TÍNH TOÁN KẾT QUẢ ĐÁP ÁN.\n"
        "2. Để trống correct_answer: \"\" nếu trên ảnh không có dấu tích/khoanh tròn đáp án.\n"
        "3. Xuất ngay mảng JSON bắt đầu bằng [ và kết thúc bằng ]. Giữ nguyên tiếng Việt có dấu."
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
    Ensures model name sent to 9Router has proper provider prefix.
    9Router requires 'openrouter/' prefix for models routed to OpenRouter.
    If '9router' or 'smart-route' is passed, redirects to 'openrouter/dots-studio/dots-3-note-preview:free'
    because 9router default alias forwards to deprecated minimax-m3 (HTTP 410 Gone).
    """
    m = (model or "").strip()
    if not m or m in ("9router", "smart-route"):
        return "openrouter/dots-studio/dots-3-note-preview:free"
    if m.startswith("openrouter/"):
        return m
    if m.startswith("nvidia/nemotron"):
        return f"openrouter/{m}"
    if m.startswith("nvidia/"):
        return m
    return f"openrouter/{m}"


async def call_openai_compatible_vision(
    base_url: str,
    api_key: str,
    model: str,
    image_data_uri: str,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: float = 65.0
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
            return None
    except Exception as e:
        print(f"[call_openai_compatible_vision] Request failed to {endpoint} ({norm_model}): {e}")
        return None

    # Handle 410 Gone (model expired upstream on 9Router)
    if resp and resp.status_code == 410:
        print(f"[call_openai_compatible_vision] ⚠️ Model '{norm_model}' trả về HTTP 410 Gone (mô hình đã hết hạn upstream trên 9Router). Bỏ qua ngay.")
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
            return None

        # Check if provider returned 200 with an error object inside
        if "error" in result_json:
            err_info = result_json.get("error", {})
            err_msg = err_info.get("message", str(err_info)) if isinstance(err_info, dict) else str(err_info)
            print(f"[call_openai_compatible_vision] Upstream error from {endpoint} ({norm_model}): {err_msg}")
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
                return parsed
    elif resp:
        print(f"[call_openai_compatible_vision] Error {resp.status_code} from {endpoint} ({norm_model}): {resp.text[:200]}")

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
                    label = data.get("label", "Key hợp lệ")
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "status_code": 200,
                        "message": f"Kết nối OpenRouter thành công ({latency}ms)! Hạn mức miễn phí: {rem}/{limit} requests/ngày.",
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
                    return False, 410, f"Model '{target_model}' trên 9Router báo 410 (Hết hạn upstream). Vui lòng chọn 'openrouter/dots-studio/dots-3-note-preview:free'.", 0
                elif res.status_code in (401, 403):
                    return False, res.status_code, f"9Router yêu cầu API Key chính xác (HTTP {res.status_code}).", 0
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
        # Prioritize dedicated vision models first, with openrouter/free as a late fallback
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
        if not c_models:
            c_models = [cfg["custom_vision_model"]] if cfg.get("custom_vision_model") else [
                "openrouter/dots-studio/dots-3-note-preview:free",
                "openrouter/google/gemma-4-26b-a4b-it:free",
                "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
            ]
        built = []
        for m in c_models:
            actual_m = _normalize_9router_model_name(m)
            built.append((
                "9Router",
                custom_url,
                cfg.get("custom_vision_key", "").strip(),
                actual_m,
                None
            ))
        # Ensure openrouter/dots-studio/dots-3-note-preview:free is present as a fallback for 9Router
        if not any("dots-3-note-preview" in item[3] for item in built):
            built.append(("9Router", custom_url, cfg.get("custom_vision_key", "").strip(), "openrouter/dots-studio/dots-3-note-preview:free", None))
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
        # Default "auto": If 9Router endpoint is configured, try 9Router first or fallback
        # Given user's setup, if 9router is provided, prioritize 9router then openrouter
        attempts.extend(_build_9router_attempts())
        attempts.extend(_build_openrouter_attempts())
        attempts.extend(_build_opencode_attempts())

    # 3. Execute with automated multi-model fallback chain
    failed_models: List[str] = []
    for idx, (provider_name, base_url, key, model_name, extra_headers) in enumerate(attempts):
        try:
            print(f"[AI Vision] [Model {idx + 1}/{len(attempts)}] Đang thử {provider_name} :: {model_name}...")
            # Local 9Router models (especially reasoning models) need up to 75s to complete
            per_model_timeout = 75.0 if ("20129" in base_url or "9router" in provider_name.lower()) else 32.0
            extracted = await call_openai_compatible_vision(
                base_url=base_url,
                api_key=key,
                model=model_name,
                image_data_uri=image_data_uri,
                extra_headers=extra_headers,
                timeout=per_model_timeout
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
                    options = item.get("options", [])
                    if not isinstance(options, list):
                        options = []
                    options = [str(opt).strip() for opt in options if str(opt).strip()]

                    # If options were embedded in raw_text, separate them
                    if not options and "\n" in q_text:
                        lines = q_text.split("\n")
                        cand_opts = []
                        main_lines = []
                        for ln in lines:
                            ln_s = ln.strip()
                            if re.match(r"^[A-D]\s*[\.\:\)]\s*", ln_s):
                                cand_opts.append(ln_s)
                            else:
                                main_lines.append(ln)
                        if cand_opts:
                            options = cand_opts
                            q_text = "\n".join(main_lines).strip()

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

                if failed_models:
                    engine_label = f"{provider_name}:{model_name} (sau khi {len(failed_models)} model trước lỗi)"
                else:
                    engine_label = f"{provider_name}:{model_name}"

                print(f"[AI Vision] ✅ Thành công với {engine_label}!")
                return normalized_questions, engine_label
            else:
                failed_models.append(f"{model_name}")
                print(f"[AI Vision] ⚠️ Model {provider_name}:{model_name} không trả về kết quả hợp lệ. Tự động chuyển model dự phòng...")
        except Exception as e:
            failed_models.append(f"{model_name}")
            print(f"[AI Vision] ⚠️ Fallback từ {provider_name} ({model_name}) do: {e}")
            continue

    fail_info = f"ai_vision_failed (đã thử qua {len(attempts)} model)"
    return [], fail_info
