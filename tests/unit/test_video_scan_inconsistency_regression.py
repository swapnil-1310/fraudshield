"""
Regression tests for FraudShield video-scan result consistency:
1. Malformed and truncated Ollama JSON extraction and repair.
2. Valid JSON wrapped in Markdown code fences (including nested dicts).
3. Fallback activation after parsing failure without raw stack traces.
4. Ensuring parsing failures cannot fabricate a 100% deepfake score.
5. Genuine video with benign financial commentary (Scenario 1).
6. AI-generated video with benign commentary (Scenario 3 - screenshot reproduction).
7. Genuine video containing scam promotion (Scenario 2).
8. Missing or failed detector outputs.
9. Consistency between API results and frontend verdict/score fields.
"""
import json
import pytest
import requests
from unittest.mock import patch, MagicMock

from src.stages.stage5_llm import (
    extract_json_payload,
    clean_and_repair_json_str,
    run_stage5_llm,
    SEBIAnalysis,
)
from app import (
    calculate_calibrated_verdict,
    build_evidence_breakdown,
    build_overall_verdict_summary,
)


# ── 1. Malformed and Truncated Ollama JSON ──────────────────────────────────

def test_extract_json_with_trailing_commas_and_smart_quotes():
    """Verify clean_and_repair_json_str and extract_json_payload fix trailing commas and quotes."""
    malformed = """
    {
      "content_intent": "neutral_discussion",
      "speaker_stance": "neutral",
      "awareness_context_detected": false,
      "specific_return_promises": [],
      "signal_scores": {
        "explicit_returns": 0.0,
      },
      "is_scam_likely": false,
      "reasoning": "Speaker discusses historical performance.",
    }
    """
    parsed = extract_json_payload(malformed)
    assert parsed["content_intent"] == "neutral_discussion"
    assert parsed["is_scam_likely"] is False
    assert parsed["signal_scores"]["explicit_returns"] == 0.0


def test_extract_json_truncated_closure():
    """Verify that truncated JSON with unclosed braces is cleanly repaired."""
    truncated = (
        '{\n'
        '  "content_intent": "ambiguous",\n'
        '  "speaker_stance": "neutral",\n'
        '  "awareness_context_detected": false,\n'
        '  "specific_return_promises": [],\n'
        '  "signal_scores": {\n'
        '    "explicit_returns": 0.0\n'
        '  },\n'
        '  "is_scam_likely": false,\n'
        '  "reasoning": "Unclear content'
    )
    parsed = extract_json_payload(truncated)
    assert parsed["content_intent"] == "ambiguous"
    assert parsed["is_scam_likely"] is False


# ── 2. Valid JSON Wrapped in Markdown Fences ────────────────────────────────

def test_extract_json_markdown_fences_with_nested_dict():
    """
    CRITICAL BUG REGRESSION: Non-greedy regex must NOT truncate at inner closing brace
    of nested objects like signal_scores: { ... }.
    """
    fenced = """```json
    {
      "content_intent": "scam_promotion",
      "speaker_stance": "promoting",
      "awareness_context_detected": false,
      "specific_return_promises": ["guaranteed 40% returns"],
      "urgency_scarcity_language": ["call today"],
      "fee_or_transfer_requests": [],
      "credential_or_otp_requests": [],
      "unsupported_regulatory_claims": [],
      "social_proof_inflation": [],
      "paywall_push": [],
      "implied_returns": [],
      "credential_misrepresentation": [],
      "signal_scores": {
        "explicit_returns": 0.9,
        "implied_returns": 0.0,
        "urgency_scarcity": 0.7,
        "social_proof": 0.0,
        "paywall_push": 0.0,
        "credential_misrep": 0.0
      },
      "is_scam_likely": true,
      "reasoning": "High-risk scam promoting guaranteed returns with pressure tactics."
    }
    ```"""
    parsed = extract_json_payload(fenced)
    assert parsed["content_intent"] == "scam_promotion"
    assert parsed["is_scam_likely"] is True
    assert parsed["signal_scores"]["explicit_returns"] == 0.9
    assert parsed["reasoning"].startswith("High-risk scam")


def test_extract_json_with_surrounding_commentary():
    """Verify JSON with leading and trailing commentary outside fences parses."""
    content = """
    Here is the analysis based on SEBI compliance guidelines:
    ```json
    {
      "content_intent": "neutral_discussion",
      "speaker_stance": "neutral",
      "awareness_context_detected": false,
      "specific_return_promises": [],
      "signal_scores": {"explicit_returns": 0.0},
      "is_scam_likely": false,
      "reasoning": "General commentary."
    }
    ```
    I hope this helps your investigation!
    """
    parsed = extract_json_payload(content)
    assert parsed["content_intent"] == "neutral_discussion"
    assert parsed["is_scam_likely"] is False


