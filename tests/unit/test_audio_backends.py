"""
Unit Tests for Modular Audio Deepfake Backends & Configuration
==============================================================
Validates:
  1. Configuration selection (melodymachine vs wav2vec2_garystafford vs invalid)
  2. Model label mappings (MelodyMachine fake_idx vs GaryStafford fake_idx=1)
  3. Safe handling of audio clips > 10 seconds (chunking & timeline generation)
  4. Safe padding of short clips (< 1.0 second)
  5. Silence detection (RMS threshold check to avoid false positives and division by zero)
  6. Malformed audio and missing file handling (safe error dict, no unhandled exceptions)
  7. Output contract preservation (avg_score, max_score, all_segments, impersonation_check)
"""
import os
import pytest
import numpy as np
import torch
import soundfile as sf
from unittest.mock import patch, MagicMock

from src.stages.audio_backends import (
    get_audio_backend,
    clear_audio_backend_cache,
    BaseAudioBackend,
    MelodyMachineAudioBackend,
    GaryStaffordWav2Vec2Backend,
    check_finfluencer_impersonation,
)
from src.stages.stage3_audio import run_stage3_audio


@pytest.fixture(autouse=True)
def clean_backend_cache():
    """Ensure tests start and end with an empty audio backend cache."""
    clear_audio_backend_cache()
    yield
    clear_audio_backend_cache()


# ── 1. Configuration Selection Tests ─────────────────────────────────────────

def test_audio_config_selection_default_wav2vec2_garystafford():
    """When backend is unspecified, default must be 'wav2vec2_garystafford' (Model C)."""
    with patch("src.stages.audio_backends.get_audio_detector_config", return_value={}):
        with patch("src.stages.audio_backends.get_stage_config", return_value={}):
            with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
                backend = get_audio_backend(backend_name=None, device="cpu")
                assert isinstance(backend, GaryStaffordWav2Vec2Backend)
                assert backend.name == "wav2vec2_garystafford"
                assert backend.model_id == "garystafford/wav2vec2-deepfake-voice-detector"
                assert backend.revision == "c66306024a7ede0be291e9c4558b37634782dc4"


def test_audio_config_selection_explicit_melodymachine():
    """When explicitly configured with 'melodymachine', must select MelodyMachineAudioBackend."""
    with patch("src.stages.audio_backends.get_audio_detector_config", return_value={"backend": "melodymachine"}):
        with patch.object(MelodyMachineAudioBackend, "_load_model"):
            backend = get_audio_backend(backend_name=None, device="cpu")
            assert isinstance(backend, MelodyMachineAudioBackend)
            assert backend.name == "melodymachine"
            assert backend.model_id == "MelodyMachine/Deepfake-Audio-Detection-V2"


def test_audio_config_selection_explicit_garystafford():
    """When configured with 'wav2vec2_garystafford', must select GaryStaffordWav2Vec2Backend."""
    with patch("src.stages.audio_backends.get_audio_detector_config", return_value={"backend": "wav2vec2_garystafford"}):
        with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
            backend = get_audio_backend(backend_name=None, device="cpu")
            assert isinstance(backend, GaryStaffordWav2Vec2Backend)
            assert backend.name == "wav2vec2_garystafford"
            assert backend.model_id == "garystafford/wav2vec2-deepfake-voice-detector"


def test_invalid_audio_backend_raises_error():
    """Unrecognized audio backend must raise ValueError and not silently substitute another model."""
    with pytest.raises(ValueError) as excinfo:
        get_audio_backend(backend_name="unsupported_random_model", device="cpu")
    assert "Unknown audio detector backend" in str(excinfo.value)
    assert "FraudShield will not silently substitute an unconfigured model" in str(excinfo.value)


# ── 2. Label Mapping & Probability Range Tests ───────────────────────────────

