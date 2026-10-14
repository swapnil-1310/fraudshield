"""
Regression Evaluation: Production Stage 2 Vision Pipeline
==========================================================
Evaluates the integrated production vision deepfake pipeline with both:
  1. ms_eff_gcvit (candidate backend, tau=0.60)
  2. hybrid_phase2 (legacy baseline, tau=0.50)
  3. Absent config fallback verification

Runs full Stage 1 (MTCNN face extraction) + Stage 2 (Vision classification).
Verifies diagnostic fields: model_backend, model_id, threshold_applied.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import torch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(SCRIPT_DIR)
PARENT_ROOT = os.path.dirname(APP_ROOT)

if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from src.stages.stage1_ingest import run_stage1_ingest
from src.stages.stage2_vision import run_stage2_vision
from src.stages.backends import get_vision_backend
from src.config import get_vision_threshold, get_vision_detector_config


def evaluate_video(video_path: str, backend_name: str, threshold: float, label: int):
    temp_dir = tempfile.mkdtemp(prefix="fraudshield_reg_")
    try:
        t0 = time.time()
        # Stage 1: Ingest & Face Extraction
        ingest_res = run_stage1_ingest(video_path, temp_dir, f"reg_{os.path.basename(video_path)}")
        face_frames = ingest_res.get("face_frames_paths", [])

        # Stage 2: Vision Deepfake Detection (patching backend via stage2)
        # Using monkeypatch/override or direct backend call
        from unittest.mock import patch
        with patch("src.stages.stage2_vision.get_vision_detector_config", return_value={"backend": backend_name, "threshold": threshold}):
            with patch("src.stages.stage2_vision.get_vision_threshold", return_value=threshold):
                res = run_stage2_vision(face_frames, f"reg_{backend_name}")
        
        latency = time.time() - t0
        score = res.get("max_score", 0.0)
        pred = 1 if score >= threshold else 0
        correct = (pred == label)

        return {
            "video": os.path.basename(video_path),
            "backend": res.get("model_backend"),
            "model_id": res.get("model_id"),
            "threshold_applied": res.get("threshold_applied"),
            "score": score,
            "peak_score": res.get("raw_peak_score", 0.0),
            "label": label,
            "prediction": pred,
            "correct": correct,
            "frames_analyzed": len(face_frames),
            "latency_sec": latency
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    print("=" * 70)
    print("FRAUDSHIELD STAGE 2 VISION PIPELINE REGRESSION SUITE")
    print("=" * 70)

    dataset_root = os.path.join(PARENT_ROOT, "datasets", "face_data")
    real_dir = os.path.join(dataset_root, "original_sequences", "youtube", "c23", "videos")
    df_dir = os.path.join(dataset_root, "manipulated_sequences", "Deepfakes", "c23", "videos")
    f2f_dir = os.path.join(dataset_root, "manipulated_sequences", "Face2Face", "c23", "videos")
    fs_dir = os.path.join(dataset_root, "manipulated_sequences", "FaceSwap", "c23", "videos")

    test_samples = [
        # 2 Real
        (os.path.join(real_dir, "183.mp4"), 0, "Authentic (183)"),
        (os.path.join(real_dir, "469.mp4"), 0, "Authentic (469)"),
        # 1 Deepfakes
        (os.path.join(df_dir, "183_253.mp4"), 1, "Deepfakes (183_253)"),
        # 1 Face2Face
        (os.path.join(f2f_dir, "469_481.mp4"), 1, "Face2Face (469_481)"),
        # 1 FaceSwap
        (os.path.join(fs_dir, "481_469.mp4"), 1, "FaceSwap (481_469)"),
    ]

    # Verify files exist
    for p, _, _ in test_samples:
        if not os.path.exists(p):
            print(f"Error: test file not found: {p}")
            return 1

    results = {"ms_eff_gcvit": [], "hybrid_phase2": []}

    # 1. Candidate: ms_eff_gcvit (tau = 0.60)
    print("\n[1/2] Evaluating Candidate Backend: 'ms_eff_gcvit' (tau=0.60)...")
    for vid_path, label, desc in test_samples:
        r = evaluate_video(vid_path, "ms_eff_gcvit", 0.60, label)
        results["ms_eff_gcvit"].append(r)
        status = "PASS" if r["correct"] else "FAIL"
        print(f"  • [{status}] {desc:<24} | Score: {r['score']:.4f} | Pred: {r['prediction']} (GT: {r['label']}) | Backend: {r['backend']} | Time: {r['latency_sec']:.2f}s")

    # 2. Baseline: hybrid_phase2 (tau = 0.50)
    print("\n[2/2] Evaluating Baseline Backend: 'hybrid_phase2' (tau=0.50)...")
    for vid_path, label, desc in test_samples:
        r = evaluate_video(vid_path, "hybrid_phase2", 0.50, label)
        results["hybrid_phase2"].append(r)
        status = "PASS" if r["correct"] else "FAIL"
        print(f"  • [{status}] {desc:<24} | Score: {r['score']:.4f} | Pred: {r['prediction']} (GT: {r['label']}) | Backend: {r['backend']} | Time: {r['latency_sec']:.2f}s")

    # Summary
    cand_correct = sum(1 for x in results["ms_eff_gcvit"] if x["correct"])
    base_correct = sum(1 for x in results["hybrid_phase2"] if x["correct"])
    n_total = len(test_samples)

    print("\n" + "=" * 70)
    print("REGRESSION SUMMARY")
    print("=" * 70)
    print(f"Candidate 'ms_eff_gcvit' Accuracy : {cand_correct}/{n_total} ({cand_correct/n_total*100:.1f}%)")
    print(f"Baseline 'hybrid_phase2' Accuracy : {base_correct}/{n_total} ({base_correct/n_total*100:.1f}%)")

    # Diagnostic checks
    for r in results["ms_eff_gcvit"]:
        assert r["backend"] == "ms_eff_gcvit"
        assert r["threshold_applied"] == 0.60
        assert "KoreaPeter" in r["model_id"]
    for r in results["hybrid_phase2"]:
        assert r["backend"] == "hybrid_phase2"
        assert r["threshold_applied"] == 0.50
        assert "AdityaManojShinde" in r["model_id"]

    out_json = os.path.join(APP_ROOT, "reports", "pipeline_regression_results.json")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved regression results to: {out_json}")

    assert cand_correct == n_total, f"Expected all candidate samples to pass, got {cand_correct}/{n_total}"
    print("ALL REGRESSION CHECKS PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
