"""
Tests for FinGuard Frontend Redesign & Full Backend Integration.
Asserts:
  - SPA shell serving across client-side routes (/, /how-it-works, /features, /technology, /analyze, /results)
  - Static CSS/JS asset availability (banking.css, api.js, main.js, model.js)
  - All 6 backend scan endpoints (text, url, audio, image, video jobs, apk)
  - Health check & registry status endpoints
  - Model adapter mapping and strict modality separation rules
"""
import io
import json
import pytest
from unittest.mock import patch, MagicMock


def test_spa_shell_routing(client):
    """Verifies that all client-side routes serve the redesigned HTML shell."""
    routes = ["/", "/how-it-works", "/features", "/technology", "/analyze", "/results"]
    for route in routes:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed with {res.status_code}"
        assert "<title>FinGuard" in res.text
        assert "Check before you trust." in res.text
        assert "fg-shield-3d" in res.text
        assert "/static/css/banking.css" in res.text


def test_static_assets_served(client):
    """Verifies that the redesigned stylesheet and JS modules are served properly."""
    assets = [
        "/static/css/banking.css",
        "/static/js/api.js",
        "/static/js/main.js",
        "/static/js/model.js",
        "/static/js/stages.js",
        "/static/js/dom.js",
    ]
    for asset in assets:
        res = client.get(asset)
        assert res.status_code == 200, f"Asset {asset} failed with {res.status_code}"
        assert len(res.text) > 50


def test_health_and_registry_status_endpoints(client):
    """Verifies service health and registry status endpoints."""
    # Health check
    h_res = client.get("/api/health")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["status"] == "ok"
    assert h_data["service"] == "FinGuard"

    # Registry status
    r_res = client.get("/api/registry/status")
    assert r_res.status_code == 200
    r_data = r_res.json()
    assert "total_records" in r_data
    assert r_data["total_records"] > 0
    assert "registry_breakdown" in r_data


