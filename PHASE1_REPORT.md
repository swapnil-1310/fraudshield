# 🏁 PHASE1_REPORT.md — Baseline & Safety Net Phase 1 Completion Report
> **Branch**: `chore/phase-1-baseline`  
> **Status**: Completed  
> **Author**: Senior Systems Engineer (Pair AI)  
> **Commit History**:
> - `dbe65af` — `docs: add PROJECT_CONTEXT and complete Phase 1 REPO_AUDIT`
> - `6f9b27c` — `build: pin Python 3.11 and split requirements into base, ml, and dev groups`
> - `14ad328` — `test: add comprehensive characterization test suite with unit, api, and sandbox tests`
> - `880e680` — `ci: add GitHub Actions workflow, pre-commit config, gitignore updates, and git history cleanup proposal`

---

## 1. Summary of Changes

### 1.1 Invariants & Production Code Integrity
- **Zero Production Code Changes**: As asserted by `git diff main...chore/phase-1-baseline`, **zero modifications** were made to `src/`, `app.py`, `static/`, `extension/`, `scripts/`, or `config.yaml`.
- **Product Behavior**: 100% identical to baseline.
- **Strict Adherence to Standing Rules**: No public API paths, request/response models, thresholds, or file/module names were altered.

### 1.2 Created & Updated Files Matrix
| File | Action | Purpose |
|---|---|---|
| `REPO_AUDIT.md` | Created | Comprehensive initial audit recording inventory discrepancies, upload validation, CORS, hardcoded thresholds, large files, and script results. |
| `.python-version` | Created | Pins Python version strictly to `3.11.9`. |
| `requirements-base.txt` | Created | Lightweight base dependencies (FastAPI, Pydantic, RapidFuzz, PyYAML, Requests, Pillow, etc.). |
| `requirements-ml.txt` | Created | ML & forensic dependencies (PyTorch, timm, facenet-pytorch, soundfile, moviepy, faster-whisper, easyocr, androguard). |
| `requirements-dev.txt` | Created | Development & test tools (pytest, pytest-asyncio, httpx, ruff, pip-audit, pre-commit). |
| `requirements.txt` | Updated | Backward-compatible master manifest pointing to `-r requirements-base.txt` and `-r requirements-ml.txt`. |
| `README.md` | Updated | Quick-start guide updated with verified dev install instructions. |
| `pytest.ini` | Created | Pytest configuration establishing test paths, markers (`slow`, `xfail`), and warning filters. |
| `tests/conftest.py` | Created | Test setup with path injection, forced CPU mode, and FastAPI `TestClient` fixture. |
| `tests/unit/test_verdict.py` | Created | 19 parametrized test cases covering the complete truth table of `calculate_calibrated_verdict`. |
| `tests/unit/test_pii_shield.py` | Created | Unit tests asserting all 7 DPDP PII patterns + negative non-PII cases. |
| `tests/unit/test_registry.py` | Created | Tests asserting SEBI registration number regex and all 5 registry verdict states. |
| `tests/unit/test_domain_typosquat.py` | Created | Tests asserting Levenshtein distance, broker brand matching, and URL extraction. |
| `tests/unit/test_phonetic_normalizer.py` | Created | Tests asserting financial phonetic acronym conversion and Hindi/English digit word normalization. |
| `tests/unit/test_composite_scoring.py` | Created | Tests asserting weighted composite risk calculation, Hinglish slang detection, and prompt injection detection. |
| `tests/unit/test_config.py` | Created | Tests asserting configuration loading, default fallbacks, and stage config lookups. |
| `tests/api/test_api_contracts.py` | Created | Contract tests asserting FastAPI endpoints (`/api/health`, `/api/scan/text`, `/api/scan/url`, `/api/jobs`, error 400s, 413s). |
| `tests/api/test_temp_sandbox.py` | Created | Verifies `temp/<job_id>` sandbox directory is unconditionally purged on success and forced crash. |
| `tests/slow/test_slow_pipeline.py` | Created | Marked `@pytest.mark.slow` (deselected by default) for heavy model verification. |
| `KNOWN_ISSUES.md` | Created | Comprehensive catalog of existing quirks, regex bugs, and hardcoded items. |
| `.github/workflows/ci.yml` | Created | GitHub Actions workflow running CPU-only test suite, ruff (non-blocking), hardcoded threshold audit, pip-audit, and gitleaks. |
| `.gitignore` | Updated | Added model checkpoints (`*.pth`, `*.bin`, `*.safetensors`), dev caches, and system files. |
| `.pre-commit-config.yaml` | Created | Pre-commit hook configuration for ruff, YAML, JSON, and large file guards. |
| `GIT_HISTORY_HYGIENE_PROPOSAL.md` | Created | Step-by-step proposal for purging the 215MB `dataset/DeepfakeTIMIT` from Git history via `git-filter-repo`. |

---

## 2. Test Execution & Metrics

### 2.1 Pytest Execution Results
- **Command**: `pytest` (executed on CPU, zero network, zero GPU).
- **Execution Time**: **6.59 seconds**.
- **Results**:
  - **Passed**: **80 tests**
  - **Expected Failures (XFAIL)**: **1 test**
  - **Deselected (Slow)**: **1 test**
  - **Failed**: **0 tests**
  - **Errors**: **0 errors**

