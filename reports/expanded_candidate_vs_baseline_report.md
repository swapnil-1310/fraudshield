# Expanded Deepfake Detector Evaluation Report: Baseline vs. Candidate

**Evaluation Date**: 2026-10-15  
**Candidate Model**: `KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus` (MS-EffGCViT-B0, 8.9M params)  
**Baseline Model**: `AdityaManojShinde/deepfake-detector` (EfficientNet-B4 + SRM Xception, ~30M params)  
**Dataset**: FaceForensics++ c23 (20 videos: 5 Original, 5 Deepfakes, 5 Face2Face, 5 FaceSwap)  
**Evaluation Scope**: Standalone integration benchmark (`scripts/evaluate_expanded_benchmark.py`). Zero changes to production code, `app.py`, `config.yaml`, or existing checkpoint weights.

---

## 1. Executive Summary

| Metric | Baseline Detector (tau = 0.50) | Baseline Detector (tau = 0.60) | Candidate Detector (tau = 0.50) | Candidate Detector (tau = 0.60) | Candidate Advantage |
|---|:---:|:---:|:---:|:---:|:---:|
| **Overall Accuracy** | **25.00%** (5/20) | **25.00%** (5/20) | **100.00%** (20/20) | **100.00%** (20/20) | **+75.00%** |
| **Overall Recall (Fake=1)** | **0.00%** (0/15) | **0.00%** (0/15) | **100.00%** (15/15) | **100.00%** (15/15) | **+100.00%** |
| **Overall Precision (Fake=1)** | **0.00%** (0/0) | **0.00%** (0/0) | **100.00%** (15/15) | **100.00%** (15/15) | **+100.00%** |
| **Specificity (Real=0)** | **100.00%** (5/5) | **100.00%** (5/5) | **100.00%** (5/5) | **100.00%** (5/5) | **100.00%** (0 FP) |
| **F1-Score** | **0.0000** | **0.0000** | **1.0000** | **1.0000** | **+1.0000** |
| **ROC-AUC** | **0.5867** | **0.5867** | **1.0000** | **1.0000** | **+0.4133** |
| **Mean Inference Latency** | **2.61s / video** | **2.61s / video** | **1.16s / video** | **1.16s / video** | **55.6% Faster** |

The expanded evaluation across 20 FaceForensics++ c23 videos demonstrates that the baseline detector's failure is **not isolated to Deepfakes**:
- **Baseline Recall**: **0.0%** across Deepfakes (0/5), **0.0%** across Face2Face (0/5), and **0.0%** across FaceSwap (0/5). The existing checkpoint misclassifies every single manipulated video as authentic.
- **Candidate Recall**: **100.0%** across Deepfakes (5/5), **100.0%** across Face2Face (5/5), and **100.0%** across FaceSwap (5/5). The candidate achieves **100% accuracy** at both the standard 0.50 threshold and the hardened 0.60 threshold.

---

## 2. Per-Method Breakdown & Comparison

To understand detector robustness across distinct forgery mechanisms, we evaluated the models across 3 distinct FaceForensics++ manipulation pipelines against the same authentic source videos:

### 2.1 Deepfakes (Autoencoder-based Face Replacement)
* **True Samples**: 5 authentic (`183`, `469`, `481`, `585`, `599`) vs. 5 Deepfakes replacements.
* **Baseline Detector**: Accuracy = **50.0%**, Recall = **0.0%** (0/5), Precision = 0.0%, F1 = 0.0000, ROC-AUC = 0.4400.
* **Candidate Detector**: Accuracy = **100.0%**, Recall = **100.0%** (5/5), Precision = 100.0%, F1 = 1.0000, ROC-AUC = 1.0000.
* **Candidate Scores**: Consensus range [0.9619, 0.9995], Mean = 0.9906.

### 2.2 Face2Face (Expression Transfer & Facial Reenactment)
* **True Samples**: 5 authentic vs. 5 Face2Face reenactments.
* **Baseline Detector**: Accuracy = **50.0%**, Recall = **0.0%** (0/5), Precision = 0.0%, F1 = 0.0000, ROC-AUC = 0.6800.
* **Candidate Detector**: Accuracy = **100.0%**, Recall = **100.0%** (5/5), Precision = 100.0%, F1 = 1.0000, ROC-AUC = 1.0000.
* **Candidate Scores**: Consensus range [0.9982, 0.9992], Mean = 0.9990.

