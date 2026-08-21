# FraudShield-SEBI Pro 🛡️

<div align="center">

<img src="https://img.shields.io/badge/SEBI-Aligned-blue?style=for-the-badge&logo=shield" />
<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/React-Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
<img src="https://img.shields.io/badge/Gemini_1.5_Pro-AI_Engine-4285F4?style=for-the-badge&logo=google&logoColor=white" />
<img src="https://img.shields.io/badge/PyTorch-Deepfake_Vision-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" />

### **AI-Based Investor Fraud & Impersonation Detection Platform**
**Aligned with SEBI (Securities and Exchange Board of India) Investor Protection Mandate**

*Detecting Deepfake Media + Extracting Audio + Evaluating Spoken Claims Against SEBI Guidelines — All in One Pipeline*

</div>

---

## 🎯 Problem Statement

Fraudsters increasingly use **deepfake videos and audio**, exploit **messaging platforms** like WhatsApp and Telegram, **pose as registered financial intermediaries**, or run **fake trading apps** to mislead retail investors with guaranteed-return schemes.

This platform provides a **real-time dual detection system** that:
- Detects whether a video is **AI-generated / Deepfake** using Vision Transformers
- Extracts the **audio from the video** and transcribes the spoken words
- Evaluates the speech against **SEBI regulatory guidelines** using a forensic AI engine
- Returns a **Dual Matrix Verdict** classifying the exact nature of the threat

---

## 🚨 The 4-Zone Dual Verdict Matrix (Core Innovation)

The system evaluates media along **two independent axes**, generating one of four distinct outcomes:

| Zone | Badge | What It Means |
|------|-------|---------------|
| `AI_SEBI_VIOLATION` | 🚨 **HIGH RISK SCAM** | AI deepfake media + SEBI-violating spoken claims (guaranteed returns, fake advisor) |
| `AI_SEBI_COMPLIANT` | 🟦 **AI LEGIT** | AI avatar/voice media but the spoken content is fully SEBI-compliant (educational) |
| `REAL_SEBI_VIOLATION` | 🟧 **SEBI VIOLATION** | Authentic human media with non-compliant stock tips or unregistered advice |
| `REAL_SEBI_COMPLIANT` | 🟩 **SAFE & VERIFIED** | Authentic media adhering to SEBI investor protection standards |

> **Why this matters:** A fraudster can use an AI avatar to deliver *legitimate-sounding* educational content (AI but compliant), OR a *real human* can give illegal unregistered tips (real but violation). The dual matrix catches both cases independently.

---

## ✨ Special Features

### 🔬 3-Layer Forensic SEBI Compliance Engine
- **Layer 1 — Structural Pre-scan:** 34 calibrated regex signals with weighted scoring, covering everything from obvious fraud (`"guaranteed 80% returns"`) to sophisticated scams (`"93% accuracy over 3 years, subscribe to our premium plan"`)
- **Layer 2 — Gemini 1.5 Pro Deep Analysis:** Chain-of-thought forensic prompt with a SEBI Senior Director persona, explicit disambiguation of legitimate vs fraudulent content, and evidence-based reasoning with quoted text
- **Layer 3 — Ensemble Calibration:** Blends AI deep reasoning + structural scan (90/10 for HIGH confidence, 75/25 for MEDIUM, 60/40 for LOW) to prevent single-point failure

### 📹 Dual Video + Audio Pipeline
1. **Visual Frame Sampling:** OpenCV samples every 1.5 seconds of video
2. **Vision ViT Deepfake Classification:** PyTorch + HuggingFace Vision Transformer (`SadraCoding/SDXL-Deepfake-Detector`) classifies each frame
3. **Audio Extraction:** FFmpeg demuxes audio track to 16kHz mono WAV
4. **Speech Transcription:** Gemini Multimodal API transcribes spoken audio to text
5. **SEBI Forensic Analysis:** Full 3-layer engine evaluates transcribed speech
6. **Dual Matrix Scoring:** Combines visual score + audio score into final verdict

### 🧠 Catches What Even Pro Traders Might Miss
The forensic engine is specifically calibrated to catch **sophisticated evasive fraud patterns**:
- `"Our team has 93% accuracy over 3 years"` → Unaudited accuracy claim (SEBI RA Reg 16)
- `"Buy HDFC SL 1600 Target 1750"` without SEBI RA registration → Illegal structured tip
- `"Subscribe for real-time alerts, limited seats!"` → Paid unregistered advisory
- `"Forward this to 10 friends"` → Coordinated pump-and-dump distribution
- Short messages get 20% score amplification (viral forwarded tips are always short)

