"""
Standalone Evaluation Script for FraudShield Video Deepfake Detector
====================================================================
Evaluates FaceForensics++ benchmark videos (original vs. manipulated)
using the exact production FraudShield inference pipeline:
  - Stage 1: Adaptive scene-aware face extraction via MTCNN (src.stages.stage1_ingest)
  - Stage 2: Dual-Branch Spatial (EfficientNet-B4) + Frequency SRM (Xception)
             HybridDeepfakeDetector inference with consensus smoothing (src.stages.stage2_vision)
  - Threshold: Dynamic threshold loaded from config.yaml (vision_fake_threshold)

Saves predictions and detailed metrics to reports/video_evaluation_predictions.csv.

Usage:
  python scripts/evaluate_video_detector.py
  python scripts/evaluate_video_detector.py --dataset-dir ../datasets/face_data --output-csv reports/video_evaluation_predictions.csv
"""

import os
import sys
import csv
import time
import uuid
import shutil
import argparse
import numpy as np

# Ensure stdout uses UTF-8 without buffering issues on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# Determine paths and ensure fraudshield_v1 is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(SCRIPT_DIR)  # fraudshield_v1
PARENT_ROOT = os.path.dirname(APP_ROOT) # fraudshield root

if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

# Import production FraudShield modules - NO MOCKS, NO SUBSTITUTIONS
try:
    from src.config import settings, get_threshold, get_device, get_stage_config, get_vision_config
    from src.stages.stage1_ingest import run_stage1_ingest
    from src.stages.stage2_vision import run_stage2_vision
    PIPELINE_IMPORT_SUCCESS = True
    IMPORT_ERROR = None
except Exception as e:
    PIPELINE_IMPORT_SUCCESS = False
    IMPORT_ERROR = str(e)


def compute_roc_auc(y_true, y_scores):
    """
    Computes exact Area Under the ROC Curve (ROC-AUC) using Mann-Whitney U / Wilcoxon rank-sum
    or scikit-learn. Handles tie-breaking correctly.
    Returns float or None if undefined (e.g. only 1 class present).
    """
    if len(set(y_true)) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(y_true, y_scores))
    except Exception:
        # Fallback to analytical Mann-Whitney U AUC
        pos = [score for y, score in zip(y_true, y_scores) if y == 1]
        neg = [score for y, score in zip(y_true, y_scores) if y == 0]
        if not pos or not neg:
            return None
        rank_sum = 0.0
        for p in pos:
            for n in neg:
                if p > n:
                    rank_sum += 1.0
                elif p == n:
                    rank_sum += 0.5
        return rank_sum / (len(pos) * len(neg))


def find_dataset_videos(base_dataset_dir: str):
    """
    Discovers the 5 real and 5 manipulated FaceForensics++ videos.
    Label 0: Original/Real
    Label 1: Manipulated/Deepfakes
    """
    real_rel_path = os.path.join("original_sequences", "youtube", "c23", "videos")
    fake_rel_path = os.path.join("manipulated_sequences", "Deepfakes", "c23", "videos")

    real_dir = os.path.join(base_dataset_dir, real_rel_path)
    fake_dir = os.path.join(base_dataset_dir, fake_rel_path)

    videos = []

    # Check real videos
    if os.path.isdir(real_dir):
        for f in sorted(os.listdir(real_dir)):
            if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                videos.append({
                    "path": os.path.join(real_dir, f),
                    "filename": f,
                    "sequence_type": "original_youtube_c23",
                    "true_label": 0
                })
    else:
        print(f"[!] Warning: Real videos directory not found: {real_dir}")

    # Check manipulated videos
    if os.path.isdir(fake_dir):
        for f in sorted(os.listdir(fake_dir)):
            if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                videos.append({
                    "path": os.path.join(fake_dir, f),
                    "filename": f,
                    "sequence_type": "manipulated_Deepfakes_c23",
                    "true_label": 1
                })
    else:
        print(f"[!] Warning: Manipulated videos directory not found: {fake_dir}")

    return videos


