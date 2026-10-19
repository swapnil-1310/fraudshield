# 🛡️ PROJECT_CONTEXT.md — FinGuard / FraudShield Master Context Specification
> **Target Audience**: AI Coding Assistants, LLM Agents (Claude, GPT, Gemini, Cursor, Copilot), and Software Engineers.  
> **Purpose**: Single authoritative source of truth detailing the architecture, tech stack, 9-stage forensic pipeline, API contracts, VRAM management, regulatory logic, and engineering guidelines.

---

## 1. Executive Summary & Problem Statement

**Project Name**: FinGuard (also referenced as FraudShield)  
**Version**: 4.0 (Enterprise RegTech Edition)  
**Domain**: RegTech, Financial Cyber-Forensics, AI Deepfake Detection, Regulatory Compliance  

### 1.1 What FinGuard Is
FinGuard is an **offline-first, multi-modal AI forensic platform** that analyzes digital media (video, audio, screenshots, social media text, Android APKs, and web domains) to uncover two critical threats:
1. **Generative Deepfakes & Voice Cloning**: AI face-swapping, facial reenactment, synthetic voice cloning, and viseme audio-visual desync impersonating registered financial figures, CEOs, and market experts.
2. **Financial Fraud & SEBI Regulatory Violations**: Unregistered investment advice, pump-and-dump schemes, guaranteed return promises, pressure tactics, coded Hinglish scam colloquialisms, fake broker APKs, and typo-squatted phishing domains violating **SEBI (Securities and Exchange Board of India)** regulations.

### 1.2 Core Philosophy & Non-Negotiables
- **100% Offline & Local-First**: Built to execute fully on a standard consumer/developer laptop GPU (**NVIDIA RTX 4050 with 6GB VRAM budget**) or CPU fallback with **zero mandatory cloud API dependencies**.
- **DPDP Act 2023 Privacy-First**: Strict zero-retention data lifecycle. Transcribed text and extracted frames are scrubbed of Personally Identifiable Information (PII) before LLM analysis; all temporary files are purged in ephemeral sandboxes.
- **Fail-Soft Architecture**: If the local LLM (Ollama) is offline or times out, the pipeline seamlessly degrades to deterministic regex/heuristic scoring without crashing.
- **Zero Hardcoded Magic Values**: All model weights, thresholds, confidence levels, and paths are centrally declared in `config.yaml`.

---

## 2. Complete Technology Stack Matrix

| Layer / Subsystem | Technology / Library | Version / Checkpoint | Primary Role & Runtime Characteristics |
|---|---|---|---|
| **Backend Framework** | **FastAPI** | `>=0.110.0` | High-performance asynchronous API server with background task support and OpenAPI documentation. |
| **ASGI Server** | **Uvicorn** | Standard | ASGI worker serving HTTP/REST traffic on port `8000`. |
| **Configuration** | **PyYAML + Pydantic** | Standard | Typed configuration loader with environment variable overrides (`config.yaml`). |
| **Deep Learning Framework** | **PyTorch** (`torch`, `torchvision`, `torchaudio`) | `>=2.1.0` (CUDA 11.8/12.1 or CPU) | Neural network inference engine for vision and acoustic forensic models. |
| **Vision Backbone** | **MS-EffGCViT-B0** | `KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus` | Spatial-frequency deepfake classifier loaded from HuggingFace. |
| **Face Detection & Alignment** | **facenet-pytorch (MTCNN)** | Standard | Extracts bounding boxes and crops facial regions with a 25px margin. |
| **Custom Vision Forensic Model** | **MS-EffGCViT Backend** | Pretrained Hub checkpoint | Multi-scale EfficientNet + Global Context Vision Transformer architecture. |
| **Audio Deepfake Detection** | **HuggingFace Transformers (Wav2Vec2)** | `garystafford/wav2vec2-deepfake-voice-detector` (Model C) | Production default acoustic spoofing classifier evaluated across 5-second windowed chunks. |
| **Multilingual Transcription** | **faster-whisper** (CTranslate2) | `Systran/faster-whisper-small` (`float16` CUDA) | Hindi-English code-switched ASR on CUDA with seamless int8 CPU fallback. |
| **Local LLM Engine** | **Ollama (LLaMA 3.1)** | `llama3.1:latest` (`8B`) | Structured JSON extraction, 6-signal SEBI compliance evaluation, and reasoning. |
| **Fuzzy Matching & String Distances** | **RapidFuzz** + **python-Levenshtein** | Standard | Token-sort ratio matching against SEBI registry; Levenshtein distance for domain typo-squatting. |
| **Optical Character Recognition (OCR)** | **EasyOCR** | `[en, hi]` | Multi-lingual text extraction from P&L screenshots, fake certificates, and charts. |
| **Android APK Forensics** | **Androguard** | Standard | Static APK analysis: extracts AndroidManifest.xml permissions and package names. |
| **Media Processing** | **MoviePy** + **OpenCV** (`cv2`) + **librosa** + **soundfile** | Standard | Video ingestion, scene-cut frame differencing, audio track stripping, and normalization. |
| **Frontend Web Dashboard** | **Vanilla HTML5 + CSS + JavaScript** | ES6+ | Clean Fintech SPA with decoupled Audio and Scam check sections, meters, and SCORES complaint viewer. |
| **Browser Sentinel Extension** | **Chrome Extension Manifest V3** | Manifest v3 | Context menu scanner, page text/image right-click analysis, and slide-in notifications. |
| **Cloud Fallback (Optional)** | **Sightengine REST API** | Optional | Config-toggled fallback if local vision models are bypassed. |

