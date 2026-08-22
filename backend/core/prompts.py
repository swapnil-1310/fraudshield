"""
Centralized Prompts Registry for FraudShield-SEBI Pro
"""

SEBI_OFFLINE_ENGINE_DESCRIPTION = "Layer 1 Structural Pre-scan (Regex) and Layer 1.5 TF-IDF Keyword Density Scorer for offline SEBI compliance checking."

GEMINI_SEBI_DIRECTOR_PROMPT = """
You are Dr. Ananya Sharma, a highly experienced Director at the Securities and Exchange Board of India (SEBI).
Your task is to analyze financial transcripts and chats for subtle, manipulative "Pump and Dump" schemes, guaranteed returns, or unregistered financial advice.
Perform a Deep Chain-of-Thought reasoning to catch psychological manipulation designed to trick retail investors.
Be strict but fair. Output a detailed forensic report.
"""

EASYOCR_ENGINE_DESCRIPTION = "GPU-accelerated EasyOCR combined with image-level heuristics (compression, edge density, color palette) for offline screenshot analysis."

WHISPER_MODEL_DESCRIPTION = "Local faster-whisper medium model (769M params) running on GPU with FP16 for audio transcription, with Voice Activity Detection (VAD)."

GEMINI_VISION_DEEPFAKE_PROMPT = """
Analyze the provided video keyframes. Look for synthetic face artifacts, robotic lip sync, unnatural skin smoothing, inconsistent lighting, or physical AI watermarks (like Synthesia or HeyGen logos).
Determine if the video is a deepfake or authentic. Provide your confidence score and reasons.
"""

GEMINI_SCREENSHOT_SCANNER_PROMPT = """
Analyze the provided screenshot of a trading application or financial chat. 
Look for spoofed domain names, fake UI elements, scam broker app designs, guaranteed returns, or unregistered advisory claims.
Determine if this is a scam or a legitimate platform.
"""

def get_all_prompts():
    return {
        "SEBI_OFFLINE_ENGINE_DESCRIPTION": SEBI_OFFLINE_ENGINE_DESCRIPTION,
        "GEMINI_SEBI_DIRECTOR_PROMPT": GEMINI_SEBI_DIRECTOR_PROMPT,
        "EASYOCR_ENGINE_DESCRIPTION": EASYOCR_ENGINE_DESCRIPTION,
        "WHISPER_MODEL_DESCRIPTION": WHISPER_MODEL_DESCRIPTION,
        "GEMINI_VISION_DEEPFAKE_PROMPT": GEMINI_VISION_DEEPFAKE_PROMPT,
        "GEMINI_SCREENSHOT_SCANNER_PROMPT": GEMINI_SCREENSHOT_SCANNER_PROMPT
    }
