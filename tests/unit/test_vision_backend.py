"""
Unit Tests for Modular Vision Deepfake Backends & Configuration
===============================================================
Validates:
  1. Configuration selection (hybrid_phase2 vs ms_eff_gcvit vs absent config)
  2. Checkpoint loading and strict weights matching
  3. Inference output shape [B, 1] and calibrated range [0.0, 1.0]
  4. Threshold boundaries (0.0, 0.50, 0.60, 1.0)
  5. Missing weights and invalid backend error handling (no silent fallback)
  6. Diagnostic metadata fields (model_backend, model_id, threshold_applied)
"""

import os
import pytest
import numpy as np
import torch
from unittest.mock import patch

from src.stages.backends import get_vision_backend, BaseVisionBackend
from src.stages.backends.hybrid_backend import HybridPhase2Backend
from src.stages.backends.ms_eff_gcvit_backend import MsEffGCViTBackend
from src.config import get_threshold, get_vision_detector_config
from src.stages.stage2_vision import run_stage2_vision


def test_config_selection_default_fallback():
    """When vision_detector is absent, default backend must be 'hybrid_phase2'."""
    with patch("src.stages.backends.get_vision_detector_config", return_value={}):
        with patch("src.stages.backends.HybridPhase2Backend") as mock_hybrid:
            mock_instance = mock_hybrid.return_value
            backend = get_vision_backend(backend_name=None, device="cpu")
            mock_hybrid.assert_called_once()


def test_config_selection_explicit_ms_eff_gcvit():
    """When configured with ms_eff_gcvit, must select MsEffGCViTBackend."""
    with patch("src.stages.backends.get_vision_detector_config", return_value={"backend": "ms_eff_gcvit"}):
        with patch("src.stages.backends.MsEffGCViTBackend") as mock_gcvit:
            mock_instance = mock_gcvit.return_value
            backend = get_vision_backend(backend_name=None, device="cpu")
            mock_gcvit.assert_called_once()


def test_invalid_backend_raises_error_no_silent_fallback():
    """Unrecognized backend must raise ValueError and NOT silently substitute another model."""
    with pytest.raises(ValueError) as excinfo:
        get_vision_backend("unsupported_experimental_detector", device="cpu")
    assert "Unknown vision detector backend" in str(excinfo.value)
    assert "FraudShield will not silently substitute an unconfigured model" in str(excinfo.value)


def test_missing_weights_raises_filenotfound_no_silent_fallback():
    """Missing weights must raise FileNotFoundError and not substitute dummy/other weights."""
    fake_path = "/nonexistent/directory/model_weights.safetensors"
    with pytest.raises(FileNotFoundError) as excinfo:
        MsEffGCViTBackend(weights_path=fake_path, device="cpu")
    assert "Checkpoint weights not found" in str(excinfo.value)

    with pytest.raises(FileNotFoundError) as excinfo_h:
        HybridPhase2Backend(weights_path=fake_path, device="cpu")
    assert "Checkpoint weights not found" in str(excinfo_h.value)


def test_ms_eff_gcvit_inference_output_shape_and_range():
    """Verifies candidate model output shape and probability calibration."""
    backend = get_vision_backend(backend_name="ms_eff_gcvit", device="cpu")
    assert backend.backend_name == "ms_eff_gcvit"
    assert "KoreaPeter" in backend.model_id

    # Create dummy synthetic BGR face image (224x224x3)
    dummy_img = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    prob = backend.predict_frame(dummy_img)

    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0

    # Verify underlying forward pass shape
    inp = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        raw_out = backend._model(inp)
    assert raw_out.shape == (1, 1), f"Expected shape (1, 1), got {raw_out.shape}"
    backend.close()


def test_threshold_selection_and_boundaries():
    """Verifies that vision_detector.threshold overrides default threshold when configured."""
    from src.config import get_vision_threshold

    # When vision_detector.threshold is 0.60
    with patch("src.config.get_vision_detector_config", return_value={"backend": "ms_eff_gcvit", "threshold": 0.60}):
        th = get_vision_threshold()
        assert th == 0.60

    # When vision_detector is absent, falls back to thresholds.vision_fake_threshold (0.50)
    with patch("src.config.get_vision_detector_config", return_value={}):
        with patch("src.config.settings", {"thresholds": {"vision_fake_threshold": 0.50}}):
            th = get_vision_threshold()
            assert th == 0.50

    # Boundary tests
    for b_th in [0.0, 0.50, 0.60, 1.0]:
        with patch("src.config.get_vision_detector_config", return_value={"threshold": b_th}):
            assert get_vision_threshold() == b_th


def test_stage2_vision_diagnostic_result_fields(tmp_path):
    """Verifies that run_stage2_vision includes diagnostic identifiers (model_backend, model_id, threshold_applied)."""
    # Create 3 dummy JPEG face frames
    frame_paths = []
    for i in range(3):
        p = str(tmp_path / f"face_{i}.jpg")
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        import cv2
        cv2.imwrite(p, img)
        frame_paths.append(p)

    res = run_stage2_vision(frame_paths, job_id="test_diag_job")

    # Diagnostic metadata assertions
    assert "model_backend" in res, "Missing model_backend identifier in results"
    assert res["model_backend"] in ("hybrid_phase2", "ms_eff_gcvit")
    assert "model_id" in res, "Missing model_id in results"
    assert "threshold_applied" in res, "Missing threshold_applied in results"
    assert isinstance(res["threshold_applied"], float)
    assert "max_score" in res
    assert "avg_score" in res
    assert 0.0 <= res["max_score"] <= 1.0