---

## 3. System Architecture & 9-Stage Pipeline

```
                                [ User Media / Uploaded Artifact ]
                 (Video .mp4/.mov | Audio .mp3/.wav | Image .png/.jpg | Text | APK | URL)
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Ingest & Preprocessing (MoviePy, MTCNN, Adaptive Scene-Cut, Laplacian Quality)         │
│  • MoviePy separates audio track into 16kHz mono WAV                                           │
│  • OpenCV calculates frame-to-frame pixel differencing for scene-cut splice detection          │
│  • MTCNN crops faces with 25px bounding-box margin (up to 25 candidate frames)                  │
│  • Laplacian variance calculates image sharpness/blur score to benchmark input fidelity        │
└──────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌───────────────────────────────────────┐   ┌────────────────────────────────────────────────────┐
│ Stage 2: Dual-Branch Vision Forensics │   │ Stage 4: Speech Transcription & Normalization      │
│  • Spatial Branch: EfficientNet-B4    │   │  • faster-whisper (medium, int8 quantized on CPU)  │
│  • Frequency Branch: SRM + Xception   │   │  • Multilingual Hindi + English transcription      │
│  • Temporal Variance & Mouth Motion   │   │  • Financial phonetic cleanup ("say bee" → "SEBI") │
│  • Early-Exit logic (scores > 0.92)   │   │  • Timestamped segment generation                  │
└───────────────────┬───────────────────┘   └─────────────────────┬──────────────────────────────┘
                    │                                             │
                    │   ┌─────────────────────────────────────────┘
                    ▼   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Audio Spoofing & Finfluencer Impersonation Check                                      │
│  • Wav2Vec2 classifies acoustic spoofing in 5-second windowed chunks                           │
│  • DC offset removal and peak amplitude normalization                                          │
│  • Checks transcript for claimed public advisor names against acoustic voice profiles          │
└──────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Stage 5: SEBI Compliance Reasoning LLM & DPDP Security Shield                                 │
│  • DPDP Act 2023 Shield: Regex masks Indian PAN, Aadhaar, Phone, UPI, Bank A/C, and Chat Links │
│  • Anti-Jailbreak Guard: Scans for adversarial system prompt injection attempts                 │
│  • Hinglish Coded Slang Detector: Flags "rocket call", "pakka jackpot", "zero-loss", etc.      │
│  • Ollama LLaMA 3.1: 6-signal weighted compliance scoring with strict JSON output             │
│  • Deterministic Regex Fallback: Executes if Ollama is unreachable or times out                 │
└──────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Stage 6: SEBI Intermediary Registry Cross-Check                                                │
│  • Offline master snapshot: static_data/sebi_registry.json (Investment Advisers, Analysts)     │
│  • Validates claimed SEBI registration number format (regex: IN[A-Z0-9]{8,14})                  │
│  • RapidFuzz token_sort_ratio fuzzy matches advisor names and company aliases                  │
│  • In-memory TTL cache with file modification timestamp invalidation                           │
└──────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Stage 7: Optical Character Recognition (OCR)                                                   │
│  • EasyOCR (Hindi + English) extracts on-screen text from screenshots, P&L cards, certificates  │
│  • Extracted text is fed back to Stage 5 (compliance check) and Stage 9 (domain check)        │
└──────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Stage 9: APK Metadata & Typo-Squatting Domain Scanner                                          │
│  • APK: Androguard inspects manifest for dangerous permissions (READ_SMS, ACCESSIBILITY)      │
│  • Typo-Squatting: Levenshtein distance & brand keyword analysis vs broker whitelist           │
└──────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Calibrated Aggregation Engine & Timeline Scrubber Builder                                      │
│  • Multi-modal risk fusion: Combines vision, audio, text composite risk, and registry status    │
│  • 3-Tier Calibrated Verdict: Safe | Suspicious | Warning | Critical                           │
│  • Generates synchronized timeline track combining audio spoof spikes and text quote flags     │
└──────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Stage 8: SEBI SCORES 2.0 Pre-Filing Evidence Dossier Generator                                 │
│  • Formats legal complaint draft citing SEBI (PFUTP) Regulations 2003 & IA Regulations 2013     │
│  • Ready for one-click copy or text download for submission to the SEBI SCORES portal          │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Deep Dive into the 9 Forensic Stages

### Stage 1: Ingest & Preprocessing (`src/stages/stage1_ingest.py`)
- **Audio Extraction**: Uses `moviepy.editor.VideoFileClip` to write a 16,000 Hz, 16-bit mono WAV file.
- **Adaptive Scene-Cut Frame Differencing**: Calculates mean absolute pixel difference between consecutive grayscale frames. If difference exceeds `thresholds.scene_cut_threshold` (default `35.0`), a scene cut is identified. Deepfake splices frequently occur at cut boundaries.
- **Face Extraction**: Uses MTCNN (`facenet-pytorch`) with margin expansion (25px). Extracts up to `pipeline.stage1_ingest.max_frames_to_extract` (default 25 frames, min floor 15).
- **Input Quality Assessment**: Computes the variance of the Laplacian filter (`cv2.Laplacian(gray, cv2.CV_64F).var()`). Low variance signals motion blur or severe re-compression, adjusting forensic confidence ratings.

### Stage 2: Dual-Branch Vision Forensics (`src/stages/stage2_vision.py` & `src/model.py`)
- **Neural Architecture**:
  - **Spatial Branch**: `timm.create_model("efficientnet_b4", pretrained=False, num_classes=0)` → 1792 features capturing face anatomy, warping artifacts, and edge blending.
  - **Frequency/Noise Branch**: `SRMLayer` (3 fixed 5×5 high-pass filters: 1st, 2nd, and 3rd order derivatives) → `timm.create_model("xception", pretrained=False, num_classes=0, in_chans=3)` → 2048 features exposing GAN grid artifacts and resampling noise.
  - **Classifier**: Concatenated 3840-dim vector → `Linear(3840, 256)` → `ReLU` → `Dropout(0.5)` → `Linear(256, 1)` → `Sigmoid()`.
- **Early-Exit Optimization**: If the first `vision.early_exit_frame_count` (4) frames all yield deepfake scores exceeding `vision.early_exit_score` (0.92), remaining frames are bypassed to conserve compute.
- **Consensus Blending**: Blends the top-K frames mean with the peak score using `vision.consensus_top_weight` (0.65).
- **Forensic Artifacts**: Generates temporal score variance and a base64-encoded forensic heatmap highlighting spatial noise concentration.

### Stage 3: Audio Spoofing Detection (`src/stages/stage3_audio.py`)
- **Model**: HuggingFace `AutoModelForAudioClassification.from_pretrained("MelodyMachine/Deepfake-Audio-Detection-V2")`.
- **Preprocessing**: Audio loaded at 16kHz, DC offset removed (`audio - np.mean(audio)`), peak normalized.
- **Windowed Scanning**: Audio sliced into 5.0-second non-overlapping chunks. Each chunk receives an independent synthetic probability score.
- **Finfluencer Impersonation Check**: Analyzes whether claimed advisors in the spoken text conflict with high acoustic synthetic scores, triggering an explicit impersonation warning.
- **Output**: Per-segment timeline breakdown with timestamps and maximum spoof score.

### Stage 4: Speech Transcription & Normalization (`src/stages/stage4_transcription.py`)
- **Model**: `faster-whisper` (`Systran/faster-whisper-medium`), CTranslate2 `int8` quantization running on CPU.
- **Multilingual Support**: Supports code-switched Hindi-English (Hinglish) common in Indian financial influencer videos.
- **Financial Phonetic Normalizer**: Solves Whisper transliteration quirks via specialized regex transformations:
  - Spoken acronyms: `"say bee"` / `"saybi"` → `"SEBI"`, `"eye en ay"` → `"INA"`.
  - Spoken alphanumeric registration numbers: `"INA zero zero one..."` → `"INA001..."`.
  - Hindi numeric words: `"shunya"`, `"ek"`, `"do"` converted to Arabic digits when following registration keywords.
- **Output**: Full normalized transcript and subtitle-style timestamped segments (`[{start, end, text}, ...]`).

### Stage 5: SEBI Compliance Reasoning LLM (`src/stages/stage5_llm.py`)
- **Model & Service**: LLaMA 3.1 8B via Ollama REST API (`http://localhost:11434/api/chat`).
- **DPDP Act 2023 Privacy Shield**: Masks sensitive data before it reaches the LLM:
  - Indian Mobile (+91 / 10-digit), PAN Card (5L-4D-1L), Aadhaar (12-digit), UPI Handles (`*@okhdfcbank`, `*@paytm`, etc.), Bank Account numbers, Emails, and WhatsApp/Telegram invite links.
