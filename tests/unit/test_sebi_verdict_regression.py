"""
Regression tests for SEBI registry verdict calibration logic.
Validates:
  1. An absent registry record ("not found") must NOT independently prove fraud.
  2. Confirmed registration ("verified") routes clean content to Safe.
  3. Active impersonation ("name-number mismatch") routes to Warning even without explicit scam.
  4. Inconclusive/absent records ("not found", "malformed number", "uncertain match")
     without supporting scam signals route to Suspicious (Review Recommended).
  5. Genuine scam evidence (is_scam=True) always produces Warning or Critical,
     never downgraded by registry status.
  6. Deepfake detection is independent from financial fraud signals.
"""
import pytest
from app import calculate_calibrated_verdict


class TestSebiRegistryVerdictRegression:

    def test_registered_adviser_clean_content_is_safe(self):
        """A registered advisor with no scam or deepfake signals is classified as Safe."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=False,
            composite_risk=0.10,
            registry_verdict="verified",
        )
        assert verdict == "Safe"

    def test_registered_adviser_with_scam_is_warning(self):
        """Even a verified adviser who engages in scam practices receives a Warning."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=True,
            composite_risk=0.85,
            registry_verdict="verified",
        )
        assert verdict == "Warning: SEBI Violation / Scam"

    def test_absent_registry_alone_does_not_prove_fraud(self):
        """Absence from the local registry snapshot must NOT produce a definitive Scam Warning."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=False,
            composite_risk=0.15,
            registry_verdict="not found",
        )
        assert verdict == "Suspicious: Review Recommended"
        assert verdict != "Warning: SEBI Violation / Scam"

    def test_absent_registry_with_scam_escalates_to_warning(self):
        """When an unregistered entity promises guaranteed returns (is_scam=True), it is a Warning."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=True,
            composite_risk=0.80,
            registry_verdict="not found",
        )
        assert verdict == "Warning: SEBI Violation / Scam"

    def test_uncertain_match_routes_to_suspicious(self):
        """Uncertain/partial name match without scam evidence routes to Suspicious review."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=False,
            composite_risk=0.20,
            registry_verdict="uncertain match",
        )
        assert verdict == "Suspicious: Review Recommended"

    def test_uncertain_match_with_scam_routes_to_warning(self):
        """Uncertain match with scam content routes to Warning."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=True,
            composite_risk=0.75,
            registry_verdict="uncertain match",
        )
        assert verdict == "Warning: SEBI Violation / Scam"

    def test_malformed_number_alone_routes_to_suspicious(self):
        """Malformed registration format without scam signals routes to Suspicious for verification."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=False,
            composite_risk=0.10,
            registry_verdict="malformed number",
        )
        assert verdict == "Suspicious: Review Recommended"

    def test_name_number_mismatch_active_impersonation_is_warning(self):
        """Name-number mismatch is active impersonation and produces a Warning even if is_scam=False."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=False,
            composite_risk=0.15,
            registry_verdict="name-number mismatch",
        )
        assert verdict == "Warning: SEBI Violation / Scam"

    def test_name_number_mismatch_with_deepfake_is_critical(self):
        """Active impersonation + deepfake generates Critical when combined with scam signals."""
        verdict = calculate_calibrated_verdict(
            is_deepfake=True,
            is_scam=True,
            composite_risk=0.90,
            registry_verdict="name-number mismatch",
        )
        assert verdict == "Critical: Deepfake + Scam"

    def test_independently_established_scam_never_downgraded(self):
        """Confirmed scam behavior is never weakened by any registry outcome."""
        for reg in ["verified", "not claimed", "not found", "uncertain match", "malformed number"]:
            verdict = calculate_calibrated_verdict(
                is_deepfake=False,
                is_scam=True,
                composite_risk=0.90,
                registry_verdict=reg,
            )
            assert verdict == "Warning: SEBI Violation / Scam", (
                f"Failed for registry_verdict='{reg}'"
            )
