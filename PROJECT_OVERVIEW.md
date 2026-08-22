# FraudShield SEBI Pro — Complete Project Overview

Welcome to **FraudShield SEBI Pro**, an advanced AI-powered compliance and fraud detection platform. This document contains all the A-to-Z technical details, architecture, and setup instructions you need to understand, run, and present this project.

---

## 1. Project Summary
FraudShield SEBI Pro is a dual visual & audio SEBI compliance platform designed to detect financial fraud, "pump and dump" schemes, fake trading apps, and unregistered financial advisory. It uses a premium, institutional White + Emerald Green fintech aesthetic to build trust.

### Core Capabilities:
- **Text & Audio Forensic Scan:** Analyzes transcripts and chat messages for guaranteed returns, fake accuracy stats, or unregistered advice.
- **Deepfake Video Detection:** Scans video frames for AI watermarks, synthetic face artifacts, and deepfake generation patterns.
- **Trading App Screenshot Scanner:** Analyzes screenshots to detect spoofed domain names, fake UI elements, and scam broker apps.
- **Advisor Verifier:** Checks SEBI Registration numbers against a local database.

---

## 2. Technology Stack

### Frontend (User Interface)
- **Framework:** React.js powered by Vite (Fast HMR and minimal bundle sizes).
- **Styling:** Tailwind CSS with custom variables for the "Premium White Fintech Theme".
- **Icons:** `lucide-react` for clean, modern SVG iconography.
- **Components:** Modular structure (`DualVerdictCard`, `MediaUploadModal`, `RegulatorLiveFeed`).

### Backend (API & AI Processing)
- **Framework:** FastAPI (Python) for ultra-fast, asynchronous API endpoints.
- **Server:** Uvicorn (ASGI web server).
- **Database:** SQLite (local DB) for storing scan history and stats.
- **Video/Image Processing:** `OpenCV` (cv2), `Pillow` (PIL).
- **Audio Extraction:** `moviepy`, `imageio-ffmpeg`.

### AI Models & APIs
- **Gemini (Google AI):** Uses **`gemini-3.6-flash`** for multimodal vision analysis (screenshots & deepfake frames) and deep chain-of-thought forensic text compliance.
- **Groq Whisper:** Ultra-fast audio transcription from videos using Groq's hardware-accelerated Whisper model.
- **Hugging Face Inference:** Uses the `SadraCoding/SDXL-Deepfake-Detector` ViT model as a secondary deepfake heuristic layer.

### Browser Extension (Real-time Scanning)
- **Tech:** Vanilla JavaScript, HTML, CSS.
- **Functionality:** Injects into WhatsApp Web and Telegram Web to flag suspicious financial messages in real-time.

---

## 3. Project Architecture

```text
FraudShield-SEBI-Pro/
│
├── backend/                  # FastAPI Server
│   ├── api/                  # API Endpoints (main.py)
│   ├── core/                 # AI Logic Engine
│   │   ├── deepfake_vision.py      # Frame extraction & Gemini Vision deepfake detection
│   │   ├── screenshot_scanner.py   # Gemini Multimodal screenshot analysis
│   │   ├── sebi_compliance.py      # LLM Forensic Rule Engine (Gemini)
│   │   └── transcriber.py          # Audio extraction & Groq Whisper integration
│   ├── db/                   # SQLite Database & JSON records
│   ├── storage/              # Temporary file uploads (videos/images)
│   ├── config.py             # Environment variables and API keys
│   └── requirements.txt      # Python dependencies
│
├── frontend/                 # React UI
│   ├── src/
│   │   ├── components/       # UI Components (Navbar, Modals, Cards)
│   │   ├── index.css         # Global styles & Tailwind directives
│   │   ├── App.jsx           # Main Application Layout
│   │   └── main.jsx          # React DOM entry
│   ├── tailwind.config.js    # Theme settings (Fintech Green/White)
│   └── package.json          # Node dependencies
│
├── extension/                # Chrome Extension for WhatsApp/Telegram
│   ├── manifest.json         # Extension config
│   ├── background.js         # Service worker
│   ├── content.js            # DOM interaction & DOM observing
│   └── styles.css            # Extension UI injection styles
│
└── PROJECT_OVERVIEW.md       # This file
```

---

## 4. The Core Engine (AI Pipeline)
The "Core Engine" is the sophisticated AI pipeline located in the `backend/core/` directory. It uses a **local GPU-first architecture** running on RTX 3050 (4GB VRAM) with FP16 precision. API calls to Gemini/Groq serve as optional enhancements, not dependencies. All prompts are centralized in `backend/core/prompts.py`.

