import yaml
import os
from dotenv import load_dotenv

# Load environment variables from .env
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

# Ensure HF_TOKEN is propagated to HuggingFace Hub environment
if os.getenv("HF_TOKEN"):
    os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Global config object
settings = load_config()

# Helper accessors
def get_device():
    if settings.get("hardware", {}).get("force_cpu", False):
        return "cpu"
    dev = settings.get("hardware", {}).get("device", "cuda")
    if dev == "cuda":
        try:
            import torch
            if not torch.cuda.is_available():
                return "cpu"
        except Exception:
            return "cpu"
    return dev

def get_vision_detector_config() -> dict:
    return settings.get("vision_detector", {})

def get_vision_threshold() -> float:
    det_cfg = get_vision_detector_config()
    if "threshold" in det_cfg and det_cfg["threshold"] is not None:
        return float(det_cfg["threshold"])
    return get_threshold("vision_fake_threshold", 0.5)

def get_threshold(key: str, default: float = 0.5) -> float:
    return settings.get("thresholds", {}).get(key, default)

def get_stage_config(stage_name: str) -> dict:
    return settings.get("pipeline", {}).get(stage_name, {})

def get_vision_config() -> dict:
    return settings.get("vision", {})

def get_audio_config() -> dict:
    return settings.get("audio", {})

def get_server_config() -> dict:
    return settings.get("server", {})

def is_cloud_fallback_enabled() -> bool:
    return settings.get("backup_apis", {}).get("enable_cloud_fallback", False)

def get_metadata_config() -> dict:
    return settings.get("metadata", {
        "enabled": True,
        "use_ffprobe": True,
        "use_exiftool": True,
        "timeout_seconds": 10,
        "detect_provenance": True
    })