### 2.2 Test Suite Breakdown
| Suite / Module | Test Count | Status | Notes |
|---|---|---|---|
| `tests/unit/test_verdict.py` | 19 | 19 Passed | Full truth table for 4-tier calibrated verdicts. |
| `tests/unit/test_pii_shield.py` | 10 | 9 Passed, 1 XFAIL | Covers phone, PAN, Aadhaar, UPI, bank, email, Telegram. |
| `tests/unit/test_registry.py` | 14 | 14 Passed | Regex validation, real broker check, mismatch check. |
| `tests/unit/test_domain_typosquat.py` | 5 | 5 Passed | Levenshtein edit distance and domain checks. |
| `tests/unit/test_phonetic_normalizer.py` | 4 | 4 Passed | SEBI variations, English/Hindi digits. |
| `tests/unit/test_composite_scoring.py` | 7 | 7 Passed | Weighted math, Hinglish slang, anti-jailbreak. |
| `tests/unit/test_config.py` | 4 | 4 Passed | YAML config parsing and threshold fallbacks. |
| `tests/api/test_api_contracts.py` | 7 | 7 Passed | API schemas, status codes, 400 validation, 413 oversize. |
| `tests/api/test_temp_sandbox.py` | 2 | 2 Passed | Purge verification on success and crash. |
| `tests/test_metadata_forensics.py` | 8 | 8 Passed | Container parsing, ffprobe/ExifTool fallbacks. |
| `tests/slow/test_slow_pipeline.py` | 1 | 1 Deselected | Deselected by default (`-m "not slow"`). |

---

## 3. The XFAIL List (Documented Known Issues)

Per standing rules, discovered bugs were guarded with `@pytest.mark.xfail` rather than silently edited in production code:

1. **`test_scrub_bank_account_spaced_a_c` (`tests/unit/test_pii_shield.py`)**:
   - *Reason*: In `src/stages/stage5_llm.py:47`, the regex pattern `(r"(?i)(?:a/c|acc(?:ount)?(?:\s+no)?[:\s]+)(\d{9,18})", ...)` separates `a/c` from `[:\s]+` due to regex alternation precedence.
   - *Symptom*: `"a/c 123456789012"` (with a space) is not masked; only `"a/c:123456789012"` or `"a/c123456789012"` or `"account no: 123456789012"` are masked.
   - *Target Fix in Phase 2*: Group alternative prefixes: `r"(?i)(?:a/c|acc(?:ount)?(?:\s+no)?)(?:[:\s]+)(\d{9,18})"`.

---

## 4. What Could Not Be Verified Locally (Environment Realities)

The following capabilities were intentionally not exercised in local unit testing to honor constraints ("Do not download large models or datasets. Tests must run on CPU with no network and no GPU"):
1. **NVIDIA CUDA GPU Inference**: PyTorch was run in CPU mode; GPU inference with Tensor Cores and VRAM sequential offloading (`torch.cuda.empty_cache()`) was mocked or bypassed.
2. **Local Ollama Daemon (LLaMA 3.1 8B)**: Stage 5 LLM tests exercised the deterministic heuristic engine fallback; live Ollama JSON generation requires the Ollama desktop service running on `localhost:11434`.
3. **Multi-Gigabyte Hugging Face Model Downloads**: Wav2Vec2 (`MelodyMachine/Deepfake-Audio-Detection-V2`), EfficientNet weights (`deepfake_detector_phase2.pth`), and Faster-Whisper (`Systran/faster-whisper-medium`) were mocked in unit/API suites to avoid multi-gigabyte network downloads.

---

## 5. Recommended Phase 2 Priorities

Based on our architectural audit and characterization findings, the recommended backlog for Phase 2 is:

1. **Fix Documented Regex & Threshold Anomalies**:
   - Fix the PII bank account regex alternation precedence in `stage5_llm.py:47`.
   - Update `app.py:67` to read `get_threshold("scam_composite_threshold", 0.35)` instead of hardcoded `0.35`.
   - Replace Windows-specific `".venv/Scripts/python"` in `app.py:603` with `sys.executable`.
2. **Move Hardcoded Module Weights to `config.yaml`**:
   - Move `SIGNAL_WEIGHTS` (0.30, 0.20, 0.15, etc.) in `stage5_llm.py` to `config.yaml` under `pipeline.stage5_llm.signal_weights`.
   - Move heuristic fallback scores (`0.95, 0.80, ...`) to `config.yaml`.
3. **Execute Git History Cleanup**:
   - Execute the proposal in `GIT_HISTORY_HYGIENE_PROPOSAL.md` via `git-filter-repo` to purge `dataset/DeepfakeTIMIT` (215 MB) and recover repository clone speed.
4. **Harden Upload Stream Size Guards**:
   - Wrap `StreamingBody` / `UploadFile` chunks with a rolling byte counter to abort connections before spooling oversized files to disk.
5. **Basic API Authentication / Key Management**:
   - Introduce an optional API key middleware (`X-API-Key`) protecting `/api/admin/sync-registry` and job creation.
