from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
import uvicorn
import sys
import os
import json
import logging
import shutil
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from db.database import DatabaseManager
from core import prompts
from core.screenshot_scanner import analyze_screenshot
from core.deepfake_vision import VisualDeepfakeDetector
from core.audio_extractor import extract_audio_from_video
from core.transcriber import transcribe_audio_file
from core.sebi_compliance import analyze_sebi_compliance

# Suppress some verbose logging
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="FraudShield-SEBI Pro API")

# Configure CORS for frontend React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev, allow all. In prod, lock down to frontend URL.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_manager = DatabaseManager()
deepfake_engine = VisualDeepfakeDetector()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "FraudShield-SEBI Pro Backend Running (Genuine Pipeline)"}

@app.get("/api/prompts")
def get_prompts():
    """Returns the internal AI prompts registry"""
    return prompts.get_all_prompts()

@app.get("/api/stats")
def get_stats():
    """Returns overview statistics for the dashboard"""
    try:
        stats = db_manager.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/flags")
def get_flags():
    """Returns the history of flagged content"""
    try:
        flags = db_manager.list_reports()
        return flags
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/flags/{report_id}")
def delete_flag(report_id: str):
    """Deletes a specific flagged report"""
    try:
        success = db_manager.delete_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail="Report not found")
        return {"status": "success", "message": "Report deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/verify-advisor/{reg_no}")
def verify_advisor(reg_no: str):
    """Verifies a SEBI Registration Number"""
    try:
        advisor = db_manager.get_advisor(reg_no)
        if advisor:
            return {"status": "success", "advisor": advisor}
        else:
            return {"status": "not_found", "message": "Advisor not found in SEBI database"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- GENUINE AI ENDPOINTS ---

async def save_upload_file_tmp(upload_file: UploadFile) -> str:
    """Helper to save an uploaded file to a temporary location"""
    try:
        suffix = os.path.splitext(upload_file.filename)[1]
        temp_file_name = f"{uuid.uuid4().hex}{suffix}"
        temp_file_path = os.path.join(config.TEMP_DIR, temp_file_name)
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return temp_file_path
    finally:
        upload_file.file.close()

@app.post("/api/scan-screenshot")
async def scan_screenshot(image: UploadFile = File(...)):
    """Scans a screenshot using genuine core modules"""
    temp_path = None
    try:
        temp_path = await save_upload_file_tmp(image)
        
        # Genuine AI Call
        result = analyze_screenshot(temp_path)
        
        # Add metadata for UI
        result["media_type"] = "image"
        result["title"] = image.filename
        
        db_manager.save_scan_report(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/api/scan-video")
async def scan_video(video: UploadFile = File(...)):
    """Scans a video using genuine core modules (vision + audio)"""
    temp_video_path = None
    temp_audio_path = None
    try:
        temp_video_path = await save_upload_file_tmp(video)
        
        # 1. Genuine Deepfake Vision Analysis
        vision_result = deepfake_engine.analyze_video(temp_video_path)
        
        # 2. Extract Audio
        temp_audio_path = extract_audio_from_video(temp_video_path)
        
        transcript_text = ""
        sebi_result = {
            "is_sebi_violation": False,
            "sebi_risk_score": 0.0,
            "sebi_rules": [],
            "reasons": []
        }
        
        # 3. Genuine Audio Transcription & SEBI Compliance
        if temp_audio_path:
            transcription = transcribe_audio_file(temp_audio_path)
            transcript_text = transcription.get("transcript", "")
            
            if transcript_text:
                sebi_result = analyze_sebi_compliance(transcript_text)
        
        # Combine Results
        is_deepfake = vision_result.get("is_deepfake", False)
        is_sebi_violation = sebi_result.get("is_sebi_violation", False)
        
        if is_deepfake and is_sebi_violation:
            dual_verdict = "DEEPFAKE_SEBI_VIOLATION"
            verdict_label = "CRITICAL RISK"
        elif is_deepfake:
            dual_verdict = "DEEPFAKE_ONLY"
            verdict_label = "DEEPFAKE"
        elif is_sebi_violation:
            dual_verdict = "SEBI_VIOLATION_ONLY"
            verdict_label = "SEBI RISK"
        else:
            dual_verdict = "REAL_SEBI_COMPLIANT"
            verdict_label = "SAFE"
            
        final_reasons = vision_result.get("reasons", []) + sebi_result.get("reasons", [])
            
        result = {
            "is_deepfake": is_deepfake,
            "deepfake_score": vision_result.get("deepfake_score", 0.0),
            "is_sebi_violation": is_sebi_violation,
            "sebi_risk_score": sebi_result.get("sebi_risk_score", 0.0),
            "dual_verdict": dual_verdict,
            "verdict_label": verdict_label,
            "summary": "Video and audio analysis complete.",
            "reasons": final_reasons,
            "sebi_rules": sebi_result.get("sebi_rules", []),
            "transcript": transcript_text,
            "media_type": "video",
            "title": video.filename
        }
        
        db_manager.save_scan_report(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

@app.post("/api/scan-audio")
async def scan_audio(audio: UploadFile = File(...)):
    """Scans audio using genuine transcriber and SEBI compliance modules"""
    temp_audio_path = None
    try:
        temp_audio_path = await save_upload_file_tmp(audio)
        
        # 1. Genuine Transcription
        transcription = transcribe_audio_file(temp_audio_path)
        transcript_text = transcription.get("transcript", "")
        
        # 2. Genuine SEBI Compliance
        sebi_result = analyze_sebi_compliance(transcript_text)
        
        is_sebi_violation = sebi_result.get("is_sebi_violation", False)
        
        result = {
            "is_sebi_violation": is_sebi_violation,
            "sebi_risk_score": sebi_result.get("sebi_risk_score", 0.0),
            "dual_verdict": "SEBI_VIOLATION_ONLY" if is_sebi_violation else "REAL_SEBI_COMPLIANT",
            "verdict_label": "HIGH RISK SCAM" if is_sebi_violation else "SAFE",
            "summary": "Audio analysis complete.",
            "reasons": sebi_result.get("reasons", []),
            "sebi_rules": sebi_result.get("sebi_rules", []),
            "transcript": transcript_text,
            "media_type": "audio",
            "title": audio.filename
        }
        
        db_manager.save_scan_report(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

@app.post("/api/scan-text")
async def scan_text(request: Request):
    """Scans text using genuine SEBI compliance module"""
    try:
        data = await request.json()
        text = data.get("text", "")
        
        # Genuine SEBI Compliance Analysis
        sebi_result = analyze_sebi_compliance(text)
        
        is_sebi_violation = sebi_result.get("is_sebi_violation", False)
        
        result = {
            "is_sebi_violation": is_sebi_violation,
            "sebi_risk_score": sebi_result.get("sebi_risk_score", 0.0),
            "dual_verdict": "SEBI_VIOLATION_ONLY" if is_sebi_violation else "REAL_SEBI_COMPLIANT",
            "verdict_label": "HIGH RISK SCAM" if is_sebi_violation else "SAFE",
            "summary": "Text analysis complete.",
            "reasons": sebi_result.get("reasons", []),
            "sebi_rules": sebi_result.get("sebi_rules", []),
            "transcript": text,
            "media_type": "text",
            "title": "Text Scan"
        }
        
        db_manager.save_scan_report(result)
        return result
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
