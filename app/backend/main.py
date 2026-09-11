"""AgriSmart AI backend — FastAPI app.

Wires the full system: phone+OTP auth (MongoDB accounts) + per‑farmer farm
data (SQLite), the crop‑disease predict API, Module A (soil), and Modules
C (weather), D (sustainability), E (GenAI assistant).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .mongo import init_mongo_indexes
from .routers import (
    assistant,
    auth,
    diagnoses,
    logs,
    plantings,
    plots,
    predict,
    recommend,
    soil,
    sustainability,
    weather,
)

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    await init_mongo_indexes()
    yield


app = FastAPI(
    title="AgriSmart AI",
    version="1.0.0",
    summary="Intelligent Agriculture for a Sustainable Future — SIH 2026",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api so the SPA can own bare paths like /weather, /soil.
for r in (auth, plots, plantings, predict, diagnoses, logs, soil, recommend, weather, sustainability, assistant):
    app.include_router(r.router, prefix="/api")

settings.uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")


@app.get("/api/health", tags=["meta"])
@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
