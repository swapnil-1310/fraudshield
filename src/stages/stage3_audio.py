import os
import gc
import torch
import numpy as np
from typing import Optional

from src.config import get_device, get_stage_config, get_threshold, get_audio_config
from src.stages.audio_backends import get_audio_backend, check_finfluencer_impersonation, KNOWN_FINFLUENCER_NAMES


def run_stage3_audio(
    audio_path: str,
    job_id: str,
    transcript: str = "",
    backend_name: Optional[str] = None
) -> dict:
    """
    Runs audio deepfake detection on the extracted audio with acoustic normalization.
    Processes audio using the configured modular backend (MelodyMachine or GaryStafford Wav2Vec2).
    Returns:
        dict: {
            "avg_score": float,
            "max_score": float,
            "flagged_segments": list[dict], # Suspicious segments only (>0.45)
            "all_segments": list[dict],     # Full continuous timeline chunks for risk scrubber
            "impersonation_check": dict,
            "model_backend": str,
            "model_id": str
        }
    """
    print(f"[{job_id}] Running Stage 3: Audio Deepfake Detection (Modular Backend)")
    result = {
        "avg_score": 0.0,
        "max_score": 0.0,
        "raw_peak_score": 0.0,
        "flagged_segments": [],
        "all_segments": [],
        "impersonation_check": {"is_impersonation": False, "target": None}
    }
    
    if not audio_path or not os.path.exists(audio_path):
        print(f"[{job_id}] No audio track provided. Skipping audio stage.")
        return result
        
    try:
        backend = get_audio_backend(backend_name=backend_name)
        result = backend.process_audio(audio_path, job_id=job_id, transcript=transcript)
        print(
            f"[{job_id}] Audio complete ({result.get('model_backend')}). "
            f"Calibrated Score: {result['max_score']:.4f} (Peak: {result.get('raw_peak_score', result['max_score']):.4f}), "
            f"Chunks: {len(result['all_segments'])}, Impersonation: {result['impersonation_check']['is_impersonation']}"
        )
        return result
    except Exception as e:
        print(f"[{job_id}] Audio stage failed: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
