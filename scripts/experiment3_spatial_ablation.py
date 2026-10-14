"""
Experiment 3: In-Memory Spatial-Only Ablation Diagnostic
========================================================
ABLATION EXPERIMENT ONLY — NOT A PRODUCTION-READY DETECTOR.

Isolates the Spatial Stream (EfficientNet-B4) by bypassing the Frequency Stream
(Xception + SRM) in-memory only.
Zeroes out frequency branch contributions without modifying production files,
config.yaml, or checkpoint weights on disk.

Evaluates the exact same 10 FaceForensics++ benchmark videos and directly compares:
  - Original Hybrid Model (Spatial + Frequency)
  - Spatial-Only Ablated Model (Spatial features only, Frequency = 0)

Saves comparative predictions to reports/experiment3_spatial_ablation_predictions.csv.
"""

import os
import sys
import csv
import copy
import time
import uuid
import shutil
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
from src.stages.stage1_ingest import run_stage1_ingest


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


class SpatialOnlyAblationWrapper(torch.nn.Module):
    """
    In-memory wrapper that evaluates ONLY the spatial stream (EfficientNet-B4).
    Forces frequency features to zero prior to classification, completely bypassing
    the frozen Xception + SRM branch without altering weights on disk.
    """
    def __init__(self, base_hybrid_model: HybridDeepfakeDetector):
        super().__init__()
        self.spatial = base_hybrid_model.spatial
        self.classifier = base_hybrid_model.classifier

    def forward(self, x):
        spatial_features = self.spatial(x)  # [B, 1792]
        # In-memory zero vector replacing the 2048-dim frequency stream
        zero_freq = torch.zeros((x.size(0), 2048), device=x.device, dtype=spatial_features.dtype)
        combined = torch.cat([spatial_features, zero_freq], dim=1)  # [B, 3840]
        return self.classifier(combined)