### 2.3 FaceSwap (Graphics/3D Face Replacement)
* **True Samples**: 5 authentic vs. 5 FaceSwap replacements.
* **Baseline Detector**: Accuracy = **50.0%**, Recall = **0.0%** (0/5), Precision = 0.0%, F1 = 0.0000, ROC-AUC = 0.6400.
* **Candidate Detector**: Accuracy = **100.0%**, Recall = **100.0%** (5/5), Precision = 100.0%, F1 = 1.0000, ROC-AUC = 1.0000.
* **Candidate Scores**: Consensus range [0.9989, 0.9994], Mean = 0.9991.

---

## 3. Full Video-by-Video Evaluation Results

All 20 videos were processed using identical Stage 1 adaptive MTCNN face extraction (15 frames per video). The resulting face crops were fed in-memory to both detectors.

| # | Filename | Manipulation Type | Ground Truth | Baseline Score | Baseline Pred (tau=0.50) | Candidate Score | Candidate Pred (tau=0.50) | Candidate Pred (tau=0.60) | Baseline Latency | Candidate Latency |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 01 | `183.mp4` | Original   | Real (0) | 0.0096 | Real (0) | **0.0613** | Real (0) | Real (0) | 2.71s | 1.17s |
| 02 | `469.mp4` | Original   | Real (0) | 0.0196 | Real (0) | **0.3864** | Real (0) | Real (0) | 2.64s | 1.28s |
| 03 | `481.mp4` | Original   | Real (0) | 0.0002 | Real (0) | **0.0024** | Real (0) | Real (0) | 2.55s | 1.18s |
| 04 | `585.mp4` | Original   | Real (0) | 0.0010 | Real (0) | **0.0016** | Real (0) | Real (0) | 2.55s | 1.12s |
| 05 | `599.mp4` | Original   | Real (0) | 0.0005 | Real (0) | **0.1077** | Real (0) | Real (0) | 2.62s | 1.17s |
| 06 | `183_253.mp4` | Deepfakes  | Fake (1) | 0.0076 | Real (0) [FAIL] | **0.9991** | Fake (1) | Fake (1) | 2.55s | 1.13s |
| 07 | `469_481.mp4` | Deepfakes  | Fake (1) | 0.0729 | Real (0) [FAIL] | **0.9930** | Fake (1) | Fake (1) | 2.60s | 1.12s |
| 08 | `481_469.mp4` | Deepfakes  | Fake (1) | 0.0001 | Real (0) [FAIL] | **0.9994** | Fake (1) | Fake (1) | 2.54s | 1.14s |
| 09 | `585_599.mp4` | Deepfakes  | Fake (1) | 0.0005 | Real (0) [FAIL] | **0.9995** | Fake (1) | Fake (1) | 2.52s | 1.08s |
| 10 | `599_585.mp4` | Deepfakes  | Fake (1) | 0.0004 | Real (0) [FAIL] | **0.9619** | Fake (1) | Fake (1) | 2.71s | 1.12s |
| 11 | `183_253.mp4` | Face2Face  | Fake (1) | 0.0056 | Real (0) [FAIL] | **0.9991** | Fake (1) | Fake (1) | 2.62s | 1.11s |
| 12 | `469_481.mp4` | Face2Face  | Fake (1) | 0.0045 | Real (0) [FAIL] | **0.9992** | Fake (1) | Fake (1) | 2.61s | 1.20s |
| 13 | `481_469.mp4` | Face2Face  | Fake (1) | 0.0000 | Real (0) [FAIL] | **0.9982** | Fake (1) | Fake (1) | 2.68s | 1.18s |
| 14 | `585_599.mp4` | Face2Face  | Fake (1) | 0.0209 | Real (0) [FAIL] | **0.9990** | Fake (1) | Fake (1) | 2.68s | 1.17s |
| 15 | `599_585.mp4` | Face2Face  | Fake (1) | 0.1011 | Real (0) [FAIL] | **0.9986** | Fake (1) | Fake (1) | 2.76s | 1.24s |
| 16 | `183_253.mp4` | FaceSwap   | Fake (1) | 0.0009 | Real (0) [FAIL] | **0.9991** | Fake (1) | Fake (1) | 2.57s | 1.13s |
| 17 | `469_481.mp4` | FaceSwap   | Fake (1) | 0.0426 | Real (0) [FAIL] | **0.9989** | Fake (1) | Fake (1) | 2.57s | 1.11s |
| 18 | `481_469.mp4` | FaceSwap   | Fake (1) | 0.0003 | Real (0) [FAIL] | **0.9994** | Fake (1) | Fake (1) | 2.55s | 1.15s |
| 19 | `585_599.mp4` | FaceSwap   | Fake (1) | 0.0014 | Real (0) [FAIL] | **0.9990** | Fake (1) | Fake (1) | 2.51s | 1.12s |
| 20 | `599_585.mp4` | FaceSwap   | Fake (1) | 0.0002 | Real (0) [FAIL] | **0.9994** | Fake (1) | Fake (1) | 2.54s | 1.08s |

