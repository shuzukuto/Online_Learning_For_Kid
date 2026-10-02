"""
EduQuest Pro — VietOCR ONNX Inference Engine
Based on research from pbcquoc/vietocr and hoaivannguyen/deepdoc_vietocr.
Provides pure ONNX Runtime inference for Vietnamese text recognition without legacy PyTorch/PyPI dependencies.
"""

import os
import io
import unicodedata
from typing import Optional, List, Dict, Any, Union
from PIL import Image

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import onnxruntime as ort
except ImportError:
    ort = None

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

DEFAULT_MODEL_CANDIDATES = [
    os.path.join(MODELS_DIR, "vietocr_onnx.onnx"),
    os.path.join(MODELS_DIR, "vietocr.onnx"),
    os.path.join(MODELS_DIR, "seq2seq.onnx"),
    os.path.join(MODELS_DIR, "transformerocr.onnx")
]

# Vietnamese character vocabulary from standard VietOCR
VIETNAMESE_VOCAB = (
    "aAàÀảẢãÃáÁạẠăĂằẰẳẲẵẴắẮặẶâÂầẦẩẨẫẪấẤậẬbBcCdDđĐeEèÈẻẺẽẼéÉẹẸêÊềỀểỂễỄếẾệỆfFgGhHiIìÌỉỈĩĨíÍịỊ"
    "jJkKlLmMnNoOòÒỏỎõÕóÓọỌôÔồỒổỔỗỖốỐộỘơƠờỜởỞỡỠớỚợỢpPqQrRsStTuUùÙủỦũŨúÚụỤưƯừỪửỬữỮứỨựỰvVwWxX"
    "yYỳỲỷỶỹỸýÝỵỴzZ0123456789!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ "
)

class VietOcrOnnxEngine:
    _instance = None

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.getenv("VIETOCR_ONNX_PATH")
        if not self.model_path:
            for cand in DEFAULT_MODEL_CANDIDATES:
                if os.path.exists(cand):
                    self.model_path = cand
                    break
        
        self.session = None
        self.vocab = list(VIETNAMESE_VOCAB)
        self.char2idx = {c: i + 3 for i, c in enumerate(self.vocab)}
        self.idx2char = {i + 3: c for i, c in enumerate(self.vocab)}
        self.idx2char[0] = "<pad>"
        self.idx2char[1] = "<sos>"
        self.idx2char[2] = "<eos>"
        
        self._init_session()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_session(self):
        if ort is None or not self.model_path or not os.path.exists(self.model_path):
            self.session = None
            return
        try:
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(self.model_path, opts, providers=["CPUExecutionProvider"])
        except Exception as e:
            print(f"[VietOcrOnnxEngine] Session init error: {e}")
            self.session = None

    def is_ready(self) -> bool:
        """Returns True if onnxruntime is available and model weights are successfully loaded."""
        return self.session is not None

    def get_status(self) -> Dict[str, Any]:
        """Provides status details for UI and health checking."""
        ready = self.is_ready()
        return {
            "engine": "vietocr_onnx",
            "name": "VietOCR ONNX DeepDoc Engine",
            "ready": ready,
            "model_path": self.model_path if (self.model_path and os.path.exists(self.model_path)) else None,
            "models_dir": MODELS_DIR,
            "onnxruntime_version": ort.__version__ if ort else None,
            "fallback_available": True,
            "fallback_engine": "RapidOCR + Transformer Grammar Post-processing",
            "message": "VietOCR ONNX Engine đã sẵn sàng tải trọng số suy luận." if ready else (
                "Chưa có tệp trọng số vietocr.onnx trong thư mục data/models/. "
                "Hệ thống sẽ chạy ở chế độ Siêu tốc (RapidOCR) kết hợp Bộ sửa lỗi Ngữ nghĩa Transformer."
            )
        }

    def preprocess_line_image(self, img_input: Union[Image.Image, Any]) -> Optional[Any]:
        """Resizes line image to fixed height 32, preserving aspect ratio and normalizing pixel values."""
        if np is None:
            return None
        try:
            if isinstance(img_input, Image.Image):
                img = img_input.convert("RGB")
            elif isinstance(img_input, np.ndarray):
                if len(img_input.shape) == 2:
                    img = Image.fromarray(img_input).convert("RGB")
                else:
                    img = Image.fromarray(cv2.cvtColor(img_input, cv2.COLOR_BGR2RGB))
            else:
                return None

            w, h = img.size
            new_w = max(int(w * (32.0 / h)), 32)
            # Clip width to max 1024
            new_w = min(new_w, 1024)
            img_resized = img.resize((new_w, 32), Image.Resampling.BILINEAR)

            arr = np.array(img_resized, dtype=np.float32) / 255.0
            # Normalize with ImageNet standard mean & std
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            arr = (arr - mean) / std

            # Transpose HWC -> CHW and add batch dimension -> (1, 3, 32, W)
            arr = np.transpose(arr, (2, 0, 1))
            arr = np.expand_dims(arr, axis=0)
            return arr.astype(np.float32)
        except Exception as e:
            print(f"[VietOcrOnnxEngine.preprocess_line_image] Error: {e}")
            return None

    def recognize_line(self, line_img: Union[Image.Image, Any]) -> str:
        """Infers Vietnamese text from a single cropped line image using ONNX session."""
        if not self.is_ready():
            return ""

        tensor = self.preprocess_line_image(line_img)
        if tensor is None:
            return ""

        try:
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: tensor})
            # Outputs usually have logits or token indices
            preds = outputs[0]
            if len(preds.shape) == 3: # (1, seq_len, vocab_size)
                token_ids = np.argmax(preds, axis=-1)[0]
            elif len(preds.shape) == 2: # (1, seq_len)
                token_ids = preds[0]
            else:
                token_ids = []

            chars = []
            for tid in token_ids:
                tid = int(tid)
                if tid == 2: # <eos>
                    break
                if tid in self.idx2char and tid >= 3:
                    chars.append(self.idx2char[tid])

            text = "".join(chars).strip()
            return unicodedata.normalize('NFC', text)
        except Exception as e:
            print(f"[VietOcrOnnxEngine.recognize_line] Inference error: {e}")
            return ""

def get_vietocr_engine() -> VietOcrOnnxEngine:
    return VietOcrOnnxEngine.get_instance()
