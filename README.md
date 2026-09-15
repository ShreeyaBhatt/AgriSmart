<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:4C7A3D,100:E3A857&height=180&section=header&text=AgriSmart%20AI&fontSize=48&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Intelligent%20Agriculture%20for%20a%20Sustainable%20Future&descAlignY=58&descSize=18" alt="AgriSmart AI banner" width="100%"/>
</p>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com/?lines=Leaf-disease+detection+with+Grad-CAM+explainability;GPS-based+soil+analysis+%26+crop+recommendations;Rule-based+weather+advisory+engine;Gemini-powered+multilingual+farm+assistant&font=Fira+Code&center=true&width=650&height=45&color=5C8A3F&vCenter=true&size=20&pause=1500" alt="Typing SVG"/>
</p>

<p align="left">
<img alt="React" src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB"/>
<img alt="Vite" src="https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white"/>
<img alt="Tailwind CSS" src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white"/>
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white"/>
<img alt="Python" src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white"/>
<img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white"/>
<img alt="MongoDB" src="https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white"/>
<img alt="SQLite" src="https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white"/>
<img alt="scikit-learn" src="https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white"/>
</p>

*Runs entirely on your own machine — no deployment required. See [Getting Started](#getting-started) below.*

AgriSmart AI is a full-stack smart-agriculture application built for **SIH 2026** (L. J. Institute of Engineering & Technology, Problem Statement 1 / C-433). It gives a farmer a single, role-free login that remembers their fields and answers the questions that matter day to day: what's wrong with this leaf, what does my soil need, what should today's weather change about my plan, and — for anything else — a grounded assistant to ask in their own language.

---

### Quick Links (Submission Contract — Section 7)
- 🎥 **Demo Video (3–5 min)**: https://drive.google.com/drive/folders/1vK7i15-6G1r529hgeQ6ysduutTO0hW6h?usp=drive_link
- 📋 **One-Page Model Report**: [`report/model_report.md`](report/model_report.md)
- ⚡ **Fast Evaluator Check**: `python model/predict.py --image data/samples/leaves/Tomato___Early_blight.jpg`
- 🧪 **Test Suite**: `pytest -q` (121 / 121 tests passing)

---

## Problem Statement 1 (SIH 2026) — Implemented Modules Matrix

| Module | PS-1 Category | Status | Implementation Highlights |
|---|---|---|---|
| **Crop Disease Detection** | **Mandatory Core Task** | ✅ **Built** | EfficientNet-B0 (transfer learning), 18 crop disease classes, 4-view Test-Time Augmentation (TTA), temperature scaling, confidence abstention ($\tau=0.40$), Grad-CAM visual explanation heatmaps, organic & chemical precautionary guidance. Verified via CLI `predict.py` and Web UI. |
| **Crop Recommendation** | Bonus Module A | ✅ **Built** | Multi-variable agronomic fit engine utilizing SoilGrids 2.0 (texture, pH, SOC) + Soil Health Card (district NPK) + seasonal crop requirements. |
| **Smart Irrigation** | Bonus Module B | ✅ **Built** | Weather-forecast-driven irrigation timing rules, evapotranspiration reduction (dawn/dusk watering), and soil moisture deficit prevention. |
| **Weather-Based Intelligence** | Bonus Module C | ✅ **Built** | Open-Meteo 3-day forecast integration with deterministic rule engine; triggers actionable fungal risk alerts, spray delay on high winds, and frost/heat stress warnings. |
| **Sustainability Score** | Bonus Module D | ✅ **Built** | Transparent, reproducible 0–100 formula published in `docs/sustainability.md`; evaluates water efficiency, chemical usage, and crop health with actionable improvement tips. |
| **Farmer Assistant (GenAI)** | Bonus Module E | ✅ **Built** | Conversational voice and text assistant grounded in disease cards and farm plots; dual-engine (Gemini 1.5 Flash + offline local RAG), on-premise speech recognition (faster-whisper) in 7 Indian languages (EN, HI, GU, MR, TA, TE, PA). |
| **Autonomous Agentic Advisor** | Bonus Module G | ✅ **Built** | Proactive ReAct decision loop evaluating multi-stream conflicts across soil, crop stage, active disease diagnosis, and 3-day weather; surfaces inspectable live **Decision Trace** (observations, conflicts, rules, action plan). |
| *IoT Integration* | *Bonus Module F* | ➖ *Excluded* | Intentionally omitted from scope to prioritize software robustness, edge AI, and verified agronomic decision intelligence. |

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:4C7A3D,100:E3A857&height=3&width=100%25" alt="divider"/>

## Fast Evaluator Reproducibility Check (< 10 Seconds)

Per **Section 4.1 & 7.2 of the Hackathon Submission Contract**, the trained weights are committed and the prediction interface runs immediately without training:

```bash
# 1. Run the core prediction interface on a sample leaf image:
python model/predict.py --image data/samples/leaves/Tomato___Early_blight.jpg
# Output: Tomato___Early_blight

# 2. Run the complete automated test suite (121 tests):
pytest -q
# Output: 121 passed in ~24s
```

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:4C7A3D,100:E3A857&height=3&width=100%25" alt="divider"/>

## Architecture

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 6, Tailwind CSS v4, react-router-dom, react-leaflet |
| Backend | FastAPI, JWT auth |
| Farm-Data Store | SQLite (SQLAlchemy 2, async) |
| Accounts Store | MongoDB (Motor, async) |
| Machine Learning | PyTorch, timm (EfficientNet-B0), torchvision, pytorch-grad-cam, scikit-learn |
| Soil Intelligence | SoilGrids 2.0 (ISRIC), Soil Health Card, Nominatim |
| Weather Intelligence | Open-Meteo forecast → rule engine |
| Conversational AI | Google Gemini API (optional; offline fallback included) |

**Design notes:**
- FastAPI is the single point of contact for the client. All routes live under `/api`; the SPA keeps bare paths like `/weather` and `/soil` for its own routing, and Grad-CAM overlays/uploads are served from `/uploads`.
- The disease classifier never returns a confident wrong answer by default — low-confidence predictions are deliberately abstained on rather than forced to a label.
- Accounts and farm data are split across two databases on purpose: MongoDB satisfies the original plan and stays inspectable in Compass, while SQLite keeps the farm-data side of the app runnable on any machine with zero infrastructure. Tests never touch a real MongoDB server — an in-memory `mongomock-motor` client stands in.

## Project Structure

```
AgriSmart-AI/
├── app/backend/     FastAPI: auth, db (SQLite), mongo (accounts), models/, routers/, services/
├── app/frontend/    React SPA: pages/, components/, auth/, i18n/, lib/
├── model/           download_data · dataset · net · train · predict · evaluate · gradcam · infer
├── data/            disease_cards.json · crop_suitability.json · soil_amendments.json · samples/
├── docs/            soil_sources · weather_rules · sustainability
├── report/          model_report.md (generated)
└── tests/           121 tests (pytest)
```

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:4C7A3D,100:E3A857&height=3&width=100%25" alt="divider"/>

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB (local instance, or `docker run -p 27017:27017 mongo`) — needed for accounts, not for the test suite

### 1. Run with Docker (Fastest — Zero Setup)

Anyone can immediately run the application with a single command:

```bash
# Option A: Standalone Docker (Runs app + in-memory store on port 8000)
docker run -p 8000:8000 ghcr.io/shreeyabhatt/agrismart:latest

# Option B: Full Stack with persistent MongoDB via Docker Compose
docker compose up -d
```

Visit `http://localhost:8000` to access the full UI and API documentation at `http://localhost:8000/docs`.

### 2. Manual Local Setup

#### Backend (FastAPI)

```bash
cd .
pip install -r requirements.txt
python -m uvicorn app.backend.main:app --reload   # http://127.0.0.1:8000/docs
```

First run creates `agrismart.db` (SQLite) and an `uploads/` folder — no extra setup required. The disease model ships already trained in `model/artifacts/`, so `/predict` works immediately.

#### Frontend (React Dev Server)

```bash
cd app/frontend
npm install
npm run dev   # http://localhost:5173 — proxies /api and /uploads to :8000
```

Start the backend first; Vite's dev proxy forwards API calls, so no CORS setup is needed locally.

### 3. (Optional) Enable the live Gemini assistant

Without a key, the farm assistant still answers from the offline disease-card knowledge base.

```bash
# 1. Get a free key: https://aistudio.google.com/apikey
# 2. Copy .env.example to .env in the repo root
# 3. Set in .env:
AGRISMART_GEMINI_API_KEY=<your key>
AGRISMART_GEMINI_MODEL=gemini-1.5-flash   # optional, this is the default
# 4. Restart the backend
```

### 4. (Optional) Retrain the disease classifier

Only needed to reproduce or redo training — trained weights are already committed.

```bash
python model/download_data.py --out data/plantvillage --per-class 160
python model/train.py --data-dir data/plantvillage --epochs 4
python model/evaluate.py --dir data/plantvillage --out report/model_report.md
```

## Testing

```bash
# Backend — pytest, 121 tests covering soil, auth, plots, predict, and modules A/B/C/D/E/G.
# MongoDB calls are swapped for an in-memory mongomock-motor client, so no real
# database is required to run the suite.
pytest -q

# Frontend — type/build check (Node 18+)
cd app/frontend && npm run build    # or npm.cmd run build on Windows PowerShell
```

## Configuration

Copy `.env.example` to `.env` in the repo root and populate the values you need — every setting has a working default.

| File | Key Variables |
|---|---|
| `.env` (backend) | `JWT_SECRET`, `AGRISMART_GEMINI_API_KEY`, `AGRISMART_GEMINI_MODEL`, `MONGO_URI` |

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:4C7A3D,100:E3A857&height=3&width=100%25" alt="divider"/>

## Account Types

| Type | Scope |
|---|---|
| **Registered Farmer** | Signs in with phone + OTP. Plots, scans, and activity logs are saved to their account and persist across sessions. |
| **Guest** | Explores the app — scan a leaf, check weather advice, ask the assistant — without creating an account. Plots, scans, and logs are saved just like a registered farmer's, but reachable only through the login token held in that browser; clearing site data or switching devices loses access to them. Adding a phone number from Settings at any time attaches that same data to a proper phone-verified account instead of losing it. |

There are no admin or multi-user family roles in this build; each farmer's data is private to their own account.

## Core Features & Bonus Modules

- **Crop-Disease Detection (Mandatory Core Task)** — a photo of a leaf returns a disease label across 18 classes, a Grad-CAM overlay showing where the model focused, and an explicit "not confident" result when the prediction falls below threshold ($\tau=0.40$), rather than a forced guess.
- **Soil-Aware Crop Recommendation (Bonus Module A)** — a plot's GPS coordinates are resolved against SoilGrids 2.0 and the Soil Health Card to get real texture, pH, and N-P-K values, which then drive crop-fit and amendment suggestions.
- **Smart Irrigation Timing (Bonus Module B)** — weather-forecast-driven irrigation timing rules, evapotranspiration reduction (dawn/dusk watering), and soil moisture deficit prevention.
- **Weather Advisory (Bonus Module C)** — a 3-day Open-Meteo forecast is passed through a rule engine that turns raw weather data into a specific action for the farmer, from irrigation timing to wind/rain warnings to proactive "good weather window" tips.
- **Sustainability Scoring (Bonus Module D)** — each plot is scored against a published, reproducible formula (0–100), with concrete tips attached to raise the score.
- **Farm Assistant (Bonus Module E)** — a grounded RAG pipeline over a disease-card knowledge base plus the farmer's own plot data, answering in English, Hindi, Gujarati, Marathi, Tamil, Telugu, or Punjabi, with voice input and output. Runs on Gemini when a key is configured, or fully offline otherwise. Voice input is transcribed locally by this backend (faster-whisper) rather than a cloud speech API, so it keeps working with no internet beyond reaching your own server.
- **Autonomous Agentic Advisor (Bonus Module G)** — a proactive ReAct reasoning engine continuously evaluating multi-stream data (soil snapshot, active crop growth stage, recent leaf scan diagnoses, and 3-day weather forecast). It resolves agronomic conflicts (e.g., rain forecasted during active fungal blight → delays irrigation while scheduling rain-fast fungicide application before downpour; high wind → halts spraying to prevent spray drift). The UI provides an inspectable **Decision Trace** showing observations, conflicts detected, rules applied, and execution time in milliseconds.
- **Multilingual, Theme-Aware UI** — navigation, weather advice, sustainability tips, disease/diagnosis labels, and the plot activity timeline all work across all 7 supported languages, with a language switcher and light/dark theme toggle available from the login screen and Settings.
- **Guest → Registered, No Data Loss** — a guest isn't stuck choosing between trying the app and keeping their data: adding a phone number from Settings at any point attaches it to their *existing* account in place, so every plot, scan, and log they already have stays exactly where it was.

## Disease Coverage & Verified Metrics

The classifier is trained on an 18-class subset of PlantVillage, spanning multiple crops including tomato, potato, corn, apple, grape, and bell pepper, with both healthy and diseased leaf classes per crop.

For evaluation, results are reported at two levels: **per-class** precision/recall (see [`report/model_report.md`](report/model_report.md)) and **aggregate** macro-F1/accuracy across the held-out validation split.

| Metric | Score | Baseline Reference | Status |
|---|---|---|---|
| **Macro-F1 (Held-out validation)** | **0.992** | 0.840 | **+15.2% above baseline** |
| **Accuracy (Held-out validation)** | **0.992** | 0.850 | **+14.2% above baseline** |
| **Abstention Rate (In-distribution)** | **0.000** (0/630) | N/A | High confidence on clear leaves |
| **Automated Tests Passing** | **121 / 121** | — | `pytest -q` (100% pass) |

These are lab-image numbers; the real benchmark is lab-to-field generalisation, which is what the training augmentation and abstention logic are built for. A complete confusion matrix and per-class metrics are published in [`report/model_report.md`](report/model_report.md).

## Known Limitations

- **Field Domain Shift**: Models trained on clean lab backgrounds (PlantVillage) face real-world clutter, overlapping leaves, and varying sunlight. AgriSmart mitigates this through aggressive augmentations and an abstention threshold ($\tau = 0.40$), abstaining gracefully rather than outputting false diagnoses.
- **Class Scope**: Current release targets 18 high-impact agricultural disease and healthy classes; retraining on newly released kickoff classes is straightforward via `model/train.py`.

## Documentation

Module-level documentation is maintained in [`docs/soil_sources.md`](docs/soil_sources.md), [`docs/weather_rules.md`](docs/weather_rules.md), and [`docs/sustainability.md`](docs/sustainability.md). Interactive API docs are available at `/docs` once the backend is running.

## Data Sources & Licences

| Source | Used For | Licence |
|---|---|---|
| PlantVillage | training the disease classifier | CC0 |
| SoilGrids 2.0 (ISRIC) | texture, pH, SOC, N, CEC, bulk density | CC-BY 4.0 |
| Soil Health Card | district-average N/P/K | Govt. of India open data |
| Open-Meteo | 3-day weather forecast | free API, CC-BY 4.0 |
| Nominatim / OpenStreetMap | reverse geocoding, map tiles | ODbL |
| Google Gemini (optional) | assistant answer generation | Google API terms |

## Originality & Third-Party Code Declaration

Per **Section 8 (Originality & Timeframe Rules)**:
- **Original Architecture & Code**: The full application design, FastAPI backend services, ReAct agentic advisor reasoning loop (`services/agent.py`), rule-based weather and sustainability engines (`services/weather.py`, `services/sustainability.py`), grounded RAG assistant pipeline (`services/assistant.py`), database schemas, and React frontend were designed and implemented specifically for SIH 2026.
- **Third-Party Open-Source Libraries & Backbones Used**:
  - `timm` / PyTorch: Pretrained EfficientNet-B0 backbone for leaf transfer learning.
  - `faster-whisper`: Local voice transcription for multilingual speech.
  - `pytorch-grad-cam`: Grad-CAM feature attribution heatmaps.
  - `Open-Meteo`: Weather forecast API (CC-BY 4.0).
  - `SoilGrids 2.0 (ISRIC)`: Digital soil mapping API (CC-BY 4.0).
  - `Government of India Soil Health Card (SHC)`: Reference NPK dataset.
  - `PlantVillage`: Public leaf disease image dataset (CC0).

## License

Academic project — Smart India Hackathon 2026 internal round, L. J. Institute of Engineering & Technology (PS-1 / C-433).

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:E3A857,100:4C7A3D&height=100&section=footer" alt="footer wave"/>
</p>
