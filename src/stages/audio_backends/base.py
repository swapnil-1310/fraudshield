"""
Base Audio Deepfake Detection Backend
======================================
Defines the abstract interface for all audio deepfake detectors in FraudShield.
Handles:
  - Acoustic normalization (DC offset removal + peak scaling)
  - Silence detection (RMS threshold check to prevent false positives and zero division)
  - Chunking for arbitrary-length audio files (including clips > 10 seconds)
  - Short clip safe padding
  - Robust exception handling for unreadable or corrupted audio
  - Calibrated consensus blending and timeline generation
"""
import os
import gc
import abc
import numpy as np
import librosa
import torch
from typing import Optional, List, Dict, Any

from src.config import get_threshold, get_audio_config

KNOWN_FINFLUENCER_NAMES = [
    "nithin kamath", "nikhil kamath", "ankur warikoo", "radhakishan damani",
    "jhunjhunwala", "akshat shrivastava", "rachana ranade", "pranjal kamra",
    "sunil singhania", "saurabh mukherjea", "vijay kedia", "porinju veliyath"
]

def check_finfluencer_impersonation(transcript: str, max_audio_fake_score: float) -> dict:
    """
    Checks if a high-profile financial personality is named in the transcript
    combined with an elevated synthetic audio score, indicating a voice clone impersonation scam.
    Threshold read from config: thresholds.impersonation_audio_threshold
    """
    impersonation_thresh = get_threshold("impersonation_audio_threshold", 0.45)
    if not transcript:
        return {"is_impersonation": False, "target": None}
        
    t_lower = transcript.lower()
    for name in KNOWN_FINFLUENCER_NAMES:
        if name in t_lower:
            if max_audio_fake_score > impersonation_thresh:
                return {
                    "is_impersonation": True,
                    "target": name.title(),
                    "warning": f"Potential AI Voice Clone Impersonation of '{name.title()}' (Voice Spoof Confidence: {max_audio_fake_score*100:.1f}%)"
                }
            else:
                return {
                    "is_impersonation": False,
                    "target": name.title(),
                    "warning": None
                }
    return {"is_impersonation": False, "target": None}


class BaseAudioBackend(abc.ABC):
    """Abstract Base Class for audio deepfake detection backends."""

    def __init__(self, name: str, model_id: str, device: str = "cpu", threshold: float = 0.5):
        self.name = name
        self.model_id = model_id
        self.device = device
        self.threshold = threshold

    @abc.abstractmethod
    def predict_chunk(self, chunk: np.ndarray, sample_rate: int = 16000) -> float:
        """
        Runs model inference on a single audio chunk (1D float32 numpy array).
        Returns:
            float: Synthetic/spoof probability strictly clamped between 0.0 and 1.0.
        """
        raise NotImplementedError

    def process_audio(
        self,
        audio_path: str,
        job_id: str = "audio-job",
        transcript: str = "",
        chunk_duration: Optional[float] = None,
        consensus_weight: Optional[float] = None,
        consensus_min_chunks: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Processes full audio recording through chunking, acoustic normalization,
        inference, and consensus scoring.
        Handles clips longer than 10 seconds, short clips, silent clips, and malformed files safely.
        """
        audio_cfg = get_audio_config()
        if chunk_duration is None:
            chunk_duration = float(audio_cfg.get("chunk_duration_seconds", 5.0))
        if consensus_weight is None:
            consensus_weight = float(audio_cfg.get("consensus_top_weight", 0.65))
        if consensus_min_chunks is None:
            consensus_min_chunks = int(audio_cfg.get("consensus_min_chunks", 2))

        segment_flag_thresh = get_threshold("audio_segment_flag_threshold", 0.45)
        target_sr = 16000

        result: Dict[str, Any] = {
            "avg_score": 0.0,
            "max_score": 0.0,
            "raw_peak_score": 0.0,
            "flagged_segments": [],
            "all_segments": [],
            "impersonation_check": {"is_impersonation": False, "target": None},
            "model_backend": self.name,
            "model_id": self.model_id,
            "revision": getattr(self, "revision", None),
        }

        if not audio_path or not os.path.exists(audio_path):
            print(f"[{job_id}] [{self.name}] Audio path missing or does not exist: {audio_path}")
            result["status"] = "error"
            result["error"] = "File not found"
            return result

        # 1. Safe audio decoding
        try:
            audio, sr = librosa.load(audio_path, sr=target_sr)
        except Exception as load_exc:
            print(f"[{job_id}] [{self.name}] Failed to decode audio file ({audio_path}): {load_exc}")
            result["status"] = "error"
            result["error"] = f"Decoding failed: {load_exc}"
            return result

        audio = np.asarray(audio, dtype=np.float32)

        # 2. Silence & Energy check (RMS < 0.001 or peak < 1e-5)
        rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) > 0 else 0.0
        if len(audio) == 0 or rms < 0.001 or np.max(np.abs(audio)) < 1e-5:
            print(f"[{job_id}] [{self.name}] Audio is silent (RMS={rms:.6f}). Returning 0.0 spoof score.")
            result["is_silent"] = True
            result["impersonation_check"] = check_finfluencer_impersonation(transcript, 0.0)
            return result

        # 3. Acoustic Normalization (DC offset removal + Peak scaling)
        audio = audio - np.mean(audio)
        peak = float(np.max(np.abs(audio)))
        if peak > 0:
            audio = audio / peak

        # 4. Chunking: Handles recordings of any length (including > 10 seconds)
        chunk_samples = int(chunk_duration * target_sr)
        scores: List[float] = []
        max_s = 0.0

        for i in range(0, len(audio), chunk_samples):
            chunk = audio[i:i + chunk_samples]
            # Safe zero-padding for trailing short chunk under 1 second
            if len(chunk) < target_sr:
                chunk = np.pad(chunk, (0, target_sr - len(chunk)), "constant")

            try:
                prob = self.predict_chunk(chunk, sample_rate=target_sr)
                prob = max(0.0, min(1.0, float(prob)))
            except Exception as inf_exc:
                print(f"[{job_id}] [{self.name}] Inference failed on chunk at sample {i}: {inf_exc}")
                prob = 0.0

            scores.append(prob)
            start_time = round(i / target_sr, 2)
            end_time = round((i + len(chunk)) / target_sr, 2)

            segment_info = {
                "start": start_time,
                "end": end_time,
                "score": round(prob, 4),
            }
            result["all_segments"].append(segment_info)

            if prob > segment_flag_thresh:
                result["flagged_segments"].append(segment_info)

            if prob > max_s:
                max_s = prob

        # 5. Consensus Scoring & Output assembly
        if scores:
            scores_sorted = sorted(scores, reverse=True)
            k = min(2, len(scores_sorted))
            top_k_mean = float(np.mean(scores_sorted[:k]))
            anti_weight = round(1.0 - consensus_weight, 4)
            consensus_audio = (
                float(consensus_weight * top_k_mean + anti_weight * max_s)
                if len(scores) >= consensus_min_chunks
                else float(max_s)
            )

            result["avg_score"] = round(float(np.mean(scores)), 4)
            result["max_score"] = round(consensus_audio, 4)
            result["raw_peak_score"] = round(float(max_s), 4)

        result["impersonation_check"] = check_finfluencer_impersonation(transcript, result["max_score"])
        return result
