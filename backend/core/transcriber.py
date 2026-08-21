import os
import sys
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

try:
    from groq import Groq
    if config.GROQ_API_KEY:
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
        HAS_GROQ = True
    else:
        HAS_GROQ = False
except Exception:
    HAS_GROQ = False

def transcribe_audio_file(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe audio file into text using Groq Whisper-Large-V3 (SOTA).
    """
    if not audio_path or not os.path.exists(audio_path):
        return {
            "transcript": "",
            "success": False,
            "engine": "none",
            "message": "Audio file not available."
        }

    # Try Groq API for state-of-the-art transcription
    if HAS_GROQ and config.GROQ_API_KEY:
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
            
            # Whisper sometimes hallucinates silence as 'Thank you for watching' or 'Amara.org'
            hallucinations = ["Thank you.", "Thank you", "Subscribe to the channel", "Amara.org", "you"]
            if transcript_text in hallucinations or len(transcript_text) < 2:
                transcript_text = ""

            return {
                "transcript": transcript_text,
                "success": True,
                "engine": "whisper-large-v3",
                "message": "Transcription completed via Groq Whisper API"
            }
        except Exception as e:
            print(f"Groq audio upload note: {e}")

    # Fallback if API fails or no key
    return {
        "transcript": "",
        "success": False,
        "engine": "fallback",
        "message": "Transcription unavailable or failed."
    }
