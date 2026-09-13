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

AgriSmart AI is a full-stack smart-agriculture application built for **SIH 2026** (L. J. Institute, PS-1 / C-433). It gives a farmer a single, role-free login that remembers their fields and answers the questions that matter day to day: what's wrong with this leaf, what does my soil need, what should today's weather change about my plan, and — for anything else — a grounded assistant to ask in their own language.

The system is one FastAPI backend serving a React frontend. Farm data (plots, plantings, diagnoses, activity logs) lives in **SQLite**, chosen for zero-setup portability; user accounts (phone/OTP login, guest mode) live in **MongoDB**, matching the project's original data-storage plan. The two stores are kept intentionally separate so each can be reasoned about, tested, and demoed independently.

<!--
  TODO: Add 2–4 screenshots here — this is usually the fastest way for
  an evaluator to understand what you built.

  Suggested shots: My Farm map view, the leaf-scan diagnosis screen
  with the Grad-CAM overlay, the weather/sustainability panel, and
  the farm assistant chat.

  1. Create a folder for them, e.g. docs/screenshots/
  2. Add each image there
  3. Reference them like this:

  ![My Farm](docs/screenshots/my-farm.png)
  ![Diagnosis + Grad-CAM](docs/screenshots/diagnosis.png)
  ![Farm Assistant](docs/screenshots/assistant.png)
-->

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
└── tests/           47 tests (pytest)
```

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:4C7A3D,100:E3A857&height=3&width=100%25" alt="divider"/>

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB (local instance, or `docker run -p 27017:27017 mongo`) — needed for accounts, not for the test suite

### 1. Backend (FastAPI)

```bash
cd .
pip install -r requirements.txt
python -m uvicorn app.backend.main:app --reload   # http://127.0.0.1:8000/docs
```

First run creates `agrismart.db` (SQLite) and an `uploads/` folder — no extra setup required. The disease model ships already trained in `model/artifacts/`, so `/predict` works immediately.

### 2. Frontend (React)

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
# Backend — pytest, 47 tests covering soil, auth, plots, predict, and modules C/D/E.
# MongoDB calls are swapped for an in-memory mongomock-motor client, so no real
# database is required to run the suite.
pytest -q

# Frontend — type/build check
cd app/frontend && npm run build
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

## Core Features

- **Crop-Disease Detection** — a photo of a leaf returns a disease label, a Grad-CAM overlay showing where the model focused, and an explicit "not confident" result when the prediction falls below threshold, rather than a forced guess.
- **Soil-Aware Crop Recommendation** — a plot's GPS coordinates are resolved against SoilGrids 2.0 and the Soil Health Card to get real texture, pH, and N-P-K values, which then drive crop-fit and amendment suggestions.
- **Weather Advisory** — a 3-day Open-Meteo forecast is passed through a rule engine that turns raw weather data into a specific action for the farmer, from irrigation timing to wind/rain warnings to proactive "good weather window" tips.
- **Sustainability Scoring** — each plot is scored against a published, reproducible formula, with concrete tips attached to raise the score.
- **Farm Assistant** — a grounded RAG pipeline over a disease-card knowledge base plus the farmer's own plot data, answering in English, Hindi, or Gujarati, with voice input and output. Runs on Gemini when a key is configured, or fully offline otherwise. Voice input is transcribed locally by this backend (faster-whisper) rather than a cloud speech API, so it keeps working with no internet beyond reaching your own server.
- **Multilingual, Theme-Aware UI** — navigation, weather advice, sustainability tips, disease/diagnosis labels, and the plot activity timeline all work in English, Hindi, or Gujarati, with a language switcher and light/dark theme toggle available from the login screen and Settings.
- **Guest → Registered, No Data Loss** — a guest isn't stuck choosing between trying the app and keeping their data: adding a phone number from Settings at any point attaches it to their *existing* account in place, so every plot, scan, and log they already have stays exactly where it was.

## Disease Coverage

The classifier is trained on an 18-class subset of PlantVillage, spanning multiple crops including tomato, potato, and corn, with both healthy and diseased leaf classes per crop.

For evaluation, results are reported at two levels: **per-class** precision/recall (see [`report/model_report.md`](report/model_report.md)) and **aggregate** macro-F1/accuracy across the full validation split — because a model can look strong in aggregate while quietly failing on one or two under-represented classes.

| Metric | Score | Notes |
|---|---|---|
| Macro-F1 (15% held-out validation) | **0.966** | lab-condition images, same distribution as training |
| Accuracy (15% held-out validation) | **0.967** | " |
| Tests passing | **47 / 47** | `pytest -q` |

These are lab-image numbers; the real benchmark is lab-to-field generalisation, which is what the training augmentation and abstention logic are built for.

## Not Included in This Build

IoT sensor integration and an autonomous agentic advisor were scoped during planning and deliberately left out, to keep the five shipped modules solid rather than spreading effort thin.

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

## License

Academic project — Smart India Hackathon 2026 internal round, L. J. Institute of Engineering & Technology (PS-1 / C-433).

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:E3A857,100:4C7A3D&height=100&section=footer" alt="footer wave"/>
</p>