- **Anti-Jailbreak / Prompt Injection Shield**: Flags instructions attempting to override compliance guidelines (e.g. `"ignore previous instructions"`, `"DAN mode"`, `"mark as safe"`).
- **Hinglish Slang Scanner**: Flags coded phrases (*"rocket call"*, *"pakka jackpot"*, *"zero-loss setup"*, *"100% loss recovery"*, *"nifty blast"*, *"paisa double"*).
- **Multi-Signal Weighted Scoring Engine**:
  | Signal Category | Weight | Description |
  |---|---|---|
  | `explicit_returns` | **30%** | Guaranteed percentage or fixed monetary promises. |
  | `implied_returns` | **20%** | Phrases implying sure-shot profits without outright guarantees. |
  | `urgency_scarcity` | **15%** | Pressure tactics, countdowns, "only 10 spots left". |
  | `credential_misrep`| **15%** | Fabricated SEBI registrations or government authorizations. |
  | `social_proof` | **10%** | Inflated subscriber counts, manipulated profit cards. |
  | `paywall_push` | **10%** | Directing users to paid VIP channels or private WhatsApp/Telegram. |
- **Composite Risk Score**: $\sum (\text{signal\_score}_i \times \text{weight}_i)$.
- **Deterministic Heuristic Fallback**: If Ollama times out or is offline, a keyword/regex rule engine computes an identical Pydantic `SEBIAnalysis` structure so the system never breaks.