def test_garystafford_label_mapping():
    """GaryStafford model must use fake_index = 1 with output probability strictly in [0.0, 1.0]."""
    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
        backend = GaryStaffordWav2Vec2Backend(device="cpu")
        backend.fake_index = 1
        backend.processor = MagicMock(return_value={"input_values": torch.zeros((1, 16000))})
        
        # Mock logits: class 0 (real)=1.0, class 1 (fake)=3.0 -> fake_prob > 0.8
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[1.0, 3.0]])
        backend.model = MagicMock(return_value=mock_output)
        backend.model.parameters.return_value = [torch.zeros(1)]

        dummy_chunk = np.zeros(16000, dtype=np.float32)
        score = backend.predict_chunk(dummy_chunk, sample_rate=16000)

        assert 0.0 <= score <= 1.0
        assert score > 0.85  # softmax of [1.0, 3.0] puts ~88% probability on class 1


def test_melodymachine_label_mapping():
    """MelodyMachine model inspects id2label dynamically."""
    with patch.object(MelodyMachineAudioBackend, "_load_model"):
        backend = MelodyMachineAudioBackend(device="cpu")
        backend.fake_index = 0
        backend.processor = MagicMock(return_value={"input_values": torch.zeros((1, 16000))})
        
        # Mock logits: class 0 (fake)=3.0, class 1 (real)=1.0 -> fake_prob > 0.8
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[3.0, 1.0]])
        backend.model = MagicMock(return_value=mock_output)
        backend.model.parameters.return_value = [torch.zeros(1)]

        dummy_chunk = np.zeros(16000, dtype=np.float32)
        score = backend.predict_chunk(dummy_chunk, sample_rate=16000)

        assert 0.0 <= score <= 1.0
        assert score > 0.85


# ── 3. Audio Length & Chunking Edge Cases ───────────────────────────────────

def test_audio_longer_than_10_seconds_handling(tmp_path):
    """
    Audio recordings longer than 10 seconds must be safely chunked into <= 10s windows,
    evaluating across the entire timeline without crashing or truncating.
    """
    sr = 16000
    # Create 25 seconds of synthetic audio (sine wave + noise)
    duration = 25.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    waveform = (0.5 * np.sin(2 * np.pi * 440 * t) + 0.05 * np.random.randn(len(t))).astype(np.float32)
    
    test_file = str(tmp_path / "long_sample_25s.wav")
    sf.write(test_file, waveform, sr)

    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
        backend = GaryStaffordWav2Vec2Backend(device="cpu")
        # Predict 0.75 for each chunk
        backend.predict_chunk = MagicMock(return_value=0.75)

        result = backend.process_audio(test_file, chunk_duration=5.0)

        assert result["model_backend"] == "wav2vec2_garystafford"
        assert len(result["all_segments"]) == 5  # 25s / 5s = 5 chunks
        assert result["max_score"] == pytest.approx(0.75, abs=1e-3)
        assert result["avg_score"] == pytest.approx(0.75, abs=1e-3)
        assert len(result["flagged_segments"]) == 5  # all > 0.45 threshold
        assert result["all_segments"][0]["start"] == 0.0
        assert result["all_segments"][-1]["end"] == 25.0


def test_short_audio_clip_padding(tmp_path):
    """Clips shorter than 1 second must be safely padded and processed without dimension errors."""
    sr = 16000
    short_len = int(0.4 * sr)  # 0.4s = 6400 samples
    waveform = (0.3 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.4, short_len))).astype(np.float32)
    test_file = str(tmp_path / "short_clip.wav")
    sf.write(test_file, waveform, sr)

    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
        backend = GaryStaffordWav2Vec2Backend(device="cpu")
        backend.predict_chunk = MagicMock(return_value=0.20)

        result = backend.process_audio(test_file)
        assert len(result["all_segments"]) == 1
        assert result["max_score"] == pytest.approx(0.20, abs=1e-3)


def test_silent_audio_clip_handling(tmp_path):
    """Silent or near-silent clips must be caught by RMS check, returning 0.0 spoof score without division by zero."""
    sr = 16000
    waveform = np.zeros(sr * 3, dtype=np.float32)  # 3 seconds of perfect digital silence
    test_file = str(tmp_path / "silent.wav")
    sf.write(test_file, waveform, sr)

    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
        backend = GaryStaffordWav2Vec2Backend(device="cpu")
        backend.predict_chunk = MagicMock()

        result = backend.process_audio(test_file)
        assert result["is_silent"] is True
        assert result["max_score"] == 0.0
        assert result["avg_score"] == 0.0
        assert len(result["flagged_segments"]) == 0
        # Model inference should NOT be called on pure silence
        backend.predict_chunk.assert_not_called()


