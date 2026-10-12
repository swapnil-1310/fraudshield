# 🔍 REPO_AUDIT.md — Phase 1: Baseline & Safety Net Audit
> **Date**: October 12, 2026  
> **Branch**: `chore/phase-1-baseline`  
> **Auditor**: Senior RegTech & Systems Engineer (Pair AI)  
> **Status**: Completed — Awaiting User Approval before Proceeding to Step 1  

---

## 1. Actual Directory & Module Inventory vs. `PROJECT_CONTEXT.md`

A thorough cross-check between git tracking (`git ls-files`), on-disk structures, and `PROJECT_CONTEXT.md` reveals the following inventory and discrepancies:

### 1.1 Complete Actual Inventory
```
fraudshield_v1/
├── .env.example
├── .gitignore
├── DOCUMENTATION.md
├── HACKATHON_GUIDE.md
├── README.md
├── SKILL G Project Status..pdf             [146 KB, tracked in git]
├── TEAM_ONBOARDING_GUIDE.md
├── WhatsApp Video 2026-08-27 at 10.23.37 PM.mp4 [1.51 MB, tracked in git]
├── WhatsApp Video 2026-08-27 at 10.29.55 PM.mp4 [1.50 MB, tracked in git]
├── app.py
├── config.yaml
├── model.py                                [root shim import]
├── progress1.md
├── requirements.txt
├── run_frontend.py
├── dataset/
│   └── DeepfakeTIMIT/                      [215 MB, 1,200+ .wav/.avi files tracked in git]
├── extension/
│   ├── background.js, content.js, manifest.json, popup.css, popup.html, popup.js, icons/
├── scripts/
│   ├── audit_hardcoded.py, download_models.py, e2e_system_test.py, generate_sample.py
│   ├── run_folder_test.py, self_test.py, sync_sebi_registry.py, verify_all_models.py
├── src/
│   ├── backup_api.py, config.py, metadata_forensics.py, model.py
│   └── stages/
│       ├── __init__.py, stage1_ingest.py, stage2_vision.py, stage3_audio.py
│       ├── stage4_transcription.py, stage5_llm.py, stage6_registry.py
│       ├── stage7_ocr.py, stage8_report.py, stage9_apk_domain.py
├── static/
│   ├── index.html, legacy-index.html, css/ (app.css, core.css), js/ (api.js, dom.js, main.js, model.js, stages.js)
│   └── videos/ (README.md, fingaurd-intro-desktop.mp4 [2.27MB], fingaurd-intro-mobile.mp4 [2.43MB])
├── static_data/
│   ├── broker_apk_whitelist.json, sebi_registry.json
├── temp/
│   └── .gitkeep
├── test_vid/
│   ├── noscam_vid/ (2 MP4 files, ~7.9 MB)
│   └── scam_vid/   (2 MP4 files, ~9.8 MB)
└── tests/
    ├── test_metadata_forensics.py
    └── test_verification.py
```

### 1.2 Discrepancies Cataloged
1. **Omitted Core Module — `src/metadata_forensics.py`**:
   - *Status*: Actively invoked by `src/stages/stage1_ingest.py` (lines 147-152) to perform container/box parsing, ffprobe/ExifTool fallback, and C2PA provenance detection.
   - *Discrepancy*: Was completely absent from the `src/` tree listing in `PROJECT_CONTEXT.md`.
2. **Omitted Test Module — `tests/test_metadata_forensics.py`**:
   - *Status*: A 213-line unittest suite covering 8 test scenarios for metadata extraction and provenance analysis.
   - *Discrepancy*: Omitted from the `tests/` inventory in `PROJECT_CONTEXT.md`.
3. **Ghost Artifact — `tests/test_results.csv`**:
   - *Status*: Documented in `PROJECT_CONTEXT.md` (and `HACKATHON_GUIDE.md`) as an existing stored benchmark CSV.
   - *Discrepancy*: Does not exist in the repository or working tree. It is an artifact produced on-demand by `scripts/run_folder_test.py`.
4. **Committed Root Binaries**:
   - *Status*: Three binary files are committed directly to repository root: `SKILL G Project Status..pdf` (146 KB), `WhatsApp Video 2026-08-27 at 10.23.37 PM.mp4` (1.51 MB), and `WhatsApp Video 2026-08-27 at 10.29.55 PM.mp4` (1.50 MB).
   - *Discrepancy*: Omitted from repository file maps.