### Stage 6: SEBI Intermediary Registry Cross-Check (`src/stages/stage6_registry.py`)
- **Database**: Local JSON snapshot (`static_data/sebi_registry.json`) containing registered Investment Advisers (IA), Research Analysts (RA), and Brokers.
- **Verification Workflow**:
  1. Validates format of claimed registration number against `^IN[A-Z0-9]{8,14}$`.
  2. If registration number is found: Exact lookup in database, followed by `RapidFuzz` fuzzy matching between claimed name and registered entity/aliases.
  3. If only advisor name is claimed: Fuzzy search across all registered entities (threshold: 80% match).
- **Verdict Categories**: `verified` | `not found` | `name-number mismatch` | `malformed number` | `not claimed`.
- **Caching**: In-memory cache with 24-hour TTL and file modification time (`mtime`) tracking.

### Stage 7: On-Screen OCR Text Extraction (`src/stages/stage7_ocr.py`)
- **Model**: `easyocr.Reader(['en', 'hi'], gpu=True)`.
- **Target Content**: Screenshots of fake P&L statements, doctored SEBI certificates, trading terminal captures, Telegram forwards.
- **Output**: Full extracted text, bounding boxes, and average OCR confidence. Extracted text automatically cascades into Stages 5, 6, and 9.

### Stage 8: SEBI SCORES Legal Evidence Dossier (`src/stages/stage8_report.py`)
- **Functionality**: Automatically compiles an evidentiary legal complaint for the SEBI Complaints Redress System (SCORES 2.0).
- **Statutory Grounds Cited**:
  - Regulations 3 & 4 of **SEBI (Prohibition of Fraudulent and Unfair Trade Practices relating to Securities Market) Regulations, 2003**.
  - Regulation 3(1) of **SEBI (Investment Advisers) Regulations, 2013**.
- **Included Evidence**: Full transcript quotes, vision/audio deepfake confidence, fuzzy registry failure logs, and domain/APK threats.

