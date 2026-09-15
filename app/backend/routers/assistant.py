"""Module E — GenAI Farmer Assistant endpoint."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user_optional
from ..db import get_session
from ..models.modules import AssistantAnswer, AssistantRequest, TranscribeOut
from ..models.orm import Diagnosis, Planting, Plot
from ..models.user import User
from ..services.assistant import answer_question
from ..services.transcribe import transcribe
from ..services import weather as weather_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])
_MAX_AUDIO_BYTES = 15 * 1024 * 1024  # a few seconds of speech is a few hundred KB; 15MB is generous


@router.post("/ask", response_model=AssistantAnswer)
async def ask(
    req: AssistantRequest,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(get_current_user_optional),
) -> AssistantAnswer:
    plot_ctx: dict | None = None
    last_class: str | None = None

    if user and req.plot_id:
        plot = await session.get(Plot, req.plot_id)
        if plot and plot.owner_id == user.id:
            plot_ctx = {
                "id": plot.id,
                "name": plot.name,
                "lat": plot.lat,
                "lon": plot.lon,
                "area_ha": plot.area_ha,
                "main_crop": plot.main_crop,
                "soil_snapshot": plot.soil_snapshot,
            }
            # Active planting telemetry
            planting = await session.scalar(
                select(Planting)
                .where(Planting.plot_id == plot.id, Planting.status == "active")
                .order_by(Planting.created_at.desc())
            )
            if planting:
                plot_ctx["planting"] = {
                    "crop": planting.crop,
                    "stage": planting.stage,
                    "sown_date": str(planting.sown_date) if planting.sown_date else None,
                }
                if not plot_ctx.get("main_crop"):
                    plot_ctx["main_crop"] = planting.crop

            # Latest leaf scan diagnosis
            last = await session.scalar(
                select(Diagnosis)
                .where(Diagnosis.plot_id == plot.id, Diagnosis.abstained == False)  # noqa: E712
                .order_by(Diagnosis.created_at.desc())
            )
            if last:
                last_class = last.predicted_class
                plot_ctx["latest_diagnosis"] = {
                    "disease": last.predicted_class,
                    "confidence": last.confidence,
                }

            # Live weather telemetry
            try:
                raw_fc = await weather_service.fetch_forecast(plot.lat, plot.lon)
                daily = raw_fc.get("daily", {})
                plot_ctx["weather_summary"] = {
                    "rain_prob": daily.get("precipitation_probability_max", [0])[0],
                    "rain_mm": daily.get("precipitation_sum", [0.0])[0],
                    "tmax": daily.get("temperature_2m_max", [None])[0],
                    "wind": daily.get("wind_speed_10m_max", [0])[0],
                }
            except Exception:
                pass

    history_list = [m.model_dump() for m in req.history] if req.history else None

    return await answer_question(
        req.question,
        lang=req.lang,
        plot=plot_ctx,
        last_class=last_class,
        land_unit=req.land_unit,
        bigha_region=req.bigha_region,
        history=history_list,
    )


@router.post("/transcribe", response_model=TranscribeOut)
async def transcribe_audio(
    file: UploadFile = File(...),
    lang: str = Form(default="en"),
) -> TranscribeOut:
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No audio received")
    if len(data) > _MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Recording too long")

    suffix = Path(file.filename or "").suffix or ".webm"
    try:
        # transcribe() is a synchronous faster-whisper call (plus a blocking
        # model load on the very first request) — off the event loop so it
        # doesn't stall other requests for its duration.
        text = await asyncio.to_thread(transcribe, data, suffix, lang)
    except Exception as exc:  # missing model deps, corrupt audio, decode failure
        log.exception("transcription failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Transcription failed: {exc}")
    return TranscribeOut(text=text)