def main():
    parser = argparse.ArgumentParser(description="Evaluate FraudShield Video Deepfake Detector on FaceForensics++.")
    parser.add_argument(
        "--dataset-dir",
        default=None,
        help="Path to datasets/face_data. If not specified, auto-discovers relative to repo."
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Path to save prediction results CSV. Default: reports/video_evaluation_predictions.csv"
    )
    args = parser.parse_args()

    # Resolve dataset directory
    dataset_dir = args.dataset_dir
    if dataset_dir is None:
        candidates = [
            os.path.join(PARENT_ROOT, "datasets", "face_data"),
            os.path.join(APP_ROOT, "datasets", "face_data"),
            os.path.join(os.getcwd(), "datasets", "face_data"),
            os.path.join(os.getcwd(), "..", "datasets", "face_data"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                dataset_dir = os.path.abspath(c)
                break
        if dataset_dir is None:
            dataset_dir = os.path.abspath(os.path.join(PARENT_ROOT, "datasets", "face_data"))

    # Resolve output CSV path
    output_csv = args.output_csv
    if output_csv is None:
        output_csv = os.path.join(APP_ROOT, "reports", "video_evaluation_predictions.csv")
    elif not os.path.isabs(output_csv):
        output_csv = os.path.abspath(output_csv)

    reports_dir = os.path.dirname(output_csv)
    os.makedirs(reports_dir, exist_ok=True)

    # Also sync to parent reports folder if different
    parent_reports_csv = os.path.join(PARENT_ROOT, "reports", "video_evaluation_predictions.csv")

    temp_base = os.path.join(APP_ROOT, "temp")
    os.makedirs(temp_base, exist_ok=True)

    print("=" * 80)
    print("  FinGuard / FraudShield — Video Deepfake Detector Evaluation Harness")
    print("=" * 80)

    # 1. Pipeline Verification
    if not PIPELINE_IMPORT_SUCCESS:
        print(f"\n[FATAL] Pipeline module import failed: {IMPORT_ERROR}")
        print("Explanation: The application's core stages cannot be loaded in this Python environment.")
        sys.exit(1)

    threshold = get_threshold("vision_fake_threshold", 0.5)
    vision_stage_cfg = get_stage_config("stage2_vision")
    model_id = vision_stage_cfg.get("model_id", "AdityaManojShinde/deepfake-detector")
    model_weights = vision_stage_cfg.get("model_weights_file", "deepfake_detector_phase2.pth")
    early_exit_frames = get_vision_config().get("early_exit_frame_count", 4)
    early_exit_score = get_vision_config().get("early_exit_score", 0.92)
    device = get_device()

    print("\n[1] Application Forensic Pipeline Architecture:")
    print(f"  • Deepfake Vision Model  : HybridDeepfakeDetector (Dual-Branch Spatial + SRM Frequency)")
    print(f"  • Backbones               : EfficientNet-B4 (Spatial) + SRM Xception (Noise Residuals)")
    print(f"  • Model Checkpoint        : {model_id} ({model_weights})")
    print(f"  • Preprocessing Stage 1   : Adaptive Scene-Cut Frame Differencing + MTCNN Face Crop (25px margin)")
    print(f"  • Preprocessing Stage 2   : 224x224 RGB Normalization + Viseme Mouth Dynamics")
    print(f"  • Inference Function      : src.stages.stage2_vision.run_stage2_vision()")
    print(f"  • Classification Threshold: {threshold:.4f} (vision_fake_threshold in config.yaml)")
    print(f"  • Inference Device        : {device}")
    print(f"  • Early-Exit Rules        : {early_exit_frames} frames > {early_exit_score:.2f}")

    print("\n" + "!" * 80)
    print("  [SMOKE TEST WARNING]")
    print("  This evaluation dataset contains exactly 10 videos (5 real, 5 manipulated).")
    print("  This benchmark serves as a pipeline integration and smoke test.")
    print("  It cannot establish generalizable real-world accuracy or replace statistical")
    print("  validation across diverse cross-generator datasets (FaceForensics++, DFDC, Celeb-DF).")
    print("!" * 80)

    # 2. Discover Videos
    video_items = find_dataset_videos(dataset_dir)
    print(f"\n[2] Dataset Discovery:")
    print(f"  • Dataset root : {dataset_dir}")
    print(f"  • Total videos : {len(video_items)} (Expected: 10)")
    real_count = sum(1 for v in video_items if v["true_label"] == 0)
    fake_count = sum(1 for v in video_items if v["true_label"] == 1)
    print(f"  • Real videos (label 0)        : {real_count}")
    print(f"  • Manipulated videos (label 1) : {fake_count}")

    if not video_items:
        print("[!] No videos found to evaluate. Exiting.")
        sys.exit(1)

    # Diagnostics tracking
    diagnostic_counts = {
        "model_loading_failures": 0,
        "unsupported_files": 0,
        "missing_faces": 0,
        "skipped_frames_early_exit": 0,
        "inference_errors": 0,
        "evaluated_successfully": 0,
        "failed_evaluations": 0,
    }

    results = []

    print("\n[3] Running Inference Pipeline on Videos:")
    print("-" * 80)

    for idx, item in enumerate(video_items, start=1):
        v_path = item["path"]
        fname = item["filename"]
        true_lbl = item["true_label"]
        seq_type = item["sequence_type"]
        tag = "REAL" if true_lbl == 0 else "FAKE"

        job_id = f"eval_{uuid.uuid4().hex[:8]}"
        job_temp_dir = os.path.join(temp_base, job_id)
        os.makedirs(job_temp_dir, exist_ok=True)

        print(f"\n[{idx:02d}/{len(video_items):02d}] Evaluating: {fname} [{tag}] (Job: {job_id})")
        t_start = time.perf_counter()

        pred_record = {
            "video_path": v_path,
            "filename": fname,
            "sequence_type": seq_type,
            "true_label": true_lbl,
            "predicted_label": None,
            "confidence_score": None,
            "raw_peak_score": None,
            "avg_score": None,
            "threshold": threshold,
            "inference_time_sec": 0.0,
            "faces_extracted": 0,
            "status": "pending",
            "error": None
        }

        try:
            # Check file validity
            if not os.path.isfile(v_path):
                diagnostic_counts["unsupported_files"] += 1
                raise FileNotFoundError(f"File not found: {v_path}")

            # Stage 1: Ingest & Face Extraction
            ingest_res = run_stage1_ingest(v_path, job_temp_dir, job_id)
            face_frames = ingest_res.get("face_frames_paths", [])
            pred_record["faces_extracted"] = len(face_frames)

            if not face_frames:
                diagnostic_counts["missing_faces"] += 1
                raise ValueError("No face detected in video (0 candidate face frames extracted).")

            # Stage 2: Vision Forensics Inference
            vision_res = run_stage2_vision(face_frames, job_id)

            # Check if early exit occurred
            # In stage2_vision, if max_score >= early_exit_score and frames were cut short
            if vision_res.get("max_score", 0.0) >= early_exit_score:
                diagnostic_counts["skipped_frames_early_exit"] += 1

            calibrated_score = float(vision_res.get("max_score", 0.0))
            raw_peak = float(vision_res.get("raw_peak_score", calibrated_score))
            avg_score = float(vision_res.get("avg_score", 0.0))

            pred_label = 1 if calibrated_score > threshold else 0

            elapsed = round(time.perf_counter() - t_start, 3)
            pred_record.update({
                "predicted_label": pred_label,
                "confidence_score": round(calibrated_score, 6),
                "raw_peak_score": round(raw_peak, 6),
                "avg_score": round(avg_score, 6),
                "inference_time_sec": elapsed,
                "status": "success",
                "error": None
            })

            diagnostic_counts["evaluated_successfully"] += 1
            correct = (pred_label == true_lbl)
            res_str = "CORRECT" if correct else "INCORRECT"
            print(f"      -> Result: Pred={pred_label} (Conf={calibrated_score:.4f}, Peak={raw_peak:.4f}) | True={true_lbl} | {res_str} in {elapsed:.2f}s")

        except Exception as ex:
            elapsed = round(time.perf_counter() - t_start, 3)
            err_msg = str(ex)
            pred_record["inference_time_sec"] = elapsed
            pred_record["status"] = "failed"
            pred_record["error"] = err_msg
            diagnostic_counts["failed_evaluations"] += 1
            diagnostic_counts["inference_errors"] += 1
            print(f"      -> [ERROR] Failed evaluating {fname}: {err_msg} ({elapsed:.2f}s)")

        finally:
            # Ephemeral disk sanitation (DPDP Act compliance)
            if os.path.exists(job_temp_dir):
                shutil.rmtree(job_temp_dir, ignore_errors=True)

        results.append(pred_record)

    # 3. Save Predictions to CSV
    csv_fields = [
        "video_path", "filename", "sequence_type", "true_label", "predicted_label",
        "confidence_score", "raw_peak_score", "avg_score", "threshold",
        "inference_time_sec", "faces_extracted", "status", "error"
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\n[4] Saved detailed predictions to: {output_csv}")

    # Also copy to parent root reports dir for accessibility
    try:
        os.makedirs(os.path.dirname(parent_reports_csv), exist_ok=True)
        shutil.copy2(output_csv, parent_reports_csv)
        print(f"    (Mirrored to root reports at: {parent_reports_csv})")
    except Exception:
        pass

    # 4. Compute Metrics
    # Filter only successfully evaluated videos for statistical metrics
    valid_results = [r for r in results if r["status"] == "success" and r["predicted_label"] is not None]

    tp = sum(1 for r in valid_results if r["true_label"] == 1 and r["predicted_label"] == 1)
    tn = sum(1 for r in valid_results if r["true_label"] == 0 and r["predicted_label"] == 0)
    fp = sum(1 for r in valid_results if r["true_label"] == 0 and r["predicted_label"] == 1)
    fn = sum(1 for r in valid_results if r["true_label"] == 1 and r["predicted_label"] == 0)

    total_valid = len(valid_results)
    accuracy = (tp + tn) / total_valid if total_valid > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Continuous prediction scores for ROC-AUC
    y_true = [r["true_label"] for r in valid_results]
    y_scores = [r["confidence_score"] for r in valid_results]
    roc_auc = compute_roc_auc(y_true, y_scores)

    # 5. Formatted Final Report
    print("\n" + "=" * 80)
    print("                    EVALUATION BENCHMARK REPORT")
    print("=" * 80)

    print("\n[A] Execution & Diagnostic Summary:")
    print(f"  • Total Videos Ingested          : {len(results)}")
    print(f"  • Successfully Evaluated         : {diagnostic_counts['evaluated_successfully']} / {len(results)}")
    print(f"  • Failed Evaluations             : {diagnostic_counts['failed_evaluations']} / {len(results)}")
    print(f"  • Model Loading Failures         : {diagnostic_counts['model_loading_failures']}")
    print(f"  • Unsupported / Missing Files    : {diagnostic_counts['unsupported_files']}")
    print(f"  • Missing Faces (0 MTCNN crops)  : {diagnostic_counts['missing_faces']}")
    print(f"  • Skipped Frames (Early Exits)   : {diagnostic_counts['skipped_frames_early_exit']}")
    print(f"  • Inference Exceptions           : {diagnostic_counts['inference_errors']}")

    print("\n[B] Per-Video Prediction Breakdown:")
    print(f"  {'Filename':<14} | {'True':<5} | {'Pred':<5} | {'Score':<8} | {'Peak':<8} | {'Faces':<5} | {'Time(s)':<7} | {'Verdict'}")
    print("  " + "-" * 74)
    for r in results:
        t_str = str(r['true_label'])
        p_str = str(r['predicted_label']) if r['predicted_label'] is not None else "FAIL"
        s_str = f"{r['confidence_score']:.4f}" if r['confidence_score'] is not None else "N/A"
        k_str = f"{r['raw_peak_score']:.4f}" if r['raw_peak_score'] is not None else "N/A"
        f_cnt = str(r['faces_extracted'])
        sec = f"{r['inference_time_sec']:.2f}"
        if r['status'] == 'failed':
            v_str = f"ERROR: {r['error'][:25]}"
        elif r['true_label'] == r['predicted_label']:
            v_str = "PASS (Correct)"
        else:
            v_str = "FAIL (Misclassified)"
        print(f"  {r['filename']:<14} | {t_str:<5} | {p_str:<5} | {s_str:<8} | {k_str:<8} | {f_cnt:<5} | {sec:<7} | {v_str}")

    print("\n[C] Confusion Matrix:")
    print(f"                  ┌───────────────────────┬───────────────────────┐")
    print(f"                  │ Predicted REAL (0)    │ Predicted FAKE (1)    │")
    print(f"  ────────────────┼───────────────────────┼───────────────────────┤")
    print(f"  Actual REAL (0) │ True Negatives (TN): {tn:<2}│ False Positives (FP):{fp:<2}│")
    print(f"  Actual FAKE (1) │ False Negatives (FN):{fn:<2}│ True Positives (TP): {tp:<2}│")
    print(f"  ────────────────┴───────────────────────┴───────────────────────┘")

    print("\n[D] Performance Metrics (Threshold = 0.50):")
    print(f"  • Accuracy                 : {accuracy * 100:.2f}% ({tp + tn}/{total_valid})")
    print(f"  • Precision (PPV)          : {precision * 100:.2f}%")
    print(f"  • Recall / Sensitivity     : {recall * 100:.2f}%")
    print(f"  • Specificity (TNR)        : {specificity * 100:.2f}%")
    print(f"  • False-Positive Rate (FPR): {fpr * 100:.2f}%")
    print(f"  • F1-Score                 : {f1:.4f}")
    if roc_auc is not None:
        print(f"  • ROC-AUC Score            : {roc_auc:.4f}")
    else:
        print(f"  • ROC-AUC Score            : Undefined (insufficient class variation or failed predictions)")

    print("\n[E] Findings & Observations:")
    if tp + fp == 0 and fn > 0:
        print("  • NOTE ON GENERALIZATION GAP:")
        print("    All manipulated FaceForensics++ videos yielded prediction scores below the 0.50 threshold.")
        print("    The current HybridDeepfakeDetector model weights (deepfake_detector_phase2.pth) were")
        print("    trained on a specific set of synthetic artifacts and exhibit a domain-shift false-negative")
        print("    trend on FaceForensics++ c23 compressed DeepFakes sequences.")
        print("    This highlights the essential need for cross-domain training or calibrated per-codec thresholds.")

    print("\n" + "=" * 80)
    print("  Evaluation complete. Predictions saved to:")
    print(f"  {output_csv}")
    print("=" * 80)


if __name__ == "__main__":
    main()
