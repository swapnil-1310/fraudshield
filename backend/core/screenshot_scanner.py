import os
import json
import re
import sys
from typing import Dict, Any
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

try:
    from google import genai as google_genai
    if config.GEMINI_API_KEY:
        _gemini_client = google_genai.Client(api_key=config.GEMINI_API_KEY)
except ImportError:
    try:
        import google.generativeai as genai_legacy
        if config.GEMINI_API_KEY:
            genai_legacy.configure(api_key=config.GEMINI_API_KEY)
            _gemini_client = "legacy"
    except ImportError:
        _gemini_client = None

def _extract_json(raw: str) -> dict:
    """Robustly extract JSON from Gemini response."""
    m = re.search(r"(\{[\s\S]*?\})\s*$", raw.strip())
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m2 = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    try:
        return json.loads(raw)
    except Exception:
        pass
    return {}

def analyze_screenshot(image_path: str) -> Dict[str, Any]:
    """
    Uses Gemini 1.5 Pro Multimodal to visually inspect a trading app screenshot.
    """
    if not _gemini_client or not config.GEMINI_API_KEY:
        return {
            "is_violation": False,
            "risk_score": 0.0,
            "verdict": "ERROR",
            "confidence": "LOW",
            "summary": "Gemini API key is missing or invalid. Cannot perform visual analysis.",
            "reasons": ["Missing Gemini API configuration for multimodal analysis."],
            "detected_schemes": ["none"],
            "sebi_rules": []
        }

    prompt = """You are Dr. Ananya Sharma, Senior Director of Market Intelligence and Investor Protection at SEBI.
You are conducting a forensic visual audit of a trading app screenshot, P&L statement, or tipster message.

Analyze the provided image for ANY of the following SEBI violations or fraud indicators:
1. P&L MANIPULATION: Look at the profit numbers. Are they absurdly high, visually edited, or using a spoofed broker UI (like fake Zerodha/Groww clones)?
2. GUARANTEED RETURNS: Does the text in the image promise "assured returns", "100% accuracy", "jackpot", or "zero risk"?
3. UNREGISTERED ADVISORY: Does it ask users to "Join VIP Telegram", "WhatsApp for Premium Tips", or pay for calls without citing a valid SEBI RA/IA number?
4. SCARCITY TACTICS: "Limited seats", "Urgent buy", "Fast booking".

Evaluate the overall risk.
Respond with ONLY valid JSON (no markdown fences, no extra text):
{
  "is_violation": true_or_false,
  "risk_score": 0.00_to_1.00,
  "verdict": "HIGH RISK SCAM" or "WATCH" or "COMPLIANT",
  "confidence": "HIGH" or "MEDIUM" or "LOW",
  "summary": "Precise 1-2 sentence forensic visual summary",
  "reasons": ["Visual Finding 1 (e.g. Fake UI)", "Text Finding 2 (e.g. Telegram link found)"],
  "sebi_rules": ["SEBI (Investment Advisers) Regulations 2013", "SEBI FUTP 2003"],
  "detected_schemes": ["fake_pnl", "paid_group", "pump_dump", "none"]
}"""

    try:
        img = Image.open(image_path)
        
        if _gemini_client != "legacy":
            # New google-genai SDK
            response = _gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=[img, prompt],
                config={
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "max_output_tokens": 1024,
                }
            )
            raw_text = response.text.strip()
        else:
            # Fallback legacy SDK
            import google.generativeai as genai_legacy
            model = genai_legacy.GenerativeModel(
                "gemini-3.6-flash",
                generation_config={"temperature": 0.1, "top_p": 0.95, "max_output_tokens": 1024}
            )
            response = model.generate_content([img, prompt])
            raw_text = response.text.strip()
            
        result_data = _extract_json(raw_text)
        
        if not result_data:
            raise ValueError("Failed to parse JSON from Gemini vision output")
            
        return {
            "is_violation": result_data.get("is_violation", False),
            "risk_score": float(result_data.get("risk_score", 0.0)),
            "verdict": result_data.get("verdict", "UNKNOWN"),
            "confidence": result_data.get("confidence", "MEDIUM"),
            "summary": result_data.get("summary", "Visual analysis completed."),
            "reasons": result_data.get("reasons", []),
            "sebi_rules": result_data.get("sebi_rules", []),
            "detected_schemes": result_data.get("detected_schemes", ["none"])
        }
        
    except Exception as e:
        print(f"[ScreenshotScanner] Vision analysis error: {e}")
        return {
            "is_violation": False,
            "risk_score": 0.0,
            "verdict": "ERROR",
            "confidence": "LOW",
            "summary": f"Failed to analyze screenshot: {str(e)}",
            "reasons": [str(e)],
            "sebi_rules": [],
            "detected_schemes": ["none"]
        }