### 📊 Regulator Live Audit Dashboard
- Real-time flagged reports queue with dual-score breakdown
- KPI cards: Total Scans, Deepfakes Detected, SEBI Violations, High-Risk Scams
- One-click scheme tag labels (Pump & Dump, Ponzi, Insider Tip, Paid Group)
- AI Confidence badge (HIGH / MEDIUM / LOW)
- Full SEBI regulation citations with act, regulation, and sub-clause
- Transcript inspector showing exact spoken text with highlighted violation markers

### 🏛️ SEBI Advisor Verification Portal
- Cross-check Registration IDs (RA/RIA/Broker) against official SEBI database
- Instant status display: VALID / SUSPENDED / EXPIRED / UNREGISTERED
- Auto-bumps risk score when claimed Reg No. doesn't match valid format or database

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INVESTOR / REGULATOR                                  │
│              React + Vite + TailwindCSS UI  (Port 3000)                │
│   ┌─────────────┬──────────────────────┬──────────────────────────┐    │
│   │Dual Scanner │ Regulator Dashboard  │ SEBI Advisor Verifier    │    │
│   │(Upload MP4/ │ (Live Audit Feed     │ (RA/RIA/Broker Reg No.   │    │
│   │ text tip)   │  KPI Cards, Reports) │  database lookup)        │    │
│   └──────┬──────┴───────────┬──────────┴──────────────────────────┘    │
└──────────┼──────────────────┼──────────────────────────────────────────┘
           │  HTTP REST API   │
           ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 FastAPI Python AI Engine  (Port 8000)                   │
│                                                                         │
│  POST /api/scan-video          POST /api/scan-text                      │
│  GET  /api/verify-advisor/:id  GET  /api/flags                         │
│  GET  /api/stats               DELETE /api/flags/:id                   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                   CORE AI ENGINE                                  │   │
│  │                                                                   │   │
│  │  deepfake_vision.py         audio_extractor.py                   │   │
│  │  ┌─────────────────┐       ┌──────────────────┐                 │   │
│  │  │ OpenCV Frame    │       │ FFmpeg Audio      │                 │   │
│  │  │ Sampling (1.5s) │       │ Extraction (WAV)  │                 │   │
│  │  │ HuggingFace ViT │       └────────┬─────────┘                 │   │
│  │  │ Deepfake Model  │                │                            │   │
│  │  └────────┬────────┘       transcriber.py                       │   │
│  │           │               ┌──────────────────┐                  │   │
│  │   Visual Score            │ Gemini Multimodal │                  │   │
│  │   (0.0 - 1.0)             │ Speech-to-Text   │                  │   │
│  │           │               └────────┬─────────┘                  │   │
│  │           │                        │                             │   │
│  │           │               sebi_compliance.py                    │   │
│  │           │               ┌─────────────────────────────┐       │   │
│  │           │               │ Layer 1: 34-Signal Regex Scan│       │   │
│  │           │               │ Layer 2: Gemini 1.5 Pro      │       │   │
│  │           │               │          Chain-of-Thought    │       │   │
│  │           │               │ Layer 3: Ensemble Calibration│       │   │
│  │           │               └────────────┬────────────────┘       │   │
│  │           │                            │ SEBI Risk Score         │   │
│  │           ▼                            ▼ (0.0 - 1.0)            │   │
│  │   ┌──────────────────────────────────────────┐                  │   │
│  │   │         DUAL MATRIX VERDICT ENGINE       │                  │   │
│  │   │  is_deepfake × is_violation → 4-Zone     │                  │   │
│  │   └──────────────────────────────────────────┘                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  db/database.py (SQLite)       db/sebi_advisors.json                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 18 + Vite + TailwindCSS | Modern glassmorphism UI with dark mode |
| **UI Components** | Lucide React icons | Consistent icon system |
| **Backend** | Python 3.11+ + FastAPI + Uvicorn | High-performance async API |
| **Video Processing** | OpenCV (`cv2`) | Frame sampling, image decoding |
| **Deepfake Detection** | PyTorch + HuggingFace Transformers | Vision ViT model for AI-generated image classification |
| **Audio Extraction** | FFmpeg subprocess | Demux audio track from video |
| **Speech-to-Text** | Gemini 1.5 Flash Multimodal API | Audio file transcription |
| **SEBI Compliance AI** | Gemini 1.5 Pro (Chain-of-Thought) | Forensic regulatory analysis |
| **Structural Analysis** | Python `re` module (34 weighted signals) | Rule-based pre-scan layer |
| **Database** | SQLite (via `sqlite3`) | Audit reports, flags, scan history |
| **Advisor Database** | JSON seeded SQLite | SEBI RA/IA/Broker registration records |

