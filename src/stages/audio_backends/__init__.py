"""
Audio Deepfake Detector Backends Factory
========================================
Factory for instantiating audio deepfake detection backends.
Supports:
  - "melodymachine": MelodyMachine/Deepfake-Audio-Detection-V2 (Default production model)
  - "wav2vec2_garystafford": garystafford/wav2vec2-deepfake-voice-detector (GitHub Model C)
"""
from typing import Optional

from src.stages.audio_backends.base import (
    BaseAudioBackend,
    check_finfluencer_impersonation,
    KNOWN_FINFLUENCER_NAMES,
)
from src.stages.audio_backends.melodymachine_backend import MelodyMachineAudioBackend
from src.stages.audio_backends.garystafford_backend import GaryStaffordWav2Vec2Backend
from src.config import get_device, get_stage_config, get_audio_detector_config, get_threshold


_BACKEND_CACHE: dict = {}


def clear_audio_backend_cache():
    """Clears the cached audio backend instances (used during testing or reconfiguration)."""
    global _BACKEND_CACHE
    _BACKEND_CACHE.clear()


def get_audio_backend(backend_name: Optional[str] = None, device: Optional[str] = None) -> BaseAudioBackend:
    """
    Instantiates and returns the configured audio deepfake detection backend.
    Caches loaded backends to avoid redundant weights loading across audio scans.
    
    Args:
        backend_name: "melodymachine" or "wav2vec2_garystafford". If None, resolves from config.yaml.
        device: "cpu" or "cuda". If None, resolves from hardware config.
        
    Raises:
        ValueError: If an unrecognized backend name is requested (prevents silent model substitution).
    """
    detector_cfg = get_audio_detector_config()
    stage_cfg = get_stage_config("stage3_audio")

    if backend_name is None:
        backend_name = detector_cfg.get("backend") or stage_cfg.get("backend") or "wav2vec2_garystafford"

    backend_key = str(backend_name).lower().strip()

    if device is None:
        if stage_cfg.get("use_cpu", False):
            device = "cpu"
        else:
            device = get_device()

    cache_key = (backend_key, str(device))
    if cache_key in _BACKEND_CACHE:
        return _BACKEND_CACHE[cache_key]

    threshold = get_threshold("audio_fake_threshold", 0.5)

    if backend_key in ("wav2vec2_garystafford", "garystafford", "model_c", "github", "default"):
        model_id = (
            detector_cfg.get("github_model_id")
            or (detector_cfg.get("model_id") if "garystafford" in str(detector_cfg.get("model_id", "")).lower() else None)
            or (stage_cfg.get("model_id") if "garystafford" in str(stage_cfg.get("model_id", "")).lower() else None)
            or "garystafford/wav2vec2-deepfake-voice-detector"
        )
        revision = detector_cfg.get("github_model_revision") or "c66306024a7ede0be291e9c4558b37634782dc4"
        backend = GaryStaffordWav2Vec2Backend(model_id=model_id, revision=revision, device=device, threshold=threshold)
        _BACKEND_CACHE[cache_key] = backend
        return backend

    elif backend_key in ("melodymachine", "melody"):
        model_id = (
            detector_cfg.get("melodymachine_model_id")
            or (detector_cfg.get("model_id") if "melodymachine" in str(detector_cfg.get("model_id", "")).lower() else None)
            or (stage_cfg.get("model_id") if "melodymachine" in str(stage_cfg.get("model_id", "")).lower() else None)
            or "MelodyMachine/Deepfake-Audio-Detection-V2"
        )
        backend = MelodyMachineAudioBackend(model_id=model_id, device=device, threshold=threshold)
        _BACKEND_CACHE[cache_key] = backend
        return backend

    else:
        raise ValueError(
            f"Unknown audio detector backend: '{backend_name}'. "
            f"Supported backends: 'melodymachine', 'wav2vec2_garystafford'. "
            f"FraudShield will not silently substitute an unconfigured model."
        )


__all__ = [
    "BaseAudioBackend",
    "MelodyMachineAudioBackend",
    "GaryStaffordWav2Vec2Backend",
    "get_audio_backend",
    "check_finfluencer_impersonation",
    "KNOWN_FINFLUENCER_NAMES",
]