5. **Committed Raw Benchmark Dataset (`dataset/DeepfakeTIMIT`)**:
   - *Status*: Contains **1,248 individual files** totaling **215.07 MB** of audio (`.wav`) and video (`.avi`) files committed directly into git history.
   - *Discrepancy*: Documented as an external or reference dataset, but actually checked into the active Git repository.
6. **Dynamic File — `static_data/sebi_sync_log.json`**:
   - *Status*: Checked for existence in `app.py` line 569 inside `/api/registry/status`.
   - *Discrepancy*: Missing until `scripts/sync_sebi_registry.py` is executed for the first time.
7. **Version Divergence**:
   - *Status*: `app.py` line 28 declares FastAPI `version="3.1"`, while `/api/health` returns `version="4.0"`, and `PROJECT_CONTEXT.md` documents `Version: 4.0`.

---

## 2. Jobs, State Storage, Upload Validation, CORS, and Auth (Facts Only)

### 2.1 Job and State Storage
- **Mechanism**: In-memory Python dictionary `jobs: dict = {}` declared at module scope in `app.py` (line 46).
- **Persistence**: **None**. State is entirely ephemeral and bound to the lifespan of the `uvicorn` process. Process restart or worker crash causes total loss of queued, processing, and completed job states.
- **Concurrency & Locks**: No threading locks, asyncio locks, or atomic primitives protect mutations to `jobs[job_id]`. Concurrent reads/writes across asynchronous background tasks rely entirely on Python's GIL.
- **Job Lifecycle**:
  - `queued` → Set immediately in `/api/jobs` upon receiving upload.
  - `processing` → Updated synchronously at start of `run_pipeline()`.
  - Stage transitions → Updated per stage (`stage1_ingest`, `stage2_vision`, `stage4_transcription`, `stage3_audio`, `stage5_llm`, `stage6_registry`, `stage9_apk_domain`, `stage8_report`, `stage7_aggregation`).
  - `completed` or `failed` → Set upon completion or unhandled exception.

### 2.2 Upload Validation
- **Size Validation**:
  - Function: `validate_file_size(file: UploadFile)` in `app.py` (lines 48-51).
  - Maximum limit: `MAX_UPLOAD_SIZE = settings.get("server", {}).get("max_upload_mb", 100) * 1024 * 1024` (100 MB).
  - Logic: Checks `hasattr(file, "size") and file.size and file.size > MAX_UPLOAD_SIZE`. Raises `HTTPException(413)`.
  - *Fact*: In Starlette/FastAPI, streaming multipart uploads spooled to disk/memory may have `file.size` as `None` or inaccurate until fully buffered, meaning oversized streams may buffer before being rejected.
- **File Extension Validation**:
  - `/api/jobs` (Video): Enforces `ext in [".mp4", ".avi", ".mov", ".mkv"]`. Raises `HTTPException(400)` otherwise.
  - `/api/scan/audio`: Enforces `ext in [".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"]`. Raises `HTTPException(400)` otherwise.
  - `/api/scan/image`: Enforces `ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]`. Raises `HTTPException(400)` otherwise.
  - `/api/scan/apk`: Enforces `ext == ".apk"`. Raises `HTTPException(400)` otherwise.
  - `/api/scan/text`: Checks `len(req.text.strip()) >= 5`. Raises `HTTPException(400)` if shorter.
  - `/api/scan/url`: Checks `len(req.url.strip()) >= 3`. Raises `HTTPException(400)` if shorter.
- **MIME & Magic Byte Verification**:
  - Upload endpoints in `app.py` perform **zero magic-byte or file signature inspection** during ingestion. Extensions are trusted at the API boundary (though downstream `src/metadata_forensics.py` parses ISO-BMFF container boxes on video).

### 2.3 CORS Configuration
- **Middleware**: `fastapi.middleware.cors.CORSMiddleware` in `app.py` (lines 31-37).
- **Settings**:
  - `allow_origins=["*"]`
  - `allow_credentials=True`
  - `allow_methods=["*"]`
  - `allow_headers=["*"]`