---

## 📁 Project Structure

```
FraudShield-SEBI-Pro/
│
├── backend/                              # Python FastAPI AI Engine
│   ├── api/
│   │   └── main.py                       # FastAPI app: routes, models, endpoints
│   ├── core/
│   │   ├── deepfake_vision.py            # PyTorch ViT visual deepfake detector
│   │   ├── audio_extractor.py            # FFmpeg audio track extraction
│   │   ├── transcriber.py               # Gemini Multimodal speech-to-text
│   │   └── sebi_compliance.py           # 3-layer forensic SEBI engine
│   ├── db/
│   │   ├── database.py                  # SQLite manager: reports, advisors, stats
│   │   └── sebi_advisors.json           # SEBI registered advisor seed data
│   ├── storage/
│   │   └── temp/                        # Temporary file processing area
│   └── config.py                        # Thresholds, paths, API key config
│
├── frontend/                            # React + Vite Frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx               # Navigation bar & status badge
│   │   │   ├── KPICards.jsx             # Live metric dashboard cards
│   │   │   ├── MediaUploadModal.jsx     # Video/text dropzone & progress steps
│   │   │   ├── DualVerdictCard.jsx      # Dual matrix result card with full breakdown
│   │   │   ├── RegulatorLiveFeed.jsx    # Regulator audit queue feed
│   │   │   └── AdvisorVerifier.jsx      # SEBI Reg No. verification portal
│   │   ├── App.jsx                      # Main app shell (tab routing, state)
│   │   ├── main.jsx                     # React entry point
│   │   └── index.css                    # Global styles + glassmorphism utilities
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── start_fraudshield.bat                # One-click Windows launcher
├── test_accuracy.py                     # Forensic engine accuracy test suite
└── README.md                            # This file
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** and npm
- **ffmpeg** (optional, for audio extraction from real video)
- **Google Gemini API Key** (free at [aistudio.google.com](https://aistudio.google.com))

### 1. Clone the Repository

```bash
git clone https://github.com/swapnil-1310/fraudshield.git
cd fraudshield
```

### 2. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install fastapi uvicorn python-multipart numpy google-generativeai opencv-python Pillow google-genai

# Optional: Install for full deepfake model (requires ~2GB download)
# pip install torch transformers deepface retinaface-pytorch faiss-cpu

# Set your Gemini API Key
# Windows:
set GEMINI_API_KEY=your_gemini_api_key_here

# Linux/Mac:
# export GEMINI_API_KEY=your_gemini_api_key_here

# Start backend
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

### 4. One-Click Launch (Windows)

```bash
# From project root, double-click or run:
start_fraudshield.bat
```

### 5. Access the Platform

| Service | URL |
|---------|-----|
| **Frontend Dashboard** | http://localhost:3000 |
| **Backend API** | http://127.0.0.1:8000 |
| **API Swagger Docs** | http://127.0.0.1:8000/docs |

---

## 🔌 API Reference

### `POST /api/scan-video`
Upload a video file for full dual pipeline analysis.

**Form fields:**
| Field | Type | Required |
|-------|------|----------|
| `file` | Video file (MP4/MOV/WEBM) | ✅ |
| `advisor_reg_no` | string | Optional |

**Response:**
```json
{
  "id": "FLAG-A1B2C3D4",
  "dual_verdict": "AI_SEBI_VIOLATION",
  "verdict_label": "HIGH RISK SCAM (AI Deepfake + SEBI Violation)",
  "is_deepfake": true,
  "deepfake_score": 0.82,
  "visual_summary": "AI Manipulated / Deepfake Video Detected (Confidence: 82%)",
  "is_sebi_violation": true,
  "sebi_risk_score": 0.91,
  "sebi_summary": "Guaranteed return promises detected in transcribed audio",
  "transcript": "Invest now! Guaranteed 80% returns in 10 days...",
  "reasons": ["Explicit guaranteed return promise — core SEBI fraud indicator"],
  "sebi_rules": ["SEBI (Investment Advisers) Regulations 2013 — Reg 7A"],
  "detected_schemes": ["pump_dump", "paid_group"],
  "confidence": "HIGH"
}
```

---

### `POST /api/scan-text`
Analyze a text tip, social media post, or WhatsApp forward.

**Request body (JSON):**
```json
{
  "text": "Buy ZOMATO NOW! Target 240. Our team has 93% accuracy. Join premium Telegram. Limited seats!",
  "advisor_reg_no": "FAKE123"
}
```

---

### `GET /api/verify-advisor/{reg_no}`
Verify a SEBI Registration Number.

```bash
GET /api/verify-advisor/INH000005678
```

---

### `GET /api/flags`
Retrieve all flagged scan reports for the Regulator Dashboard.

### `GET /api/stats`
Get KPI metrics: total scans, deepfakes, SEBI violations, high-risk scams.

### `DELETE /api/flags/{id}`
Dismiss a flagged report.

---

## 🧪 Accuracy Test Suite

Run the included test suite to validate the forensic engine:

```bash
cd backend
python -c "
import sys; sys.path.insert(0, '.')
from core.sebi_compliance import _run_forensic_scan

