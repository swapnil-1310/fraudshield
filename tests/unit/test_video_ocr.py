"""
Unit tests for Video Keyframe OCR and multimodal text integration (Priority 2).
Validates:
  1. run_video_keyframes_ocr safely handles empty/missing frames.
  2. Redundant/near-identical frames are skipped via visual similarity checks.
  3. Frame references and timestamps are preserved in frame_results.
  4. OCR errors on individual frames never crash the pipeline or imply safety.
  5. Stage 5 incorporates on-screen video text into fraud analysis.
  6. Stage 9 scans URLs discovered in video OCR text.
"""
import os
import cv2
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from src.stages.stage7_ocr import run_video_keyframes_ocr
from src.stages.stage5_llm import run_stage5_llm
from src.stages.stage9_apk_domain import run_stage9_apk_domain


class TestVideoKeyframesOCR:

    def test_empty_keyframes_handled_safely(self):
        """Empty keyframes list returns gracefully without crashing."""
        res = run_video_keyframes_ocr([], job_id="test-empty-ocr")
        assert res["status"] == "skipped_no_frames"
        assert res["extracted_text"] == ""
        assert res["frame_results"] == []

    def test_timestamps_and_frame_indices_preserved(self, tmp_path):
        """Keyframe timestamps and frame indices are preserved in output metadata."""
        # Create 2 simple distinct dummy images
        img1_path = str(tmp_path / "frame_0.jpg")
        img2_path = str(tmp_path / "frame_1.jpg")

        # Distinct images (one black, one white)
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        img2 = np.ones((100, 100, 3), dtype=np.uint8) * 255
        cv2.imwrite(img1_path, img1)
        cv2.imwrite(img2_path, img2)

        keyframes = [
            {"path": img1_path, "timestamp_sec": 1.5, "frame_index": 45},
            {"path": img2_path, "timestamp_sec": 4.5, "frame_index": 135},
        ]

        # Mock EasyOCR reader
        mock_reader = MagicMock()
        mock_reader.readtext.side_effect = [
            [([[0, 0], [10, 0], [10, 10], [0, 10]], "Guaranteed 100% Return", 0.95)],
            [([[0, 0], [10, 0], [10, 10], [0, 10]], "Join Telegram @scamgroup", 0.92)],
        ]

        with patch("easyocr.Reader", return_value=mock_reader):
            res = run_video_keyframes_ocr(keyframes, job_id="test-ts-preserve")

        assert res["status"] == "success"
        assert len(res["frame_results"]) == 2
        assert res["frame_results"][0]["timestamp_sec"] == 1.5
        assert res["frame_results"][0]["frame_index"] == 45
        assert res["frame_results"][0]["skipped_as_duplicate"] is False
        assert res["frame_results"][1]["timestamp_sec"] == 4.5
        assert res["frame_results"][1]["frame_index"] == 135
        assert "Guaranteed 100% Return" in res["extracted_text"]
        assert "Join Telegram @scamgroup" in res["extracted_text"]

    def test_duplicate_near_identical_frames_skipped(self, tmp_path):
        """Near-identical consecutive keyframes are skipped via visual similarity check."""
        img1_path = str(tmp_path / "dup1.jpg")
        img2_path = str(tmp_path / "dup2.jpg")

        # Create two identical images
        base_img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        cv2.imwrite(img1_path, base_img)
        cv2.imwrite(img2_path, base_img)  # Identical

        keyframes = [
            {"path": img1_path, "timestamp_sec": 2.0, "frame_index": 60},
            {"path": img2_path, "timestamp_sec": 3.5, "frame_index": 105},
        ]

        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            [([[0, 0], [10, 0], [10, 10], [0, 10]], "Invest Now", 0.90)]
        ]

        with patch("easyocr.Reader", return_value=mock_reader):
            res = run_video_keyframes_ocr(keyframes, job_id="test-dup-skip")

        assert res["status"] == "success"
        assert res["keyframes_skipped_duplicate"] == 1
        assert res["keyframes_processed"] == 1
        # mock_reader.readtext should only be called once, for the first non-duplicate frame
        assert mock_reader.readtext.call_count == 1
        assert res["frame_results"][1]["skipped_as_duplicate"] is True

    def test_ocr_failure_does_not_crash_pipeline(self, tmp_path):
        """An error on a single keyframe or reader failure logs safely and returns gracefully."""
        bad_frame = str(tmp_path / "corrupt.jpg")
        with open(bad_frame, "w") as f:
            f.write("corrupted data not an image")

        keyframes = [{"path": bad_frame, "timestamp_sec": 0.0, "frame_index": 0}]

        mock_reader = MagicMock()
        mock_reader.readtext.side_effect = RuntimeError("OpenCV decoder error")

        with patch("easyocr.Reader", return_value=mock_reader):
            res = run_video_keyframes_ocr(keyframes, job_id="test-error-resilience")

        # Did not raise, handled safely
        assert res["status"] == "success"
        assert res["extracted_text"] == ""

    def test_stage5_analyzes_video_ocr_financial_claims(self):
        """Financial fraud claims present in video OCR are detected even with minimal transcript."""
        import requests
        ocr_text = "GUARANTEED 200% RETURNS IN 24 HOURS! Join VIP Telegram @crorepati_calls"
        with patch("requests.post", side_effect=requests.RequestException("Simulated offline")):
            res = run_stage5_llm(transcript="", job_id="test-ocr-stage5", ocr_text=ocr_text)

        assert res["is_scam_likely"] is True
        assert res["composite_risk_score"] > 0.35
        # Verified return promises or paywall push detected
        assert len(res["specific_return_promises"]) > 0 or len(res["paywall_push"]) > 0

    def test_stage9_detects_phishing_domain_in_ocr_text(self):
        """Phishing / typo-squatting domains in video OCR text trigger Stage 9 threat flag."""
        ocr_text = "Login to your account at http://zerodha-bonus-trade.com to claim ₹50,000 profit"
        stage9_res = run_stage9_apk_domain(job_id="test-ocr-stage9", ocr_text=ocr_text)

        assert stage9_res["any_threat_detected"] is True
        assert stage9_res["ocr_domain_result"] is not None
        assert stage9_res["ocr_domain_result"]["any_phishing"] is True
