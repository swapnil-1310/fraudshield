"""
FraudShield-SEBI Pro — Audio Transcription Engine v2 (Local GPU-First)
======================================================================
Local-first architecture using faster-whisper on RTX 3050 GPU.
Falls back to Groq API if local model is unavailable.

Model Architecture documented in: core/prompts.py → WHISPER_MODEL_DESCRIPTION
"""

import os
import sys
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

# ── Groq API client (optional fallback) ──────────────────────────────────────
HAS_GROQ = False
_groq_client = None

try:
    from groq import Groq
    if config.GROQ_API_KEY:
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
        HAS_GROQ = True
except Exception:
    HAS_GROQ = False

# ── Local Whisper model (cached singleton) ───────────────────────────────────
_local_whisper_model = None


def _get_local_whisper():
    """
    Load faster-whisper model on GPU (cached singleton).
    Uses config.WHISPER_MODEL_SIZE (default: "medium") for better Hindi/English accuracy.
    Runs on CUDA with FP16 on RTX 3050.
    """
    global _local_whisper_model
    
    if _local_whisper_model is not None:
        return _local_whisper_model
    
    try:
        from faster_whisper import WhisperModel
        import torch
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        model_size = config.WHISPER_MODEL_SIZE  # "medium" by default
        
        print(f"[Transcriber] Loading local faster-whisper '{model_size}' on {device} ({compute_type})...")
        _local_whisper_model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )
        print(f"[Transcriber] ✅ Whisper '{model_size}' loaded on {device}.")
        return _local_whisper_model
    except ImportError:
        print("[Transcriber] faster-whisper is not installed.")
        return None
    except Exception as e:
        print(f"[Transcriber] Failed to load local Whisper model: {e}")
        return None


# Known Whisper hallucination patterns (silence interpreted as speech)
HALLUCINATION_PATTERNS = [
    "Thank you.", "Thank you", "Thanks for watching.",
    "Subscribe to the channel", "Amara.org", "you",
    "Please subscribe.", "Like and subscribe.",
    "Thank you for watching.", "Bye.",
    "MBC 뉴스", "ご視聴ありがとうございました",
    "字幕は自動生成されました", "Sous-titres",
]


def _is_hallucination(text: str) -> bool:
    """Check if transcribed text is a known Whisper hallucination."""
    text_stripped = text.strip()
    if len(text_stripped) < 3:
        return True
    if text_stripped in HALLUCINATION_PATTERNS:
        return True
    # Repetition detection: same short phrase repeated many times
    words = text_stripped.split()
    if len(words) > 5:
        unique = set(words)
        if len(unique) <= 2:
            return True
    return False


def _transcribe_local(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe audio using local faster-whisper model on GPU.
    Uses VAD (Voice Activity Detection) to skip silence and reduce hallucinations.
    """
    model = _get_local_whisper()
    if model is None:
        return {"transcript": "", "success": False, "engine": "none",
                "message": "Local Whisper model not available."}
    
    try:
        print(f"[Transcriber] Transcribing with local Whisper ({config.WHISPER_MODEL_SIZE})...")
        
        # Use VAD filter to skip silence segments — reduces hallucinations significantly
        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,  # Silence threshold
                speech_pad_ms=200,            # Padding around speech
            )
        )
        
        transcript_text = " ".join([segment.text for segment in segments]).strip()
        
        if _is_hallucination(transcript_text):
            transcript_text = ""
        
        engine_name = f"faster-whisper-{config.WHISPER_MODEL_SIZE}-local"
        import torch
        if torch.cuda.is_available():
            engine_name += "-gpu"
        
        return {
            "transcript": transcript_text,
            "success": True,
            "engine": engine_name,
            "language": getattr(info, "language", "unknown"),
            "language_probability": round(getattr(info, "language_probability", 0.0), 2),
            "message": f"Transcription completed via local faster-whisper ({config.WHISPER_MODEL_SIZE}) on GPU"
        }
    except Exception as e:
        print(f"[Transcriber] Local whisper error: {e}")
        return {"transcript": "", "success": False, "engine": "local_error",
                "message": f"Local transcription failed: {str(e)}"}


def _transcribe_groq(audio_path: str) -> Dict[str, Any]:
    """Transcribe audio using Groq Whisper API (cloud fallback)."""
    if not HAS_GROQ or not config.GROQ_API_KEY:
        return {"transcript": "", "success": False, "engine": "none",
                "message": "Groq API not available."}
    
    try:
        print(f"[Transcriber] Uploading audio to Groq Whisper: {audio_path}...")
        with open(audio_path, "rb") as file:
            transcription = _groq_client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                temperature=0.0
            )
        
        transcript_text = transcription.text.strip()
        
        if _is_hallucination(transcript_text):
            transcript_text = ""

        return {
            "transcript": transcript_text,
            "success": True,
            "engine": "whisper-large-v3-groq",
            "message": "Transcription completed via Groq Whisper API"
        }
    except Exception as e:
        print(f"[Transcriber] Groq API error: {e}")
        return {"transcript": "", "success": False, "engine": "groq_error",
                "message": f"Groq transcription failed: {str(e)}"}


def transcribe_audio_file(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe audio file into text.
    
    Priority (when PREFER_LOCAL = True):
      1. Local faster-whisper on GPU (RTX 3050, FP16)
      2. Groq Whisper API (cloud fallback)
    
    Priority (when PREFER_LOCAL = False):
      1. Groq Whisper API (cloud, fastest)
      2. Local faster-whisper on GPU (fallback)
    """
    if not audio_path or not os.path.exists(audio_path):
        return {
            "transcript": "",
            "success": False,
            "engine": "none",
            "message": "Audio file not available."
        }

    if config.PREFER_LOCAL:
        # LOCAL FIRST: Try GPU Whisper, no cloud API fallback in offline mode
        result = _transcribe_local(audio_path)
        if result["success"] and result["transcript"]:
            return result
        
        # If local fails, return error rather than leaking to API
        return {
            "transcript": "",
            "success": False,
            "engine": "local_error",
            "message": "Local transcription failed and API fallback is disabled."
        }
    else:
        # API FIRST: Try Groq, then local
        result = _transcribe_groq(audio_path)
        if result["success"] and result["transcript"]:
            return result
        
        # Fallback to local
        result = _transcribe_local(audio_path)
        if result["success"]:
            return result

    return {
        "transcript": "",
        "success": False,
        "engine": "fallback",
        "message": "All transcription methods failed."
    }