- *Fact*: Wildcard `allow_origins=["*"]` combined with `allow_credentials=True` is non-standard per W3C Fetch Specification and blocked by modern web browsers when sending credentials (`withCredentials: true`), though it functions for unauthenticated extension calls and curl.

### 2.4 Authentication & Authorization
- **Status**: **Completely absent**.
- *Fact*: There is no authentication layer, token validation, API key check, or rate-limiting middleware configured on any route.
- *Fact*: Sensitive administrative operations (such as `POST /api/admin/sync-registry`, which triggers a subprocess execution of `scripts/sync_sebi_registry.py`) are fully open to unauthenticated public requests.

---

## 3. Hardcoded Thresholds, Scoring Weights, Timeouts & Paths vs. `config.yaml`

A comprehensive static audit (`scripts/audit_hardcoded.py`) and manual code review identified the following exact configuration splits:

### 3.1 Parameters Properly Read from `config.yaml`
| Parameter | Source Key in `config.yaml` | Reading Code Location |
|---|---|---|
| Hardware Device | `hardware.device`, `hardware.force_cpu` | `src/config.py::get_device()` |
| Vision Fake Threshold | `thresholds.vision_fake_threshold` (0.5) | `app.py:165, 445`, `stage8_report.py:61` |
| Audio Fake Threshold | `thresholds.audio_fake_threshold` (0.5) | `app.py:166, 367`, `stage8_report.py:62` |
| Audio Segment Flag Threshold | `thresholds.audio_segment_flag_threshold` (0.45) | `src/stages/stage3_audio.py:62` |
| Impersonation Audio Threshold | `thresholds.impersonation_audio_threshold` (0.45) | `src/stages/stage3_audio.py:110` |
| Scene-Cut Delta Threshold | `thresholds.scene_cut_threshold` (35.0) | `src/stages/stage1_ingest.py:97` |
| OCR Min Confidence | `thresholds.ocr_min_confidence` (0.15) | `src/stages/stage7_ocr.py:48` |
| Scam Composite Threshold | `thresholds.scam_composite_threshold` (0.35) | `src/stages/stage5_llm.py:200` |
| LLM Auto-Flag Threshold | `thresholds.llm_risk_auto_flag_threshold` (0.45) | `src/stages/stage5_llm.py:201` |
| Registry Match Thresholds | `thresholds.registry_name_*_match_score` (65, 80) | `src/stages/stage6_registry.py:51-52` |
| APK Typo-squat Levenshtein Dist | `thresholds.apk_domain_levenshtein_max_dist` (3) | `src/stages/stage9_apk_domain.py:97` |
| Ingest Frames Limits | `pipeline.stage1_ingest.max_frames_to_extract` (25) | `src/stages/stage1_ingest.py:94-96` |
| Early Exit Vision Criteria | `vision.early_exit_frame_count` (4), `early_exit_score` (0.92) | `src/stages/stage2_vision.py:103-104` |
| Model IDs | `pipeline.*.model_id` | `stage2_vision.py`, `stage3_audio.py`, `stage4_transcription.py` |
| LLM API URL & Timeouts | `pipeline.stage5_llm.api_url`, `timeout_*_sec` | `src/stages/stage5_llm.py:252, 266-267` |

