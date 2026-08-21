import os
import sys
import tempfile
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from db.database import DatabaseManager
from core.deepfake_vision import VisualDeepfakeDetector
from core.audio_extractor import extract_audio_from_video
from core.transcriber import transcribe_audio_file
from core.sebi_compliance import analyze_sebi_compliance
from core.screenshot_scanner import analyze_screenshot

app = FastAPI(
    title="FraudShield-SEBI Pro API",
    description="Dual Visual Deepfake & Audio SEBI Compliance Fraud Detection Platform",
    version="2.0.0"
)

# Enable CORS for Next.js Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instances
db = DatabaseManager()
deepfake_detector = VisualDeepfakeDetector()


# ── Response Models ─────────────────────────────────────────────────────────

class TextScanRequest(BaseModel):
    text: str
    advisor_reg_no: Optional[str] = ""

class AdvisorVerifyResponse(BaseModel):
    reg_no: str
    status: str
    is_valid: bool
    name: Optional[str] = None
    category: Optional[str] = None
    company: Optional[str] = None
    valid_till: Optional[str] = None
    details: str

class DualVerdictResponse(BaseModel):
    id: str
    timestamp: str
    media_type: str
    title: str
    
    # Dual Axes
    is_deepfake: bool
    deepfake_score: float
    visual_summary: str
    
    is_sebi_violation: bool
    sebi_risk_score: float
    sebi_summary: str
    
    # Combined Dual Verdict
    dual_verdict: str
    verdict_label: str
    verdict_badge_color: str
    summary: str
    
    transcript: str
    reasons: List[str]
    sebi_rules: List[str]
    
    advisor_reg_no: Optional[str] = ""
    advisor_status: Optional[str] = "UNREGISTERED"

    # Enhanced accuracy fields
    confidence: Optional[str] = "MEDIUM"
    detected_schemes: Optional[List[str]] = []
    compliance_signals: Optional[List[str]] = []
    
    # New Visual Forensics Fields
    watermark_detected: Optional[str] = "none"
    gemini_reasoning: Optional[str] = ""
    artifacts: Optional[List[str]] = []


# ── Helper for Dual Verdict Classification ──────────────────────────────────

def compute_dual_verdict(is_deepfake: bool, is_violation: bool, deepfake_score: float, sebi_score: float) -> Dict[str, str]:
    """
    Computes the 4-Zone Dual Verdict Matrix:
    1. AI_SEBI_VIOLATION  : AI Media + SEBI Violation -> 🚨 HIGH RISK SCAM
    2. AI_SEBI_COMPLIANT  : AI Media + SEBI Compliant -> 🟦 AI LEGIT / EDUCATIONAL
    3. REAL_SEBI_VIOLATION: Real Media + SEBI Violation -> 🟧 SEBI VIOLATION
    4. REAL_SEBI_COMPLIANT: Real Media + SEBI Compliant -> 🟩 SAFE / VERIFIED
    """
    if is_deepfake and is_violation:
        return {
            "dual_verdict": "AI_SEBI_VIOLATION",
            "verdict_label": "HIGH RISK SCAM (AI Deepfake + SEBI Violation)",
            "badge_color": "red",
            "summary": "🚨 CRITICAL ALERT: AI-generated deepfake media promoting non-compliant SEBI financial claims!"
        }
    elif is_deepfake and not is_violation:
        return {
            "dual_verdict": "AI_SEBI_COMPLIANT",
            "verdict_label": "AI DETECTED (SEBI Compliant Content)",
            "badge_color": "blue",
            "summary": "🟦 AI Media Detected: Spoken content strictly complies with SEBI investor guidelines (Legitimate AI Educational Content)."
        }
    elif not is_deepfake and is_violation:
        return {
            "dual_verdict": "REAL_SEBI_VIOLATION",
            "verdict_label": "SEBI REGULATORY VIOLATION",
            "badge_color": "orange",
            "summary": "🟧 SEBI Violation: Authentic human media giving non-compliant stock tips or unregistered advice."
        }
    else:
        return {
            "dual_verdict": "REAL_SEBI_COMPLIANT",
            "verdict_label": "SAFE & SEBI VERIFIED",
            "badge_color": "green",
            "summary": "🟩 CLEAR: Authentic media adhering to SEBI investor protection standards."
        }


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status": "online",
        "system": "FraudShield-SEBI Pro Engine",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/scan-video", response_model=DualVerdictResponse)
