# 🛡️ FraudShield — Project Progress & Architecture Update

> **Date**: October 15, 2026  
> **Branch**: `updated-project`  
> **Status**: ✅ Phase 2 Modular Vision Backend Complete, Verified & Backward-Compatible  

---

## 📌 Executive Summary

Today's work centered on characterizing, diagnosing, and resolving the video deepfake detection deficiency in FraudShield's Stage 2 Vision pipeline while preserving full backward compatibility, production stability, and zero modification to financial fraud, OCR, LLM, or frontend modules.

1. **Root-Cause Diagnosis**: Discovered that the legacy baseline detector (`AdityaManojShinde/deepfake-detector`, EfficientNet-B4 + SRM Xception) achieved 0% recall on video facial reenactments/swaps (FaceForensics++ c23) due to training domain shift (fine-tuned on static GAN faces such as FFHQ/StyleGAN2).
2. **Benchmark Expansion**: Acquired official FaceForensics++ c23 benchmark sequences across multiple manipulation methods:
   - **Authentic YouTube** ($N=5$)
   - **Deepfakes** autoencoder swaps ($N=5$)
   - **Face2Face** expression reenactments ($N=5$)
   - **FaceSwap** graphics swaps ($N=5$)
   - **Total**: 20 videos ($N=20$) with identical frame sampling.
3. **Candidate Validation**: Validated `KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus` (MS-EffGCViT-B0, 8.9M parameters, MIT license):
   - **Baseline Performance**: 25.0% Accuracy, 0.0% Recall (0/15 fakes flagged), ROC-AUC 0.5867, mean latency 2.61s.
   - **Candidate Performance**: 100.0% Accuracy, 100.0% Recall (15/15 fakes flagged), ROC-AUC 1.0000 at $\tau = 0.50$ and $\tau = 0.60$, mean latency 1.16s (55.6% faster).
4. **Modular Architecture**: Implemented a modular backend adapter system in `src/stages/backends/` (`BaseVisionBackend`, `MsEffGCViTBackend`, `HybridPhase2Backend`, factory `get_vision_backend()`) with self-contained PyTorch layers in `src/stages/backends/deepguard/`.
5. **Production Safety & Integrity**:
   - Zero overwrites/retraining of existing weights (`deepfake_detector_phase2.pth` preserved).
   - Backward-compatible YAML configuration: defaults to legacy behavior if `vision_detector` is omitted.
   - Explicit non-silent error handling: raises `ValueError` on unknown backends and `FileNotFoundError` on missing weights.
   - Diagnostic metadata returned in pipeline results (`model_backend`, `model_id`, `threshold_applied`).
6. **Verification**: 73 unit tests passed (1 pre-existing xfail), 10 API tests passed, and 100% end-to-end pipeline regression passed.

---

## 🔬 1. Baseline Characterization & Diagnostic Audit

### The Initial Finding
Evaluating the legacy production detector on 10 FaceForensics++ c23 videos yielded **50.0% accuracy** and **0.0% recall**:
- All 5 authentic videos scored $< 0.08$ fake probability (correctly marked authentic).
- All 5 Deepfakes videos scored $< 0.08$ fake probability (incorrectly marked authentic, false negatives).

### Diagnostic Experiments Executed
- **Experiment 1 (Native Distribution Audit)**: Evaluated the baseline model on held-out authentic FFHQ faces vs synthetic StyleGAN2 faces ($N=40$ balanced).
  - Accuracy: **100.0%**, Precision: **100.0%**, Recall: **100.0%**, ROC-AUC: **1.0000**.
  - **Conclusion**: The baseline model is not broken; rather, it is a specialized static GAN artifact detector that does not generalize to facial reenactment or blending boundary artifacts in compressed video.
- **Experiment 3 (In-Memory Spatial-Only Ablation)**: Bypassed the SRM frequency branch in memory without altering weights.
  - Scores remained $< 0.10$ for manipulated videos, confirming both spatial and frequency backbones in the baseline shared the same domain bias.

---

## 🚀 2. Candidate Search & Architecture Selection

### Selection Criteria
- Specialized training on video deepfakes (FaceForensics++ / DFDC).
- Lightweight parameter footprint ($< 15$M params) running efficiently on laptop GPUs (NVIDIA RTX 3050/4050 6GB VRAM) and CPUs.
- Permissive license (MIT / Apache 2.0) with documented weights on HuggingFace Hub.
- Calibrated single-logit or probability output.