### 3.2 Parameters That Remain HARDCODED in Python Code
| Location | Hardcoded Value | Description / Impact |
|---|---|---|
| `app.py:67` | `composite_risk >= 0.35` | Hardcodes the `0.35` threshold for the "Suspicious" calibrated verdict instead of reading `get_threshold("scam_composite_threshold", 0.35)`. |
| `app.py:603` | `[".venv/Scripts/python", ...]` | Hardcoded Windows-specific virtualenv interpreter path; fails on Linux, macOS, or custom venvs. |
| `src/stages/stage5_llm.py:27-34` | `SIGNAL_WEIGHTS = {explicit_returns: 0.30, implied_returns: 0.20, urgency_scarcity: 0.15, social_proof: 0.10, paywall_push: 0.10, credential_misrep: 0.15}` | Core regulatory scoring weights are hardcoded at module scope and cannot be tuned via `config.yaml`. |
| `src/stages/stage5_llm.py:152-185` | Fallback scores: `0.95, 0.80, 0.75, 0.70, 0.85, 0.90` | Exact signal scores emitted during deterministic heuristic fallback are hardcoded. |
| `src/stages/stage5_llm.py:268` | `len(text) < 400` | Character count cutoff choosing between short and long LLM timeout is hardcoded. |
| `src/stages/stage2_vision.py:31` | `h*0.60:h*0.95, w*0.25:w*0.75` | Mouth crop region bounding fractions are hardcoded. |
| `src/stages/stage2_vision.py:83, 86` | `temporal_variance > 0.04`, `mouth_motion < 0.005` | Forensic flag triggers for temporal variance and mouth motion activity are hardcoded. |
| `src/stages/stage6_registry.py:24` | `CACHE_TTL_SECONDS = 3600 * 24` | Hardcoded module constant (24h), duplicating `config.yaml` `refresh_interval_hours`. |
| `src/stages/stage9_apk_domain.py:186` | `DANGEROUS_PERMISSIONS = [...]` | Hardcoded fallback list in addition to YAML config. |
| `src/metadata_forensics.py:69, 137` | `50 * 1024 * 1024` (50MB), `timeout=10` | Box parsing byte ceiling and subprocess execution timeouts are hardcoded. |

---

## 4. Large Files, Committed Media, Datasets & Secret Inspection

### 4.1 Committed Large Media & Datasets (>1 MB)
*(Paths only; contents not exposed)*
- `dataset/DeepfakeTIMIT/` — Directory total: **215.07 MB** (1,248 audio/video files)
  - `dataset/DeepfakeTIMIT/fram1-original.mov` (3.35 MB)
  - `dataset/DeepfakeTIMIT/fadg0-original.mov` (3.23 MB)
  - `dataset/DeepfakeTIMIT/deepfake_images_1.png` (1.43 MB)
  - 1,200+ `.avi` and `.wav` clips in `higher_quality/` and `lower_quality/` (0.2 - 0.5 MB each)
- `test_vid/` — Directory total: **17.74 MB** (4 video benchmark clips)
  - `test_vid/scam_vid/WhatsApp Video 2026-08-26 at 4.05.39 PM.mp4` (5.07 MB)
  - `test_vid/scam_vid/WhatsApp Video 2026-08-26 at 4.05.01 PM.mp4` (4.73 MB)
  - `test_vid/noscam_vid/WhatsApp Video 2026-08-26 at 4.05.46 PM.mp4` (4.07 MB)
  - `test_vid/noscam_vid/WhatsApp Video 2026-08-26 at 4.06.22 PM.mp4` (3.87 MB)
- `static/videos/` — Directory total: **4.70 MB**
  - `static/videos/fingaurd-intro-mobile.mp4` (2.43 MB)
  - `static/videos/fingaurd-intro-desktop.mp4` (2.27 MB)
- Repository Root Media & Document Files:
  - `WhatsApp Video 2026-08-27 at 10.23.37 PM.mp4` (1.51 MB)
  - `WhatsApp Video 2026-08-27 at 10.29.55 PM.mp4` (1.50 MB)
  - `SKILL G Project Status..pdf` (0.15 MB)

### 4.2 Model Weights
- **Status**: No `.pth`, `.pt`, `.bin`, `.onnx`, or `.safetensors` model weight files are committed in Git.
- Model checkpoints are pulled at runtime or cached via `scripts/download_models.py` into HuggingFace and PyTorch default cache directories.

### 4.3 Secrets & Environment Files Analysis
- Committed template: `.env.example` (template with empty placeholders for `SIGHTENGINE_API_USER`, `SIGHTENGINE_API_SECRET`, and `HF_TOKEN`).
- Active `.env`: **None present**.
- Git tree inspection: No committed live private keys, tokens, or credential strings were identified in code.
- Files referencing external credential environment variables:
  - `src/backup_api.py` (`SIGHTENGINE_API_USER`, `SIGHTENGINE_API_SECRET`)
  - `src/stages/stage2_vision.py` (`HUGGINGFACE_TOKEN`, `HF_TOKEN`)
  - `scripts/download_models.py` (`HF_TOKEN`)

---

## 5. Execution Status of Existing Verification & Test Scripts

