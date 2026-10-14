"""
Standalone Evaluation Script for Candidate Video Deepfake Detector
===================================================================
Evaluates the candidate model: KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus
on the identical 10 FaceForensics++ benchmark videos used for the FraudShield baseline.

Architecture: MS-EffGCViT-B0 (Multi-Scale Efficient GCViT B0)
Parameters: ~8.9M (34.02 MB)
Backbone: tf_efficientnet_b0.ns_jft_in1k + GCViT attention heads
Trained on: FaceForensics++ (Deepfakes, Face2Face, FaceSwap, FaceShifter, NeuralTextures)
License: MIT

Requirements:
  - Isolated script: zero modifications to production pipeline, app.py, config.yaml, or existing weights.
  - Same 10 FF++ videos and Stage 1 MTCNN face crops as baseline.
  - Verifies probability calibration and output interpretation.
  - Saves per-video predictions and comparative metrics to reports/.

Usage:
  python scripts/evaluate_candidate_detector.py
"""

import os
import sys
import csv
import time
import uuid
import shutil
import argparse
import numpy as np
import cv2
import torch

# Ensure line-buffered stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# Add application root and candidate library to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(SCRIPT_DIR)
PARENT_ROOT = os.path.dirname(APP_ROOT)

if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

DEEPGUARD_PATH = r"C:\Users\LOQ\.gemini\antigravity-ide\brain\0f62b656-64c0-41a1-9c93-381e7c006b16\scratch\deepguard_pkg"
if DEEPGUARD_PATH not in sys.path:
    sys.path.insert(0, DEEPGUARD_PATH)

from safetensors.torch import load_file
from deepguard.models.ms_eff_gcvit import ms_eff_gcvit_b0
from src.stages.stage1_ingest import run_stage1_ingest