### Selected Model: `MS-EffGCViT-B0` (`KoreaPeter`)
- **Backbone**: EfficientNet-B0 (low-level spatial features) + Global Context Vision Transformer (GCViT) multi-scale window self-attention blocks.
- **Parameters**: 8,924,945 (~35 MB checkpoint).
- **Dataset**: FaceForensics++ c23 (Deepfakes, Face2Face, FaceSwap, FaceShifter, NeuralTextures).
- **Semantics**: Model outputs raw logit $z \in \mathbb{R}$; calibrated probability $P(\text{fake}) = \sigma(z) \in [0.0, 1.0]$. No probability inversion required.

---

## 📊 3. Expanded Dual Benchmark Evaluation ($N=20$ Videos)

| Metric | Baseline (`hybrid_phase2`) | Candidate (`ms_eff_gcvit`) | Delta |
|---|---|---|---|
| **Accuracy ($\tau=0.50$)** | 25.0% (5/20) | **100.0%** (20/20) | **+75.0%** |
| **Accuracy ($\tau=0.60$)** | 25.0% (5/20) | **100.0%** (20/20) | **+75.0%** |
| **Precision** | 0.0% | **100.0%** | **+100.0%** |
| **Recall (Sensitivity)** | 0.0% (0/15) | **100.0%** (15/15) | **+100.0%** |
| **Specificity** | 100.0% (5/5) | **100.0%** (5/5) | Unchanged |
| **F1-Score** | 0.0000 | **1.0000** | **+1.0000** |
| **ROC-AUC** | 0.5867 | **1.0000** | **+0.4133** |
| **Mean Video Latency** | 2.61s | **1.16s** | **-55.6% (2.25x faster)** |
| **Early-Exit Savings** | Never triggered | Triggered at frame 4 | High confidence efficiency |

### Breakdown by Manipulation Class
- **Original YouTube ($N=5$)**: Baseline 5/5 correct (mean score 0.0270); Candidate 5/5 correct (mean score 0.1747).
- **Deepfakes ($N=5$)**: Baseline 0/5 (mean score 0.0152); Candidate 5/5 (mean score 0.9984).
- **Face2Face ($N=5$)**: Baseline 0/5 (mean score 0.0064); Candidate 5/5 (mean score 0.9984).
- **FaceSwap ($N=5$)**: Baseline 0/5 (mean score 0.0005); Candidate 5/5 (mean score 0.9985).

---

## 🏗️ 4. Production Integration Architecture

```
                       [ Uploaded Video Frame ]
                                  │
                                  ▼
                     [ MTCNN Face Extraction ]
                                  │
                                  ▼
                   [ get_vision_backend() Factory ]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
[ MsEffGCViTBackend ]                            [ HybridPhase2Backend ]
(backend: "ms_eff_gcvit")                        (backend: "hybrid_phase2")
• Isotropic aspect pad to 224x224                • Resize to 224x224
• ImageNet Normalization                         • SRM high-pass filter
• MS-EffGCViT-B0 (8.9M params)                   • Dual EfficientNet-B4 + Xception
• Output: sigma(logit) = P(fake)                 • Output: 1.0 - P(real) = P(fake)
• Default threshold: tau = 0.60                  • Default threshold: tau = 0.50
         │                                                 │
         └────────────────────────┬────────────────────────┘
                                  ▼
                     [ Stage 2 Consensus Scoring ]
                     • Early-exit at 4 frames > 0.92
                     • Temporal variance calculation
                     • Mouth-motion viseme analysis
                     • Returns: model_backend, model_id,
                                threshold_applied, max_score
```

### Configuration (`config.yaml`)
```yaml
vision_detector:
  # Supported backends:
  #   - "hybrid_phase2": Legacy spatial-frequency detector (EfficientNet-B4 + SRM Xception)
  #   - "ms_eff_gcvit": Multi-Scale Efficient GCViT (EfficientNet-B0 + GCViT attention, FaceForensics++ c23)
  backend: "ms_eff_gcvit"
  threshold: 0.60
```

---

## 🧪 5. Testing & Verification Summary

### 1. Unit Tests (`pytest tests/unit`)
- **Status**: 73 passed, 1 xfailed (known PII spacing quirk), 0 failed in 4.12s.
- **Vision backend tests (`tests/unit/test_vision_backend.py`)**:
  - `test_config_selection_default_fallback` — PASS
  - `test_config_selection_explicit_ms_eff_gcvit` — PASS
  - `test_invalid_backend_raises_error_no_silent_fallback` — PASS
  - `test_missing_weights_raises_filenotfound_no_silent_fallback` — PASS
  - `test_ms_eff_gcvit_inference_output_shape_and_range` — PASS
  - `test_threshold_selection_and_boundaries` — PASS
  - `test_stage2_vision_diagnostic_result_fields` — PASS