### Stage 9: APK Metadata & Typo-Squatting Scanner (`src/stages/stage9_apk_domain.py`)
- **Android APK Manifest Audit**:
  - Uses `androguard` to decompile `AndroidManifest.xml` without executing the APK.
  - Flags package name typosquatting against legitimate broker apps in `static_data/broker_apk_whitelist.json` (e.g., Zerodha Kite, Groww, Angel One).
  - Inspects dangerous permissions: `READ_SMS`, `RECEIVE_SMS`, `BIND_ACCESSIBILITY_SERVICE`, `READ_CONTACTS`, `PACKAGE_USAGE_STATS`.
- **Domain & URL Typosquatting**:
  - Normalizes URLs and extracts hostnames.
  - Runs Levenshtein edit distance and brand-keyword token matching against official broker domains.
  - Detects phishing domains such as `groww-bonus-login.xyz` or `zerodha-wealth.vip`.

---

## 5. Decision Engine & Calibrated Verdicts

The platform combines multi-modal scores into a 4-tier calibrated regulatory verdict:

```python
def calculate_calibrated_verdict(is_deepfake: bool, is_scam: bool, composite_risk: float, registry_verdict: str) -> str:
    if is_deepfake and is_scam:
        return "Critical: Deepfake + Scam"
    elif is_deepfake:
        return "Warning: Deepfake Detected"
    elif is_scam or registry_verdict in ["not found", "name-number mismatch", "malformed number"]:
        return "Warning: SEBI Violation / Scam"
    elif composite_risk >= 0.35:
        return "Suspicious: Review Recommended"
    else:
        return "Safe"
```

| Calibrated Verdict | Visual Indicator | Trigger Conditions | Recommended Action |
|---|---|---|---|
| **Critical: Deepfake + Scam** | 🔴 Red Glowing Badge | Vision/Audio fake score $> 0.5$ **AND** SEBI scam confirmed. | Immediate cybercrime report & SEBI SCORES lodgement. |
| **Warning: Deepfake Detected** | 🟠 Orange Badge | Synthetic face or cloned voice detected ($> 0.5$), content non-fraudulent. | Flagged for synthetic media disclosure compliance. |
| **Warning: SEBI Violation / Scam** | 🟡 Amber Badge | Regulatory violation, fake SEBI reg number, phishing domain, or malicious APK. | Immediate compliance investigation. |
| **Suspicious: Review Recommended** | 🔵 Blue Badge | Composite scam risk between $0.35$ and $0.65$ without explicit violation. | Human compliance officer manual review. |
| **Safe** | 🟢 Green Badge | Verified advisor, clean media, composite risk $< 0.35$. | Approved. |

---

## 6. Repository Layout & File Catalog

