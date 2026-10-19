"""
Unit tests for calculate_calibrated_verdict pure logic truth table.

Registry signal policy (P1 fix):
  - "not found" / "malformed number" alone  → Suspicious: Review Recommended
  - "name-number mismatch" alone            → Warning: SEBI Violation / Scam
  - is_scam=True (any registry verdict)     → Warning: SEBI Violation / Scam
  - "verified" / "not claimed" clean        → composite_risk path or Safe
"""
import pytest

from app import calculate_calibrated_verdict


@pytest.mark.parametrize(
    "is_deepfake,is_scam,composite_risk,registry_verdict,expected",
    [
        # ── Branch 1: Critical — Deepfake + Scam ──────────────────────────────
        (True, True, 0.9, "verified",      "Critical: Deepfake + Scam"),
        (True, True, 0.1, "not claimed",   "Critical: Deepfake + Scam"),
        (True, True, 0.0, "not found",     "Critical: Deepfake + Scam"),
        # ── Branch 2: Warning — Deepfake only ────────────────────────────────
        (True, False, 0.1, "verified",     "Warning: Deepfake Detected"),
        (True, False, 0.8, "verified",     "Warning: Deepfake Detected"),
        # not-found + deepfake (no scam) → deepfake branch wins
        (True, False, 0.0, "not found",    "Warning: Deepfake Detected"),
        # ── Branch 3a: Warning — confirmed financial scam ────────────────────
        (False, True, 0.9, "verified",     "Warning: SEBI Violation / Scam"),
        (False, True, 0.1, "verified",     "Warning: SEBI Violation / Scam"),
        # is_scam=True overrides even a clean registry verdict
        (False, True, 0.0, "not claimed",  "Warning: SEBI Violation / Scam"),
        # is_scam=True + not-found → scam branch wins (not just Suspicious)
        (False, True, 0.0, "not found",    "Warning: SEBI Violation / Scam"),
        # ── Branch 3b: Warning — active impersonation (name-number mismatch) ─
        # Mismatch alone is an active impersonation signal → Warning
        (False, False, 0.1, "name-number mismatch", "Warning: SEBI Violation / Scam"),
        (False, False, 0.0, "name-number mismatch", "Warning: SEBI Violation / Scam"),
        # ── Branch 4: Suspicious — absent/unverifiable registry alone ────────
        # "not found" alone (no scam, no deepfake) → Suspicious, NOT Warning
        (False, False, 0.1, "not found",    "Suspicious: Review Recommended"),
        (False, False, 0.0, "not found",    "Suspicious: Review Recommended"),
        # "malformed number" alone → Suspicious, NOT Warning
        (False, False, 0.1, "malformed number", "Suspicious: Review Recommended"),
        (False, False, 0.0, "malformed number", "Suspicious: Review Recommended"),
        # ── Branch 4: Suspicious — composite risk ambiguity band ─────────────
        (False, False, 0.35, "verified",   "Suspicious: Review Recommended"),
        (False, False, 0.50, "verified",   "Suspicious: Review Recommended"),
        (False, False, 0.65, "not claimed","Suspicious: Review Recommended"),
        (False, False, 0.99, "verified",   "Suspicious: Review Recommended"),
        # ── Branch 5: Safe — clean content ───────────────────────────────────
        (False, False, 0.0,   "verified",  "Safe"),
        (False, False, 0.20,  "verified",  "Safe"),
        (False, False, 0.349, "verified",  "Safe"),
        (False, False, 0.10,  "not claimed","Safe"),
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
    assert actual == expected, (
        f"Expected '{expected}' but got '{actual}' for "
        f"(deepfake={is_deepfake}, scam={is_scam}, risk={composite_risk}, "
        f"registry='{registry_verdict}')"
    )