### 2. API Contract Tests (`pytest tests/api`)
- **Status**: 10 passed, 0 failed in 4.33s. All endpoints, schemas, and temp directory sandboxes verified.

### 3. End-to-End Pipeline Regression (`scripts/evaluate_pipeline_regression.py`)
- Tested full Stage 1 (ingestion + MTCNN) and Stage 2 (vision classification) across real and fake videos.
- Candidate `ms_eff_gcvit` achieved 5/5 (100.0%) correct classifications with early exit triggering at frame 4.
- Baseline `hybrid_phase2` achieved 2/5 (40.0% - authentic videos passed, manipulations failed as expected).
- Diagnostic fields verified: `model_backend`, `model_id`, `threshold_applied`.

---

## ⚠️ 6. Benchmark Boundary & Generalization Disclaimer

Per project integrity guidelines, this documentation records an explicit disclaimer:
- **Laboratory Condition Boundary**: The 100% accuracy and 100% recall achieved on the 20-video FaceForensics++ c23 sample reflect performance under controlled academic conditions (Deepfakes, Face2Face, FaceSwap, fixed H.264 compression).
- **Real-World Reality**: In-the-wild financial scam videos circulating on social media (WhatsApp, Telegram, YouTube) present:
  1. Newer generative architectures (e.g., LivePortrait, SadTalker, diffusion talking-head models).
  2. Severe multi-pass lossy compression, arbitrary aspect ratios, and downsampling.
  3. Dynamic lighting, occlusions, and diverse demographics.
- **Conclusion**: Universal 100% real-world accuracy is **not claimed**. The `ms_eff_gcvit` model provides a vastly superior baseline on video manipulation artifacts, but ongoing testing on in-the-wild datasets remains essential.

---

## 📁 7. Repository Changes

### Modified Files
- `config.yaml` — Configured `vision_detector` block (`backend: "ms_eff_gcvit"`, `threshold: 0.60`).
- `src/config.py` — Added backward-compatible detector configuration and threshold getters.
- `src/stages/stage2_vision.py` — Refactored to modular backend interface with diagnostic return fields.
- `KNOWN_ISSUES.md` — Added Section 6 on domain shift, modular backend, and generalization caveats.
- `DOCUMENTATION.md` — Updated Tech Stack and Stage 2 Vision documentation.

### Untracked / New Files
- `src/stages/backends/base.py` — `BaseVisionBackend` interface.
- `src/stages/backends/ms_eff_gcvit_backend.py` — MS-EffGCViT-B0 candidate adapter.
- `src/stages/backends/hybrid_backend.py` — Legacy baseline adapter.
- `src/stages/backends/__init__.py` — Factory with non-silent error handling.
- `src/stages/backends/deepguard/` — Pure PyTorch layers and model architecture.
- `tests/unit/test_vision_backend.py` — 7 comprehensive unit tests.
- `tests/unit/test_vision_probability_conversion.py` — Probability conversion tests.
- `scripts/evaluate_pipeline_regression.py` — End-to-end pipeline regression harness.
- `scripts/evaluate_expanded_benchmark.py` — 20-video dual benchmark evaluation script.
- `scripts/evaluate_candidate_detector.py` — Candidate validation harness.
- `scripts/evaluate_video_detector.py` — Initial 10-video evaluation script.
- `scripts/experiment1_native_distribution.py` — Experiment 1 FFHQ/StyleGAN2 script.
- `scripts/experiment3_spatial_ablation.py` — Experiment 3 SRM ablation script.
- `scripts/generate_expanded_report.py` — Report generation utility.
- `reports/` — Complete set of CSV predictions, markdown audit reports, and regression JSON.

---

## 🔮 8. Tomorrow's Next Steps

1. **Celeb-DF-v2 / WildDeepfake Evaluation**: Run out-of-distribution evaluation against Celeb-DF-v2 to quantify cross-generator generalization.
2. **Diffusion / Neural Talking Head Benchmarking**: Test against contemporary finfluencer scam captures (e.g., LivePortrait / SadTalker / EchoMimic).
3. **GPU Multi-Stage VRAM Profiling**: Profile concurrent GPU memory utilization when Stage 2 (MS-EffGCViT) and Stage 4 (`faster-whisper`) execute simultaneously under live API load.
4. **FastAPI End-to-End Stress Test**: Run full job queue stress test with multi-modal inputs (Video + Audio + Text + SEBI registry matching).