```
c:\Users\LOQ\OneDrive\Desktop\fraudshield\
├── PROJECT_CONTEXT.md              # 📖 Master AI Context File (This specification)
└── fraudshield_v1/                 # 🚀 Active Production Repository
    ├── app.py                      # FastAPI application entry point, all endpoints & background jobs
    ├── config.yaml                 # Master configuration file (all thresholds, model IDs, hardware settings)
    ├── requirements.txt            # Pinned Python package dependencies
    ├── .env.example                # Template for environment secrets (Sightengine, HuggingFace)
    ├── .gitignore                  # Git ignore rules (virtualenvs, temp files, media caches)
    ├── model.py                    # Root import shim for HybridDeepfakeDetector
    ├── run_frontend.py             # Standalone Python HTTP server for frontend (port 3000)
    ├── README.md                   # Repository overview and quick start
    ├── DOCUMENTATION.md            # Comprehensive technical architecture deep-dive
    ├── HACKATHON_GUIDE.md          # Judge defense guide, Q&A talking points, and storage lifecycle
    ├── TEAM_ONBOARDING_GUIDE.md    # Developer onboarding, troubleshooting, and architectural principles
    ├── progress1.md                # Development status log and milestone tracking
    │
    ├── src/                        # 🧠 Core Python Engine
    │   ├── config.py               # Typed YAML config loader with environment variable overrides
    │   ├── model.py                # PyTorch HybridDeepfakeDetector (EfficientNet-B4 + SRM Xception)
    │   ├── backup_api.py           # Optional Sightengine cloud fallback integration
    │   └── stages/                 # 🔬 9-Stage Forensic Modules
    │       ├── __init__.py
    │       ├── stage1_ingest.py    # MoviePy audio extraction, MTCNN face crops, Laplacian quality index
    │       ├── stage2_vision.py    # Dual-branch spatial + frequency inference, early exit, heatmaps
    │       ├── stage3_audio.py     # Wav2Vec2 audio deepfake classification, 5s chunk scrubber
    │       ├── stage4_transcription.py # faster-whisper multilingual ASR + phonetic financial cleaner
    │       ├── stage5_llm.py       # LLaMA 3.1 compliance reasoning, DPDP PII shield, Hinglish slang
    │       ├── stage6_registry.py  # RapidFuzz SEBI intermediary database verification & TTL cache
    │       ├── stage7_ocr.py       # EasyOCR Hindi+English text extraction from screenshots/cards
    │       ├── stage8_report.py    # Auto-generation of SEBI SCORES 2.0 legal complaint dossiers
    │       └── stage9_apk_domain.py # Androguard APK permission audit & Levenshtein domain scanner
    │
    ├── static/                     # 🎨 Frontend Web Dashboard
    │   ├── index.html              # Modern glassmorphic SPA dashboard
    │   ├── legacy-index.html       # Legacy reference UI
    │   ├── css/                    # Modular HSL design system & tokens
    │   │   ├── app.css             # Component layout, cards, badges, and responsive grids
    │   │   └── core.css            # Typography, CSS variables, glassmorphism, animations
    │   ├── js/                     # Client application architecture
    │   │   ├── api.js              # REST client and asynchronous job polling
    │   │   ├── dom.js              # DOM querying and dynamic element rendering
    │   │   ├── main.js             # Event handling, tabs, file uploads, media playback
    │   │   ├── model.js            # View model transformation & evidence payload formatting
    │   │   └── stages.js           # 9-stage pipeline metadata and progress steps
    │   └── videos/                 # Demo videos and visual assets
    │
    ├── static_data/                # 📊 Reference Databases
    │   ├── sebi_registry.json      # Offline snapshot of registered SEBI intermediaries & advisors
    │   └── broker_apk_whitelist.json # Whitelist of legitimate broker package names and domains
    │
    ├── extension/                  # 🧩 Chrome Browser Sentinel Extension (Manifest V3)
    │   ├── manifest.json           # Manifest V3 permissions and endpoints
    │   ├── background.js           # Service worker handling right-click context menus & API requests
    │   ├── content.js              # Content script injecting slide-in scan status toasts
    │   ├── popup.html              # Extension popup HTML
    │   ├── popup.css               # Extension popup styling
    │   ├── popup.js                # Extension popup logic & settings
    │   └── icons/                  # Extension icons (16px, 48px, 128px)
    │
    ├── scripts/                    # 🛠️ Operational, Developer & Benchmark Tooling
    │   ├── self_test.py            # 13-point automated unit & integration regression test suite
    │   ├── e2e_system_test.py      # 7-point live end-to-end API stress test suite
    │   ├── sync_sebi_registry.py   # Standalone daemon and CLI for synchronizing SEBI registry
    │   ├── audit_hardcoded.py      # Static scanner asserting zero hardcoded values outside config
    │   ├── run_folder_test.py      # Batch folder evaluation harness (outputs tests/test_results.csv)
    │   ├── verify_all_models.py    # Isolated model memory and VRAM benchmark
    │   ├── download_models.py      # Pre-download all ML model weights to local HuggingFace cache
    │   └── generate_sample.py      # Generates synthetic multi-modal test media for offline testing
    │
    ├── dataset/                    # Benchmark datasets (e.g. DeepfakeTIMIT)
    ├── test_vid/                   # Benchmark video samples (scam_vid, noscam_vid)
    ├── tests/                      # Test outputs & verification scripts
    │   ├── test_verification.py    # Model pipeline unit verification test
    │   └── test_results.csv        # Stored benchmark results
    └── temp/                       # ⏳ Ephemeral Runtime Scratchpad (Auto-purged per job)
        └── .gitkeep
```

---

## 7. Complete REST API Specifications

### 7.1 Asynchronous Video Pipeline
- **`POST /api/jobs`**: Upload video for full 9-stage analysis.
  - **Form Data**: `file` (Allowed: `.mp4`, `.avi`, `.mov`, `.mkv`, Max: 100MB).
  - **Response (200)**: `{"job_id": "<uuid>", "status": "queued"}`.
- **`GET /api/jobs/{job_id}`**: Poll job progress or retrieve results.
  - **Response (Processing)**: `{"job_id": "<uuid>", "status": "processing", "stage": "stage2_vision"}`.
  - **Response (Completed)**: Full results payload containing `verdict`, `is_deepfake`, `is_scam`, `composite_risk_score`, `vision_score`, `audio_score`, `timeline_track`, `sebi_analysis`, `registry_check`, `scores_complaint`, `heatmap_base64`.
