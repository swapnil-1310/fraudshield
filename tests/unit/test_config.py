"""
Unit tests for configuration loading and threshold accessors in src/config.py.
"""
from src.config import get_stage_config, get_threshold, settings


def test_config_settings_loaded():
    assert isinstance(settings, dict)
    assert "hardware" in settings
    assert "thresholds" in settings
    assert "pipeline" in settings


def test_get_threshold_existing():
    val = get_threshold("vision_fake_threshold")
    assert val == 0.5
    val_audio = get_threshold("audio_fake_threshold")
    assert val_audio == 0.5


def test_get_threshold_default_fallback():
    val = get_threshold("completely_unknown_threshold_key", default=0.77)
    assert val == 0.77


def test_get_stage_config():
    stage1 = get_stage_config("stage1_ingest")
    assert isinstance(stage1, dict)
    assert stage1.get("max_frames_to_extract") == 25
    assert stage1.get("audio_sample_rate") == 16000

    unknown = get_stage_config("non_existent_stage_99")
    assert unknown == {}