async def scan_video(
    file: UploadFile = File(...),
    advisor_reg_no: Optional[str] = Form("")
):
    """
    Process uploaded video:
    1. Extract visual frames & compute Deepfake score via Vision ViT
    2. Extract audio track from video
    3. Transcribe spoken audio to text
    4. Evaluate transcript against SEBI regulatory rules & Gemini AI
    5. Compute Dual Verdict Matrix
    """
    filename = file.filename or "uploaded_video.mp4"
    suffix = os.path.splitext(filename)[1] or ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=config.TEMP_DIR) as tmp:
        tmp.write(await file.read())
        video_path = tmp.name

    try:
        # Step 1: Visual Deepfake Analysis
        visual_res = deepfake_detector.analyze_video(video_path)
        is_deepfake = visual_res["is_deepfake"]
        deepfake_score = visual_res["score"]
        visual_summary = visual_res["summary"]
        watermark_detected = visual_res.get("watermark_detected", "none")
        gemini_reasoning = visual_res.get("gemini_reasoning", "")
        artifacts = visual_res.get("artifacts", [])

        # Step 2: Audio Extraction
        audio_path = extract_audio_from_video(video_path)

        # Step 3: Audio Transcription
        transcript_res = transcribe_audio_file(audio_path)
        transcript_text = transcript_res.get("transcript", "")

        # Step 4: Advisor Lookup
        advisor_info = db.get_advisor(advisor_reg_no) if advisor_reg_no else None
        advisor_status = advisor_info["status"] if advisor_info else ("NOT_PROVIDED" if not advisor_reg_no else "UNREGISTERED")

        # Step 5: SEBI Spoken Compliance Analysis
        sebi_res = analyze_sebi_compliance(transcript_text, advisor_reg_no=advisor_reg_no)
        is_violation = sebi_res["is_violation"]
        sebi_risk_score = sebi_res["risk_score"]
        sebi_summary = sebi_res["summary"]

        # Flag unregistered advisor if they claim a fake registration
        if advisor_reg_no and not advisor_info:
            is_violation = True
            sebi_risk_score = max(sebi_risk_score, 0.85)
            sebi_res["reasons"].append(f"Unregistered Advisor Reg No claimed: '{advisor_reg_no}'")
            sebi_res["sebi_rules"].append("SEBI (Investment Advisers) Regulations 2013")

        # Step 6: Compute Dual Verdict
        dual = compute_dual_verdict(is_deepfake, is_violation, deepfake_score, sebi_risk_score)

        report_id = f"FLAG-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.now().isoformat()

        report_data = {
            "id": report_id,
            "timestamp": timestamp,
            "media_type": "video",
            "title": filename,
            "is_deepfake": is_deepfake,
            "deepfake_score": deepfake_score,
            "visual_summary": visual_summary,
            "is_sebi_violation": is_violation,
            "sebi_risk_score": sebi_risk_score,
            "sebi_summary": sebi_summary,
            "dual_verdict": dual["dual_verdict"],
            "verdict_label": dual["verdict_label"],
            "verdict_badge_color": dual["badge_color"],
            "summary": dual["summary"],
            "transcript": transcript_text,
            "reasons": sebi_res["reasons"],
            "sebi_rules": sebi_res["sebi_rules"],
            "advisor_reg_no": advisor_reg_no,
            "advisor_status": advisor_status,
            "status": "FLAGGED" if (is_deepfake or is_violation) else "SAFE",
            "confidence": sebi_res.get("confidence", "MEDIUM"),
            "detected_schemes": sebi_res.get("detected_schemes", ["none"]),
            "compliance_signals": sebi_res.get("compliance_signals", []),
            "watermark_detected": watermark_detected,
            "gemini_reasoning": gemini_reasoning,
            "artifacts": artifacts
        }

        # Save to SQLite database
        db.save_scan_report(report_data)

        return DualVerdictResponse(**report_data)

    finally:
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass

@app.post("/api/scan-screenshot", response_model=DualVerdictResponse)
async def scan_screenshot(
    file: UploadFile = File(...),
    advisor_reg_no: Optional[str] = Form("")
):
    """
    Process uploaded screenshot (P&L, WhatsApp tip, app interface):
    1. Send image to Gemini 1.5 Pro Multimodal.
    2. Perform forensic OCR and visual UI inspection.
    3. Return Dual Verdict (Visual fraud + SEBI rules).
    """
    filename = file.filename or "uploaded_screenshot.png"
    suffix = os.path.splitext(filename)[1] or ".png"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=config.TEMP_DIR) as tmp:
        tmp.write(await file.read())
        image_path = tmp.name

    try:
        advisor_info = db.get_advisor(advisor_reg_no) if advisor_reg_no else None
        advisor_status = advisor_info["status"] if advisor_info else ("NOT_PROVIDED" if not advisor_reg_no else "UNREGISTERED")

        # Step 1: Visual Forensic Analysis via Gemini
        sebi_res = analyze_screenshot(image_path)
        is_violation = sebi_res["is_violation"]
        sebi_risk_score = sebi_res["risk_score"]
        sebi_summary = sebi_res["summary"]

        if advisor_reg_no and not advisor_info:
            is_violation = True
            sebi_risk_score = max(sebi_risk_score, 0.85)
            sebi_res["reasons"].append(f"Unregistered Advisor Reg No claimed: '{advisor_reg_no}'")
            sebi_res["sebi_rules"].append("SEBI (Investment Advisers) Regulations 2013")

        # For screenshots, if it's a fake P&L or UI manipulation, we consider it a deepfake/visual fraud
        is_visual_fraud = "fake_pnl" in sebi_res.get("detected_schemes", []) or sebi_risk_score > 0.8
        
        # Step 2: Compute Dual Verdict
        dual = compute_dual_verdict(is_visual_fraud, is_violation, sebi_risk_score, sebi_risk_score)

        report_id = f"FLAG-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.now().isoformat()

        report_data = {
            "id": report_id,
            "timestamp": timestamp,
            "media_type": "image",
            "title": filename,
            "is_deepfake": is_visual_fraud,
            "deepfake_score": sebi_risk_score,
            "visual_summary": sebi_summary,
            "is_sebi_violation": is_violation,
            "sebi_risk_score": sebi_risk_score,
            "sebi_summary": sebi_summary,
            "dual_verdict": dual["dual_verdict"],
            "verdict_label": dual["verdict_label"],
            "verdict_badge_color": dual["badge_color"],
            "summary": dual["summary"],
            "transcript": "N/A (Visual Text Extraction performed by Gemini)",
            "reasons": sebi_res["reasons"],
            "sebi_rules": sebi_res["sebi_rules"],
            "advisor_reg_no": advisor_reg_no,
            "advisor_status": advisor_status,
            "status": "FLAGGED" if (is_visual_fraud or is_violation) else "SAFE",
            "confidence": sebi_res.get("confidence", "MEDIUM"),
            "detected_schemes": sebi_res.get("detected_schemes", ["none"]),
            "compliance_signals": [],
            "watermark_detected": "none",
            "gemini_reasoning": sebi_summary,
            "artifacts": []
        }

        db.save_scan_report(report_data)
        return DualVerdictResponse(**report_data)

    finally:
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

