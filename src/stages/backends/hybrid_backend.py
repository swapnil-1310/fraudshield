"""
Hybrid Phase 2 Vision Deepfake Backend
======================================
Implements Dual-Branch Spatial (EfficientNet-B4) + Frequency (Xception SRM) detector.
Outputs P(real); converted to P(fake) via: P(fake) = max(0.0, min(1.0, 1.0 - P(real))).
"""

import os
import cv2
import base64
import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from src.stages.backends.base import BaseVisionBackend
from src.model import HybridDeepfakeDetector


def generate_srm_heatmap_base64(image_path: str, model) -> str:
    """Generates a color-mapped forensic noise residual heatmap using SRM filters."""
    try:
        orig_img = cv2.imread(image_path)
        if orig_img is None:
            return ""

        orig_h, orig_w = orig_img.shape[:2]
        rgb_img = cv2.cvtColor(orig_img, cv2.COLOR_BGR2RGB)
        tensor_img = transforms.ToTensor()(Image.fromarray(rgb_img)).unsqueeze(0)

        device = next(model.parameters()).device
        tensor_img = tensor_img.to(device)

        with torch.no_grad():
            srm_out = model.srm(tensor_img).squeeze(0).cpu().numpy()

        residual_energy = np.mean(np.abs(srm_out), axis=0)
        norm_map = cv2.normalize(residual_energy, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        norm_map = cv2.resize(norm_map, (orig_w, orig_h))
        heatmap = cv2.applyColorMap(norm_map, cv2.COLORMAP_JET)
        blended = cv2.addWeighted(orig_img, 0.6, heatmap, 0.4, 0)

        _, buffer = cv2.imencode('.jpg', blended, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        b64_str = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        print(f"[EXPLAINABILITY] Failed to generate SRM heatmap: {e}")
        return ""


class HybridPhase2Backend(BaseVisionBackend):
    """
    Production baseline deepfake detector:
    - Backbone: EfficientNet-B4 (Spatial) + SRM Xception (Frequency)
    - Output: P(real) -> inverted to P(fake)
    """

    def __init__(self, weights_path: str = None, model_id: str = "AdityaManojShinde/deepfake-detector", device: str = "cpu"):
        self._model_id = model_id
        self._device = device
        self._model = None

        if weights_path is not None:
            if not os.path.isfile(weights_path):
                raise FileNotFoundError(f"Checkpoint weights not found: {weights_path}")
        else:
            try:
                from huggingface_hub import hf_hub_download
                weights_path = hf_hub_download(repo_id=model_id, filename="deepfake_detector_phase2.pth")
            except Exception as ex:
                raise FileNotFoundError(f"Failed to locate or download weights for {model_id}: {ex}")

        if not os.path.isfile(weights_path):
            raise FileNotFoundError(f"Checkpoint weights not found: {weights_path}")

        self._model = HybridDeepfakeDetector()
        state_dict = torch.load(weights_path, map_location=device)
        self._model.load_state_dict(state_dict)
        self._model.to(device)
        self._model.eval()

        self._transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    @property
    def backend_name(self) -> str:
        return "hybrid_phase2"

    @property
    def model_id(self) -> str:
        return self._model_id

    def predict_frame(self, frame_path_or_img) -> float:
        if isinstance(frame_path_or_img, str):
            if not os.path.exists(frame_path_or_img):
                raise FileNotFoundError(f"Frame not found: {frame_path_or_img}")
            img = Image.open(frame_path_or_img).convert("RGB")
        elif isinstance(frame_path_or_img, np.ndarray):
            if frame_path_or_img.shape[-1] == 3:
                img = Image.fromarray(cv2.cvtColor(frame_path_or_img, cv2.COLOR_BGR2RGB))
            else:
                img = Image.fromarray(frame_path_or_img)
        elif isinstance(frame_path_or_img, Image.Image):
            img = frame_path_or_img.convert("RGB")
        else:
            raise TypeError(f"Unsupported frame type: {type(frame_path_or_img)}")

        inp = self._transform(img).unsqueeze(0).to(self._device)
        with torch.no_grad():
            prob_real = self._model(inp).item()
        return float(max(0.0, min(1.0, 1.0 - prob_real)))

    def predict_batch(self, frame_paths: list) -> list:
        scores = []
        for fp in frame_paths:
            if not os.path.exists(fp):
                continue
            scores.append(self.predict_frame(fp))
        return scores

    def generate_heatmap(self, frame_path: str) -> str:
        if self._model is not None and os.path.exists(frame_path):
            return generate_srm_heatmap_base64(frame_path, self._model)
        return ""

    def close(self):
        if self._model is not None:
            del self._model
            self._model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