All existing verification scripts were run against the current Python runtime environment (`Python 3.11.9` on Windows). Exact commands and execution outcomes are recorded below:

### 5.1 `scripts/audit_hardcoded.py`
- **Command Executed**: `python scripts/audit_hardcoded.py`
- **Working Directory**: `c:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1`
- **Result**: **PASS** (Exit code `0`).
- **Observations**: Scanned 21 Python files in the repository. Identified 44 individual findings of hardcoded parameters, model IDs, localhost URLs, and thresholds as detailed in Section 3 of this audit.

### 5.2 `scripts/self_test.py`
- **Command Executed**: `python scripts/self_test.py`
- **Working Directory**: `c:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1`
- **Result**: **FAIL** (Exit code `1`).
- **Exact Failure Output**:
  ```
  ============================================================
    FinGuard Self-Test Suite — Round 2
  ============================================================
  [PASS] Test 1: C1+M1 — LLM threshold + timeout keys in config
  Traceback (most recent call last):
    File "C:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1\scripts\self_test.py", line 24, in <module>
      from src.stages.stage4_transcription import run_stage4_transcription
    File "C:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1\src\stages\stage4_transcription.py", line 5, in <module>
      from faster_whisper import WhisperModel
  ModuleNotFoundError: No module named 'faster_whisper'
  ```
- **Root Cause**: The Python environment lacks `faster-whisper`. A dedicated, isolated virtual environment with locked dependencies has not been initialized.

### 5.3 `scripts/e2e_system_test.py`
- **Command Executed**: `python scripts/e2e_system_test.py`
- **Working Directory**: `c:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1`
- **Result**: **FAIL** (Exit code `1`).
- **Exact Failure Output**:
  ```
  =================================================================
    FinGuard End-to-End Live System Stress & Verification Test
  =================================================================
  Traceback (most recent call last):
    File "C:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1\scripts\e2e_system_test.py", line 24, in <module>
      from app import app, calculate_calibrated_verdict
    File "C:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1\app.py", line 15, in <module>
      from src.stages.stage1_ingest import run_stage1_ingest
    File "C:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1\src\stages\stage1_ingest.py", line 6, in <module>
      from moviepy import VideoFileClip
  ModuleNotFoundError: No module named 'moviepy'
  ```
- **Root Cause**: The Python environment lacks `moviepy` (and transitive dependencies).

### 5.4 `tests/test_verification.py`
- **Command Executed**: `python tests/test_verification.py`
- **Working Directory**: `c:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1`
- **Result**: **FAIL** (Exit code `1`).
- **Failure Output**: `ModuleNotFoundError: No module named 'timm'` during PyTorch hybrid detector import.

### 5.5 `tests/test_metadata_forensics.py`
- **Command Executed**: `python tests/test_metadata_forensics.py`
- **Working Directory**: `c:\Users\LOQ\OneDrive\Desktop\fraudshield\fraudshield_v1`
- **Result**: **FAIL** (7 passed, 1 error).
- **Failure Output**: `test_07_stage1_ingest_integration` failed with `ModuleNotFoundError: No module named 'moviepy'`. The remaining 7 pure-Python metadata forensics tests passed cleanly.

---

## 6. Proposed Task List & Risk Assessment for Subsequent Steps

The following sequential plan is proposed for executing the remaining steps of Phase 1 upon user approval:

### Proposed Task Breakdown

