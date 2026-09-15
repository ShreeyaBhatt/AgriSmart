"""AgriSmart AI backend — FastAPI app.

Wires the full system: phone+OTP auth (MongoDB accounts) + per‑farmer farm
data (SQLite), the crop‑disease predict API, Module A (soil), and Modules
C (weather), D (sustainability), E (GenAI assistant).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .mongo import init_mongo_indexes
from .services import assistant as assistant_service
from .services import transcribe as transcribe_service
from .routers import (
    agent,
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
    # Both pay a real one-time cost (Whisper model load, Gemini SDK/channel
    # setup) on whichever request happens to be first otherwise — see the
    # docstrings on warm_up() in each service. Run together since they're
    # independent, so startup pays max(whisper, gemini), not their sum.
    await asyncio.gather(transcribe_service.warm_up(), assistant_service.warm_up())
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
for r in (auth, plots, plantings, predict, diagnoses, logs, soil, recommend, weather, sustainability, assistant, agent):
    app.include_router(r.router, prefix="/api")

settings.uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")


@app.get("/api/health", tags=["meta"])
@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve production frontend if built
if settings.frontend_dist_dir.is_dir():
    assets_dir = settings.frontend_dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("uploads/"):
            raise HTTPException(status_code=404, detail="Not Found")
        # full_path comes straight from the URL and Path's `/` operator does
        # not collapse ".." segments, so without resolving+containment-
        # checking it, a request like "/../../../etc/passwd" (or an
        # OS-appropriate traversal against this repo's own files, e.g.
        # ".env") would resolve outside frontend_dist_dir and get served.
        target = (settings.frontend_dist_dir / full_path).resolve()
        dist_root = settings.frontend_dist_dir.resolve()
        if target.is_relative_to(dist_root) and target.is_file():
            return FileResponse(target)
        index_file = settings.frontend_dist_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend index.html not found")

