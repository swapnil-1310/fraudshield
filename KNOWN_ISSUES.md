# 📋 KNOWN_ISSUES.md — Characterization & Known Anomalies Log
> **Phase 1 Baseline Record**: Documents all known behavioral quirks, bugs, and edge cases discovered during characterization testing. Per standing rules, these are recorded and guarded with `@pytest.mark.xfail` without altering production code.

---

## 1. PII Regex Precedence Anomaly (`stage5_llm.py`)
- **Location**: `src/stages/stage5_llm.py:47`
- **Pattern**:
  ```python
  (r"(?i)(?:a/c|acc(?:ount)?(?:\s+no)?[:\s]+)(\d{9,18})", r"a/c [MASKED_BANK_ACCOUNT_DPDP]")
  ```
- **Observed Behavior**: The alternation operator `|` binds `a/c` separately from `(?:\s+no)?[:\s]+`. Consequently:
  - `"account no: 123456789012"` → **MATCHED & MASKED**
  - `"acc 123456789012"` → **MATCHED & MASKED**
  - `"a/c: 123456789012"` → **MATCHED & MASKED**
  - `"a/c 123456789012"` (standard Indian financial phrasing with a space) → **NOT MATCHED / UNMASKED**
- **Test Guard**: Marked with `@pytest.mark.xfail` in `tests/unit/test_pii_shield.py::test_scrub_bank_account_spaced_a_c`.
- **Recommended Phase 2 Fix**: Group prefix alternatives: `r"(?i)(?:a/c|acc(?:ount)?(?:\s+no)?)(?:[:\s]+)(\d{9,18})"`.

---

## 2. Hardcoded Composite Risk Threshold in Calibrated Verdict (`app.py`)
- **Location**: `app.py:67`
- **Code**:
  ```python
  elif composite_risk >= 0.35:
      return "Suspicious: Review Recommended"
  ```
- **Observed Behavior**: While `config.yaml` exposes `thresholds.scam_composite_threshold: 0.35`, `app.py:67` hardcodes the literal float `0.35` instead of invoking `get_threshold("scam_composite_threshold", 0.35)`.
- **Impact**: Changing `scam_composite_threshold` in `config.yaml` updates LLM flagging in Stage 5 but fails to update the final calibrated verdict branch in `app.py`.

---

## 3. Platform-Dependent Virtualenv Path in Registry Sync Endpoint (`app.py`)
- **Location**: `app.py:603`
- **Code**:
  ```python
  result = subprocess.run(
      [".venv/Scripts/python", "scripts/sync_sebi_registry.py"],
      capture_output=True, text=True, cwd=os.getcwd()
  )
  ```
- **Observed Behavior**: Hardcodes the Windows virtualenv interpreter path `".venv/Scripts/python"`.
- **Impact**: Fails with `FileNotFoundError` when deployed on Linux or macOS containers (`.venv/bin/python`), or when running under a non-standard virtualenv name.
- **Recommended Phase 2 Fix**: Use `sys.executable` (`[sys.executable, "scripts/sync_sebi_registry.py"]`).

---

## 4. Unmocked Model Downloads in Legacy `e2e_system_test.py`
- **Location**: `scripts/e2e_system_test.py:24`
- **Observed Behavior**: The test imports `app.py` directly and triggers live video/audio pipeline calls without mocking stage functions, attempting multi-gigabyte HuggingFace weight downloads (`models--Systran--faster-whisper-medium`).
- **Mitigation**: New test suite in `tests/api/test_api_contracts.py` thoroughly mocks ML stages to guarantee instant CPU testing with zero network access.

---

## 5. Starlette / FastAPI TestClient Deprecation Warning
- **Observed Warning**:
  `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`
- **Status**: Non-fatal deprecation warning from Starlette's compatibility shim with recent `httpx` versions. Filtered in `pytest.ini`.

---

## 6. Vision Deepfake Detector: Domain Shift, Modular Backends & Benchmark Caveats
- **Background**:
  - The legacy production detector (`hybrid_phase2`, `AdityaManojShinde/deepfake-detector`) combines spatial EfficientNet-B4 and frequency-domain SRM Xception.
  - During benchmark evaluation on FaceForensics++ c23, the legacy model scored authentic probabilities near 1.0 for all manipulated videos (0% recall across Deepfakes, Face2Face, and FaceSwap). This was traced to dataset domain shift: the model weights appear fine-tuned predominantly on synthetic static GAN faces (FFHQ/StyleGAN2) where spatial-frequency cues differ fundamentally from video face-swap boundary blending.
- **Resolution**:
  - A modular vision detector adapter interface was implemented (`src/stages/backends/base.py`, `get_vision_backend()`), supporting:
    1. `backend: "ms_eff_gcvit"` (Default): Multi-Scale Efficient GCViT-B0 (`KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus`), fine-tuned directly on FaceForensics++ c23 manipulation methods.
    2. `backend: "hybrid_phase2"`: Legacy spatial-frequency detector, preserved for 100% backward compatibility.
  - Calibrated decision threshold configured via `vision_detector.threshold: 0.60` (or `0.50` fallback for legacy).
- **Validation Results (FaceForensics++ c23, N=20 videos)**:
  - Evaluated on 20 TUM FaceForensics++ c23 videos (5 Original/Real, 5 Deepfakes, 5 Face2Face, 5 FaceSwap):
    - `hybrid_phase2`: 25.0% Accuracy, 0.0% Recall (0/15 fakes flagged), ROC-AUC 0.5867, mean latency 2.61s.
    - `ms_eff_gcvit`: 100.0% Accuracy, 100.0% Recall (15/15 fakes flagged), ROC-AUC 1.0000 at both $\tau=0.50$ and $\tau=0.60$, mean latency 1.16s (55.6% faster).
- **CRITICAL Benchmark Generalization Caveat**:
  - The 100% accuracy and 100% recall achieved on the 20-video FaceForensics++ c23 evaluation **must NOT be interpreted as universal 100% real-world detection accuracy**.
  - FaceForensics++ c23 is a controlled academic benchmark with specific manipulation algorithms (Deepfakes autoencoder, Face2Face graphics re-rendering, FaceSwap 3D warping) and fixed H.264 compression ($CRF=23$).
  - Real-world financial fraud videos circulating on social media (WhatsApp, Telegram, YouTube) exhibit:
    1. Unseen generative models (e.g., LivePortrait, SadTalker, Diffusion-based neural talking head synthesizers).
    2. Multiple re-compression passes, resolution downscaling, and variable frame rates.
    3. Severe lighting variation, occlusion, and in-the-wild facial expressions.
  - Production deployments must treat `ms_eff_gcvit` as a significantly stronger baseline on standard video artifacts, while continuing out-of-distribution characterization against larger benchmarks (Celeb-DF-v2, WildDeepfake, and real-world finfluencer fraud captures).