- **`GET /api/jobs/{job_id}/complaint`**: Download formatted SEBI SCORES complaint as plain text.

### 7.2 Synchronous Single-Modal Scanners
- **`POST /api/scan/text`**:
  - **Body**: `{"text": "Guaranteed 40% monthly returns on BankNifty jackpot calls. Join Telegram: t.me/vip"}`
  - **Response**: Full `SEBIAnalysis` breakdown, composite risk score, domain scan, registry check, and SCORES complaint.
- **`POST /api/scan/audio`**:
  - **Form Data**: `file` (`.mp3`, `.wav`, `.ogg`, `.m4a`, `.flac`, `.aac`).
  - **Response**: Speech transcription, Wav2Vec2 synthetic score, segment breakdown, timeline scrubber track, and SEBI analysis.
- **`POST /api/scan/image`**:
  - **Form Data**: `file` (`.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`).
  - **Response**: Vision deepfake score, SRM heatmap, EasyOCR text blocks, domain check, and SEBI analysis.
- **`POST /api/scan/apk`**:
  - **Form Data**: `file` (`.apk`).
  - **Response**: Package typosquatting analysis, dangerous permissions list, risk level, and pre-drafted complaint.
- **`POST /api/scan/url`**:
  - **Body**: `{"url": "https://zerodha-bonus-offer.xyz/login"}`
  - **Response**: Levenshtein distance check against official broker whitelist, phishing status, and explanation.

### 7.3 System & Administration Endpoints
- **`GET /api/health`**: `{"status": "ok", "version": "4.0", "stages": 9, "service": "FinGuard"}`.
- **`GET /api/registry/status`**: Record count, last sync timestamp, breakdown by entity type.
- **`POST /api/admin/sync-registry`**: Triggers background synchronization of `sebi_registry.json`.

---

## 8. Hardware & Memory Management Strategy

Running 4 large neural networks + an 8B LLM on a consumer laptop GPU (**6GB VRAM budget**) requires strict architectural memory controls:

1. **Sequential Execution & Aggressive Garbage Collection**:
   - Models run sequentially. After Stage 2 (vision) completes, its PyTorch weights are cleared before Stage 3 (audio) loads:
     ```python
     del model
     gc.collect()
     torch.cuda.empty_cache()
     ```
2. **CPU/GPU Workload Partitioning**:
   - **Stage 2 (Vision)**: PyTorch on CUDA (peak ~1.8GB VRAM).
   - **Stage 3 (Audio)**: Wav2Vec2 on CUDA (peak ~1.2GB VRAM).
   - **Stage 4 (Transcription)**: `faster-whisper` run on **CPU** with `int8` quantization (`compute_type="int8"`). Zero VRAM consumed.
   - **Stage 5 (LLM)**: Handled by Ollama in an external daemon process with dynamic RAM/VRAM offloading.
3. **Early-Exit Inference**:
   - If the first 4 video frames produce strong deepfake confidence ($> 0.92$), inference halts immediately, reducing GPU runtime by up to 75%.
4. **Zero-Retention Ephemeral Sandboxes**:
   - All uploaded media is stored in `temp/<job_id>/`.
   - Purged unconditionally in `finally:` blocks via `shutil.rmtree(temp_job_dir, ignore_errors=True)`.

---

## 9. Configuration Master File (`config.yaml`)

