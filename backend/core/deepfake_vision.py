import os
import sys
import numpy as np
import cv2
from PIL import Image
from typing import Dict, Any, List
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

HAS_TRANSFORMERS = False
try:
    import torch
    from transformers import AutoModelForImageClassification, AutoImageProcessor
    HAS_TRANSFORMERS = True
except Exception:
    HAS_TRANSFORMERS = False


class VisualDeepfakeDetector:
    """
    Visual Deepfake Detector adapting Swaraksha's HuggingFace ViT model pipeline with OpenCV fallback.
    """
    def __init__(self, model_name: str = "SadraCoding/SDXL-Deepfake-Detector"):
        self.model_name = model_name
        self.device = "cuda" if HAS_TRANSFORMERS and torch.cuda.is_available() else "cpu"
        self.model = None
        self.processor = None
        self._load_model()

    def _load_model(self):
        if not HAS_TRANSFORMERS:
            print("Note: PyTorch/Transformers not installed. Using OpenCV video artifact analysis.")
            return

        try:
            print(f"[DeepfakeVision] Loading model '{self.model_name}' on {self.device}...")
            self.processor = AutoImageProcessor.from_pretrained(self.model_name)
            self.model = AutoModelForImageClassification.from_pretrained(self.model_name).to(self.device)
            self.model.eval()
            print("[DeepfakeVision] HuggingFace ViT Deepfake model loaded successfully!")
        except Exception as e:
            print(f"[DeepfakeVision] Model load note: {e}. Fallback to video heuristic analyzer.")
            self.model = None

    def analyze_frame(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        """Analyze a single BGR frame for AI generation / manipulation."""
        if frame_bgr is None or frame_bgr.size == 0:
            return {"is_ai": False, "ai_confidence": 0.0}

        # 1. If PyTorch model loaded, use Transformers inference (from Swaraksha)
        if self.model and self.processor:
            try:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                inputs = self.processor(images=pil_img, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

                # Identify AI class index
                ai_idx = 1
                if hasattr(self.model.config, 'id2label'):
                    for idx, label in self.model.config.id2label.items():
                        if any(kw in str(label).lower() for kw in ['fake', 'ai', 'synthetic']):
                            ai_idx = int(idx)
                            break
                ai_conf = float(probs[ai_idx].item()) if ai_idx < len(probs) else float(probs[1].item())
                return {"is_ai": ai_conf >= config.DEEPFAKE_THRESHOLD, "ai_confidence": round(ai_conf, 4)}
            except Exception as e:
                print(f"Transformers frame inference note: {e}")

        # 2. Heuristic video frequency & facial texture analysis fallback
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Exceptionally smooth texture (very low laplacian variance) or extreme compression artifacts
        ai_score = 0.68 if laplacian_var < 80.0 else 0.15
        return {
            "is_ai": ai_score >= config.DEEPFAKE_THRESHOLD,
            "ai_confidence": round(ai_score, 4)
        }

    def analyze_video(self, video_path: str, max_frames: int = 150) -> Dict[str, Any]:
        """
        Extract video frames every N seconds, scan for visual artifacts, and return overall deepfake score.
        (Adapted from Swaraksha video sampling workflow)
        """
        if not os.path.exists(video_path):
            return {"is_deepfake": False, "score": 0.0, "frames_analyzed": 0, "reason": "Video file not found."}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"is_deepfake": False, "score": 0.0, "frames_analyzed": 0, "reason": "Could not open video."}

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        sample_interval = max(1, int(fps * 1.5))  # Sample every 1.5s
        
        frame_idx = 0
        analyzed_count = 0
        ai_confidences = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_interval == 0:
                result = self.analyze_frame(frame)
                ai_confidences.append(result["ai_confidence"])
                analyzed_count += 1
                if analyzed_count >= max_frames:
                    break
            frame_idx += 1

        cap.release()

        if not ai_confidences:
            return {"is_deepfake": False, "score": 0.0, "frames_analyzed": 0, "summary": "No frames extracted."}

        avg_score = float(np.mean(ai_confidences))
        max_score = float(np.max(ai_confidences))
        combined_score = round(0.6 * avg_score + 0.4 * max_score, 4)
        is_deepfake = combined_score >= config.DEEPFAKE_THRESHOLD

        if is_deepfake:
            summary = f"🚨 AI Manipulated / Deepfake Video Detected (Confidence: {combined_score:.1%})"
        else:
            summary = f"✅ Authentic Visual Media (Deepfake Score: {combined_score:.1%})"

        return {
            "is_deepfake": is_deepfake,
            "score": combined_score,
            "frames_analyzed": analyzed_count,
            "summary": summary
        }