def test_malformed_or_missing_audio_handling():
    """Non-existent or corrupt audio files must return a safe error dict and not raise unhandled exceptions."""
    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
        backend = GaryStaffordWav2Vec2Backend(device="cpu")
        
        # Missing file
        res_missing = backend.process_audio("/nonexistent/path/to/missing_audio.wav")
        assert res_missing["status"] == "error"
        assert res_missing["max_score"] == 0.0
        assert res_missing["all_segments"] == []

        # Empty string
        res_empty = backend.process_audio("")
        assert res_empty["status"] == "error"
        assert res_empty["max_score"] == 0.0


# ── 4. Stage 3 Integration & Impersonation Tests ─────────────────────────────

def test_run_stage3_audio_output_contract(tmp_path):
    """run_stage3_audio must preserve the exact dictionary keys expected by app.py."""
    sr = 16000
    t = np.linspace(0, 4, sr * 4, endpoint=False)
    waveform = (0.4 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    test_file = str(tmp_path / "sample_stage3.wav")
    sf.write(test_file, waveform, sr)

    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model"):
        with patch.object(GaryStaffordWav2Vec2Backend, "predict_chunk", return_value=0.88):
            res = run_stage3_audio(
                test_file,
                job_id="test-contract",
                transcript="Hello this is Nikhil Kamath speaking about stock investing.",
                backend_name="wav2vec2_garystafford"
            )

            # Contract assertion
            assert "avg_score" in res
            assert "max_score" in res
            assert "raw_peak_score" in res
            assert "flagged_segments" in res
            assert "all_segments" in res
            assert "impersonation_check" in res
            assert "model_backend" in res
            assert "model_id" in res

            assert res["model_backend"] == "wav2vec2_garystafford"
            assert res["max_score"] > 0.8
            assert res["impersonation_check"]["is_impersonation"] is True
            assert res["impersonation_check"]["target"] == "Nikhil Kamath"


def test_run_stage3_audio_default_selects_model_c_without_loading_melodymachine(tmp_path):
    """Calling run_stage3_audio without backend_name must select Model C and never load MelodyMachine."""
    sr = 16000
    t = np.linspace(0, 3, sr * 3, endpoint=False)
    waveform = (0.3 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
    test_file = str(tmp_path / "default_test.wav")
    sf.write(test_file, waveform, sr)

    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model") as mock_load_gs:
        with patch.object(GaryStaffordWav2Vec2Backend, "predict_chunk", return_value=0.15):
            with patch.object(MelodyMachineAudioBackend, "_load_model") as mock_load_mm:
                from src.stages.audio_backends import clear_audio_backend_cache
                clear_audio_backend_cache()

                res = run_stage3_audio(test_file, job_id="test-default-c")

                assert res["model_backend"] == "wav2vec2_garystafford"
                assert res["model_id"] == "garystafford/wav2vec2-deepfake-voice-detector"
                assert res.get("revision") == "c66306024a7ede0be291e9c4558b37634782dc4"
                assert mock_load_gs.called
                assert not mock_load_mm.called


def test_run_stage3_audio_loads_melodymachine_only_when_explicit(tmp_path):
    """Calling run_stage3_audio with backend_name='melodymachine' must load MelodyMachine and not Model C."""
    sr = 16000
    t = np.linspace(0, 3, sr * 3, endpoint=False)
    waveform = (0.3 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)
    test_file = str(tmp_path / "explicit_mm_test.wav")
    sf.write(test_file, waveform, sr)

    with patch.object(GaryStaffordWav2Vec2Backend, "_load_model") as mock_load_gs:
        with patch.object(MelodyMachineAudioBackend, "_load_model") as mock_load_mm:
            with patch.object(MelodyMachineAudioBackend, "predict_chunk", return_value=0.92):
                from src.stages.audio_backends import clear_audio_backend_cache
                clear_audio_backend_cache()

                res = run_stage3_audio(test_file, job_id="test-explicit-mm", backend_name="melodymachine")

                assert res["model_backend"] == "melodymachine"
                assert res["model_id"] == "MelodyMachine/Deepfake-Audio-Detection-V2"
                assert mock_load_mm.called
                assert not mock_load_gs.called
