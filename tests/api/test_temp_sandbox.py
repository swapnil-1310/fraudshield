"""
Tests asserting ephemeral sandbox isolation and guaranteed cleanup of temp/<job_id>
on both pipeline success and forced unhandled failure.
"""
import os
import uuid
from unittest.mock import patch

from app import jobs, run_pipeline


def test_temp_sandbox_cleanup_on_success():
    """Verifies temp/<job_id> directory is purged after successful video pipeline execution."""
    job_id = f"test-clean-{uuid.uuid4().hex[:8]}"
    temp_dir = os.path.join("temp", job_id)
    os.makedirs(temp_dir, exist_ok=True)
    temp_file = os.path.join(temp_dir, "input.mp4")
    with open(temp_file, "wb") as f:
        f.write(b"test video payload")

    jobs[job_id] = {"status": "processing"}

    # Mock all stage executions to return mock dicts
    mock_ingest = {
        "face_frames_paths": [],
        "audio_path": "fake.wav",
        "quality_assessment": {},
        "metadata_forensics": {},
    }
    mock_vision = {"max_score": 0.1, "temporal_variance": 0.0, "mouth_motion_activity": 0.05}
    mock_tx = {"transcript": "Clean educational stock tutorial.", "segments": []}
    mock_audio = {"max_score": 0.1, "flagged_segments": [], "all_segments": []}
    mock_llm = {"is_scam_likely": False, "composite_risk_score": 0.1}
    mock_registry = {"verdict": "verified"}
    mock_stage9 = {"any_threat_detected": False}

    with patch("app.run_stage1_ingest", return_value=mock_ingest), \
         patch("app.run_stage2_vision", return_value=mock_vision), \
         patch("app.run_stage4_transcription", return_value=mock_tx), \
         patch("app.run_stage3_audio", return_value=mock_audio), \
         patch("app.run_stage5_llm", return_value=mock_llm), \
         patch("app.run_stage6_registry", return_value=mock_registry), \
         patch("app.run_stage9_apk_domain", return_value=mock_stage9):

        assert os.path.exists(temp_dir)
        run_pipeline(job_id, temp_dir, temp_file)

        # Assert job finished successfully
        assert jobs[job_id]["status"] == "completed"
        # Assert temp directory was unconditionally purged
        assert not os.path.exists(temp_dir), f"Sandbox directory {temp_dir} was not purged on success!"


def test_temp_sandbox_cleanup_on_forced_failure():
    """Verifies temp/<job_id> directory is purged even when an unhandled exception crashes the pipeline."""
    job_id = f"test-fail-{uuid.uuid4().hex[:8]}"
    temp_dir = os.path.join("temp", job_id)
    os.makedirs(temp_dir, exist_ok=True)
    temp_file = os.path.join(temp_dir, "input.mp4")
    with open(temp_file, "wb") as f:
        f.write(b"corrupt video payload")

    jobs[job_id] = {"status": "processing"}

    # Force an unhandled exception in Stage 1
    with patch("app.run_stage1_ingest", side_effect=RuntimeError("Simulated catastrophic crash")):
        assert os.path.exists(temp_dir)
        run_pipeline(job_id, temp_dir, temp_file)

        # Assert job state recorded the failure
        assert jobs[job_id]["status"] == "failed"
        assert "Simulated catastrophic crash" in jobs[job_id]["error"]
        # Assert temp directory was purged in the finally block
        assert not os.path.exists(temp_dir), f"Sandbox directory {temp_dir} was not purged on forced failure!"