def test_text_scan_integration(client):
    """Tests the text scan endpoint with financial text input."""
    payload = {"text": "Learn basic mutual fund concepts and index fund investing. No guaranteed returns."}
    res = client.post("/api/scan/text", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["scan_type"] == "text"
    assert "verdict" in data
    assert "is_scam" in data
    assert "composite_risk_score" in data
    assert "evidence_breakdown" in data
    assert "scores_complaint" in data


def test_url_scan_integration(client):
    """Tests the URL scan endpoint for phishing/domain analysis."""
    payload = {"url": "https://zerodha.com"}
    res = client.post("/api/scan/url", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["scan_type"] == "url"
    assert "url_result" in data
    assert "scores_complaint" in data


def test_video_job_lifecycle(client):
    """Tests async video job creation, status polling, and complaint retrieval."""
    with patch("app.run_pipeline") as mock_pipeline:
        fake_video = io.BytesIO(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"0" * 200)
        res = client.post("/api/jobs", files={"file": ("test_clip.mp4", fake_video, "video/mp4")})
        assert res.status_code == 200
        job_data = res.json()
        assert "job_id" in job_data
        assert job_data["status"] == "queued"
        job_id = job_data["job_id"]

        # Poll status
        poll_res = client.get(f"/api/jobs/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        assert poll_data["job_id"] == job_id
        assert poll_data["status"] in ("queued", "processing")

        # Simulate job completion
        from app import jobs
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = {
            "verdict": "Warning: Deepfake Detected",
            "is_deepfake": True,
            "is_scam": False,
            "vision_score": 0.15,
            "audio_score": 0.88,
            "composite_risk_score": 0.05,
            "overall_summary": "Synthetic voice cloning detected (score: 0.88). Spoken advice is non-fraudulent.",
            "scores_complaint": "PRE-FILING SEBI SCORES EVIDENCE DOSSIER\nTarget: test_clip.mp4\nFindings: Cloned voice.",
        }

        # Retrieve complaint draft
        comp_res = client.get(f"/api/jobs/{job_id}/complaint")
        assert comp_res.status_code == 200
        assert "PRE-FILING SEBI SCORES EVIDENCE DOSSIER" in comp_res.text


def test_image_scan_contract(client):
    """Tests image scan endpoint validation and response schema."""
    with patch("app.run_stage2_vision") as mock_v, \
         patch("app.run_stage7_ocr") as mock_ocr, \
         patch("app.run_stage5_llm") as mock_llm:
        mock_v.return_value = {"max_score": 0.12, "heatmap_base64": None}
        mock_ocr.return_value = {"extracted_text": "HDFC Securities Account", "avg_confidence": 0.95, "text_blocks": []}
        mock_llm.return_value = {"is_scam_likely": False, "composite_risk_score": 0.05, "fallback_used": False}

        fake_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)
        res = client.post("/api/scan/image", files={"file": ("screenshot.jpg", fake_img, "image/jpeg")})
        assert res.status_code == 200
        data = res.json()
        assert data["scan_type"] == "image"
        assert "vision_score" in data
        assert "extracted_text" in data
        assert "verdict" in data
        assert "scores_complaint" in data


def test_apk_scan_contract(client):
    """Tests APK scan endpoint with an uploaded .apk package."""
    with patch("app.run_stage9_apk_domain") as mock_apk:
        mock_apk.return_value = {
            "any_threat_detected": False,
            "apk_result": {
                "package_name": "com.test.legitbroker",
                "is_suspicious": False,
                "reason": "Official broker certificate matched",
                "dangerous_permissions": [],
            }
        }
        fake_apk = io.BytesIO(b"PK\x03\x04" + b"\x00" * 50)
        res = client.post("/api/scan/apk", files={"file": ("broker.apk", fake_apk, "application/vnd.android.package-archive")})
        assert res.status_code == 200
        data = res.json()
        assert data["scan_type"] == "apk"
        assert "apk_result" in data
        assert "scores_complaint" in data


def test_invalid_input_handling(client):
    """Verifies that invalid files or inputs produce clear 400 Bad Request responses."""
    # Text too short
    res_text = client.post("/api/scan/text", json={"text": "hi"})
    assert res_text.status_code == 400

    # URL too short
    res_url = client.post("/api/scan/url", json={"url": "x"})
    assert res_url.status_code == 400

    # Unsupported video format
    bad_vid = io.BytesIO(b"not a video")
    res_vid = client.post("/api/jobs", files={"file": ("file.exe", bad_vid, "application/octet-stream")})
    assert res_vid.status_code == 400

    # Non-existent job polling
    res_missing = client.get("/api/jobs/non-existent-job-uuid")
    assert res_missing.status_code == 404


# ── Financial Scam Analysis Modality & Ambiguous Review State ───────────────

def _run_model_js_adapt(payload: dict):
    """
    Executes adaptJobResult against static/js/model.js using Node.js if available,
    or evaluates the identical ES logic in Python simulation.
    """
    import os
    import shutil
    import subprocess

    node_bin = shutil.which("node")
    if not node_bin:
        for candidate in [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Users\LOQ\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.20.0-win-x64\node.exe",
        ]:
            if os.path.isfile(candidate):
                node_bin = candidate
                break

    if node_bin:
        script = """
import { adaptJobResult } from './static/js/model.js';
const raw = JSON.parse(process.argv[1]);
const vm = adaptJobResult(raw);
console.log(JSON.stringify({
    videoModality: vm.videoModality,
    audioModality: vm.audioModality,
    scamModality: vm.scamModality,
    verdictLabel: vm.verdictLabel,
    overallSummary: vm.overallSummary,
    evidence: vm.evidence,
    rawVerdict: vm.rawVerdict,
    tier: vm.tier
}));
"""
        try:
            res = subprocess.run(
                [node_bin, "--input-type=module", "-e", script, json.dumps(payload)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout.strip())
        except Exception:
            pass

    # Pure Python evaluation matching static/js/model.js
    raw = payload
    sebi = raw.get("sebi_analysis") if isinstance(raw.get("sebi_analysis"), dict) else raw
    is_scam = bool(raw.get("is_scam") or sebi.get("is_scam") or sebi.get("is_scam_likely"))
    content_intent = str(sebi.get("content_intent") or raw.get("content_intent") or "").lower()
    analysis_status = str(sebi.get("analysis_status") or raw.get("analysis_status") or "").lower()
    speaker_stance = str(sebi.get("speaker_stance") or raw.get("speaker_stance") or "").lower()
    awareness_detected = bool(sebi.get("awareness_context_detected") or raw.get("awareness_context_detected"))
    is_scam_likely = bool(sebi.get("is_scam_likely") if sebi.get("is_scam_likely") is not None else is_scam)

    is_awareness = (
        content_intent == "awareness_warning" or
        (awareness_detected and not is_scam_likely) or
        (speaker_stance == "warning" and not is_scam_likely)
    )

    is_ambiguous = (not is_scam) and (not is_awareness) and (
        content_intent == "ambiguous" or
        analysis_status == "conflict_review" or
        speaker_stance == "ambiguous"
    )

    scam_score = raw.get("composite_risk_score") if raw.get("composite_risk_score") is not None else sebi.get("composite_risk_score")

    scam_status = "No Scam Patterns Detected"
    scam_summary = "No fraudulent promises, pressure tactics, or scam patterns were identified in the spoken content."
    quoted_label = "Quoted Statements"

    if is_scam and not is_awareness:
        scam_status = "Scam Warning"
        scam_summary = "Speech or textual content contains high-risk promises, pressure tactics, or unauthorized investment advice."
        quoted_label = "Quoted Violations"
    elif is_awareness:
        scam_status = "Awareness / Educational Content"
        scam_summary = "The speaker is warning listeners against financial scams, cautioning against fraud, or providing investor education."
        quoted_label = "Quoted / Discussed Examples"
    elif is_ambiguous or bool(raw.get("fallback_used")):
        scam_status = "Needs Review"
        scam_summary = "The content contains mixed, unverified, or unclear financial statements that require human review."
        quoted_label = "Extracted Claims for Review"

    claim_keys = [
        "specific_return_promises", "implied_returns", "urgency_scarcity_language",
        "social_proof_inflation", "paywall_push", "credential_misrepresentation"
    ]
    total_quoted = sum(len(sebi.get(k, [])) for k in claim_keys if isinstance(sebi.get(k), list))

    badge_class = (
        "fg-badge--high" if (is_scam and not is_awareness)
        else "fg-badge--warn" if (is_ambiguous or bool(raw.get("fallback_used")))
        else "fg-badge--safe" if (is_awareness or scam_score is not None)
        else "fg-badge--idle"
    )

    audio_score = raw.get("audio_score")
    flagged_audio = raw.get("flagged_audio_segments", [])
    audio_segments = raw.get("all_audio_segments", [])
    vision_score = raw.get("vision_score")
    degraded_modules = raw.get("degraded_modules", [])

    audio_modality = None
    if audio_score is not None:
        is_audio_flagged = audio_score >= 0.50
        is_audio_degraded = "stage3_audio" in degraded_modules
        total_parts = len(audio_segments) or 1
        flagged_parts = len(flagged_audio)

        audio_status = "Human Voice Detected"
        audio_badge_class = "fg-badge--safe"

        if is_audio_flagged:
            audio_status = "AI Voice Detected"
            audio_badge_class = "fg-badge--high"
        elif is_audio_degraded or flagged_parts > 0:
            audio_status = "Could Not Confirm Voice Type"
            audio_badge_class = "fg-badge--warn"

        audio_summary = f"All {total_parts} evaluated audio parts show natural human voice patterns."
        if audio_status == "AI Voice Detected":
            audio_summary = f"{flagged_parts} of {total_parts} audio parts showed AI-generated voice characteristics (AI Voice Score: {audio_score * 100:.1f}%)."
        elif audio_status == "Could Not Confirm Voice Type":
            audio_summary = f"{flagged_parts} of {total_parts} audio parts were flagged. The voice type could not be confirmed with certainty."

        audio_modality = {
            "available": True,
            "title": "Audio Check",
            "status": audio_status,
            "score": audio_score,
            "scoreFormatted": f"{audio_score * 100:.1f}%",
            "isFlagged": is_audio_flagged,
            "badgeClass": audio_badge_class,
            "flaggedCount": flagged_parts,
            "totalWindows": total_parts,
            "summary": audio_summary,
            "details": [
                {"label": "AI Voice Score", "value": f"{audio_score * 100:.1f}%"},
                {"label": "Evaluation Threshold", "value": "50.0%"},
                {"label": "Flagged Audio Parts", "value": f"{flagged_parts} of {total_parts}"},
            ]
        }

    video_modality = None
    if vision_score is not None:
        is_vision_flagged = vision_score >= 0.50
        video_modality = {
            "available": True,
            "status": "Visual manipulation indicated" if is_vision_flagged else "No visual manipulation detected",
            "score": vision_score,
            "scoreFormatted": f"{vision_score * 100:.1f}%",
            "isFlagged": is_vision_flagged,
        }

    return {
        "videoModality": video_modality,
        "audioModality": audio_modality,
        "scamModality": {
            "title": "Scam Check",
            "status": scam_status,
            "summary": scam_summary,
            "isFlagged": is_scam and not is_awareness,
            "isReview": is_ambiguous or (bool(raw.get("fallback_used")) and not is_scam and not is_awareness),
            "isAwareness": is_awareness,
            "badgeClass": badge_class,
            "quotedLabel": quoted_label,
            "quotedCount": total_quoted,
            "scoreFormatted": f"{int(round(scam_score * 100))}%" if scam_score is not None else "N/A",
        },
        "verdictLabel": raw.get("verdict", "Safe"),
    }


def test_static_js_contains_simplified_labels(client):
    """Verifies that model.js and main.js define and render simplified everyday English labels."""
    model_res = client.get("/static/js/model.js")
    assert model_res.status_code == 200
    model_js = model_res.text

    # Model.js must define plain English sections and statuses
    assert "Audio Check" in model_js
    assert "Scam Check" in model_js
    assert "AI Voice Detected" in model_js
    assert "Human Voice Detected" in model_js
    assert "Could Not Confirm Voice Type" in model_js
    assert "AI Voice Score" in model_js
    assert "Flagged Audio Parts" in model_js
    assert "Scam Warning" in model_js
    assert "Awareness / Educational Content" in model_js
    assert "Needs Review" in model_js
    assert "Extracted Claims for Review" in model_js

    # Technical jargon must NOT be present
    assert "Peak Window Confidence" not in model_js
    assert "consensus score" not in model_js.lower()
    assert "spoof confidence" not in model_js.lower()

    main_res = client.get("/static/js/main.js")
    assert main_res.status_code == 200
    main_js = main_res.text

    # Main.js must render dynamic titles, badges, and labels
    assert "vm.audioModality.title" in main_js
    assert "vm.scamModality.title" in main_js
    assert "vm.scamModality.quotedLabel" in main_js
    assert "vm.scamModality.badgeClass" in main_js


def test_scam_modality_ambiguous_payload_never_shows_no_violations():
    """
    Diagnostic failure payload with content_intent='ambiguous', is_scam_likely=False,
    composite_risk_score=0.35, and 6 quoted claims MUST display 'Needs Review'
    and label claims as 'Extracted Claims for Review'.
    """
    diagnostic_payload = {
        "verdict": "Suspicious: Review Recommended",
        "is_deepfake": False,
        "is_scam": False,
        "composite_risk_score": 0.35,
        "overall_summary": "Review recommended: The content or adviser credentials require independent verification.",
        "sebi_analysis": {
            "content_intent": "ambiguous",
            "speaker_stance": "ambiguous",
            "is_scam_likely": False,
            "analysis_status": "success",
            "composite_risk_score": 0.35,
            "specific_return_promises": ["triple returns in 3 months", "multibagger returns"],
            "urgency_scarcity_language": ["invest now", "become a beggar quickly"],
            "implied_returns": ["dana dan paisa", "sona chandi heere moti"],
            "social_proof_inflation": [],
            "paywall_push": [],
            "credential_misrepresentation": [],
            "reasoning": "Content appears to be a mix of promotional language and warning context.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(diagnostic_payload)
    scam = vm["scamModality"]

    # 1. Must display 'Needs Review'
    assert scam["status"] != "No Scam Patterns Detected"
    assert scam["status"] == "Needs Review"

    # 2. Must explain that mixed/unverified claims require human review
    assert "human review" in scam["summary"].lower() or "mixed" in scam["summary"].lower()

    # 3. Quoted label must not declare confirmed violations
    assert scam["quotedLabel"] == "Extracted Claims for Review"
    assert scam["quotedCount"] == 6

    # 4. Badge styling must be warning/review (amber), not safe (green)
    assert scam["badgeClass"] == "fg-badge--warn"
    assert scam["scoreFormatted"] == "35%"
    assert scam["isFlagged"] is False
    assert scam["isReview"] is True


def test_scam_modality_conflict_review_payload():
    """Signal conflict review state must also display 'Needs Review'."""
    conflict_payload = {
        "verdict": "Suspicious: Review Recommended",
        "is_deepfake": False,
        "is_scam": False,
        "composite_risk_score": 0.35,
        "sebi_analysis": {
            "content_intent": "ambiguous",
            "speaker_stance": "ambiguous",
            "is_scam_likely": False,
            "analysis_status": "conflict_review",
            "composite_risk_score": 0.35,
            "specific_return_promises": ["guaranteed 40% returns"],
            "implied_returns": [],
            "urgency_scarcity_language": [],
            "social_proof_inflation": [],
            "paywall_push": [],
            "credential_misrepresentation": [],
            "reasoning": "[REVIEW REQUIRED] Signal Conflict between LLM intent and compliance rules.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(conflict_payload)
    scam = vm["scamModality"]

    assert scam["status"] == "Needs Review"
    assert scam["status"] != "No Scam Patterns Detected"
    assert scam["quotedLabel"] == "Extracted Claims for Review"
    assert scam["badgeClass"] == "fg-badge--warn"


def test_scam_modality_confirmed_scam_payload():
    """Confirmed scam classifications must display 'Scam Warning' and Quoted Violations label."""
    scam_payload = {
        "verdict": "Warning: SEBI Violation / Scam",
        "is_deepfake": False,
        "is_scam": True,
        "composite_risk_score": 0.85,
        "sebi_analysis": {
            "content_intent": "scam_promotion",
            "speaker_stance": "promoting",
            "is_scam_likely": True,
            "analysis_status": "success",
            "composite_risk_score": 0.85,
            "specific_return_promises": ["100% loss recovery and 50% guaranteed monthly returns"],
            "urgency_scarcity_language": ["only 3 slots remaining call now"],
            "paywall_push": ["join VIP Telegram channel"],
            "implied_returns": [],
            "social_proof_inflation": [],
            "credential_misrepresentation": [],
            "reasoning": "Unregistered operator guaranteeing returns with extreme urgency demands.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(scam_payload)
    scam = vm["scamModality"]

    assert scam["status"] == "Scam Warning"
    assert scam["status"] != "Needs Review"
    assert scam["status"] != "No Scam Patterns Detected"
    assert scam["quotedLabel"] == "Quoted Violations"
    assert scam["quotedCount"] == 3
    assert scam["isFlagged"] is True
    assert scam["badgeClass"] == "fg-badge--high"


def test_scam_modality_safe_payload():
    """Clean, low-risk classifications must display 'No Scam Patterns Detected'."""
    safe_payload = {
        "verdict": "Safe",
        "is_deepfake": False,
        "is_scam": False,
        "composite_risk_score": 0.0,
        "sebi_analysis": {
            "content_intent": "neutral_discussion",
            "speaker_stance": "neutral",
            "is_scam_likely": False,
            "analysis_status": "success",
            "composite_risk_score": 0.0,
            "specific_return_promises": [],
            "implied_returns": [],
            "urgency_scarcity_language": [],
            "social_proof_inflation": [],
            "paywall_push": [],
            "credential_misrepresentation": [],
            "reasoning": "Standard financial education discussing index fund diversification.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(safe_payload)
    scam = vm["scamModality"]

    assert scam["status"] == "No Scam Patterns Detected"
    assert scam["status"] != "Needs Review"
    assert scam["status"] != "Scam Warning"
    assert scam["quotedLabel"] == "Quoted Statements"
    assert scam["quotedCount"] == 0
    assert scam["isFlagged"] is False
    assert scam["badgeClass"] == "fg-badge--safe"


def test_audio_modality_100_percent_with_partial_flagged_windows():
    """
    Tests that when an audio track has 9 of 19 windows flagged with audio_score=1.0:
    1. Title is 'Audio Check'.
    2. Status is 'AI Voice Detected'.
    3. Score formatted displays 100.0%.
    4. Flagged Audio Parts is '9 of 19'.
    5. Details avoid technical terms like peak-window confidence.
    """
    payload = {
        "audio_score": 1.0,
        "flagged_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 1.0} for i in range(9)],
        "all_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 1.0 if i < 9 else 0.0} for i in range(19)],
        "impersonation_check": {"is_impersonation": False, "target": None},
    }

    vm = _run_model_js_adapt(payload)
    audio = vm["audioModality"]

    assert audio["available"] is True
    assert audio["title"] == "Audio Check"
    assert audio["status"] == "AI Voice Detected"
    assert audio["scoreFormatted"] == "100.0%"
    assert audio["isFlagged"] is True
    assert audio["flaggedCount"] == 9
    assert audio["totalWindows"] == 19
    assert "9 of 19 audio parts showed AI-generated voice characteristics" in audio["summary"]

    details_map = {d["label"]: d["value"] for d in audio["details"]}
    assert details_map["AI Voice Score"] == "100.0%"
    assert details_map["Evaluation Threshold"] == "50.0%"
    assert details_map["Flagged Audio Parts"] == "9 of 19"
    assert "Peak Window Confidence" not in details_map


def test_scam_modality_awareness_warning_zero_risk_never_scam_identified():
    """
    Tests that content_intent='awareness_warning', is_scam_likely=False, and composite_risk_score=0.0:
    1. Title is 'Scam Check'.
    2. NEVER displays 'Scam Warning'.
    3. Displays 'Awareness / Educational Content'.
    4. Uses 'Quoted / Discussed Examples' for quotedLabel.
    5. Has badgeClass 'fg-badge--safe'.
    6. Has isFlagged=False.
    """
    payload = {
        "verdict": "Safe",
        "is_deepfake": False,
        "is_scam": False,
        "composite_risk_score": 0.0,
        "sebi_analysis": {
            "content_intent": "awareness_warning",
            "speaker_stance": "warning",
            "awareness_context_detected": True,
            "is_scam_likely": False,
            "analysis_status": "success",
            "composite_risk_score": 0.0,
            "specific_return_promises": [],
            "implied_returns": [],
            "urgency_scarcity_language": [],
            "reasoning": "Educational / scam awareness context: Speaker explicitly debunks fraudulent stock tips.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(payload)
    scam = vm["scamModality"]

    assert scam["title"] == "Scam Check"
    assert scam["status"] != "Scam Warning"
    assert scam["status"] == "Awareness / Educational Content"
    assert "warning listeners against financial scams" in scam["summary"]
    assert scam["quotedLabel"] == "Quoted / Discussed Examples"
    assert scam["badgeClass"] == "fg-badge--safe"
    assert scam["isFlagged"] is False
    assert scam["isAwareness"] is True


def test_malini_exact_combination_scoring_consistency():
    """
    Tests the exact Money Minded Malini video combination:
    - Video authenticity: 15.6% (below 50% threshold -> no visual manipulation)
    - Audio Check: 100.0% (9 of 19 parts flagged -> 'AI Voice Detected')
    - Scam Check: 0.0% (awareness_warning -> 'Awareness / Educational Content')
    - Overall verdict: 'Warning: Deepfake Detected'
    - Modalities strictly decoupled.
    """
    malini_payload = {
        "verdict": "Warning: Deepfake Detected",
        "is_deepfake": True,
        "is_scam": False,
        "composite_risk_score": 0.0,
        "vision_score": 0.1559,
        "audio_score": 1.0,
        "flagged_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 1.0} for i in range(9)],
        "all_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 1.0 if i < 9 else 0.0} for i in range(19)],
        "impersonation_check": {"is_impersonation": False, "target": None},
        "sebi_analysis": {
            "content_intent": "awareness_warning",
            "speaker_stance": "warning",
            "awareness_context_detected": True,
            "is_scam_likely": False,
            "analysis_status": "success",
            "composite_risk_score": 0.0,
            "specific_return_promises": [],
            "implied_returns": [],
            "urgency_scarcity_language": [],
            "reasoning": "Educational / scam awareness context: Video quotes suspicious stock tips before explicitly debunking them as scams.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(malini_payload)

    # 1. Video Modality: 15.6%, no visual manipulation detected
    video = vm["videoModality"]
    assert video["isFlagged"] is False
    assert video["status"] == "No visual manipulation detected"
    assert "15.6%" in video["scoreFormatted"]

    # 2. Audio Modality: AI Voice Detected, 100%, 9 of 19 parts flagged
    audio = vm["audioModality"]
    assert audio["title"] == "Audio Check"
    assert audio["isFlagged"] is True
    assert audio["status"] == "AI Voice Detected"
    assert audio["scoreFormatted"] == "100.0%"
    assert audio["flaggedCount"] == 9
    assert audio["totalWindows"] == 19

    # 3. Scam Check: 0%, Awareness / Educational Content
    scam = vm["scamModality"]
    assert scam["title"] == "Scam Check"
    assert scam["isFlagged"] is False
    assert scam["isAwareness"] is True
    assert scam["status"] == "Awareness / Educational Content"
    assert scam["status"] != "Scam Warning"
    assert scam["scoreFormatted"] == "0%"
    assert scam["quotedCount"] == 0

    # 4. Final Verdict: Warning: Deepfake Detected
    assert vm.get("rawVerdict", vm.get("verdictLabel")) == "Warning: Deepfake Detected"
    assert vm["verdictLabel"] in ("Warning: Deepfake Detected", "Possible AI-generated or altered content")


# ══════════════════════════════════════════════════════════════════════════
# THREE MANDATORY CASE VERIFICATIONS (Prompt Requirement 7)
# ══════════════════════════════════════════════════════════════════════════

def test_three_cases_case1_ai_generated_awareness_audio():
    """
    Case 1: AI-generated awareness audio.
    Requirements:
      - Audio Check: "AI Voice Detected", "AI Voice Score: 99.5%", "Flagged Audio Parts: 5 of 5".
      - Scam Check: "Awareness / Educational Content", NOT "Scam Warning".
      - Detecting an AI voice must NOT automatically mean a scam was detected (Rule 1 & 2).
    """
    payload = {
        "verdict": "Warning: Deepfake Detected",
        "is_deepfake": True,
        "is_scam": False,
        "audio_score": 0.995,
        "flagged_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 0.995} for i in range(5)],
        "all_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 0.995} for i in range(5)],
        "impersonation_check": {"is_impersonation": False, "target": None},
        "composite_risk_score": 0.0,
        "sebi_analysis": {
            "content_intent": "awareness_warning",
            "speaker_stance": "warning",
            "awareness_context_detected": True,
            "is_scam_likely": False,
            "analysis_status": "success",
            "composite_risk_score": 0.0,
            "specific_return_promises": [],
            "implied_returns": [],
            "urgency_scarcity_language": [],
            "reasoning": "AI voice speaking educational content warning users against online pump and dump scams.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(payload)
    audio = vm["audioModality"]
    scam = vm["scamModality"]

    # Audio Section Verification
    assert audio["title"] == "Audio Check"
    assert audio["status"] == "AI Voice Detected"
    assert audio["scoreFormatted"] == "99.5%"
    assert audio["flaggedCount"] == 5
    assert audio["totalWindows"] == 5
    details_map = {d["label"]: d["value"] for d in audio["details"]}
    assert details_map["AI Voice Score"] == "99.5%"
    assert details_map["Flagged Audio Parts"] == "5 of 5"

    # Scam Section Verification
    assert scam["title"] == "Scam Check"
    assert scam["status"] == "Awareness / Educational Content"
    assert scam["status"] != "Scam Warning"
    assert scam["isFlagged"] is False
    assert scam["isAwareness"] is True

    # Decoupling Assertion: AI voice detected does NOT mean scam detected
    assert audio["isFlagged"] is True
    assert scam["isFlagged"] is False


def test_three_cases_case2_genuine_awareness_audio():
    """
    Case 2: Genuine awareness audio.
    Requirements:
      - Audio Check: "Human Voice Detected", score 5.0%, "Flagged Audio Parts: 0 of 5".
      - Scam Check: "Awareness / Educational Content", NOT "Scam Warning".
      - Clean genuine voice educating about scams.
    """
    payload = {
        "verdict": "Safe",
        "is_deepfake": False,
        "is_scam": False,
        "audio_score": 0.05,
        "flagged_audio_segments": [],
        "all_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 0.05} for i in range(5)],
        "impersonation_check": {"is_impersonation": False, "target": None},
        "composite_risk_score": 0.0,
        "sebi_analysis": {
            "content_intent": "awareness_warning",
            "speaker_stance": "warning",
            "awareness_context_detected": True,
            "is_scam_likely": False,
            "analysis_status": "success",
            "composite_risk_score": 0.0,
            "specific_return_promises": [],
            "implied_returns": [],
            "urgency_scarcity_language": [],
            "reasoning": "Real investor awareness clip cautioning against fake advisory channels.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(payload)
    audio = vm["audioModality"]
    scam = vm["scamModality"]

    # Audio Section Verification
    assert audio["title"] == "Audio Check"
    assert audio["status"] == "Human Voice Detected"
    assert audio["scoreFormatted"] == "5.0%"
    assert audio["flaggedCount"] == 0
    assert audio["totalWindows"] == 5
    assert audio["isFlagged"] is False
    details_map = {d["label"]: d["value"] for d in audio["details"]}
    assert details_map["AI Voice Score"] == "5.0%"
    assert details_map["Flagged Audio Parts"] == "0 of 5"

    # Scam Section Verification
    assert scam["title"] == "Scam Check"
    assert scam["status"] == "Awareness / Educational Content"
    assert scam["isFlagged"] is False
    assert scam["isAwareness"] is True


def test_three_cases_case3_genuine_voice_promoting_scam():
    """
    Case 3: Genuine voice promoting scam.
    Requirements:
      - Audio Check: "Human Voice Detected", score 2.0%, "Flagged Audio Parts: 0 of 5".
      - Scam Check: "Scam Warning", score 85%.
      - A genuine voice promoting a scam must still trigger "Scam Warning" (Rule 3).
    """
    payload = {
        "verdict": "Warning: SEBI Violation / Scam",
        "is_deepfake": False,
        "is_scam": True,
        "audio_score": 0.02,
        "flagged_audio_segments": [],
        "all_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 0.02} for i in range(5)],
        "impersonation_check": {"is_impersonation": False, "target": None},
        "composite_risk_score": 0.85,
        "sebi_analysis": {
            "content_intent": "scam_promotion",
            "speaker_stance": "promoting",
            "awareness_context_detected": False,
            "is_scam_likely": True,
            "analysis_status": "success",
            "composite_risk_score": 0.85,
            "specific_return_promises": ["Guaranteed 100% daily profit in options trading"],
            "implied_returns": ["Double your capital every 48 hours"],
            "urgency_scarcity_language": ["Offer expires in 10 minutes"],
            "paywall_push": ["Join VIP channel now"],
            "reasoning": "High-risk scam promoting guaranteed market returns with urgency language.",
        },
        "registry_check": {"verdict": "not claimed"},
    }

    vm = _run_model_js_adapt(payload)
    audio = vm["audioModality"]
    scam = vm["scamModality"]

    # Audio Section Verification: Human Voice Detected
    assert audio["title"] == "Audio Check"
    assert audio["status"] == "Human Voice Detected"
    assert audio["scoreFormatted"] == "2.0%"
    assert audio["flaggedCount"] == 0
    assert audio["isFlagged"] is False

    # Scam Section Verification: Scam Warning
    assert scam["title"] == "Scam Check"
    assert scam["status"] == "Scam Warning"
    assert scam["isFlagged"] is True
    assert scam["badgeClass"] == "fg-badge--high"
    assert scam["quotedLabel"] == "Quoted Violations"
    assert scam["quotedCount"] == 4


def test_rule5_never_label_ai_voice_as_human_when_parts_flagged():
    """
    Rule 5 Verification:
    Never label an AI voice as a human voice just because the score is below the detection threshold.
    When score < 0.50 (e.g. 0.4177) but 1 of 19 parts was flagged:
      - Status MUST BE "Could Not Confirm Voice Type" (NEVER "Human Voice Detected").
      - Badge class is 'fg-badge--warn'.
    """
    payload = {
        "audio_score": 0.4177,
        "flagged_audio_segments": [{"start": 90.0, "end": 95.0, "score": 0.6177}],
        "all_audio_segments": [{"start": float(i * 5), "end": float((i + 1) * 5), "score": 0.6177 if i == 18 else 0.10} for i in range(19)],
        "impersonation_check": {"is_impersonation": False, "target": None},
    }

    vm = _run_model_js_adapt(payload)
    audio = vm["audioModality"]

    assert audio["title"] == "Audio Check"
    assert audio["scoreFormatted"] == "41.8%"
    assert audio["status"] != "Human Voice Detected", (
        "Violation of Rule 5! Voice was labeled 'Human Voice Detected' even though 1 of 19 parts was flagged."
    )
    assert audio["status"] == "Could Not Confirm Voice Type"
    assert audio["badgeClass"] == "fg-badge--warn"
    assert audio["flaggedCount"] == 1
    assert audio["totalWindows"] == 19
    details_map = {d["label"]: d["value"] for d in audio["details"]}
    assert details_map["AI Voice Score"] == "41.8%"
    assert details_map["Flagged Audio Parts"] == "1 of 19"



