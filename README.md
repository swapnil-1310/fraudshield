# 🛡️ FraudShield — Multi-Modal AI Deepfake & Financial Fraud Detection

An offline-first, local multi-modal AI forensic platform that analyzes digital media (audio, video, images, text, and Android APKs) to expose two interconnected threats:
1. **Generative Deepfakes & Voice Cloning**: AI face-swapping, facial manipulation, and synthetic voice cloning.
2. **Financial Fraud & SEBI Violations**: Unregistered investment advice, pump-and-dump stock schemes, guaranteed-return promises, pressure tactics, coded Hinglish scam slang, fake broker APKs, and phishing domains.

---

## 🌟 Key Features

- **Acoustic Voice Spoof Detection (Model C)**: Powered by `garystafford/wav2vec2-deepfake-voice-detector` (pinned revision: `c6630602`) evaluating 5-second windowed chunks for synthetic voice artifacts.
- **Visual Deepfake Detection**: High-performance `MS-EffGCViT-B0` architecture (`KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus`) analyzing facial regions extracted via MTCNN.
- **Multilingual Speech Transcription**: Fast local speech-to-text using `faster-whisper-small` (CTranslate2 CUDA float16 with seamless CPU int8 fallback) with phonetic financial normalization (e.g. *"say bee"* → *"SEBI"*, *"eye en ay"* → *"INA"*).
- **Timestamp-Aware Semantic Fraud Reasoning (Ollama)**: Local LLM (`llama3.1:latest`) reasoning over discourse segments to distinguish active scam promotions from legitimate investor awareness and debunking.
- **DPDP Act 2023 Enterprise Data Shield**: Automatic local scrubbing of Indian PAN, Aadhaar, phone numbers, UPI IDs, and bank account numbers before reasoning.
- **Adversarial Hinglish Slang Detection**: Built-in scanner for Indian financial fraud colloquialisms (*"rocket calls"*, *"pakka jackpot"*, *"operator call"*, *"zero-loss setup"*).
- **SEBI Intermediary Registry Cross-Check**: Local offline fuzzy-matching (`rapidfuzz`) against SEBI-registered Investment Advisers and Research Analysts (`static_data/sebi_registry.json`).
- **APK & Domain Threat Scanner**: Static Android manifest analysis (`androguard`) for dangerous permissions alongside Levenshtein distance checks against trusted Indian broker domains.
- **SEBI SCORES Complaint Drafting**: Automated generation of formal regulatory complaint drafts ready for submission to SEBI's SCORES portal.
- **Modern Fintech UI Dashboard**: Lightweight, responsive dark/white fintech dashboard built with Vanilla HTML5/CSS/JavaScript.

---

## 🏗️ System Architecture

```
                       [ Uploaded Media Artifact ]
          (Audio .wav/.mp3 | Video .mp4 | Image | Text | APK | URL)
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Stage 1: Ingest & Preprocessing (MTCNN Face Crop, 16kHz Audio Extract) │
 └───────────────────┬────────────────────────────────┬───────────────────┘
                     │                                │
          ┌──────────┴──────────┐          ┌──────────┴──────────┐
          ▼                     ▼          ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────────────┐
│  Stage 2: Vision  │ │  Stage 3: Audio   │ │   Stage 4: Transcription  │
│    MS-EffGCViT    │ │  Model C Wav2Vec2 │ │  faster-whisper (CUDA/CPU)│
└─────────┬─────────┘ └─────────┬─────────┘ └─────────────┬─────────────┘
          │                     │                         │
          └─────────────────────┼─────────────────────────┘
                                ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Stage 5: Timestamp-Aware SEBI Compliance Reasoning (Ollama LLaMA 3.1)  │
 │  • DPDP Act 2023 PII Masking (PAN, Aadhaar, Phone, UPI)                │
 │  • Hinglish Fraud Slang Detection ("rocket call", "pakka jackpot")     │
 │  • Decoupled Intent: Scam Promotion vs. Awareness Warning              │
 └──────────────────────────────────┬─────────────────────────────────────┘
                                    ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Stage 6: SEBI Intermediary Registry Verification (Offline Fuzzy Match) │
 └──────────────────────────────────┬─────────────────────────────────────┘
                                    ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Stage 7/8/9: OCR Extraction, APK Permission Scan, SCORES Complaint Gen │
 └──────────────────────────────────┬─────────────────────────────────────┘
                                    ▼
       [ Calibrated Regulatory Verdict & Unified Evidence Dashboard ]
```

---

## 📋 Prerequisites

