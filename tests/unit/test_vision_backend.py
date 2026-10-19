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
    assert "checkpoint_source" in res
    assert "is_finetuned" in res
    assert res["is_finetuned"] is False
    assert "Original Pretrained Hugging Face" in res["checkpoint_source"]


def test_production_backend_loads_pretrained_weights_not_finetuned():
    """Verifies that the default production backend loads pretrained safetensors, not the fine-tuned checkpoint."""
    backend = get_vision_backend(device="cpu")
    try:
        assert backend.backend_name == "ms_eff_gcvit"
        assert "KoreaPeter" in backend.model_id
        assert backend.is_finetuned is False
        assert "Original Pretrained Hugging Face" in backend.checkpoint_source
        assert backend.weights_path.endswith(".safetensors")
    finally:
        backend.close()


def test_fine_tuned_weights_explicit_loading_and_reversibility():
    """Verifies that the fine-tuned checkpoint can be loaded when explicitly configured, and safely reversed."""
    app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ft_weights = os.path.join(app_root, "experiments", "deepfake_finetune", "checkpoints", "best_checkpoint_weights.pth")

    if os.path.isfile(ft_weights):
        # 1. Test explicit configuration of fine-tuned checkpoint
        with patch("src.stages.backends.get_vision_detector_config", return_value={"backend": "ms_eff_gcvit", "model_weights_file": ft_weights}):
            ft_backend = get_vision_backend(device="cpu")
            try:
                assert ft_backend.is_finetuned is True
                assert "Local Fine-Tuned Checkpoint" in ft_backend.checkpoint_source
                assert os.path.samefile(ft_backend.weights_path, ft_weights)
            finally:
                ft_backend.close()

    # 2. Test rollback / reversion to pretrained model (model_weights_file: None)
    with patch("src.stages.backends.get_vision_detector_config", return_value={"backend": "ms_eff_gcvit", "model_weights_file": None}):
        pre_backend = get_vision_backend(device="cpu")
        try:
            assert pre_backend.is_finetuned is False
            assert "Original Pretrained Hugging Face" in pre_backend.checkpoint_source
            assert pre_backend.weights_path.endswith(".safetensors")
        finally:
            pre_backend.close()

