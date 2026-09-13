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
from ..models.orm import Diagnosis, Plot
from ..models.user import User
from ..services.assistant import answer_question
from ..services.transcribe import transcribe

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
                "name": plot.name, "lat": plot.lat, "lon": plot.lon,
                "soil_snapshot": plot.soil_snapshot,
            }
            last = await session.scalar(
                select(Diagnosis)
                .where(Diagnosis.plot_id == plot.id, Diagnosis.abstained == False)  # noqa: E712
                .order_by(Diagnosis.created_at.desc())
            )
            if last:
                last_class = last.predicted_class

    return await answer_question(
        req.question, lang=req.lang, plot=plot_ctx, last_class=last_class
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
