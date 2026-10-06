from __future__ import annotations
"""
EduQuest Pro — VietOCR ONNX Inference Engine
Based on research from pbcquoc/vietocr and hoaivannguyen/deepdoc_vietocr.
Provides pure ONNX Runtime inference for Vietnamese text recognition without legacy PyTorch/PyPI dependencies.

# To export VietOCR model to ONNX:
# pip install vietocr
# from vietocr.tool.config import Cfg
# from vietocr.tool.predictor import Predictor
# config = Cfg.load_config_from_name('vgg_transformer')
# config['cnn']['pretrained'] = False
# config['device'] = 'cpu'
# detector = Predictor(config)
# ... (torch.onnx.export code)
"""

import os
import io
import unicodedata
import urllib.request
from typing import Optional, List, Dict, Any, Union, Tuple
from PIL import Image, ImageOps

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

    def download_default_model(self) -> bool:
        """
        Downloads the default pre-trained VietOCR ONNX model from a public URL.
        Use this if the user hasn't supplied a custom ONNX file.
        """
        url = "https://example.com/placeholder_vietocr.onnx" # Placeholder URL
        dest_path = os.path.join(MODELS_DIR, "vietocr.onnx")
        try:
            print(f"[VietOcrOnnxEngine] Downloading ONNX model from {url} to {dest_path}...")
            # urllib.request.urlretrieve(url, dest_path)
            # return True
            print("Download function is a placeholder.")
            return False
        except Exception as e:
            print(f"[VietOcrOnnxEngine] Download failed: {e}")
            return False

    def preprocess_line_image(self, img_input: Union[Image.Image, Any], grayscale: bool = False) -> Optional[Any]:
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

            if grayscale:
                img = ImageOps.grayscale(img).convert("RGB")

            w, h = img.size
            new_w = max(int(w * (32.0 / h)), 1)
            # Clip width to max 1024
            new_w = min(new_w, 1024)
            img_resized = img.resize((new_w, 32), Image.Resampling.LANCZOS)
            
            # Pad to at least 32px width if too small
            if new_w < 32:
                pad_width = 32 - new_w
                padded_img = Image.new("RGB", (32, 32), (255, 255, 255))
                padded_img.paste(img_resized, (0, 0))
                img_resized = padded_img
                new_w = 32

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

    def recognize_line(self, line_img: Union[Image.Image, Any], return_confidence: bool = False, grayscale: bool = False) -> Union[str, Tuple[str, float]]:
        """Infers Vietnamese text from a single cropped line image using ONNX session."""
        if not self.is_ready():
            return ("", 0.0) if return_confidence else ""

        tensor = self.preprocess_line_image(line_img, grayscale=grayscale)
        if tensor is None:
            return ("", 0.0) if return_confidence else ""

        try:
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: tensor})
            preds = outputs[0]
            
            confidence = 1.0
            if len(preds.shape) == 3: # (1, seq_len, vocab_size)
                # Softmax across vocab
                probs = np.exp(preds) / np.sum(np.exp(preds), axis=-1, keepdims=True)
                token_ids = np.argmax(preds, axis=-1)[0]
                
                # Calculate confidence
                for i, tid in enumerate(token_ids):
                    if int(tid) == 2: # <eos>
                        break
                    if int(tid) >= 3:
                        confidence *= float(probs[0, i, tid])
                        
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
            norm_text = unicodedata.normalize('NFC', text)
            
            if return_confidence:
                return norm_text, confidence
            return norm_text
        except Exception as e:
            print(f"[VietOcrOnnxEngine.recognize_line] Inference error: {e}")
            return ("", 0.0) if return_confidence else ""

    def recognize_line_beam(self, line_img: Union[Image.Image, Any], beam_width: int = 3, return_confidence: bool = False, grayscale: bool = False) -> Union[str, Tuple[str, float]]:
        """Infers Vietnamese text using beam search decoding."""
        if not self.is_ready():
            return ("", 0.0) if return_confidence else ""

        tensor = self.preprocess_line_image(line_img, grayscale=grayscale)
        if tensor is None:
            return ("", 0.0) if return_confidence else ""

        try:
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: tensor})
            preds = outputs[0]
            
            if len(preds.shape) != 3:
                return self.recognize_line(line_img, return_confidence=return_confidence, grayscale=grayscale)
                
            probs = np.exp(preds) / np.sum(np.exp(preds), axis=-1, keepdims=True)
            seq_len = probs.shape[1]
            vocab_size = probs.shape[2]
            
            sequences = [(1.0, [])]
            
            for step in range(seq_len):
                all_candidates = list()
                for seq_score, seq_tokens in sequences:
                    if len(seq_tokens) > 0 and seq_tokens[-1] == 2:
                        all_candidates.append((seq_score, seq_tokens))
                        continue
                        
                    for v in range(vocab_size):
                        prob = probs[0, step, v]
                        candidate_score = seq_score * float(prob)
                        candidate_tokens = seq_tokens + [v]
                        all_candidates.append((candidate_score, candidate_tokens))
                        
                ordered = sorted(all_candidates, key=lambda tup: tup[0], reverse=True)
                sequences = ordered[:beam_width]
                
            best_score, best_tokens = sequences[0]
            
            chars = []
            for tid in best_tokens:
                if tid == 2:
                    break
                if tid in self.idx2char and tid >= 3:
                    chars.append(self.idx2char[tid])
                    
            text = "".join(chars).strip()
            norm_text = unicodedata.normalize('NFC', text)
            
            if return_confidence:
                return norm_text, best_score
            return norm_text
            
        except Exception as e:
            print(f"[VietOcrOnnxEngine.recognize_line_beam] Inference error: {e}")
            return ("", 0.0) if return_confidence else ""

    def recognize_lines_batch(self, line_imgs: List[Union[Image.Image, Any]], grayscale: bool = False) -> List[str]:
        """Processes multiple line images in a batch for efficiency."""
        if not self.is_ready() or not line_imgs:
            return []
            
        tensors = []
        valid_indices = []
        for i, img in enumerate(line_imgs):
            tensor = self.preprocess_line_image(img, grayscale=grayscale)
            if tensor is not None:
                tensors.append(tensor)
                valid_indices.append(i)
                
        if not tensors:
            return ["" for _ in line_imgs]
            
        max_w = max(t.shape[3] for t in tensors)
        batch_tensors = []
        for t in tensors:
            _, _, h, w = t.shape
            if w < max_w:
                pad_width = max_w - w
                t_padded = np.pad(t, ((0,0), (0,0), (0,0), (0, pad_width)), mode='constant', constant_values=0)
                batch_tensors.append(t_padded)
            else:
                batch_tensors.append(t)
                
        batch_array = np.concatenate(batch_tensors, axis=0)
        
        try:
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: batch_array})
            preds = outputs[0]
            
            batch_texts = []
            if len(preds.shape) == 3: # (batch, seq_len, vocab_size)
                token_ids_batch = np.argmax(preds, axis=-1)
            elif len(preds.shape) == 2: # (batch, seq_len)
                token_ids_batch = preds
            else:
                token_ids_batch = [[] for _ in range(len(batch_tensors))]
                
            for token_ids in token_ids_batch:
                chars = []
                for tid in token_ids:
                    tid = int(tid)
                    if tid == 2:
                        break
                    if tid in self.idx2char and tid >= 3:
                        chars.append(self.idx2char[tid])
                text = "".join(chars).strip()
                batch_texts.append(unicodedata.normalize('NFC', text))
                
            results = ["" for _ in line_imgs]
            for i, valid_idx in enumerate(valid_indices):
                results[valid_idx] = batch_texts[i]
                
            return results
        except Exception as e:
            print(f"[VietOcrOnnxEngine.recognize_lines_batch] Inference error: {e}")
            return ["" for _ in line_imgs]

def get_vietocr_engine() -> VietOcrOnnxEngine:
    return VietOcrOnnxEngine.get_instance()
