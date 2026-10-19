"""
Stage 5 LLM Integration and Error/Fallback Regression Tests.
Tests:
1. Mocked error handling (timeout, connection error, malformed JSON).
2. Verification that analysis failure is never confused with verified low risk.
3. Live Ollama integration tests with realistic timeout for reported scam transcript and benign statements.
"""
import time
import pytest
import requests
from unittest.mock import patch, MagicMock

from src.stages.stage5_llm import run_stage5_llm


REPORTED_TRANSCRIPT = (
    "Hello, I am calling regarding urgent stock sell. "
    "This stock guarantees return of more than 40%. Call now."
)

BENIGN_TRANSCRIPT = (
    "The Reserve Bank of India kept the repo rate unchanged at 6.5 percent "
    "in today's monetary policy committee review."
)


# ── 1. Mocked Error & Fallback Status Tests ───────────────────────────────

def test_run_stage5_timeout_handling():
    """Verify that timeout is explicitly caught, sets fallback status, and does not silently report 0% risk."""
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out (timeout=45.0s)")):
        res = run_stage5_llm(REPORTED_TRANSCRIPT, "TEST-TIMEOUT")

    assert res["llm_used"] is False
    assert res["fallback_used"] is True
    assert res["analysis_status"] == "fallback_timeout"
    assert "timeout" in res["error"].lower()
    assert "HEURISTIC FALLBACK" in res["reasoning"]

    # Even on LLM timeout, heuristic fallback identifies the scam indicators
    assert res["is_scam_likely"] is True
    assert res["composite_risk_score"] > 0.0
    assert len(res["specific_return_promises"]) > 0
    assert len(res["urgency_scarcity_language"]) > 0


def test_run_stage5_connection_error_handling():
    """Verify that connection failure sets fallback_unavailable status."""
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused: port 11434")):
        res = run_stage5_llm(REPORTED_TRANSCRIPT, "TEST-CONN-ERR")

    assert res["llm_used"] is False
    assert res["fallback_used"] is True
    assert res["analysis_status"] == "fallback_unavailable"
    assert "unreachable" in res["error"].lower()
    assert "HEURISTIC FALLBACK" in res["reasoning"]
    assert res["is_scam_likely"] is True


def test_run_stage5_malformed_json_handling():
    """Verify that malformed LLM response triggers fallback_parse_error."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "Sorry, I cannot answer in valid JSON right now."}}
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp):
        res = run_stage5_llm(REPORTED_TRANSCRIPT, "TEST-PARSE-ERR")

    assert res["llm_used"] is False
    assert res["fallback_used"] is True
    assert res["analysis_status"] == "fallback_parse_error"
    assert "parse error" in res["error"].lower()
    assert res["is_scam_likely"] is True


def test_run_stage5_mocked_llm_success_with_mismatched_keys():
    """Verify that LLM output using descriptive keys is correctly normalized and scores computed."""
    mock_content = {
        "specific_return_promises": ["guarantees return of more than 40%"],
        "urgency_scarcity_language": ["urgent", "call now"],
        "social_proof_inflation": [],
        "paywall_push": [],
        "implied_returns": ["guarantees return"],
        "credential_misrepresentation": [],
        "signal_scores": {
            "specific_return_promises": 0.85,
            "urgency_scarcity_language": 0.70,
            "social_proof_inflation": 0.0,
            "paywall_push": 0.0,
            "implied_returns": 0.90,
            "credential_misrepresentation": 0.0,
        },
        "is_scam_likely": True,
        "reasoning": "High-risk scam promising guaranteed returns with high urgency."
    }
    mock_resp = MagicMock()
    import json
    mock_resp.json.return_value = {"message": {"content": json.dumps(mock_content)}}
    mock_resp.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_resp):
        res = run_stage5_llm(REPORTED_TRANSCRIPT, "TEST-MOCK-SUCCESS")

    assert res["llm_used"] is True
    assert res["fallback_used"] is False
    assert res["analysis_status"] == "success"
    assert res["error"] is None
    assert res["is_scam_likely"] is True
    # Normalized canonical keys
    assert res["signal_scores"]["explicit_returns"] == 0.85
    assert res["signal_scores"]["urgency_scarcity"] == 0.70
    assert res["signal_scores"]["implied_returns"] == 0.90
    # Composite calculation: 0.85*0.30 + 0.90*0.20 + 0.70*0.15 = 0.255 + 0.18 + 0.105 = 0.540
    assert res["composite_risk_score"] == 0.5400
    assert len(res["specific_return_promises"]) == 1
    assert len(res["urgency_scarcity_language"]) == 2


# ── 2. Live Ollama Integration Tests ──────────────────────────────────────

def _is_ollama_reachable():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _is_ollama_reachable(), reason="Local Ollama instance not reachable on port 11434")
def test_live_ollama_integration_reported_scam():
    """
    Live end-to-end integration test with the real local Ollama and llama3.1:latest.
    Measures latency and asserts model verdict, indicator extraction, and status.
    """
    t0 = time.time()
    res = run_stage5_llm(REPORTED_TRANSCRIPT, "LIVE-TEST-SCAM")
    elapsed = time.time() - t0

    print(f"\n[LIVE TEST] Inference completed in {elapsed:.2f}s")
    print(f"[LIVE TEST] Status: {res.get('analysis_status')}, LLM used: {res.get('llm_used')}")
    print(f"[LIVE TEST] Composite Risk Score: {res.get('composite_risk_score')}")
    print(f"[LIVE TEST] Detected Specific Returns: {res.get('specific_return_promises')}")
    print(f"[LIVE TEST] Detected Urgency Quotes: {res.get('urgency_scarcity_language')}")
    print(f"[LIVE TEST] Signal Scores: {res.get('signal_scores')}")

    assert res["llm_used"] is True
    assert res["fallback_used"] is False
    assert res["analysis_status"] == "success"
    assert res["error"] is None
    assert res["is_scam_likely"] is True
    assert res["composite_risk_score"] >= 0.35
    assert len(res["specific_return_promises"]) > 0
    assert len(res["urgency_scarcity_language"]) > 0
    assert res["signal_scores"]["explicit_returns"] > 0.0
    assert res["signal_scores"]["urgency_scarcity"] > 0.0


@pytest.mark.skipif(not _is_ollama_reachable(), reason="Local Ollama instance not reachable on port 11434")
def test_live_ollama_integration_benign_statement():
    """Live integration test asserting that benign statements do not produce false positives."""
    t0 = time.time()
    res = run_stage5_llm(BENIGN_TRANSCRIPT, "LIVE-TEST-BENIGN")
    elapsed = time.time() - t0

    print(f"\n[LIVE BENIGN TEST] Completed in {elapsed:.2f}s")
    print(f"[LIVE BENIGN TEST] Scam Likely: {res.get('is_scam_likely')}, Composite: {res.get('composite_risk_score')}")

    assert res["llm_used"] is True
    assert res["fallback_used"] is False
    assert res["analysis_status"] == "success"
    assert res["error"] is None
    assert res["is_scam_likely"] is False
    assert res["composite_risk_score"] < 0.35