---

## 4. Threshold Calibration Evaluation (0.50 vs. 0.60)

In compliance with Requirement 5, both tau = 0.50 and tau = 0.60 thresholds were evaluated on this expanded validation set:

### 4.1 Calibration & Separation Window
* **Authentic Videos (N=5)**:
  * Score range: [0.0016, 0.3864]
  * Mean score: 0.1119
  * Max authentic score: **0.3864** (`469.mp4`, degraded low-bitrate video)
* **Manipulated Videos (N=15)**:
  * Score range: [0.9619, 0.9995]
  * Mean score: 0.9963
  * Min manipulated score: **0.9619** (`599_585.mp4`, Deepfakes)
* **Separation Gap**:
  Delta = min(P_fake_manipulated) - max(P_fake_authentic) = 0.9619 - 0.3864 = +0.5755

### 4.2 Comparison of tau = 0.50 vs. tau = 0.60
* **At tau = 0.50**:
  * TP = 15, TN = 5, FP = 0, FN = 0
  * Accuracy = 100.0%, Precision = 100.0%, Recall = 100.0%, F1 = 1.0000
* **At tau = 0.60**:
  * TP = 15, TN = 5, FP = 0, FN = 0
  * Accuracy = 100.0%, Precision = 100.0%, Recall = 100.0%, F1 = 1.0000
* **Analysis**:
  Both thresholds achieve identical 100% metrics on this validation set. However, setting tau = 0.60 widens the safety margin against compressed, noisy authentic uploads from 0.1136 (at 0.50) to **0.2136** (at 0.60), providing substantial headroom against false positives without any drop in recall.

---

## 5. Computational Efficiency & Latency

* **Baseline Inference Time**: Mean = **2.61s** per video (scoring 15 frames)
* **Candidate Inference Time**: Mean = **1.16s** per video (scoring 15 frames)
* **Speedup**: Candidate is **55.6% faster** on pure vision inference.
* **Model Size**: Candidate checkpoint is **34.02 MB** (vs 114.2 MB for baseline).

---

## 6. Recommendations & Practical Next Steps

> [!IMPORTANT]
> ### Methodological Note
> Although the candidate achieved 100% accuracy on all 20 videos across 3 manipulation methods, **this expanded validation set remains a sample size of 20 videos**. It firmly confirms cross-manipulation competence on FaceForensics++ c23, but **does not by itself establish production readiness across diverse, unconstrained in-the-wild generators** (such as Sora, Stable Video Diffusion, or unseen commercial face swappers).

### Recommended Next Steps:
1. **Model Adapter Implementation**: Create an isolated Stage 2 backend adapter `src/stages/backends/ms_eff_gcvit_backend.py` implementing the `FraudShieldDetectorInterface`.
2. **Configuration Toggle**: Add a non-breaking configuration switch in `config.yaml`:
   ```yaml
   vision_detector:
     backend: "ms_eff_gcvit"  # options: "hybrid_phase2", "ms_eff_gcvit"
     threshold: 0.60
   ```
3. **Cross-Dataset Benchmark (Celeb-DF-v2)**: Evaluate on a sample of Celeb-DF-v2 to quantify cross-dataset transfer before fully deprecating the legacy checkpoint.