- **Operating System**: Windows 10/11 or Linux
- **Python**: Version `3.11.x`
- **GPU (Recommended)**: NVIDIA GPU with CUDA 11.8 or 12.x (4GB–6GB+ VRAM). The platform automatically falls back to CPU if no GPU is available.
- **Ollama**: Installed and running locally ([Download Ollama](https://ollama.com/)) with the `llama3.1:latest` model pulled.

---

## 🚀 Quick Start Guide

### 1. Clone the Repository

```bash
git clone https://github.com/swapnil-1310/fraudshield.git
cd fraudshield
git checkout running_fraudshield_v1
```

### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (cmd):
.venv\Scripts\activate.bat
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install PyTorch with CUDA support (for CUDA 12.1):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install required packages:
pip install -r requirements.txt
```

*(Note: For CPU-only machines, simply run `pip install torch torchvision torchaudio` followed by `pip install -r requirements.txt`.)*

### 4. Setup Ollama Local LLM

Make sure Ollama is installed and running, then pull the LLaMA 3.1 model:

```bash
ollama serve
ollama pull llama3.1:latest
```

---

## 🖥️ Running FraudShield

### Option A: One-Click Start (Windows)

Simply double-click or run:
```cmd
start.bat
```
This script automatically checks Ollama, starts the FastAPI backend server on port `8000`, launches the frontend dashboard on port `3000`, and opens your default web browser.

To stop both services:
```cmd
stop.bat
```

### Option B: Manual Start (Two Terminals)

**Terminal 1 — Backend API Server:**
```bash
python app.py
```
*Backend runs on `http://localhost:8000` (API documentation available at `http://localhost:8000/docs`).*

**Terminal 2 — Frontend Dashboard:**
```bash
python run_frontend.py
```
*Frontend runs on `http://localhost:3000`.*

Open your browser and navigate to:
```
http://localhost:3000
```

---

## 📡 API Endpoints Reference

| Endpoint | Method | Supported File Types | Description |
|---|---|---|---|
| `/api/scan/audio` | `POST` | `.wav`, `.mp3`, `.m4a`, `.aac`, `.flac` | Model C acoustic deepfake detection + Whisper transcription + Ollama SEBI compliance reasoning. |
| `/api/scan/video` | `POST` | `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm` | Full 9-stage multi-modal analysis (Vision deepfakes, audio cloning, speech, OCR, registry check). |
| `/api/scan/image` | `POST` | `.jpg`, `.jpeg`, `.png`, `.webp` | Vision deepfake detection + EasyOCR text extraction + SEBI compliance scan. |
| `/api/scan/text` | `POST` | JSON payload `{"text": "..."}` | Direct SEBI compliance analysis, DPDP PII scrubbing, and registry cross-check on text. |
| `/api/scan/apk` | `POST` | `.apk` | Static Android manifest permission audit and malicious broker package analysis. |
| `/api/health` | `GET` | — | Health check verifying model backend availability and server readiness. |

---

## ⚙️ Configuration (`config.yaml`)

All model checkpoints, detection thresholds, and timeouts are centrally managed in [`config.yaml`](file:///c:/Users/LOQ/OneDrive/Desktop/fraudshield/fraudshield_v1/config.yaml):

```yaml
audio_detector:
  backend: wav2vec2_garystafford
  github_model_id: garystafford/wav2vec2-deepfake-voice-detector
  github_model_revision: c66306024a7ede0be291e9c4558b37634782dc4

vision_detector:
  backend: ms_eff_gcvit
  model_weights_file: null # Loads pretrained KoreaPeter/ms-eff-gcvit-deepfake-b0-ff-plus-plus
  threshold: 0.60

pipeline:
  stage4_transcription:
    model_id: Systran/faster-whisper-small
    compute_type: float16
    use_cpu: false
  stage5_llm:
    api_url: http://localhost:11434/api/chat
    model_id: llama3.1:latest
    timeout_long_sec: 180.0
    timeout_short_sec: 90.0
```

---

## 🧪 Running Automated Tests

Run the test suite using `pytest`:

```bash
# Run audio backend and verdict logic tests
pytest tests/unit/test_audio_backends.py tests/unit/test_verdict.py -v

# Run full unit test suite
pytest tests/unit/
```

---

## 🔒 Privacy & Compliance

- **Offline-First Execution**: No audio, video, or text data is sent to external cloud APIs by default.
- **DPDP Act 2023 Data Shield**: All personal identifiable information is masked before linguistic processing.
- **Ephemeral Sandbox**: Extracted audio segments and video frames are automatically purged from temporary storage after analysis.
