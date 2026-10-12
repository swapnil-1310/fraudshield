"""
Unit tests for calculate_calibrated_verdict pure logic truth table.
Tests behavior exactly as implemented in app.py today.
"""
import pytest

from app import calculate_calibrated_verdict


@pytest.mark.parametrize(
    "is_deepfake,is_scam,composite_risk,registry_verdict,expected",
    [
        # Branch 1: Critical — Deepfake + Scam
        (True, True, 0.9, "verified", "Critical: Deepfake + Scam"),
        (True, True, 0.1, "not claimed", "Critical: Deepfake + Scam"),
        (True, True, 0.0, "not found", "Critical: Deepfake + Scam"),
        # Branch 2: Warning — Deepfake only
        (True, False, 0.1, "verified", "Warning: Deepfake Detected"),
        (True, False, 0.8, "verified", "Warning: Deepfake Detected"),
        (True, False, 0.0, "not found", "Warning: Deepfake Detected"),
        # Branch 3: Warning — SEBI Scam or Registry Violation
        (False, True, 0.9, "verified", "Warning: SEBI Violation / Scam"),
        (False, True, 0.1, "verified", "Warning: SEBI Violation / Scam"),
        (False, False, 0.1, "not found", "Warning: SEBI Violation / Scam"),
        (False, False, 0.1, "name-number mismatch", "Warning: SEBI Violation / Scam"),
        (False, False, 0.1, "malformed number", "Warning: SEBI Violation / Scam"),
        # Branch 4: Suspicious — Composite risk >= 0.35 (ambiguity band)
        (False, False, 0.35, "verified", "Suspicious: Review Recommended"),
        (False, False, 0.50, "verified", "Suspicious: Review Recommended"),
        (False, False, 0.65, "not claimed", "Suspicious: Review Recommended"),
        (False, False, 0.99, "verified", "Suspicious: Review Recommended"),
        # Branch 5: Safe — Clean content with composite risk < 0.35
        (False, False, 0.0, "verified", "Safe"),
        (False, False, 0.20, "verified", "Safe"),
        (False, False, 0.349, "verified", "Safe"),
        (False, False, 0.10, "not claimed", "Safe"),
    ],
)
def test_calculate_calibrated_verdict_matrix(
    is_deepfake, is_scam, composite_risk, registry_verdict, expected
):
    actual = calculate_calibrated_verdict(
        is_deepfake=is_deepfake,
        is_scam=is_scam,
        composite_risk=composite_risk,
        registry_verdict=registry_verdict,
    )
    assert actual == expected