@app.post("/api/scan-text", response_model=DualVerdictResponse)
async def scan_text(req: TextScanRequest):
    """Scan text tip or advertisement for SEBI compliance violations."""
    advisor_info = db.get_advisor(req.advisor_reg_no) if req.advisor_reg_no else None
    advisor_status = advisor_info["status"] if advisor_info else ("NOT_PROVIDED" if not req.advisor_reg_no else "UNREGISTERED")

    sebi_res = analyze_sebi_compliance(req.text, advisor_reg_no=req.advisor_reg_no)
    is_violation = sebi_res["is_violation"]
    sebi_risk_score = sebi_res["risk_score"]

    if req.advisor_reg_no and not advisor_info:
        is_violation = True
        sebi_risk_score = max(sebi_risk_score, 0.85)
        sebi_res["reasons"].append(f"Unregistered Advisor Reg No claimed: '{req.advisor_reg_no}'")

    dual = compute_dual_verdict(False, is_violation, 0.0, sebi_risk_score)
    report_id = f"FLAG-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now().isoformat()

    report_data = {
        "id": report_id,
        "timestamp": timestamp,
        "media_type": "text",
        "title": "Text Investment Tip Analysis",
        "is_deepfake": False,
        "deepfake_score": 0.0,
        "visual_summary": "N/A (Text Analysis)",
        "is_sebi_violation": is_violation,
        "sebi_risk_score": sebi_risk_score,
        "sebi_summary": sebi_res["summary"],
        "dual_verdict": dual["dual_verdict"],
        "verdict_label": dual["verdict_label"],
        "verdict_badge_color": dual["badge_color"],
        "summary": dual["summary"],
        "transcript": req.text,
        "reasons": sebi_res["reasons"],
        "sebi_rules": sebi_res["sebi_rules"],
        "advisor_reg_no": req.advisor_reg_no,
        "advisor_status": advisor_status,
        "status": "FLAGGED" if is_violation else "SAFE",
        "confidence": sebi_res.get("confidence", "MEDIUM"),
        "detected_schemes": sebi_res.get("detected_schemes", ["none"]),
        "compliance_signals": sebi_res.get("compliance_signals", [])
    }

    db.save_scan_report(report_data)
    return DualVerdictResponse(**report_data)

@app.get("/api/verify-advisor/{reg_no}", response_model=AdvisorVerifyResponse)
def verify_advisor(reg_no: str):
    """Verify SEBI Registration Number against official database."""
    adv = db.get_advisor(reg_no)
    if adv:
        is_valid = (adv["status"] == "VALID")
        return AdvisorVerifyResponse(
            reg_no=adv["reg_no"],
            status=adv["status"],
            is_valid=is_valid,
            name=adv["name"],
            category=adv["category"],
            company=adv["company"],
            valid_till=adv["valid_till"],
            details=f"SEBI Registered {adv['category']} - Status: {adv['status']}"
        )
    return AdvisorVerifyResponse(
        reg_no=reg_no.upper(),
        status="UNREGISTERED",
        is_valid=False,
        details="❌ Registration ID not found in SEBI database. Operating without authorization."
    )

@app.get("/api/flags")
def get_flags(limit: int = 50):
    """List all scanned reports for Regulator Dashboard."""
    return db.list_reports(limit=limit)

@app.delete("/api/flags/{report_id}")
def delete_flag(report_id: str):
    """Dismiss or remove a report flag."""
    success = db.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report ID not found.")
    return {"message": f"Report {report_id} dismissed."}

@app.get("/api/stats")
def get_stats():
    """Summary KPI metrics for Regulator Dashboard."""
    return db.get_stats()