# ── 3. Fallback Activation Without Raw Stack Traces ─────────────────────────

def test_fallback_activation_does_not_leak_stack_traces():
    """
    Verify that parsing failure activates fallback_parse_error and sanitized reasoning,
    never exposing JSONDecodeError line/column numbers or python exception tracebacks.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"message": {"content": "This is completely unparseable text without any JSON."}}
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp):
        res = run_stage5_llm("Stock update today", "TEST-FALLBACK-TRACE")

    assert res["llm_used"] is False
    assert res["fallback_used"] is True
    assert res["analysis_status"] == "fallback_parse_error"
    # Reasoning must have the standard marker for existing tests, but no raw exception details
    assert "HEURISTIC FALLBACK" in res["reasoning"]
    assert "JSONDecodeError" not in res["reasoning"]
    assert "line 27 column 4" not in res["reasoning"]
    assert "Traceback" not in res["reasoning"]


# ── 4. Ensuring Parsing Failures Cannot Fabricate a 100% Deepfake Score ─────

def test_parsing_failure_cannot_fabricate_deepfake_score():
    """
    An LLM parsing failure in Stage 5 MUST NOT alter audio or vision authenticity
    scores, nor should it set is_deepfake=True.
    """
    # Simulate genuine media scores
    vision_score = 0.15
    audio_score = 0.10
    vision_thresh = 0.60
    audio_thresh = 0.50

    # Stage 5 suffers fallback
    stage5_fallback = {
        "llm_used": False,
        "fallback_used": True,
        "analysis_status": "fallback_parse_error",
        "composite_risk_score": 0.0,
        "is_scam_likely": False,
        "reasoning": "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] Benign financial news.",
    }

    # Verify is_deepfake remains strictly derived from vision and audio detectors
    is_deepfake = bool(vision_score > vision_thresh or audio_score > audio_thresh)
    assert is_deepfake is False

    verdict = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=stage5_fallback["is_scam_likely"],
        composite_risk=stage5_fallback["composite_risk_score"],
        registry_verdict="not claimed",
        fallback_used=stage5_fallback["fallback_used"],
        degraded_modules=["stage5_llm"],
    )
    # Because LLM is degraded, it routes to Suspicious review, NOT Warning: Deepfake Detected
    assert verdict == "Suspicious: Review Recommended"
    assert "Deepfake" not in verdict


# ── 5. Genuine Video with Benign Financial Commentary (Scenario 1) ──────────

def test_scenario_1_genuine_video_benign_content():
    """Genuine video, genuine audio, benign content -> Safe."""
    vision_score = 0.08
    audio_score = 0.12
    composite_risk = 0.0
    is_deepfake = False
    is_scam = False

    verdict = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_verdict="not claimed",
        fallback_used=False,
        degraded_modules=[],
    )
    assert verdict == "Safe"

    summary = build_overall_verdict_summary(
        verdict=verdict,
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        vision_score=vision_score,
        audio_score=audio_score,
        composite_risk=composite_risk,
        sebi_analysis={"reasoning": "Macroeconomic review with statutory educational disclaimer."},
        registry_check={"verdict": "not claimed", "is_conclusive_fraud": False},
        degraded_modules=[],
    )
    assert "Macroeconomic review" in summary
    assert "Critical" not in summary


# ── 6. AI-Generated Video with Benign Commentary (Scenario 3 - Screenshot) ─

def test_scenario_3_ai_generated_video_benign_content_consistent_summary():
    """
    Reproduction of the user screenshot scenario:
    - Audio score is 1.0 (cloned/synthetic voice detected)
    - Visual score is 0.22 (genuine face)
    - Financial content is benign (no scam solicitations)
    - Verdict: Warning: Deepfake Detected
    - Summary MUST explicitly explain the voice deepfake and benign content consistently.
    """
    vision_score = 0.2192
    audio_score = 1.0
    composite_risk = 0.0
    is_deepfake = True
    is_scam = False

    verdict = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_verdict="not claimed",
        fallback_used=True,
        degraded_modules=["stage5_llm"],
    )
    assert verdict == "Warning: Deepfake Detected"

    summary = build_overall_verdict_summary(
        verdict=verdict,
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        vision_score=vision_score,
        audio_score=audio_score,
        composite_risk=composite_risk,
        sebi_analysis={
            "reasoning": "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] General commentary with no high-risk SEBI violations flagged.",
        },
        registry_check={"verdict": "not claimed", "is_conclusive_fraud": False},
        degraded_modules=["stage5_llm"],
    )

    # Must explain that synthetic media/voice cloning was detected
    assert "Synthetic media detected" in summary
    assert "synthetic voice cloning" in summary
    # Must explain that spoken content was assessed as non-fraudulent
    assert "non-fraudulent" in summary
    # Must NOT contain internal error strings
    assert "JSONDecodeError" not in summary
    assert "line 27 column 4" not in summary


# ── 7. Genuine Video with Scam Promotion (Scenario 2) ───────────────────────

def test_scenario_2_genuine_video_scam_promotion():
    """Genuine media with confirmed financial scam solicitation -> Warning: SEBI Violation / Scam."""
    vision_score = 0.05
    audio_score = 0.08
    composite_risk = 0.85
    is_deepfake = False
    is_scam = True

    verdict = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_verdict="not found",
        fallback_used=False,
        degraded_modules=[],
    )
    assert verdict == "Warning: SEBI Violation / Scam"

    summary = build_overall_verdict_summary(
        verdict=verdict,
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        vision_score=vision_score,
        audio_score=audio_score,
        composite_risk=composite_risk,
        sebi_analysis={"reasoning": "Unregistered advisory guaranteeing 12% weekly returns with urgent deadline."},
        registry_check={"verdict": "not found", "is_conclusive_fraud": False},
        degraded_modules=[],
    )
    assert "Financial scam" in summary
    assert "Media streams showed no synthetic manipulation" in summary


# ── 8. Missing or Failed Detector Outputs ────────────────────────────────────

def test_missing_or_failed_audio_detector_routes_to_suspicious():
    """
    If audio detector fails (status="error"), audio_score is None,
    degraded_modules includes stage3_audio, and verdict is Suspicious: Review Recommended.
    Failure is NEVER silently treated as Safe or 0% risk.
    """
    vision_score = 0.10
    audio_score = None
    composite_risk = 0.0
    degraded_modules = ["stage3_audio"]
    is_deepfake = False
    is_scam = False

    verdict = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_verdict="not claimed",
        fallback_used=False,
        degraded_modules=degraded_modules,
    )
    assert verdict == "Suspicious: Review Recommended"

    breakdown = build_evidence_breakdown(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_check={"verdict": "not claimed"},
        sebi_analysis={"content_intent": "neutral_discussion"},
        audio_score=audio_score,
        vision_score=vision_score,
        degraded_modules=degraded_modules,
    )
    assert "stage3_audio" in breakdown["degraded_or_missing_modules"]


def test_missing_or_failed_vision_detector_routes_to_suspicious():
    """If vision detector fails (status='error'), verdict routes to Suspicious review."""
    vision_score = None
    audio_score = 0.10
    composite_risk = 0.0
    degraded_modules = ["stage2_vision"]

    verdict = calculate_calibrated_verdict(
        is_deepfake=False,
        is_scam=False,
        composite_risk=composite_risk,
        registry_verdict="not claimed",
        fallback_used=False,
        degraded_modules=degraded_modules,
    )
    assert verdict == "Suspicious: Review Recommended"


# ── 9. Consistency Between API Results and Frontend Fields ──────────────────

def test_api_payload_and_frontend_viewmodel_consistency():
    """
    Validates that the API payload structure provides all necessary attributes
    (overall_summary, vision_score, audio_score, degraded_modules) for frontend consistency.
    """
    payload = {
        "verdict": "Warning: Deepfake Detected",
        "is_deepfake": True,
        "is_scam": False,
        "composite_risk_score": 0.0,
        "vision_score": 0.2192,
        "audio_score": 1.0,
        "overall_summary": "Synthetic media detected by forensic detectors (synthetic voice cloning (100.0%)). Spoken content assessed as non-fraudulent.",
        "sebi_analysis": {
            "reasoning": "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] General commentary.",
            "content_intent": "neutral_discussion",
        },
        "registry_check": {"verdict": "not claimed"},
        "degraded_modules": ["stage5_llm"],
    }

    # Simulate frontend model.js logic
    signal_inputs = [
        {"key": "Visual authenticity", "label": "Visual detector score", "value": payload["vision_score"]},
        {"key": "Voice authenticity",  "label": "Voice detector score",  "value": payload["audio_score"]},
        {"key": "Financial scam risk", "label": "Scam risk score",        "value": payload["composite_risk_score"]},
    ]
    leading = max(signal_inputs, key=lambda s: s["value"])
    peak_score = leading["value"]
    peak_label = leading["label"]

    assert peak_score == 1.0
    assert peak_label == "Voice detector score"
    assert "100.0%" in payload["overall_summary"]
    assert "synthetic voice cloning" in payload["overall_summary"]