def run_experiment3():
    print("=" * 80)
    print("  EXPERIMENT 3: IN-MEMORY SPATIAL-ONLY ABLATION DIAGNOSTIC")
    print("  (Ablation Experiment Only — Not A Production-Ready Detector)")
    print("=" * 80)

    # 1. Load unchanged production checkpoint
    model_id = "AdityaManojShinde/deepfake-detector"
    weights_filename = "deepfake_detector_phase2.pth"
    print(f"\n[1] Checkpoint & Models Setup:")
    print(f"  • Checkpoint Identity : {model_id} ({weights_filename})")

    weights_path = hf_hub_download(repo_id=model_id, filename=weights_filename)
    hybrid_model = HybridDeepfakeDetector()
    hybrid_model.load_state_dict(torch.load(weights_path, map_location="cpu"), strict=True)
    hybrid_model.eval()

    # Create in-memory spatial-only ablation model
    spatial_only_model = SpatialOnlyAblationWrapper(hybrid_model)
    spatial_only_model.eval()
    print("  • Hybrid Model and Spatial-Only Ablation instantiated in-memory.")

    # 2. Locate the 10 FaceForensics++ videos
    dataset_root = os.path.abspath(os.path.join(APP_ROOT, "..", "datasets", "face_data"))
    real_dir = os.path.join(dataset_root, "original_sequences", "youtube", "c23", "videos")
    fake_dir = os.path.join(dataset_root, "manipulated_sequences", "Deepfakes", "c23", "videos")

    video_items = []
    for f in sorted(os.listdir(real_dir)):
        if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            video_items.append({"path": os.path.join(real_dir, f), "filename": f, "true_label": 0, "type": "REAL"})
    for f in sorted(os.listdir(fake_dir)):
        if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            video_items.append({"path": os.path.join(fake_dir, f), "filename": f, "true_label": 1, "type": "MANIPULATED"})

    print(f"\n[2] Target Videos: {len(video_items)} FaceForensics++ c23 videos (5 Real, 5 Manipulated)")

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    temp_base = os.path.join(APP_ROOT, "temp", "ablation_test")
    os.makedirs(temp_base, exist_ok=True)

    threshold = 0.50
    consensus_weight = 0.65
    records = []

    print(f"\n[3] Running Comparative Inference Across Both Models (Threshold = {threshold}):")
    print("-" * 80)
    print(f"  {'Filename':<12} | {'True':<5} | {'Hybrid Conf':<11} | {'Ablated Conf':<12} | {'Hybrid Pred':<11} | {'Ablated Pred':<12} | {'Delta Conf'}")
    print("  " + "-" * 80)

    for item in video_items:
        v_path = item["path"]
        fname = item["filename"]
        true_lbl = item["true_label"]
        v_type = item["type"]

        job_id = f"abl_{uuid.uuid4().hex[:8]}"
        job_temp = os.path.join(temp_base, job_id)
        os.makedirs(job_temp, exist_ok=True)

        t_start = time.perf_counter()
        try:
            ingest_res = run_stage1_ingest(v_path, job_temp, job_id)
            face_paths = ingest_res.get("face_frames_paths", [])

            scores_hybrid = []
            scores_spatial = []
            raw_p_real_hybrid = []
            raw_p_real_spatial = []

            with torch.no_grad():
                for fp in face_paths:
                    img = Image.open(fp).convert("RGB")
                    tensor = transform(img).unsqueeze(0)

                    # Original Hybrid
                    p_real_h = float(hybrid_model(tensor).item())
                    fake_p_h = max(0.0, min(1.0, 1.0 - p_real_h))
                    scores_hybrid.append(fake_p_h)
                    raw_p_real_hybrid.append(p_real_h)

                    # Spatial-Only Ablated
                    p_real_s = float(spatial_only_model(tensor).item())
                    fake_p_s = max(0.0, min(1.0, 1.0 - p_real_s))
                    scores_spatial.append(fake_p_s)
                    raw_p_real_spatial.append(p_real_s)

            # Consensus smoothing (identical formula to production stage2_vision.py)
            def calc_consensus(scs):
                if not scs:
                    return 0.0, 0.0, 0.0
                scs_sorted = sorted(scs, reverse=True)
                top_k = float(np.mean(scs_sorted[:min(3, len(scs_sorted))]))
                peak = float(scs_sorted[0])
                avg = float(np.mean(scs))
                cons = float(consensus_weight * top_k + (1.0 - consensus_weight) * peak) if len(scs) >= 3 else peak
                return cons, peak, avg

            conf_h, peak_h, avg_h = calc_consensus(scores_hybrid)
            conf_s, peak_s, avg_s = calc_consensus(scores_spatial)

            pred_h = 1 if conf_h > threshold else 0
            pred_s = 1 if conf_s > threshold else 0
            delta_conf = conf_s - conf_h

            elapsed = round(time.perf_counter() - t_start, 2)

            print(f"  {fname:<12} | {true_lbl:<5} | {conf_h:<11.6f} | {conf_s:<12.6f} | {pred_h:<11} | {pred_s:<12} | {delta_conf:+.6f}")

            records.append({
                "filename": fname,
                "sequence_type": v_type,
                "true_label": true_lbl,
                "faces_count": len(face_paths),
                "hybrid_confidence_score": round(conf_h, 6),
                "hybrid_peak_score": round(peak_h, 6),
                "hybrid_avg_score": round(avg_h, 6),
                "hybrid_mean_raw_real": round(float(np.mean(raw_p_real_hybrid)), 6),
                "hybrid_predicted_label": pred_h,
                "spatial_confidence_score": round(conf_s, 6),
                "spatial_peak_score": round(peak_s, 6),
                "spatial_avg_score": round(avg_s, 6),
                "spatial_mean_raw_real": round(float(np.mean(raw_p_real_spatial)), 6),
                "spatial_predicted_label": pred_s,
                "delta_confidence (spatial - hybrid)": round(delta_conf, 6),
                "inference_time_sec": elapsed,
                "error": None
            })

        except Exception as ex:
            print(f"  {fname:<12} | ERROR: {ex}")
            records.append({
                "filename": fname,
                "sequence_type": v_type,
                "true_label": true_lbl,
                "faces_count": 0,
                "hybrid_confidence_score": None,
                "hybrid_peak_score": None,
                "hybrid_avg_score": None,
                "hybrid_mean_raw_real": None,
                "hybrid_predicted_label": None,
                "spatial_confidence_score": None,
                "spatial_peak_score": None,
                "spatial_avg_score": None,
                "spatial_mean_raw_real": None,
                "spatial_predicted_label": None,
                "delta_confidence (spatial - hybrid)": None,
                "inference_time_sec": 0.0,
                "error": str(ex)
            })
        finally:
            shutil.rmtree(job_temp, ignore_errors=True)

    shutil.rmtree(temp_base, ignore_errors=True)

    # 4. Save to CSV
    output_csv = os.path.join(APP_ROOT, "reports", "experiment3_spatial_ablation_predictions.csv")
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    fieldnames = list(records[0].keys())
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    print(f"\n[4] Saved comparative predictions to: {output_csv}")

    # Mirror to workspace root reports
    root_csv = os.path.join(APP_ROOT, "..", "reports", "experiment3_spatial_ablation_predictions.csv")
    try:
        os.makedirs(os.path.dirname(root_csv), exist_ok=True)
        shutil.copy2(output_csv, root_csv)
    except Exception:
        pass

    # 5. Compute Comparative Metrics
    valid = [r for r in records if r["hybrid_predicted_label"] is not None and r["spatial_predicted_label"] is not None]

    def get_metrics(pred_key, conf_key):
        tp = sum(1 for r in valid if r["true_label"] == 1 and r[pred_key] == 1)
        tn = sum(1 for r in valid if r["true_label"] == 0 and r[pred_key] == 0)
        fp = sum(1 for r in valid if r["true_label"] == 0 and r[pred_key] == 1)
        fn = sum(1 for r in valid if r["true_label"] == 1 and r[pred_key] == 0)
        tot = len(valid)
        acc = (tp + tn) / tot if tot > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        roc = compute_roc_auc([r["true_label"] for r in valid], [r[conf_key] for r in valid])
        return {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "acc": acc, "prec": prec, "rec": rec, "spec": spec, "f1": f1, "roc": roc}

    m_hybrid = get_metrics("hybrid_predicted_label", "hybrid_confidence_score")
    m_spatial = get_metrics("spatial_predicted_label", "spatial_confidence_score")

    print("\n" + "=" * 80)
    print("             EXPERIMENT 3: COMPARATIVE PERFORMANCE METRICS")
    print("=" * 80)
    print(f"  {'Metric':<25} | {'Original Hybrid':<16} | {'Spatial-Only Ablated':<20}")
    print("  " + "-" * 67)
    print(f"  {'Accuracy':<25} | {m_hybrid['acc']*100:<15.2f}% | {m_spatial['acc']*100:<19.2f}%")
    print(f"  {'Precision':<25} | {m_hybrid['prec']*100:<15.2f}% | {m_spatial['prec']*100:<19.2f}%")
    print(f"  {'Recall / Sensitivity':<25} | {m_hybrid['rec']*100:<15.2f}% | {m_spatial['rec']*100:<19.2f}%")
    print(f"  {'Specificity':<25} | {m_hybrid['spec']*100:<15.2f}% | {m_spatial['spec']*100:<19.2f}%")
    print(f"  {'F1-Score':<25} | {m_hybrid['f1']:<16.4f} | {m_spatial['f1']:<20.4f}")
    roc_h_str = f"{m_hybrid['roc']:.4f}" if m_hybrid['roc'] is not None else "N/A"
    roc_s_str = f"{m_spatial['roc']:.4f}" if m_spatial['roc'] is not None else "N/A"
    print(f"  {'ROC-AUC':<25} | {roc_h_str:<16} | {roc_s_str:<20}")
    print(f"  {'Confusion Matrix (TP/TN/FP/FN)':<25} | {m_hybrid['tp']}/{m_hybrid['tn']}/{m_hybrid['fp']}/{m_hybrid['fn']:<10} | {m_spatial['tp']}/{m_spatial['tn']}/{m_spatial['fp']}/{m_spatial['fn']:<14}")
    print("=" * 80)


if __name__ == "__main__":
    run_experiment3()
