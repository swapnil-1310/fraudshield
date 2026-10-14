"""
Experiment 1: Native Distribution Benchmark on Held-Out Test Split
===================================================================
Evaluates the unchanged FraudShield vision checkpoint (deepfake_detector_phase2.pth)
on its native training distribution:
  - Dataset: 140k Real and Fake Faces (held-out 'test' split)
  - Real: Flickr-Faces-HQ (FFHQ) genuine human faces
  - Fake: StyleGAN2 synthesized AI faces
  - Checkpoint: AdityaManojShinde/deepfake-detector (deepfake_detector_phase2.pth)
  - Preprocessing: Exact author pipeline (Resize 224x224, ToTensor, ImageNet Normalize)
  - Classification Threshold: 0.50 (unchanged production threshold)

Saves predictions to reports/experiment1_native_test_predictions.csv.
"""

import os
import sys
import csv
import io
import time
import json
import urllib.request
import numpy as np
import torch
from PIL import Image
from torchvision import transforms

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from huggingface_hub import hf_hub_download
from src.model import HybridDeepfakeDetector


def compute_roc_auc(y_true, y_scores):
    if len(set(y_true)) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(y_true, y_scores))
    except Exception:
        pos = [s for y, s in zip(y_true, y_scores) if y == 1]
        neg = [s for y, s in zip(y_true, y_scores) if y == 0]
        if not pos or not neg:
            return None
        rank_sum = sum(1.0 if p > n else (0.5 if p == n else 0.0) for p in pos for n in neg)
        return rank_sum / (len(pos) * len(neg))