```
[Phase 1 Implementation Plan]
 ├── Step 1: Reproducible Environment
 │    ├── 1.1 Pin Python version (3.11.9 / >=3.10, <3.12) in .python-version
 │    ├── 1.2 Structure layered requirements (requirements-base.txt, requirements-ml.txt, requirements-dev.txt)
 │    ├── 1.3 Preserve requirements.txt backward compatibility (installs all layers)
 │    ├── 1.4 Resolve and record MoviePy v1 vs v2 import conventions
 │    └── 1.5 Update README.md quick-start with verified commands only
 │
 ├── Step 2: Characterization Tests (pytest)
 │    ├── 2.1 Set up directory tree: tests/unit/, tests/api/, tests/slow/, conftest.py, pytest.ini
 │    ├── 2.2 Write Unit Tests for Pure Logic:
 │    │     • calculate_calibrated_verdict (complete truth table matrix)
 │    │     • scrub_pii_dpdp (all 7 PII regex patterns + non-PII false-positive negatives)
 │    │     • Registry regex (^IN[A-Z0-9]{8,14}$) and verdict category states
 │    │     • RapidFuzz & Levenshtein domain typosquatting logic
 │    │     • Phonetic financial normalizer rules
 │    │     • Multi-signal composite weighted scoring logic
 │    │     • Config parsing, stage lookup, and default fallback values
 │    ├── 2.3 Write API Contract Tests (FastAPI TestClient with ML stages stubbed):
 │    │     • GET /api/health
 │    │     • POST /api/scan/text (valid, empty, short text)
 │    │     • POST /api/scan/url (valid, malformed, phishing)
 │    │     • POST /api/jobs (create, poll status, download complaint)
 │    │     • Invalid file types (e.g. .txt to video) & oversize payload responses
 │    ├── 2.4 Write Ephemeral Sandbox Isolation Test:
 │    │     • Assert temp/<job_id> cleanup on job success
 │    │     • Assert temp/<job_id> cleanup on forced unhandled pipeline exception
 │    ├── 2.5 Catalog discovered behavioral quirks in KNOWN_ISSUES.md using @pytest.mark.xfail
 │
 ├── Step 3: CI & Hygiene
 │    ├── 3.1 Create GitHub Actions workflow (.github/workflows/ci.yml):
 │    │     • CPU-only matrix test run
 │    │     • pytest execution (excluding @pytest.mark.slow)
 │    │     • scripts/audit_hardcoded.py validation
 │    │     • Non-blocking pip-audit and gitleaks jobs
 │    ├── 3.2 Update .gitignore with exhaustive rules (caches, virtualenvs, models, runtime temp)
 │    ├── 3.3 Draft Git History Hygiene Plan (propose BFG / git-filter-repo strategy for 215MB dataset)
 │    └── 3.4 Add .pre-commit-config.yaml with ruff and standard formatting/hygiene hooks
 │
 └── Step 4: Reporting
      └── 4.1 Produce PHASE1_REPORT.md detailing test counts, xfails, and Phase 2 recommendations
```

### Risk Assessment & Mitigation Matrix

| Risk Identified | Severity | Likelihood | Mitigation Strategy |
|---|---|---|---|
| **MoviePy Import Path Drift** (`moviepy.editor` vs `moviepy`) | High | High | MoviePy 2.x broke legacy `from moviepy.editor import VideoFileClip`. We will inspect the exact import behavior used in `stage1_ingest.py` (`from moviepy import VideoFileClip`) and pin the compatible major version (`moviepy>=2.0.0` or `<2.0.0` depending on exact syntax) without modifying production code. |
| **PyTorch CPU Wheel Bloat in CI** | Medium | High | In CI environments, default `pip install torch` downloads multi-gigabyte CUDA binaries. Configure CI to explicitly install CPU-only wheels (`--extra-index-url https://download.pytorch.org/whl/cpu`) to keep CI fast and bandwidth-efficient. |
| **Test Client Stage Leaks** (accidental ML inference during unit tests) | High | Medium | In `tests/api/`, aggressively mock `run_stage1_ingest`, `run_stage2_vision`, `run_stage3_audio`, `run_stage4_transcription`, and `run_stage5_llm` in `conftest.py` using `unittest.mock.patch` to guarantee zero GPU, network, or weight-loading overhead. |
| **Windows Path Separator Flakiness** (`\` vs `/`) | Medium | Medium | Use `pathlib.Path` or `os.path.normpath` exclusively across all test fixtures and assertions to ensure cross-platform compatibility across Windows and Linux CI runners. |
| **Modifying Production Behavior** | Critical | Low | Strictly enforce the standing rule: characterization tests test current behavior as-is. If an unexpected behavior or bug is uncovered, do NOT fix it in production code; mark it with `@pytest.mark.xfail` and list it in `KNOWN_ISSUES.md`. |

---

## 7. Immediate Next Action

Execution is halted per instruction (`STEP 0 — PLAN FIRST (stop for my approval)`).  
Please review this audit and provide approval to begin **Step 1 (Reproducible Environment)** and **Step 2 (Characterization Tests)**.