tests = [
    ('CLEAR FRAUD',    'Reliance guaranteed 80% returns! No risk. Join VIP Telegram. Pay after profit!'),
    ('LEGIT ANALYSIS', 'Infosys Q3 strong results. Past performance is not a guarantee. Consult a SEBI registered advisor.'),
    ('SUBTLE SCAM',    'Our team has 93% accuracy over 3 years. Subscribe to premium plan. Limited seats!'),
    ('STRUCTURED TIP', 'Buy HDFC SL 1600 Target 1750. Join paid Telegram for intraday tips. Rs 5000/3months.'),
    ('BORDERLINE',     'Nifty looks bullish. Expecting 200 point move. Watch 17500 level closely.'),
]
for label, msg in tests:
    score, r, _ = _run_forensic_scan(msg)
    verdict = 'VIOLATION' if score >= 0.6 else ('WATCH' if score >= 0.35 else 'SAFE')
    print(f'[{label}] {verdict} ({score:.2f})')
"
```

**Expected output:**
```
[CLEAR FRAUD]    VIOLATION (1.00)   ✅
[LEGIT ANALYSIS] SAFE (0.00)        ✅
[SUBTLE SCAM]    VIOLATION (0.65)   ✅
[STRUCTURED TIP] VIOLATION (0.90)   ✅
[BORDERLINE]     SAFE (0.00)        ✅
```

---

## 🔐 Environment Variables

Create a `.env` file in `backend/` (or set system env variables):

```env
# Required for Gemini AI analysis (get free at aistudio.google.com)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Detection thresholds (defaults shown)
# DEEPFAKE_THRESHOLD=0.55    # 55%+ → AI deepfake
# SEBI_RISK_THRESHOLD=0.60   # 60%+ → SEBI violation
```

> ⚠️ **Never commit your API key.** The `.gitignore` excludes `.env` files.

---

## 🛡️ SEBI Regulations Referenced

The forensic engine cites specific acts and sub-clauses:

| Regulation | Coverage |
|-----------|----------|
| SEBI (Investment Advisers) Regulations 2013 — Reg 7A | Guaranteed return prohibition |
| SEBI (Investment Advisers) Regulations 2013 — Reg 13(d) | Fee structure rules |
| SEBI (Research Analysts) Regulations 2014 — Reg 3 | RA registration requirement |
| SEBI (Research Analysts) Regulations 2014 — Reg 16 | Disclosure obligations |
| SEBI (Research Analysts) Regulations 2014 — Reg 23 | Required disclaimers |
| SEBI (Prohibition of Fraudulent and Unfair Trade Practices) Regulations 2003 — Reg 3 & 4 | Fraud prohibition |
| SEBI (Prohibition of Insider Trading) Regulations 2015 — Reg 3 | Insider trading prohibition |
| SEBI Circular SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2023/123 | Social media advisory rules |
| SEBI (Collective Investment Schemes) Regulations 1999 | Ponzi/fixed return schemes |

---

## 🤝 Acknowledgements & References

This project was built by combining and extending code from:

| Repository | Contribution |
|-----------|-------------|
| [**Swaraksha**](https://github.com/Swaraksha) | Visual deepfake detection pipeline (PyTorch ViT, OpenCV frame sampling, DeepFace, FAISS identity matching) |
| [**fraudshield-sebi**](https://github.com/rshashank20/fraudshield-sebi) | Gemini AI prompt structure, regulator dashboard UI components, Next.js architecture reference |
| [**Satyashield**](https://github.com/kishanpatelp1/Satyashield) | Multi-modal architecture design, SEBI integration patterns, API gateway reference |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**FraudShield-SEBI Pro** • Built for SEBI's AI-Based Investor Fraud & Impersonation Detection Challenge  
*Protecting Indian retail investors from deepfake scams, fake advisors, and fraudulent trading platforms*

</div>
