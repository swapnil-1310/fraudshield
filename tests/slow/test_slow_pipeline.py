"""
Slow and heavy end-to-end smoke tests that require full model weights or long inference.
Marked with @pytest.mark.slow and excluded from default test suites.
"""
import pytest


@pytest.mark.slow
def test_full_video_pipeline_smoke():
    """Placeholder for heavy integration test with real multi-gigabyte models."""
    pytest.skip("Skipped by default: Requires full model weights and active GPU/Ollama instance.")
