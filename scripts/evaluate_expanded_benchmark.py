"""
Expanded Benchmark: Baseline vs. Candidate Deepfake Detector
=============================================================
Evaluates both the production Baseline Detector (EfficientNet-B4 + SRM Xception)
and Candidate Detector (MS-EffGCViT-B0) across 20 FaceForensics++ c23 videos:
  - 5 Original authentic YouTube videos (Label 0)
  - 5 Deepfakes autoencoder swap videos (Label 1)
  - 5 Face2Face expression reenactment videos (Label 1)
  - 5 FaceSwap graphics swap videos (Label 1)

Guarantees identical MTCNN face sampling and exact preprocessing comparison.
Evaluates both tau = 0.50 and tau = 0.60 decision thresholds.

Usage:
  python scripts/evaluate_expanded_benchmark.py
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
from PIL import Image
from torchvision import transforms

# Ensure line-buffered stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

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
from src.model import HybridDeepfakeDetector
from src.stages.stage1_ingest import run_stage1_ingest
from sklearn.metrics import roc_auc_score


def preprocess_candidate(img_bgr, target_size=(224, 224)):
    """Candidate isotropic resize + black pad + ImageNet normalization."""
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
    return torch.from_numpy(norm).permute(2, 0, 1).unsqueeze(0).float()


def find_all_benchmark_videos(dataset_root):
    """Discovers original and all 3 manipulation types."""
    videos = []
    
    # 1. Original YouTube
    orig_dir = os.path.join(dataset_root, "original_sequences", "youtube", "c23", "videos")
    if os.path.isdir(orig_dir):
        for f in sorted(os.listdir(orig_dir)):
            if f.lower().endswith((".mp4", ".avi", ".mov")):
                videos.append({
                    "path": os.path.join(orig_dir, f),
                    "filename": f,
                    "method": "Original",
                    "true_label": 0
                })

    # 2. Manipulated sequences: Deepfakes, Face2Face, FaceSwap
    for method in ["Deepfakes", "Face2Face", "FaceSwap"]:
        m_dir = os.path.join(dataset_root, "manipulated_sequences", method, "c23", "videos")
        if os.path.isdir(m_dir):
            for f in sorted(os.listdir(m_dir)):
                if f.lower().endswith((".mp4", ".avi", ".mov")):
                    videos.append({
                        "path": os.path.join(m_dir, f),
                        "filename": f,
                        "method": method,
                        "true_label": 1
                    })

    return videos


def compute_metrics(y_true, y_scores, threshold=0.50):
    """Computes standard binary classification metrics."""
    y_pred = [1 if s > threshold else 0 for s in y_scores]
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    total = len(y_true)
    acc = (tp + tn) / total if total > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    try:
        auc = roc_auc_score(y_true, y_scores) if len(set(y_true)) > 1 else None
    except Exception:
        auc = None

    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "acc": acc, "prec": prec, "rec": rec, "spec": spec, "f1": f1, "auc": auc
    }


def main():
    parser = argparse.ArgumentParser(description="Expanded Benchmark of Baseline vs Candidate Deepfake Detector.")
    parser.add_argument("--dataset-dir", default=None, help="Path to datasets/face_data")
    parser.add_argument("--output-csv", default=None, help="Path to save predictions CSV")
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    if dataset_dir is None:
        dataset_dir = os.path.abspath(os.path.join(PARENT_ROOT, "datasets", "face_data"))

    output_csv = args.output_csv
    if output_csv is None:
        output_csv = os.path.join(APP_ROOT, "reports", "expanded_evaluation_predictions.csv")

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    temp_base = os.path.join(APP_ROOT, "temp")
    os.makedirs(temp_base, exist_ok=True)

    print("=" * 85)
    print("  FinGuard / FraudShield — Expanded Multi-Method Video Deepfake Benchmark")
    print("=" * 85)

    # 1. Discover Videos
    videos = find_all_benchmark_videos(dataset_dir)
    print(f"\n[1] Discovered {len(videos)} videos across FaceForensics++ c23:")
    methods_count = {}
    for v in videos:
        methods_count[v["method"]] = methods_count.get(v["method"], 0) + 1
    for m, c in methods_count.items():
        print(f"  • {m:15s}: {c} videos")

    if len(videos) < 10:
        print("[!] Too few videos found. Aborting.")
        sys.exit(1)

    # 2. Load Models
    print("\n[2] Loading Forensic Detectors into Memory:")
    # Baseline
    t0 = time.perf_counter()
    baseline_weights = r"C:\Users\LOQ\.cache\huggingface\hub\models--AdityaManojShinde--deepfake-detector\snapshots\c41aa713f354dc9a836b5d2e090319ef3572420b\deepfake_detector_phase2.pth"
    baseline_model = HybridDeepfakeDetector()
    baseline_model.load_state_dict(torch.load(baseline_weights, map_location="cpu"))
    baseline_model.eval()
    print(f"  • Baseline Detector  : HybridDeepfakeDetector loaded in {time.perf_counter() - t0:.2f}s")

    # Baseline transform
    baseline_tfm = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # Candidate
    t0 = time.perf_counter()
    cand_weights = r"C:\Users\LOQ\.cache\huggingface\hub\models--KoreaPeter--ms-eff-gcvit-deepfake-b0-ff-plus-plus\snapshots\db131babaff2cac0b2e9c2d2db3db41b5c9e802b\model.safetensors"
    cand_sd = load_file(cand_weights)
    cand_clean = {k.replace("model.", ""): v for k, v in cand_sd.items() if k.startswith("model.")}
    cand_model = ms_eff_gcvit_b0(pretrained=False, dataset="ff++")
    cand_model.load_state_dict(cand_clean, strict=True)
    cand_model.eval()
    print(f"  • Candidate Detector : MS-EffGCViT-B0 loaded in {time.perf_counter() - t0:.2f}s")

    # 3. Process Each Video
    print("\n[3] Running Identical Ingestion & Dual Evaluation on Videos:")
    print("-" * 85)

    results = []

    for idx, item in enumerate(videos, start=1):
        v_path = item["path"]
        fname = item["filename"]
        method = item["method"]
        true_lbl = item["true_label"]
        tag = "REAL" if true_lbl == 0 else f"FAKE ({method})"

        job_id = f"exp_{uuid.uuid4().hex[:8]}"
        job_temp = os.path.join(temp_base, job_id)
        os.makedirs(job_temp, exist_ok=True)

        print(f"\n[{idx:02d}/{len(videos):02d}] Evaluating {fname:15s} [{tag}] (Job: {job_id})")

        rec = {
            "filename": fname,
            "method": method,
            "true_label": true_lbl,
            "faces_extracted": 0,
            "baseline_consensus": None,
            "baseline_peak": None,
            "baseline_avg": None,
            "baseline_pred_050": None,
            "baseline_pred_060": None,
            "baseline_time_sec": 0.0,
            "candidate_consensus": None,
            "candidate_peak": None,
            "candidate_avg": None,
            "candidate_pred_050": None,
            "candidate_pred_060": None,
            "candidate_time_sec": 0.0,
            "status": "success",
            "error": None
        }

        try:
            # Stage 1: Ingest ONCE per video -> identical faces for both models
            ingest_res = run_stage1_ingest(v_path, job_temp, job_id)
            face_paths = ingest_res.get("face_frames_paths", [])
            rec["faces_extracted"] = len(face_paths)

            if not face_paths:
                raise ValueError("No face detected in video.")

            # --- A. Evaluate Baseline ---
            t_base_start = time.perf_counter()
            base_scores = []
            for fp in face_paths:
                pil_img = Image.open(fp).convert("RGB")
                inp = baseline_tfm(pil_img).unsqueeze(0)
                with torch.no_grad():
                    prob_real = baseline_model(inp).item()
                    fake_prob = max(0.0, min(1.0, 1.0 - prob_real))
                    base_scores.append(fake_prob)

            base_sorted = sorted(base_scores, reverse=True)
            k = min(3, len(base_sorted))
            base_top3 = float(np.mean(base_sorted[:k]))
            base_peak = float(max(base_scores))
            base_consensus = float(0.65 * base_top3 + 0.35 * base_peak)
            base_elapsed = round(time.perf_counter() - t_base_start, 3)

            rec.update({
                "baseline_consensus": round(base_consensus, 6),
                "baseline_peak": round(base_peak, 6),
                "baseline_avg": round(float(np.mean(base_scores)), 6),
                "baseline_pred_050": 1 if base_consensus > 0.50 else 0,
                "baseline_pred_060": 1 if base_consensus > 0.60 else 0,
                "baseline_time_sec": base_elapsed
            })

            # --- B. Evaluate Candidate ---
            t_cand_start = time.perf_counter()
            cand_scores = []
            for fp in face_paths:
                bgr = cv2.imread(fp)
                if bgr is None:
                    continue
                inp = preprocess_candidate(bgr)
                with torch.no_grad():
                    logit = cand_model(inp).item()
                    prob = torch.sigmoid(torch.tensor(logit)).item()
                    cand_scores.append(prob)

            cand_sorted = sorted(cand_scores, reverse=True)
            k = min(3, len(cand_sorted))
            cand_top3 = float(np.mean(cand_sorted[:k]))
            cand_peak = float(max(cand_scores))
            cand_consensus = float(0.65 * cand_top3 + 0.35 * cand_peak)
            cand_elapsed = round(time.perf_counter() - t_cand_start, 3)

            rec.update({
                "candidate_consensus": round(cand_consensus, 6),
                "candidate_peak": round(cand_peak, 6),
                "candidate_avg": round(float(np.mean(cand_scores)), 6),
                "candidate_pred_050": 1 if cand_consensus > 0.50 else 0,
                "candidate_pred_060": 1 if cand_consensus > 0.60 else 0,
                "candidate_time_sec": cand_elapsed
            })

            b_pred = rec["baseline_pred_050"]
            c_pred = rec["candidate_pred_050"]
            b_ok = "CORRECT" if b_pred == true_lbl else "WRONG"
            c_ok = "CORRECT" if c_pred == true_lbl else "WRONG"

            print(f"      -> Baseline  : Score={base_consensus:.4f} (Pred={b_pred}) | {b_ok:7s} in {base_elapsed:.2f}s")
            print(f"      -> Candidate : Score={cand_consensus:.4f} (Pred={c_pred}) | {c_ok:7s} in {cand_elapsed:.2f}s")

        except Exception as ex:
            rec["status"] = "failed"
            rec["error"] = str(ex)
            print(f"      -> [ERROR] Failed evaluating {fname}: {ex}")

        finally:
            shutil.rmtree(job_temp, ignore_errors=True)

        results.append(rec)

    # 4. Save CSV
    fieldnames = list(results[0].keys())
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\n[4] Saved predictions to {output_csv}")

    # Mirror to parent reports
    parent_csv = os.path.join(PARENT_ROOT, "reports", "expanded_evaluation_predictions.csv")
    try:
        os.makedirs(os.path.dirname(parent_csv), exist_ok=True)
        shutil.copyfile(output_csv, parent_csv)
    except Exception:
        pass

    # 5. Compute Detailed Summaries
    valid = [r for r in results if r["status"] == "success"]
    y_true = [r["true_label"] for r in valid]
    base_scores = [r["baseline_consensus"] for r in valid]
    cand_scores = [r["candidate_consensus"] for r in valid]

    print("\n" + "=" * 85)
    print("  EXPANDED BENCHMARK SUMMARY (20 FaceForensics++ c23 Videos)")
    print("=" * 85)

    for th in [0.50, 0.60]:
        bm = compute_metrics(y_true, base_scores, threshold=th)
        cm = compute_metrics(y_true, cand_scores, threshold=th)
        print(f"\n--- Threshold tau = {th:.2f} ---")
        print(f"  • Accuracy    : Baseline = {bm['acc']*100:5.1f}% ({bm['tp']+bm['tn']}/{len(valid)}) | Candidate = {cm['acc']*100:5.1f}% ({cm['tp']+cm['tn']}/{len(valid)})")
        print(f"  • Precision   : Baseline = {bm['prec']*100:5.1f}%          | Candidate = {cm['prec']*100:5.1f}%")
        print(f"  • Recall      : Baseline = {bm['rec']*100:5.1f}% ({bm['tp']}/15)    | Candidate = {cm['rec']*100:5.1f}% ({cm['tp']}/15)")
        print(f"  • Specificity : Baseline = {bm['spec']*100:5.1f}% ({bm['tn']}/5)     | Candidate = {cm['spec']*100:5.1f}% ({cm['tn']}/5)")
        b_auc_str = f"{bm['auc']:.4f}" if bm['auc'] is not None else "N/A"
        c_auc_str = f"{cm['auc']:.4f}" if cm['auc'] is not None else "N/A"
        print(f"  • ROC-AUC     : Baseline = {b_auc_str:6s}           | Candidate = {c_auc_str:6s}")

    # Per-Method Recall
    print("\n--- Per-Method Recall Breakdown (Threshold = 0.50) ---")
    for m in ["Deepfakes", "Face2Face", "FaceSwap"]:
        sub = [r for r in valid if r["method"] == m]
        b_hits = sum(1 for r in sub if r["baseline_pred_050"] == 1)
        c_hits = sum(1 for r in sub if r["candidate_pred_050"] == 1)
        print(f"  • {m:12s} ({len(sub)} videos): Baseline Recall = {b_hits/len(sub)*100:5.1f}% ({b_hits}/{len(sub)}) | Candidate Recall = {c_hits/len(sub)*100:5.1f}% ({c_hits}/{len(sub)})")

    # Timing
    b_mean_time = np.mean([r["baseline_time_sec"] for r in valid])
    c_mean_time = np.mean([r["candidate_time_sec"] for r in valid])
    print(f"\n--- Mean Inference Latency per Video ---")
    print(f"  • Baseline  : {b_mean_time:.2f}s")
    print(f"  • Candidate : {c_mean_time:.2f}s ({((b_mean_time - c_mean_time)/b_mean_time)*100:.1f}% faster)")
    print("=" * 85)


if __name__ == "__main__":
    main()
