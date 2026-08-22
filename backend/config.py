import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"
STORAGE_DIR = BASE_DIR / "storage"
TEMP_DIR = STORAGE_DIR / "temp"
LOCAL_MODELS_DIR = BASE_DIR / "models"

# Ensure directories exist
DB_DIR.mkdir(exist_ok=True, parents=True)
STORAGE_DIR.mkdir(exist_ok=True, parents=True)
TEMP_DIR.mkdir(exist_ok=True, parents=True)
LOCAL_MODELS_DIR.mkdir(exist_ok=True, parents=True)

# API Keys (optional — system works fully offline without these)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")

# ── Local Model Preferences ─────────────────────────────────────────────────
# When True, prioritize local GPU models over API calls
PREFER_LOCAL = True

# Whisper model size: "small" (fast, ~244M) or "medium" (accurate, ~769M)
WHISPER_MODEL_SIZE = "medium"

# Deepfake ViT model from HuggingFace (auto-downloaded on first run)
DEEPFAKE_MODEL_NAME = "SadraCoding/SDXL-Deepfake-Detector"

# Detection Thresholds
DEEPFAKE_THRESHOLD = 0.65  # 65%+ confidence flags as AI generated
SEBI_RISK_THRESHOLD = 0.60  # 60%+ risk score flags as SEBI Violation

# Database Path
SQLITE_DB_PATH = DB_DIR / "fraudshield.db"
ADVISOR_JSON_PATH = DB_DIR / "sebi_advisors.json"
