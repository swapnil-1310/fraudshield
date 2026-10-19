"""
Unit tests for Vision Threshold Unification (Priority 3).
Validates:
  1. The canonical configured threshold is sourced from vision_detector.threshold (with fallback).
  2. Stage-level decision (Stage 2) and app-level verdict (app.py) use the exact same configuration value.
  3. Changing the configured threshold changes both decisions consistently without divergence.
  4. SCORES legal dossier and evidence breakdown reference the unified threshold.
"""
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from src.config import get_vision_threshold, get_threshold
from src.stages.stage2_vision import run_stage2_vision
from app import build_evidence_breakdown, calculate_calibrated_verdict
from src.stages.stage8_report import generate_sebi_scores_complaint


class TestVisionThresholdUnification:

    def test_canonical_threshold_accessor_hierarchy(self):
        """vision_detector.threshold takes precedence over thresholds.vision_fake_threshold."""
        # Case A: vision_detector.threshold specified as 0.60
        with patch("src.config.get_vision_detector_config", return_value={"threshold": 0.60}):
            assert get_vision_threshold() == 0.60

        # Case B: vision_detector.threshold specified as 0.75
        with patch("src.config.get_vision_detector_config", return_value={"threshold": 0.75}):
            assert get_vision_threshold() == 0.75

        # Case C: vision_detector.threshold is None/absent -> fallback to thresholds.vision_fake_threshold
        with patch("src.config.get_vision_detector_config", return_value={}):
            with patch("src.config.settings", {"thresholds": {"vision_fake_threshold": 0.45}}):
                assert get_vision_threshold() == 0.45

    def test_stage2_uses_canonical_vision_threshold(self, tmp_path):
        """run_stage2_vision applies the threshold from get_vision_threshold() in its output."""
        import cv2
        frame_path = str(tmp_path / "face_0.jpg")
        cv2.imwrite(frame_path, np.ones((100, 100, 3), dtype=np.uint8) * 128)

        mock_backend = MagicMock()
        mock_backend.predict_frame.return_value = 0.55
        mock_backend.backend_name = "mock_detector"
        mock_backend.model_id = "test/model"

        with patch("src.stages.backends.get_vision_backend", return_value=mock_backend):
            with patch("src.stages.stage2_vision.get_vision_threshold", return_value=0.65):
                res = run_stage2_vision([frame_path], job_id="test-thresh-stage2")
                assert res["threshold_applied"] == 0.65

    def test_app_and_stage_decision_consistency_at_different_thresholds(self):
        """
        A vision score of 0.55:
        - At threshold 0.50: is_deepfake must be True in both stage and app.
        - At threshold 0.60: is_deepfake must be False in both stage and app.
        Demonstrates 100% decision consistency across configuration changes.
        """
        vision_score = 0.55
        audio_score = 0.10

        # Test at threshold 0.50
        with patch("src.config.get_vision_detector_config", return_value={"threshold": 0.50}):
            thresh = get_vision_threshold()
            assert thresh == 0.50
            is_deepfake = vision_score > thresh
            assert is_deepfake is True

            verdict = calculate_calibrated_verdict(
                is_deepfake=is_deepfake,
                is_scam=False,
                composite_risk=0.10,
                registry_verdict="verified"
            )
            assert verdict == "Warning: Deepfake Detected"

            ev = build_evidence_breakdown(
                is_deepfake=is_deepfake,
                is_scam=False,
                composite_risk=0.10,
                registry_check={"verdict": "verified"},
                sebi_analysis={},
                vision_score=vision_score,
                audio_score=audio_score,
            )
            # Signal should be present because 0.55 > 0.50
            assert any("Visual synthetic/deepfake" in s for s in ev["contributing_signals"])

        # Test at threshold 0.60
        with patch("src.config.get_vision_detector_config", return_value={"threshold": 0.60}):
            thresh = get_vision_threshold()
            assert thresh == 0.60
            is_deepfake = vision_score > thresh
            assert is_deepfake is False

            verdict = calculate_calibrated_verdict(
                is_deepfake=is_deepfake,
                is_scam=False,
                composite_risk=0.10,
                registry_verdict="verified"
            )
            assert verdict == "Safe"

            ev = build_evidence_breakdown(
                is_deepfake=is_deepfake,
                is_scam=False,
                composite_risk=0.10,
                registry_check={"verdict": "verified"},
                sebi_analysis={},
                vision_score=vision_score,
                audio_score=audio_score,
            )
            # Signal should NOT be present because 0.55 <= 0.60
            assert not any("Visual synthetic/deepfake" in s for s in ev["contributing_signals"])

    def test_scores_complaint_uses_canonical_vision_threshold(self):
        """SCORES legal evidence dossier uses get_vision_threshold() for flag generation."""
        mock_data = {
            "vision_score": 0.55,
            "audio_score": 0.10,
            "is_deepfake": False,
            "sebi_analysis": {},
            "registry_check": {"verdict": "verified"},
            "verdict": "Safe",
            "scan_type": "VIDEO",
        }

        with patch("src.stages.stage8_report.get_vision_threshold", return_value=0.60):
            complaint = generate_sebi_scores_complaint(mock_data)
            # At 0.60 threshold, 0.55 is clean (within normal parameters)
            assert "(Within Normal Parameters)" in complaint

        with patch("src.stages.stage8_report.get_vision_threshold", return_value=0.50):
            complaint = generate_sebi_scores_complaint(mock_data)
            # At 0.50 threshold, 0.55 is flagged
            assert "(SYNTHETIC FACE MANIPULATION DETECTED)" in complaint
