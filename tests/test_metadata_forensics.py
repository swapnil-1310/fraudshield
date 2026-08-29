"""
FinGuard — Video Metadata & Media Provenance Analysis Test Suite
================================================================
Comprehensive test verification for:
1. Standard video metadata extraction
2. Minimal metadata handling & completeness calculation
3. Missing metadata handling
4. Missing / disabled ffprobe fallback
5. Missing / disabled ExifTool fallback
6. Extraction timeout & corrupt file error handling
7. Stage 1 Ingest pipeline integration
8. API response payload backward compatibility & non-blocking behavior
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.metadata_forensics import (
    extract_metadata_forensics,
    _run_ffprobe,
    _run_exiftool,
    _extract_python_fallback,
    _detect_provenance,
    _build_forensic_observations
)


class TestMetadataForensics(unittest.TestCase):
    def setUp(self):
        # Locate sample video if present in repo
        self.sample_video = os.path.join(ROOT_DIR, "WhatsApp Video 2026-08-27 at 10.23.37 PM.mp4")
        if not os.path.exists(self.sample_video):
            # Try alternate file
            alt_video = os.path.join(ROOT_DIR, "WhatsApp Video 2026-08-27 at 10.29.55 PM.mp4")
            if os.path.exists(alt_video):
                self.sample_video = alt_video

    def test_01_sample_video_extraction(self):
        """1. Test extraction on actual video file."""
        if not os.path.exists(self.sample_video):
            self.skipTest("Sample video not found on disk")

        result = extract_metadata_forensics(self.sample_video, job_id="test-job-01")
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("status"), "available")
        self.assertIn("file_info", result)
        self.assertIn("container_info", result)
        self.assertIn("video_stream", result)
        self.assertIn("audio_stream", result)
        self.assertIn("embedded_metadata", result)
        self.assertIn("provenance", result)
        self.assertIn("forensic_observations", result)
        self.assertIn("completeness", result)
        self.assertIn("metadata_confidence", result)
        self.assertIsInstance(result["forensic_observations"], list)
        self.assertGreater(len(result["forensic_observations"]), 0)
        self.assertIn(result["completeness"], ["high", "medium", "low"])
        self.assertGreaterEqual(result["metadata_confidence"], 0.0)
        self.assertLessEqual(result["metadata_confidence"], 1.0)
        print("  [OK] Test 1: Sample video extracted with completeness:", result["completeness"])

    def test_02_minimal_metadata(self):
        """2. Test video with minimal metadata tags."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            # Write a minimal MP4 header (ftyp box only)
            ftyp_data = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
            f.write(ftyp_data)
            temp_file = f.name

        try:
            result = extract_metadata_forensics(temp_file, job_id="test-minimal")
            self.assertEqual(result.get("status"), "available")
            self.assertIn(result.get("completeness"), ["low", "medium"])
            self.assertEqual(result.get("provenance_status"), "not_available")
            self.assertIn("file_info", result)
            self.assertEqual(result["file_info"]["file_extension"], ".mp4")
            print("  [OK] Test 2: Minimal metadata file handled gracefully.")
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_03_no_metadata_or_empty_file(self):
        """3. Test empty file / no metadata."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            temp_file = f.name

        try:
            result = extract_metadata_forensics(temp_file, job_id="test-empty")
            self.assertIn(result.get("status"), ["available", "unavailable"])
            self.assertEqual(result.get("completeness"), "low")
            self.assertEqual(result.get("provenance_status"), "not_available")
            print("  [OK] Test 3: Empty file handled without crashing.")
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_04_missing_ffprobe_fallback(self):
        """4. Test extraction behavior when ffprobe is missing/disabled."""
        if not os.path.exists(self.sample_video):
            self.skipTest("Sample video not found on disk")

        # Disable ffprobe in config
        cfg = {
            "enabled": True,
            "use_ffprobe": False,
            "use_exiftool": False,
            "timeout_seconds": 5,
            "detect_provenance": True
        }
        result = extract_metadata_forensics(self.sample_video, job_id="test-no-ffprobe", config=cfg)
        self.assertEqual(result.get("status"), "available")
        self.assertIn("python_fallback", result.get("extraction_sources", []))
        self.assertNotIn("ffprobe", result.get("extraction_sources", []))
        self.assertIsNotNone(result.get("file_info"))
        self.assertGreater(result["file_info"]["file_size_bytes"], 0)
        print("  [OK] Test 4: Pure Python fallback functioned with ffprobe disabled.")

    def test_05_missing_exiftool_fallback(self):
        """5. Test extraction when ExifTool is missing."""
        if not os.path.exists(self.sample_video):
            self.skipTest("Sample video not found on disk")

        with patch("shutil.which", return_value=None):
            tool_res = _run_exiftool(self.sample_video)
            self.assertIsNone(tool_res)

        # Full extraction still succeeds
        result = extract_metadata_forensics(self.sample_video, job_id="test-no-exiftool")
        self.assertEqual(result.get("status"), "available")
        print("  [OK] Test 5: Missing ExifTool handled seamlessly.")

    def test_06_timeout_and_error_safety(self):
        """6. Test timeout / unhandled subprocess failure safety."""
        cfg = {
            "enabled": True,
            "use_ffprobe": True,
            "use_exiftool": True,
            "timeout_seconds": 0.0001,  # Intentional immediate timeout
            "detect_provenance": True
        }
        # Non-existent file
        res_nonexistent = extract_metadata_forensics("non_existent_file_path_12345.mp4", config=cfg)
        self.assertEqual(res_nonexistent.get("status"), "unavailable")
        self.assertEqual(res_nonexistent.get("metadata_confidence"), 0.0)

        # File with timeout should fallback safely
        if os.path.exists(self.sample_video):
            res_timeout = extract_metadata_forensics(self.sample_video, config=cfg)
            self.assertEqual(res_timeout.get("status"), "available")
            self.assertIn("python_fallback", res_timeout.get("extraction_sources", []))
        print("  [OK] Test 6: Timeout and error recovery tested successfully.")

    def test_07_stage1_ingest_integration(self):
        """7. Verify Stage 1 Ingest runs with metadata forensics included."""
        if not os.path.exists(self.sample_video):
            self.skipTest("Sample video not found on disk")

        from src.stages.stage1_ingest import run_stage1_ingest
        temp_dir = tempfile.mkdtemp()
        try:
            ingest = run_stage1_ingest(self.sample_video, temp_dir, "test-stage1-meta")
            self.assertIn("quality_assessment", ingest)
            self.assertIn("metadata_forensics", ingest)
            meta = ingest["metadata_forensics"]
            self.assertIn("status", meta)
            self.assertIn("completeness", meta)
            self.assertIn("forensic_observations", meta)
            self.assertIn("metadata_confidence", meta)
            self.assertIn("provenance_status", meta)
            # Existing keys preserved
            self.assertIn("audio_path", ingest)
            self.assertIn("face_frames_paths", ingest)
            print("  [OK] Test 7: Stage 1 Ingest returned all required keys including metadata_forensics.")
        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def test_08_forensic_observations_principles(self):
        """8. Verify forensic observations follow non-accusatory principles."""
        # Test synthetic observation builder
        file_info = {"file_name": "test.mp4", "file_extension": ".mp4", "file_size_bytes": 1024, "file_size_mb": 0.0, "mime_type": "video/mp4"}
        container_info = {"format_name": "mp4", "format_long_name": "MP4", "duration_sec": 10.0, "overall_bitrate_kbps": 500, "metadata_tags": {}}
        video_stream = {"codec_name": "h264", "resolution": "1280x720", "frame_rate": 30.0, "encoder": "Lavf59.27.100"}
        audio_stream = {"has_audio": True, "codec_name": "aac", "sample_rate_hz": 44100, "channels": 2}
        embedded = {"camera_make": None, "software_used": "Adobe Premiere Pro", "creation_date": "2026-08-27T22:23:37Z", "gps_coordinates": None}
        provenance = {"provenance_status": "not_available", "c2pa_manifest_detected": False}

        obs, completeness, confidence = _build_forensic_observations(
            file_info, container_info, video_stream, audio_stream, embedded, provenance, ["python_fallback"]
        )

        obs_text = " ".join(obs).lower()
        # Verify no false-positive deepfake claims in metadata layer
        self.assertNotIn("fake", obs_text)
        self.assertNotIn("ai-generated", obs_text)
        self.assertIn("video container indicates processing with video editing", obs_text)
        print("  [OK] Test 8: Forensic observation objectivity confirmed.")


if __name__ == "__main__":
    print("=" * 60)
    print("  FinGuard Metadata & Media Provenance Test Suite")
    print("=" * 60)
    unittest.main(verbosity=2)
