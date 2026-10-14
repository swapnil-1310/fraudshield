"""
MS-EffGCViT-B0 Vision Deepfake Backend
======================================
Implements Multi-Scale Efficient GCViT (EfficientNet-B0 + GCViT Attention) detector.
Trained on FaceForensics++ (Deepfakes, Face2Face, FaceSwap, FaceShifter, NeuralTextures).

Output Semantics:
  - Model forward outputs a single pre-sigmoid logit [B, 1].
  - Calibrated fake probability P(fake) = sigmoid(logit) in [0.0, 1.0].
  - No probability inversion is required (higher score = fake).
"""

import os
import cv2
import numpy as np
import torch
from PIL import Image

from src.stages.backends.base import BaseVisionBackend
from src.stages.backends.deepguard import ms_eff_gcvit_b0


def preprocess_isotropic(img_bgr_or_rgb, target_size=(224, 224), is_bgr=True) -> torch.Tensor:
    """
    Isotropic resize keeping aspect ratio with constant black padding to target_size.
    Applies standard ImageNet mean/std normalization.
    """
    if is_bgr:
        img_rgb = cv2.cvtColor(img_bgr_or_rgb, cv2.COLOR_BGR2RGB)
    else:
        img_rgb = img_bgr_or_rgb

    h, w = img_rgb.shape[:2]
    target_h, target_w = target_size
    scale = min(target_h / h, target_w / w)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    pad_h = target_h - new_h
    pad_w = target_w - new_w
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left

    padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    norm = (padded.astype(np.float32) / 255.0 - mean) / std
    return torch.from_numpy(norm).permute(2, 0, 1).unsqueeze(0).float()


class MsEffGCViTBackend(BaseVisionBackend):
    """
    FaceForensics++ c23 fine-tuned detector:
    - Architecture: MS-EffGCViT-B0 (8.9M params)
    - Output: logit -> sigmoid(logit) = P(fake)
    """

    def __init__(self, weights_path: str = None, model_id: str = "KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus", device: str = "cpu"):
        self._model_id = model_id
        self._device = device
        self._model = None

        if weights_path is not None:
            if not os.path.isfile(weights_path):
                raise FileNotFoundError(f"Checkpoint weights not found: {weights_path}")
        else:
            try:
                from huggingface_hub import hf_hub_download
                weights_path = hf_hub_download(repo_id=model_id, filename="model.safetensors")
            except Exception as ex:
                raise FileNotFoundError(f"Failed to locate or download weights for {model_id}: {ex}")

        if not os.path.isfile(weights_path):
            raise FileNotFoundError(f"Checkpoint weights not found: {weights_path}")

        # Instantiate architecture
        self._model = ms_eff_gcvit_b0(pretrained=False, dataset="ff++")

        # Load weights
        if weights_path.endswith(".safetensors"):
            from safetensors.torch import load_file
            state_dict = load_file(weights_path)
        else:
            state_dict = torch.load(weights_path, map_location="cpu")

        # Strip "model." prefix if loaded from HuggingFace PreTrainedModel wrapper
        clean_sd = {k.replace("model.", ""): v for k, v in state_dict.items() if k.startswith("model.")}
        if not clean_sd:
            clean_sd = state_dict

        self._model.load_state_dict(clean_sd, strict=True)
        self._model.to(device)
        self._model.eval()

    @property
    def backend_name(self) -> str:
        return "ms_eff_gcvit"

    @property
    def model_id(self) -> str:
        return self._model_id

    def predict_frame(self, frame_path_or_img) -> float:
        if isinstance(frame_path_or_img, str):
            if not os.path.exists(frame_path_or_img):
                raise FileNotFoundError(f"Frame not found: {frame_path_or_img}")
            bgr = cv2.imread(frame_path_or_img)
            if bgr is None:
                raise ValueError(f"Could not decode image at {frame_path_or_img}")
            inp = preprocess_isotropic(bgr, is_bgr=True)
        elif isinstance(frame_path_or_img, np.ndarray):
            inp = preprocess_isotropic(frame_path_or_img, is_bgr=True)
        elif isinstance(frame_path_or_img, Image.Image):
            rgb = np.array(frame_path_or_img.convert("RGB"))
            inp = preprocess_isotropic(rgb, is_bgr=False)
        else:
            raise TypeError(f"Unsupported frame type: {type(frame_path_or_img)}")

        inp = inp.to(self._device)
        with torch.no_grad():
            logit = self._model(inp).item()
            prob = torch.sigmoid(torch.tensor(logit)).item()

        return float(max(0.0, min(1.0, prob)))

    def predict_batch(self, frame_paths: list) -> list:
        scores = []
        for fp in frame_paths:
            if not os.path.exists(fp):
                continue
            scores.append(self.predict_frame(fp))
        return scores

    def close(self):
        if self._model is not None:
            del self._model
            self._model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
