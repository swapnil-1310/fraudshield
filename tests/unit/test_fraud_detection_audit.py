"""
Unit tests auditing and validating financial fraud detection in FraudShield.
Covers:
1. Benign financial education vs scam detection.
2. Guaranteed/unrealistic return promises.
3. Urgency, pressure, and immediate action tactics.
4. Requests for fund transfers, advance fees, and deposit margin.
5. Requests for credentials, OTPs, and remote screen sharing.
6. Impersonation of regulators and unsupported claims of SEBI approval.
7. Decoupling of media authenticity from financial fraud risk.
8. LLM unavailable/degraded state handling (never silently safe).
9. SEBI registry matching communication (confirmed, uncertain, absent).
10. Evidence breakdown aggregation and transparency.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.stages.stage5_llm import (
    heuristic_sebi_analysis,
    run_stage5_llm,
    normalize_signal_scores,
    compute_composite_score,
    SIGNAL_WEIGHTS,
)
from src.stages.stage6_registry import run_stage6_registry
from app import calculate_calibrated_verdict, build_evidence_breakdown


# ── 1. Benign Financial Education ───────────────────────────────────────────

def test_benign_financial_education_not_flagged():
    """Legitimate financial education and speaker introductions must not be flagged."""
    benign_texts = [
        (
            "Hello everyone, my name is Arvind, and today we discuss the power of compounding. "
            "By investing regularly in diversified broad market index funds over 15 to 20 years, "
            "investors have historically built wealth. Remember that equity investments are subject "
            "to market fluctuations and past performance does not guarantee future results."
        ),
        (
            "Today we will understand the difference between debt mutual funds and fixed deposits. "
            "Fixed deposits offer capital safety with bank insurance up to 5 lakh rupees, while debt "
            "funds carry interest rate risk. Read the scheme information document carefully before investing."
        ),
    ]
    for text in benign_texts:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["is_scam_likely"] is False, f"Benign education flagged as scam: {text[:50]}"
        assert res["composite_risk_score"] < 0.35
        assert len(res["specific_return_promises"]) == 0
        assert len(res["fee_or_transfer_requests"]) == 0
        assert len(res["credential_or_otp_requests"]) == 0
        assert len(res["unsupported_regulatory_claims"]) == 0
        # Speaker introduction should not be falsely extracted as an unverified advisor
        assert res["claimed_advisor_name"] is None

        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=res["is_scam_likely"],
            composite_risk=res["composite_risk_score"],
            registry_verdict="not claimed",
            fallback_used=False
        )
        assert verdict == "Safe"


# ── 2. Guaranteed-Return Scams ─────────────────────────────────────────────

def test_guaranteed_return_scam_detection():
    """Guaranteed returns or promised high returns must be detected as scam indicators."""
    scam_texts = [
        "Join our VIP channel! We offer 100% loss recovery with 40% guaranteed returns every month.",
        "Paisa double strategy in just 15 days, sure-shot profit guaranteed by top traders.",
        "Invest 50,000 rupees today and get guaranteed returns of 25% weekly, zero risk involved.",
    ]
    for text in scam_texts:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["is_scam_likely"] is True, f"Guaranteed return not flagged: {text[:50]}"
        assert res["signal_scores"]["explicit_returns"] >= 0.8
        assert len(res["specific_return_promises"]) > 0

        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=res["is_scam_likely"],
            composite_risk=res["composite_risk_score"],
            registry_verdict="not claimed"
        )
        assert verdict == "Warning: SEBI Violation / Scam"


# ── 3. Urgent Investment Pitches ───────────────────────────────────────────

def test_urgent_investment_pitch_detection():
    """Manufactured urgency and pressure tactics must be extracted."""
    urgent_texts = [
        "Urgent stock call! Act now before market opens. Only 5 slots remaining, closing soon!",
        "Hurry up! Don't wait, buy immediately, this is your last chance for explosive gains!",
    ]
    for text in urgent_texts:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["signal_scores"]["urgency_scarcity"] >= 0.8
        assert len(res["urgency_scarcity_language"]) > 0


# ── 4. Requests to Transfer Money or Pay Suspicious Fees ────────────────────

def test_fee_and_money_transfer_requests():
    """Advance fee demands, withdrawal charges, or transfer requests must be detected."""
    fee_scams = [
        "Your account has earned 4 Lakh profit. Transfer money to pay 10% advance fee to withdraw your gains.",
        "Deposit margin of 25,000 rupees immediately to our UPI account to release your locked profits.",
        "Pay registration charges of Rs 2999 to unlock your premium account and start receiving tips.",
    ]
    for text in fee_scams:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["is_scam_likely"] is True, f"Fee scam not flagged: {text[:50]}"
        assert res["signal_scores"]["paywall_push"] >= 0.8
        assert len(res["fee_or_transfer_requests"]) > 0
        assert any(
            any(w in q.lower() for w in ["fee", "deposit", "transfer", "charges", "pay"])
            for q in res["fee_or_transfer_requests"]
        )


# ── 5. Requests for OTPs, Credentials, or Remote Access ─────────────────────

def test_credential_and_otp_requests():
    """Requests for OTPs, Demat passwords, MPIN, or remote control software must be detected."""
    credential_scams = [
        "Please share your OTP so we can activate auto-algo trading in your Demat account.",
        "Send your Demat password and MPIN to our executive to verify your portfolio.",
        "Kindly install AnyDesk so our technical advisor can remotely setup the high-frequency trading bot.",
        "Download TeamViewer and share your screen to complete instant KYC verification.",
    ]
    for text in credential_scams:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["is_scam_likely"] is True, f"Credential request not flagged: {text[:50]}"
        assert res["signal_scores"]["credential_misrep"] >= 0.9
        assert len(res["credential_or_otp_requests"]) > 0


# ── 6. Regulatory Impersonation and Unsupported SEBI Claims ────────────────

def test_regulatory_impersonation():
    """Impersonation of SEBI, RBI, or claims of government-guaranteed stock returns must be flagged."""
    impersonation_texts = [
        "I am calling from SEBI headquarters to alert you of a government approved guaranteed returns scheme.",
        "This special trading fund is authorized by RBI to promise 30% risk-free monthly gains.",
        "I am an official SEBI officer providing direct insider recommendations.",
    ]
    for text in impersonation_texts:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["is_scam_likely"] is True, f"Impersonation not flagged: {text[:50]}"
        assert res["signal_scores"]["credential_misrep"] >= 0.8
        assert len(res["unsupported_regulatory_claims"]) > 0


# ── 7. Decoupling: Media Authenticity vs Financial Fraud Risk ──────────────

def test_synthetic_voice_with_benign_speech():
    """A synthetic/deepfake voice must NOT automatically mean financial fraud."""
    # Scenario: AI synthetic voice reading a standard mutual fund educational script
    is_deepfake = True
    is_scam = False
    composite_risk = 0.05
    registry_verdict = "not claimed"

    verdict = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_verdict=registry_verdict
    )
    # Must report deepfake media without falsely claiming financial fraud
    assert verdict == "Warning: Deepfake Detected"

    breakdown = build_evidence_breakdown(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_check={"verdict": registry_verdict},
        sebi_analysis={"is_scam_likely": False},
        audio_score=0.92,
        vision_score=0.0
    )
    assert breakdown["media_authenticity"]["is_deepfake"] is True
    assert breakdown["financial_fraud"]["is_scam"] is False
    assert breakdown["financial_fraud"]["assessment"] == "No financial fraud detected"


def test_genuine_voice_with_scam_content():
    """A genuine human voice must NOT automatically mean safe."""
    # Scenario: A real human voice executing an advance fee scam
    is_deepfake = False
    is_scam = True
    composite_risk = 0.85
    registry_verdict = "not claimed"

    verdict = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_verdict=registry_verdict
    )
    # Must report scam violation despite genuine media
    assert verdict == "Warning: SEBI Violation / Scam"

    breakdown = build_evidence_breakdown(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_check={"verdict": registry_verdict},
        sebi_analysis={"is_scam_likely": True, "fee_or_transfer_requests": ["transfer fee"]},
        audio_score=0.05,
        vision_score=0.0
    )
    assert breakdown["media_authenticity"]["is_deepfake"] is False
    assert breakdown["financial_fraud"]["is_scam"] is True


def test_synthetic_voice_with_scam_content():
    """Both synthetic media and financial fraud combine into Critical tier."""
    verdict = calculate_calibrated_verdict(
        is_deepfake=True,
        is_scam=True,
        composite_risk=0.90,
        registry_verdict="not claimed"
    )
    assert verdict == "Critical: Deepfake + Scam"


# ── 8. LLM Degraded State Handling (Never Silently Safe) ───────────────────

def test_llm_degraded_state_never_silently_safe():
    """When LLM is unavailable or fails, fallback must be reported and never silently return Safe."""
    # Text with ambiguous language where heuristic baseline finds no overt keywords
    neutral_text = "Let us observe the trading volumes of midcap stocks today."

    with patch("requests.post", side_effect=Exception("Connection refused")):
        res = run_stage5_llm(neutral_text, "TEST-FALLBACK")

    assert res["llm_used"] is False
    assert res["fallback_used"] is True
    assert "fallback" in res["analysis_status"]

    # In app.py verdict calculation, fallback_used prevents silent "Safe"
    verdict = calculate_calibrated_verdict(
        is_deepfake=False,
        is_scam=res["is_scam_likely"],
        composite_risk=res["composite_risk_score"],
        registry_verdict="not claimed",
        fallback_used=res["fallback_used"],
        degraded_modules=["stage5_llm"]
    )
    assert verdict == "Suspicious: Review Recommended"
    assert verdict != "Safe"

    evidence = build_evidence_breakdown(
        is_deepfake=False,
        is_scam=res["is_scam_likely"],
        composite_risk=res["composite_risk_score"],
        registry_check={"verdict": "not claimed"},
        sebi_analysis=res,
        degraded_modules=["stage5_llm"]
    )
    assert len(evidence["degraded_or_missing_modules"]) > 0
    assert any("offline/degraded" in m for m in evidence["degraded_or_missing_modules"])


# ── 9. SEBI Registry Match Communication ───────────────────────────────────

def test_sebi_registry_match_states():
    """SEBI registry cross-check communicates confirmed, uncertain, and absent states properly."""
    # Case A: Confirmed match
    confirmed = run_stage6_registry(
        {"claimed_advisor_name": "Zerodha", "claimed_registration_number": "INZ000031633"},
        job_id="test-confirmed"
    )
    assert confirmed["verdict"] == "verified"
    assert confirmed["match_status"] == "confirmed"
    assert confirmed["entity_type"] == "Stock Broker / RIA"
    assert confirmed["is_conclusive_fraud"] is False

    # Case B: Uncertain match (Name-number mismatch)
    uncertain = run_stage6_registry(
        {"claimed_advisor_name": "Unknown Fake Analyst", "claimed_registration_number": "INZ000031633"},
        job_id="test-uncertain"
    )
    assert uncertain["verdict"] == "name-number mismatch"
    assert uncertain["match_status"] == "uncertain"
    assert uncertain["entity_type"] == "Stock Broker / RIA"

    # Case C: Absent match
    absent = run_stage6_registry(
        {"claimed_advisor_name": "Unknown Unregistered Entity", "claimed_registration_number": "INA999999999"},
        job_id="test-absent"
    )
    assert absent["verdict"] == "not found"
    assert absent["match_status"] == "absent"
    # Crucial requirement: An absent match alone is NOT conclusive proof of fraud
    assert absent["is_conclusive_fraud"] is False
    assert "absence alone is not conclusive" in absent["explanation"].lower()


# ── 10. Canonical Scoring Invariant ────────────────────────────────────────

def test_canonical_scoring_preserves_dimensions():
    """Ensure signal score normalization preserves exactly 6 canonical dimensions without distortion."""
    scores = {
        "specific_return_promises": 0.85,
        "fee_or_transfer_requests": 0.90,
        "credential_or_otp_requests": 0.95,
        "unsupported_regulatory_claims": 0.80,
    }
    normalized = normalize_signal_scores(scores, default_all_zero=True)
    assert len(normalized) == 6
    assert normalized["explicit_returns"] == 0.85
    assert normalized["paywall_push"] == 0.90
    assert normalized["credential_misrep"] == 0.95