def compute_roc_auc(y_true, y_scores):
    """Computes exact Area Under the ROC Curve with rank-sum tie handling."""
    if len(set(y_true)) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(y_true, y_scores))
    except Exception:
        pass

    # Fallback rank-sum implementation
    pos_scores = [s for y, s in zip(y_true, y_scores) if y == 1]
    neg_scores = [s for y, s in zip(y_true, y_scores) if y == 0]
    n_pos = len(pos_scores)
    n_neg = len(neg_scores)
    if n_pos == 0 or n_neg == 0:
        return None

    all_items = sorted([(s, y) for s, y in zip(y_scores, y_true)], key=lambda x: x[0])
    ranks = {}
    i = 0
    n = len(all_items)
    while i < n:
        j = i
        while j < n and all_items[j][0] == all_items[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j

    sum_pos_ranks = sum(ranks[k] for k, (s, y) in enumerate(all_items) if y == 1)
    u_stat = sum_pos_ranks - (n_pos * (n_pos + 1)) / 2.0
    return float(u_stat / (n_pos * n_neg))


def find_dataset_videos(dataset_root):
    """Locates the 10 FaceForensics++ benchmark videos."""
    videos = []
    real_dir = os.path.join(dataset_root, "original_sequences", "youtube", "c23", "videos")
    if os.path.isdir(real_dir):
        for f in sorted(os.listdir(real_dir)):
            if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                videos.append({
                    "path": os.path.join(real_dir, f),
                    "filename": f,
                    "sequence_type": "original_youtube_c23",
                    "true_label": 0
                })

    fake_dir = os.path.join(dataset_root, "manipulated_sequences", "Deepfakes", "c23", "videos")
    if os.path.isdir(fake_dir):
        for f in sorted(os.listdir(fake_dir)):
            if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                videos.append({
                    "path": os.path.join(fake_dir, f),
                    "filename": f,
                    "sequence_type": "manipulated_Deepfakes_c23",
                    "true_label": 1
                })

    return videos


def preprocess_face_crop(img_bgr, target_size=(224, 224)):
    """
    Candidate model preprocessing:
      - RGB conversion
      - Isotropic resize keeping aspect ratio
      - Constant black border padding to (224, 224)
      - ImageNet mean/std normalization
    """
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    target_h, target_w = target_size
    scale = min(target_h / h, target_w / w)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    pad_h = target_h - new_h
    pad_w = target_w - new_w
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left

    padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    norm = (padded.astype(np.float32) / 255.0 - mean) / std
    tensor = torch.from_numpy(norm).permute(2, 0, 1).unsqueeze(0).float()
    return tensor


def load_candidate_model(checkpoint_path, device="cpu"):
    """Loads MS-EffGCViT-B0 from safetensors with strict key matching."""
    state_dict = load_file(checkpoint_path)
    clean_sd = {k.replace("model.", ""): v for k, v in state_dict.items() if k.startswith("model.")}
    model = ms_eff_gcvit_b0(pretrained=False, dataset="ff++")
    model.load_state_dict(clean_sd, strict=True)
    model.to(device)
    model.eval()
    return model


def main():
    parser = argparse.ArgumentParser(description="Evaluate Candidate Video Deepfake Detector on FaceForensics++.")
    parser.add_argument("--dataset-dir", default=None, help="Path to datasets/face_data")
    parser.add_argument("--output-csv", default=None, help="Path to save candidate predictions CSV")
    parser.add_argument("--threshold", type=float, default=0.50, help="Classification decision threshold (default 0.50)")
    args = parser.parse_args()

    # Resolve paths
    dataset_dir = args.dataset_dir
    if dataset_dir is None:
        candidates = [
            os.path.join(PARENT_ROOT, "datasets", "face_data"),
            os.path.join(APP_ROOT, "datasets", "face_data"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                dataset_dir = os.path.abspath(c)
                break
        if dataset_dir is None:
            dataset_dir = os.path.abspath(os.path.join(PARENT_ROOT, "datasets", "face_data"))

    output_csv = args.output_csv
    if output_csv is None:
        output_csv = os.path.join(APP_ROOT, "reports", "candidate_evaluation_predictions.csv")
    elif not os.path.isabs(output_csv):
        output_csv = os.path.abspath(output_csv)

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    temp_base = os.path.join(APP_ROOT, "temp")
    os.makedirs(temp_base, exist_ok=True)

    checkpoint_path = r"C:\Users\LOQ\.cache\huggingface\hub\models--KoreaPeter--ms-eff-gcvit-deepfake-b0-ff-plus-plus\snapshots\db131babaff2cac0b2e9c2d2db3db41b5c9e802b\model.safetensors"

    print("=" * 80)
    print("  FinGuard / FraudShield — Candidate Video Deepfake Detector Evaluation")
    print("=" * 80)
    print("  Candidate Architecture : MS-EffGCViT-B0 (Multi-Scale Efficient GCViT B0)")
    print("  Candidate Checkpoint   : KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus")
    print("  Parameters / Size      : 8,916,901 params (34.02 MB float32)")
    print("  Training Dataset       : FaceForensics++ (5 manipulation types + pristine)")
    print(f"  Decision Threshold     : {args.threshold:.2f}")
    print(f"  Target Videos          : 10 FaceForensics++ c23 (5 Real, 5 Deepfakes)")
    print("=" * 80)

    # 1. Load Model
    print("\n[1] Loading Candidate Model...")
    t_load_start = time.perf_counter()
    model = load_candidate_model(checkpoint_path, device="cpu")
    t_load_end = time.perf_counter()
    print(f"  -> Model loaded successfully in {t_load_end - t_load_start:.2f}s with strict=True.")

    # 2. Discover Videos
    video_items = find_dataset_videos(dataset_dir)
    print(f"\n[2] Dataset Discovery ({len(video_items)} videos found):")
    for v in video_items:
        print(f"  • [{'REAL' if v['true_label']==0 else 'FAKE'}] {v['filename']} ({v['sequence_type']})")

    if not video_items:
        print("[!] No videos found. Exiting.")
        sys.exit(1)

    # 3. Evaluate Videos
    results = []
    print("\n[3] Running Isolated Evaluation Pipeline:")
    print("-" * 80)

    for idx, item in enumerate(video_items, start=1):
        v_path = item["path"]
        fname = item["filename"]
        true_lbl = item["true_label"]
        seq_type = item["sequence_type"]
        tag = "REAL" if true_lbl == 0 else "FAKE"

        job_id = f"cand_{uuid.uuid4().hex[:8]}"
        job_temp_dir = os.path.join(temp_base, job_id)
        os.makedirs(job_temp_dir, exist_ok=True)

        print(f"\n[{idx:02d}/{len(video_items):02d}] Evaluating: {fname} [{tag}] (Job: {job_id})")
        t_start = time.perf_counter()

        record = {
            "video_path": v_path,
            "filename": fname,
            "sequence_type": seq_type,
            "true_label": true_lbl,
            "predicted_label": None,
            "confidence_score": None,      # FraudShield Consensus score
            "raw_peak_score": None,        # Max frame score
            "top3_mean_score": None,       # Top 3 mean
            "avg_score": None,             # Mean across all frames
            "min_score": None,             # Min frame score
            "threshold": args.threshold,
            "inference_time_sec": 0.0,
            "faces_extracted": 0,
            "status": "pending",
            "error": None
        }

        try:
            # Stage 1: Ingest & Face Extraction (Exact same MTCNN extraction as baseline)
            ingest_res = run_stage1_ingest(v_path, job_temp_dir, job_id)
            face_frames = ingest_res.get("face_frames_paths", [])
            record["faces_extracted"] = len(face_frames)

            if not face_frames:
                raise ValueError("No face detected in video (0 candidate face frames extracted).")

            # Score each face frame with candidate model
            scores = []
            for fp in face_frames:
                bgr = cv2.imread(fp)
                if bgr is None:
                    continue
                inp = preprocess_face_crop(bgr)
                with torch.no_grad():
                    logit = model(inp).item()
                    prob = torch.sigmoid(torch.tensor(logit)).item()
                    scores.append(prob)

            if not scores:
                raise ValueError("Failed to evaluate face frames.")

            scores_sorted = sorted(scores, reverse=True)
            k = min(3, len(scores_sorted))
            top3_mean = float(np.mean(scores_sorted[:k]))
            peak_score = float(max(scores))
            min_score = float(min(scores))
            avg_score = float(np.mean(scores))

            # Temporal consensus formula used in FraudShield: 0.65 * top3 + 0.35 * peak
            consensus_score = float(0.65 * top3_mean + 0.35 * peak_score)
            pred_label = 1 if consensus_score > args.threshold else 0

            elapsed = round(time.perf_counter() - t_start, 3)
            record.update({
                "predicted_label": pred_label,
                "confidence_score": round(consensus_score, 6),
                "raw_peak_score": round(peak_score, 6),
                "top3_mean_score": round(top3_mean, 6),
                "avg_score": round(avg_score, 6),
                "min_score": round(min_score, 6),
                "inference_time_sec": elapsed,
                "status": "success",
                "error": None
            })

            correct = (pred_label == true_lbl)
            res_str = "CORRECT" if correct else "INCORRECT"
            print(f"      -> Result: Pred={pred_label} (Consensus={consensus_score:.4f}, Peak={peak_score:.4f}, Avg={avg_score:.4f}) | True={true_lbl} | {res_str} in {elapsed:.2f}s")

        except Exception as ex:
            elapsed = round(time.perf_counter() - t_start, 3)
            err_msg = str(ex)
            record.update({
                "inference_time_sec": elapsed,
                "status": "failed",
                "error": err_msg
            })
            print(f"      -> [ERROR] Failed: {err_msg} ({elapsed:.2f}s)")

        finally:
            shutil.rmtree(job_temp_dir, ignore_errors=True)

        results.append(record)

    # 4. Save CSV
    fieldnames = [
        "filename", "sequence_type", "true_label", "predicted_label",
        "confidence_score", "raw_peak_score", "top3_mean_score", "avg_score", "min_score",
        "threshold", "inference_time_sec", "faces_extracted", "status", "error"
    ]
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\n[4] Candidate predictions saved to: {output_csv}")

    # Also mirror to parent reports directory
    parent_output_csv = os.path.join(PARENT_ROOT, "reports", "candidate_evaluation_predictions.csv")
    os.makedirs(os.path.dirname(parent_output_csv), exist_ok=True)
    try:
        shutil.copyfile(output_csv, parent_output_csv)
    except Exception:
        pass

    # 5. Compute Metrics
    valid = [r for r in results if r["status"] == "success"]
    y_true = [r["true_label"] for r in valid]
    y_pred = [r["predicted_label"] for r in valid]
    y_scores = [r["confidence_score"] for r in valid]

    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    accuracy = (tp + tn) / len(valid) if valid else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    auc = compute_roc_auc(y_true, y_scores)
    mean_inf_time = np.mean([r["inference_time_sec"] for r in valid]) if valid else 0.0

    print("\n" + "=" * 80)
    print("  CANDIDATE DETECTOR EVALUATION SUMMARY (10 FaceForensics++ Videos)")
    print("=" * 80)
    print(f"  • Total Evaluated      : {len(valid)} / {len(results)}")
    print(f"  • Accuracy             : {accuracy * 100:.2f}% ({tp + tn}/{len(valid)})")
    print(f"  • Precision (Fake=1)   : {precision * 100:.2f}% ({tp}/{tp + fp})")
    print(f"  • Recall (Fake=1)      : {recall * 100:.2f}% ({tp}/{tp + fn})")
    print(f"  • Specificity (Real=0) : {specificity * 100:.2f}% ({tn}/{tn + fp})")
    print(f"  • F1-Score             : {f1:.4f}")
    print(f"  • ROC-AUC              : {f'{auc:.4f}' if auc is not None else 'N/A'}")
    print(f"  • Mean Inference Time  : {mean_inf_time:.2f}s per video")
    print(f"  • Confusion Matrix     : TP={tp}, TN={tn}, FP={fp}, FN={fn}")
    print("=" * 80)


if __name__ == "__main__":
    main()
