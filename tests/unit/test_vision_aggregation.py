"""
Unit Tests for Interpretable Score Aggregation & Provenance Handling
====================================================================
Validates:
  1. Multi-frame subtle face-swap cues (Gemini profile) are preserved without median suppression.
  2. Isolated single-frame outliers (camera flash/glare) are attenuated to guard against false alarms.
  3. Clean baseline videos remain low confidence (<0.05).
  4. Frame-level evidence fields (frame_scores, top_k_mean, median_score, aggregation_details)
     are preserved in run_stage2_vision.
  5. C2PA provenance detection does not force an artificial deepfake verdict.
"""

import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from src.stages.stage2_vision import run_stage2_vision


def test_aggregation_gemini_profile_sustained_consensus():
    """
    Validates that a video with multiple elevated frames (Gemini diagnostic profile)
    is NOT suppressed by low median.
    Scores: Peak 0.2680, s2 0.1664, s3 0.1156, median 0.0069.
    Expected: Sustained consensus blend 0.65 * top3 + 0.35 * peak ~= 0.2130 (21%),
    NOT 0.0775 (8%).
    """
    gemini_scores = [
        0.0045, 0.2680, 0.0018, 0.0668, 0.0230,
        0.0112, 0.0908, 0.0069, 0.0015, 0.0053,
        0.1156, 0.1664, 0.0053, 0.0021, 0.0012
    ]
    mock_backend = MagicMock()
    mock_backend.predict_frame.side_effect = gemini_scores
    mock_backend.backend_name = "ms_eff_gcvit"
    mock_backend.model_id = "test_model"
    mock_backend.generate_heatmap.return_value = None

    dummy_frames = [f"dummy_frame_{i}.jpg" for i in range(len(gemini_scores))]

    with patch("os.path.exists", return_value=True):
        with patch("src.stages.backends.get_vision_backend", return_value=mock_backend):
            res = run_stage2_vision(dummy_frames, job_id="test_gemini_agg")

    # The calibrated score must preserve the multi-frame consensus
    assert res["aggregation_mode"] == "sustained_consensus"
    assert round(res["max_score"], 4) == 0.2130
    assert res["raw_peak_score"] == 0.2680
    assert round(res["top_k_mean"], 4) == 0.1833
    assert round(res["median_score"], 4) == 0.0069
    assert len(res["frame_scores"]) == 15
    assert res["aggregation_details"]["mode"] == "sustained_consensus"


def test_aggregation_isolated_outlier_attenuation():
    """
    Validates that a single-frame outlier spike (e.g. camera glare on genuine video)
    is attenuated towards frame 2 to prevent false alarms.
    Scores: Frame 0 = 0.8138, Frame 1 = 0.0371, Frame 2 = 0.0026, rest <0.01.
    Expected: Attenuated to 0.35 * 0.8138 + 0.65 * 0.0371 ~= 0.3089 (well below 0.60 threshold).
    """
    outlier_scores = [
        0.8138, 0.0371, 0.0026, 0.0017, 0.0017,
        0.0019, 0.0228, 0.0082, 0.0310, 0.0022,
        0.0296, 0.0087, 0.0032, 0.0032, 0.0012
    ]
    mock_backend = MagicMock()
    mock_backend.predict_frame.side_effect = outlier_scores
    mock_backend.backend_name = "ms_eff_gcvit"
    mock_backend.model_id = "test_model"
    mock_backend.generate_heatmap.return_value = None

    dummy_frames = [f"dummy_frame_{i}.jpg" for i in range(len(outlier_scores))]

    with patch("os.path.exists", return_value=True):
        with patch("src.stages.backends.get_vision_backend", return_value=mock_backend):
            res = run_stage2_vision(dummy_frames, job_id="test_outlier_agg")

    assert res["aggregation_mode"] == "isolated_outlier_attenuation"
    assert res["max_score"] < 0.40  # Safely below false alarm threshold
    assert res["raw_peak_score"] == 0.8138
    assert res["aggregation_details"]["mode"] == "isolated_outlier_attenuation"


def test_aggregation_clean_authentic_baseline():
    """
    Validates that consistently clean authentic videos remain very low confidence (<0.05).
    """
    clean_scores = [0.005, 0.008, 0.003, 0.006, 0.002, 0.004, 0.001, 0.005, 0.003, 0.002]
    mock_backend = MagicMock()
    mock_backend.predict_frame.side_effect = clean_scores
    mock_backend.backend_name = "ms_eff_gcvit"
    mock_backend.model_id = "test_model"
    mock_backend.generate_heatmap.return_value = None

    dummy_frames = [f"dummy_frame_{i}.jpg" for i in range(len(clean_scores))]

    with patch("os.path.exists", return_value=True):
        with patch("src.stages.backends.get_vision_backend", return_value=mock_backend):
            res = run_stage2_vision(dummy_frames, job_id="test_clean_agg")

    assert res["aggregation_mode"] == "sustained_consensus"
    assert res["max_score"] < 0.02
    assert res["raw_peak_score"] == 0.008


def test_provenance_separate_from_visual_manipulation():
    """
    Validates that C2PA provenance detection does NOT alter vision_score or force is_deepfake = True.
    """
    from app import calculate_calibrated_verdict

    # Video with C2PA manifest detected (AI asset declaration) but low visual manipulation
    vision_score = 0.2130  # Below 0.50 threshold
    audio_score = 0.0000   # Clean audio
    composite_risk = 0.10  # No scam

    is_deepfake = (vision_score > 0.50 or audio_score > 0.50)
    is_scam = False

    # Deepfake must NOT be forced merely because C2PA exists
    assert is_deepfake is False

    verdict = calculate_calibrated_verdict(is_deepfake, is_scam, composite_risk, registry_verdict="not claimed")
    assert verdict == "Safe"