```yaml
hardware:
  device: "cuda"                  # "cuda" or "cpu"
  force_cpu: false                # Global override forcing CPU for all stages

thresholds:
  vision_fake_threshold: 0.5      # Vision score above this = deepfake
  audio_fake_threshold: 0.5       # Audio score above this = spoofed
  sebi_risk_threshold: 0.7        # Composite risk above this = scam
  audio_segment_flag_threshold: 0.45
  impersonation_audio_threshold: 0.45
  scene_cut_threshold: 35.0       # Frame pixel delta triggering scene cut
  ocr_min_confidence: 0.15
  scam_composite_threshold: 0.35  # Ambiguity threshold for "Suspicious"
  llm_risk_auto_flag_threshold: 0.45
  registry_name_number_match_score: 65
  registry_name_only_match_score: 80
  apk_domain_levenshtein_max_dist: 3

vision:
  early_exit_frame_count: 4
  early_exit_score: 0.92
  consensus_top_weight: 0.65
  consensus_min_frames: 3

audio:
  chunk_duration_seconds: 5.0
  consensus_top_weight: 0.65
  consensus_min_chunks: 2

server:
  max_upload_mb: 100
  preload_models: false

pipeline:
  stage1_ingest:
    max_frames_to_extract: 25
    min_frames_floor: 15
    audio_sample_rate: 16000
    face_detector_model: "MTCNN"
    face_crop_margin_px: 25
  stage2_vision:
    model_id: "AdityaManojShinde/deepfake-detector"
    model_weights_file: "deepfake_detector_phase2.pth"
  stage3_audio:
    model_id: "MelodyMachine/Deepfake-Audio-Detection-V2"
  stage4_transcription:
    model_id: "Systran/faster-whisper-medium"
    compute_type: "int8"
    use_cpu: true
  stage5_llm:
    model_id: "llama3.1:latest"
    api_url: "http://localhost:11434/api/chat"
    timeout_short_sec: 3.5
    timeout_long_sec: 30.0
  stage6_registry:
    source: "static_data/sebi_registry.json"
    refresh_interval_hours: 24
  stage9_apk_domain:
    apk_whitelist: "static_data/broker_apk_whitelist.json"
    dangerous_permissions:
      - "READ_SMS"
      - "RECEIVE_SMS"
      - "READ_CONTACTS"
      - "BIND_ACCESSIBILITY_SERVICE"
      - "PACKAGE_USAGE_STATS"

backup_apis:
  enable_cloud_fallback: false
  sightengine:
    enabled: false
    fake_score_threshold: 0.5
    models: "deepfake,genai"
```

---

## 10. How to Run, Test, and Verify

### 10.1 Environment Setup
```bash
# 1. Create and activate Python virtual environment (Python 3.10 or 3.11)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Pull Ollama model (Optional but recommended for local LLM reasoning)
ollama pull llama3.1:latest
```

### 10.2 Starting the Servers
- **Main Full-Stack Server** (FastAPI backend + UI on port `8000`):
  ```bash
  python app.py
  ```
  Access Dashboard at: `http://localhost:8000`
- **Standalone Frontend Server** (Port `3000`, optional):
  ```bash
  python run_frontend.py
  ```

### 10.3 Verification & Testing Suite (`scripts/`)
- **13-Point Regression & Unit Suite**:
  ```bash
  python scripts/self_test.py
  ```
- **7-Point Live API Stress Test**:
  ```bash
  python scripts/e2e_system_test.py
  ```
- **Static Audit for Hardcoded Values**:
  ```bash
  python scripts/audit_hardcoded.py
  ```
- **Isolated Model VRAM Benchmark**:
  ```bash
  python scripts/verify_all_models.py
  ```
- **Batch Evaluation on Video Directory**:
  ```bash
  python scripts/run_folder_test.py --folder test_vid --out tests/test_results.csv
  ```

---

## 11. Engineering Guidelines for AI Coding Assistants

When contributing, modifying, or refactoring code in this repository, follow these rules:

1. **Thresholds & Configuration Integrity**:
   - **NEVER** hardcode numeric thresholds (scores, weights, URLs, timeouts) in Python files.
   - Always fetch them via `src.config.get_threshold(name, default)` or `src.config.get_stage_config(stage_name)`.
2. **VRAM Safety Invariants**:
   - When introducing or modifying any PyTorch model, ensure `torch.cuda.empty_cache()` and `gc.collect()` are executed upon completion.
   - Do not run heavy models concurrently on GPU.
3. **Temp Directory Sanitation**:
   - All uploaded and extracted files must reside inside `temp/<job_id>/`.
   - Wrap all processing in `try ... finally:` blocks ensuring `shutil.rmtree(temp_job_dir, ignore_errors=True)` is called.
4. **Privacy Shield Enforcement**:
   - Any raw text passed to an LLM or cloud API must pass through `scrub_pii_dpdp()` from `src/stages/stage5_llm.py`.
5. **Frontend Conventions**:
   - The UI is built using **Vanilla HTML, Vanilla CSS, and Vanilla JavaScript**.
   - Do **NOT** install Tailwind, React, Webpack, or heavy node dependencies unless explicitly requested by the user.
   - Adhere to the existing modular HSL design tokens declared in `static/css/core.css`.
6. **Preserve Fallbacks**:
   - Never remove the heuristic fallback in `stage5_llm.py`. The system must function gracefully even when Ollama is offline.