### Pillar 1: SEBI Compliance Rule Engine (`sebi_compliance.py`)
This is the brain behind the text and audio transcript analysis, using a **4-layer approach**:
- **Layer 1 (Structural Pre-scan):** 28+ calibrated regex signals across 4 tiers to detect "Pump and Dump" signals, guaranteed returns, insider trading references, spoofing, and missing disclaimers. Compliant disclaimers actually *reduce* the risk score.
- **Layer 1.5 (TF-IDF Keyword Density Scorer):** Catches rephrased scam language that exact regex misses by computing cosine similarity against known scam archetypes from real SEBI enforcement orders.
- **Layer 2 (Gemini Forensic Analysis — Optional):** Passes text to **Gemini 3.6 Flash** using a highly customized prompt persona ("Dr. Ananya Sharma, SEBI Director"). This performs Deep Chain-of-Thought reasoning to catch subtle psychological manipulation.
- **Layer 3 (Ensemble Calibration):** Mathematically blends the offline score (regex + TF-IDF) and Gemini's confidence score to output the final SEBI violation verdict.

### Pillar 2: Deepfake Vision Engine (`deepfake_vision.py`)
This handles the video frame analysis using a **3-layer approach** with **local GPU model as primary**:
- **Layer 1 (Watermark Scanner):** Scans frame corners for known AI generator branding (Synthesia, HeyGen, Sora, etc.).
- **Layer 2 (Local GPU ViT Model — PRIMARY):** Runs the `SadraCoding/SDXL-Deepfake-Detector` Vision Transformer locally on RTX 3050 with FP16 precision (~350MB VRAM). Fine-tuned on 140K+ real/fake images.
- **Layer 3 (Gemini Vision Multimodal — Optional):** Sends keyframes to Gemini Vision to look for synthetic face artifacts and watermark text.
- **Fallback (OpenCV Heuristic):** Texture, edge, symmetry, and noise analysis when no ML model is available.

### Pillar 3: Screenshot Forensic Scanner (`screenshot_scanner.py`)
- **Primary:** EasyOCR (GPU-accelerated) extracts text + Image-level heuristics (compression artifacts, edge density, color palette analysis) + SEBI Rule Engine.
- **Enhancement:** Gemini Vision Multimodal analysis (optional). Results are ensembled when both are available.

### Pillar 4: Audio Transcriber (`transcriber.py`)
- **Primary:** Local `faster-whisper` medium model (769M params) running on GPU with FP16. Uses VAD (Voice Activity Detection) to reduce hallucinations.
- **Fallback:** Groq Whisper API for cloud-accelerated transcription when local model is unavailable.

### Pillar 5: Centralized Prompts Registry (`prompts.py`)
- All 7 system prompts and model descriptions in a single file.
- Exposed via `GET /api/prompts` endpoint and displayed in the frontend "AI Prompts" page.

---

## 5. How to Setup and Run the Project

You need to run **both** the Backend and the Frontend simultaneously in two different terminal windows.

### Step 1: Start the Backend (API Server)
1. Open a terminal and navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Install the required Python packages (if you haven't already):
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your API Keys inside `backend/config.py`:
   - `GEMINI_API_KEY`: For Gemini 3.6 Flash text and vision analysis.
   - `GROQ_API_KEY`: For Whisper audio transcription.
   - `HUGGINGFACE_API_KEY`: For HuggingFace deepfake ViT models.
4. Start the server:
   ```bash
   python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *(The API will be available at `http://127.0.0.1:8000`)*

### Step 2: Start the Frontend (React App)
1. Open a **new** terminal tab and navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install the Node.js packages (only needed once):
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *(The Website will be available at `http://localhost:3000` or `http://localhost:5173`)*

### Step 3: Install the Browser Extension (Optional)
1. Open Google Chrome and go to `chrome://extensions/`.
2. Turn on **Developer Mode** (toggle in the top right corner).
3. Click **"Load unpacked"**.
4. Select the `extension/` folder located inside the `FraudShield-SEBI-Pro` project directory.
5. The extension will now automatically monitor WhatsApp Web and Telegram Web tabs.

---

## 5. Key Points for Hackathon/Presentation
- **Why White & Green?** Most cybersecurity platforms use "hacker dark mode" which scares away standard retail investors. FraudShield uses a clean, institutional, banking-grade aesthetic to build trust.
- **Why Gemini?** Gemini Flash is used for its superior multimodal capabilities (analyzing screenshots of fake brokers and detecting artifacts in deepfake video frames) combined with a massive context window.
- **How Deepfake Detection Works:** It's a multi-layered approach. First, it extracts audio and transcribes it (Groq Whisper). Then it extracts video frames. It checks frames for physical AI watermarks, runs OpenCV heuristics (edge detection), and finally sends key frames to Gemini Vision to detect subtle synthetic facial artifacts (robotic lip sync, unnatural skin smoothing).
- **Extensibility:** The platform is designed so that the exact same API powering the website also powers the Chrome Extension for real-time protection.