def run_experiment1(num_samples: int = 40):
    print("=" * 80)
    print("  EXPERIMENT 1: NATIVE DISTRIBUTION BENCHMARK (HELD-OUT TEST SPLIT)")
    print("=" * 80)

    # 1. Load unchanged production checkpoint
    print("\n[1] Checkpoint Details:")
    model_id = "AdityaManojShinde/deepfake-detector"
    weights_filename = "deepfake_detector_phase2.pth"
    print(f"  • Model Identity : {model_id}")
    print(f"  • Weights File   : {weights_filename}")

    weights_path = hf_hub_download(repo_id=model_id, filename=weights_filename)
    model = HybridDeepfakeDetector()
    model.load_state_dict(torch.load(weights_path, map_location="cpu"), strict=True)
    model.eval()
    print("  • Checkpoint loaded successfully with strict=True.")

    # 2. Dataset Provenance
    print("\n[2] Dataset Provenance:")
    print("  • Dataset Name   : 140k Real and Fake Faces (Kaggle: xhlulu/140k-real-and-fake-faces)")
    print("  • Upstream Split : 'test' split (Held-out, strictly disjoint from 'train')")
    print("  • Classes        : 0 = Real (FFHQ), 1 = Fake (StyleGAN2)")
    print(f"  • Sample Target  : {num_samples} balanced test images (disjoint held-out set)")

    # Preprocessing
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # Fetch rows from Serverless Datasets API
    api_url = f"https://datasets-server.huggingface.co/rows?dataset=TheKernel01%2F140k-Real-and-Fake-Faces&config=default&split=test&offset=0&limit={num_samples}"
    print(f"\n[3] Fetching held-out test rows from Hugging Face Datasets API...")
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rows = data.get("rows", [])
        print(f"  • Successfully received {len(rows)} test items from held-out split.")
    except Exception as e:
        print(f"[FATAL] Failed to access held-out test split: {e}")
        print("LIMITATION REPORT: The remote test split could not be downloaded. Aborting without fabrication.")
        return

    threshold = 0.50
    results = []

    print(f"\n[4] Running Production Model on Held-Out Test Images (Threshold = {threshold}):")
    print("-" * 80)
    print(f"  {'Index':<6} | {'Generator':<10} | {'True':<5} | {'Pred':<5} | {'Raw P(real)':<12} | {'P(fake)':<10} | {'Status'}")
    print("  " + "-" * 72)

    for i, r in enumerate(rows):
        row_data = r.get("row", {})
        true_label = int(row_data.get("label", 0))
        gen_type = row_data.get("generator", "Unknown")
        img_info = row_data.get("image", {})
        img_url = img_info.get("src")

        t0 = time.perf_counter()
        try:
            img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                img_bytes = img_resp.read()
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            tensor = transform(img).unsqueeze(0)
            with torch.no_grad():
                prob_real = float(model(tensor).item())

            fake_prob = max(0.0, min(1.0, 1.0 - prob_real))
            pred_label = 1 if fake_prob > threshold else 0
            elapsed = time.perf_counter() - t0

            is_correct = (pred_label == true_label)
            status_str = "CORRECT" if is_correct else "INCORRECT"

            print(f"  {i+1:<6} | {gen_type:<10} | {true_label:<5} | {pred_label:<5} | {prob_real:<12.6f} | {fake_prob:<10.6f} | {status_str}")

            results.append({
                "sample_id": f"test_{i:04d}",
                "generator": gen_type,
                "true_label": true_label,
                "predicted_label": pred_label,
                "prob_real": round(prob_real, 6),
                "fake_prob": round(fake_prob, 6),
                "threshold": threshold,
                "is_correct": is_correct,
                "inference_time_sec": round(elapsed, 4),
                "error": None
            })

        except Exception as ex:
            print(f"  {i+1:<6} | {gen_type:<10} | {true_label:<5} | ERROR: {ex}")
            results.append({
                "sample_id": f"test_{i:04d}",
                "generator": gen_type,
                "true_label": true_label,
                "predicted_label": None,
                "prob_real": None,
                "fake_prob": None,
                "threshold": threshold,
                "is_correct": False,
                "inference_time_sec": 0.0,
                "error": str(ex)
            })

    # Save to CSV
    output_csv = os.path.join(APP_ROOT, "reports", "experiment1_native_test_predictions.csv")
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    fields = [
        "sample_id", "generator", "true_label", "predicted_label",
        "prob_real", "fake_prob", "threshold", "is_correct", "inference_time_sec", "error"
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for res in results:
            writer.writerow(res)

    print(f"\n[5] Saved native distribution test predictions to: {output_csv}")

    # Mirror to workspace root reports
    root_csv = os.path.join(APP_ROOT, "..", "reports", "experiment1_native_test_predictions.csv")
    try:
        os.makedirs(os.path.dirname(root_csv), exist_ok=True)
        import shutil
        shutil.copy2(output_csv, root_csv)
    except Exception:
        pass

    # Compute Statistical Metrics
    valid = [r for r in results if r["predicted_label"] is not None]
    tp = sum(1 for r in valid if r["true_label"] == 1 and r["predicted_label"] == 1)
    tn = sum(1 for r in valid if r["true_label"] == 0 and r["predicted_label"] == 0)
    fp = sum(1 for r in valid if r["true_label"] == 0 and r["predicted_label"] == 1)
    fn = sum(1 for r in valid if r["true_label"] == 1 and r["predicted_label"] == 0)

    total_valid = len(valid)
    accuracy = (tp + tn) / total_valid if total_valid > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    y_true = [r["true_label"] for r in valid]
    y_scores = [r["fake_prob"] for r in valid]
    roc_auc = compute_roc_auc(y_true, y_scores)

    print("\n" + "=" * 80)
    print("             EXPERIMENT 1 BENCHMARK SUMMARY (NATIVE TEST SPLIT)")
    print("=" * 80)
    print(f"  • Total Samples Evaluated    : {len(valid)} / {len(results)}")
    print(f"  • Real Samples (FFHQ)        : {sum(1 for r in valid if r['true_label'] == 0)}")
    print(f"  • Fake Samples (StyleGAN2)   : {sum(1 for r in valid if r['true_label'] == 1)}")
    print(f"  • True Positives (TP)        : {tp}")
    print(f"  • True Negatives (TN)        : {tn}")
    print(f"  • False Positives (FP)       : {fp}")
    print(f"  • False Negatives (FN)       : {fn}")
    print("  " + "-" * 50)
    print(f"  • Accuracy                   : {accuracy * 100:.2f}% ({tp+tn}/{total_valid})")
    print(f"  • Precision                  : {precision * 100:.2f}%")
    print(f"  • Recall / Sensitivity       : {recall * 100:.2f}%")
    print(f"  • Specificity                : {specificity * 100:.2f}%")
    print(f"  • False Positive Rate (FPR)  : {fpr * 100:.2f}%")
    print(f"  • F1-Score                   : {f1:.4f}")
    if roc_auc is not None:
        print(f"  • ROC-AUC Score              : {roc_auc:.4f}")
    else:
        print(f"  • ROC-AUC Score              : N/A")
    print("=" * 80)


if __name__ == "__main__":
    run_experiment1(num_samples=40)
