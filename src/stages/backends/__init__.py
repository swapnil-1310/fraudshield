"""
Vision Deepfake Detector Backends Factory
==========================================
Factory for instantiating deepfake detection backends.
Supports:
  - "hybrid_phase2": Legacy spatial-frequency detector (EfficientNet-B4 + SRM Xception)
  - "ms_eff_gcvit": MS-EffGCViT-B0 (KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus; pretrained active, fine-tuned baseline supported)
"""

import os
from typing import Optional
from src.stages.backends.base import BaseVisionBackend
from src.stages.backends.hybrid_backend import HybridPhase2Backend
from src.stages.backends.ms_eff_gcvit_backend import MsEffGCViTBackend
from src.config import get_stage_config, get_vision_detector_config, get_device


def get_vision_backend(backend_name: Optional[str] = None, device: Optional[str] = None) -> BaseVisionBackend:
    """
    Instantiates and returns the configured vision deepfake backend.
    
    Args:
        backend_name: "hybrid_phase2" or "ms_eff_gcvit". If None, resolves from config.yaml.
        device: "cpu" or "cuda". If None, resolves from hardware config.
        
    Raises:
        ValueError: If an unrecognized backend name is requested.
        FileNotFoundError: If the configured model weights cannot be loaded.
        (Note: Does NOT silently fall back to an unrequested backend).
    """
    detector_cfg = get_vision_detector_config()
    stage_cfg = get_stage_config("stage2_vision")

    if backend_name is None:
        backend_name = detector_cfg.get("backend") or "hybrid_phase2"

    backend_key = str(backend_name).lower().strip()

    if device is None:
        if stage_cfg.get("use_cpu", False):
            device = "cpu"
        else:
            device = get_device()

    if backend_key in ("hybrid_phase2", "hybrid", "phase2"):
        model_id = detector_cfg.get("model_id") or stage_cfg.get("model_id", "AdityaManojShinde/deepfake-detector")
        weights_file = detector_cfg.get("model_weights_file") or stage_cfg.get("model_weights_file", "deepfake_detector_phase2.pth")
        
        weights_path = None
        if weights_file:
            if os.path.isabs(weights_file) and os.path.isfile(weights_file):
                weights_path = weights_file
            elif os.path.isfile(weights_file):
                weights_path = os.path.abspath(weights_file)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                candidate = os.path.join(base_dir, weights_file)
                if os.path.isfile(candidate):
                    weights_path = candidate

        return HybridPhase2Backend(weights_path=weights_path, model_id=model_id, device=device)

    elif backend_key in ("ms_eff_gcvit", "gcvit", "koreapeter"):
        model_id = detector_cfg.get("model_id", "KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus")
        weights_file = detector_cfg.get("model_weights_file")
        
        weights_path = None
        if weights_file and str(weights_file).strip().lower() not in ("none", "null", ""):
            if os.path.isabs(weights_file) and os.path.isfile(weights_file):
                weights_path = weights_file
            elif os.path.isfile(weights_file):
                weights_path = os.path.abspath(weights_file)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                candidate = os.path.join(base_dir, weights_file)
                if os.path.isfile(candidate):
                    weights_path = candidate
                else:
                    raise FileNotFoundError(
                        f"Configured model_weights_file not found: '{weights_file}'. "
                        f"Looked at '{candidate}'. FraudShield will not silently substitute another checkpoint."
                    )

        return MsEffGCViTBackend(weights_path=weights_path, model_id=model_id, device=device)

    else:
        supported = ["hybrid_phase2", "ms_eff_gcvit"]
        raise ValueError(
            f"Unknown vision detector backend: '{backend_name}'. "
            f"Supported backends are: {supported}. "
            "FraudShield will not silently substitute an unconfigured model."
        )


__all__ = [
    "BaseVisionBackend",
    "HybridPhase2Backend",
    "MsEffGCViTBackend",
    "get_vision_backend"
]
