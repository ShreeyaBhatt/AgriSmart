"""Module E — GenAI Farmer Assistant endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user_optional
from ..db import get_session
from ..models.modules import AssistantAnswer, AssistantRequest
from ..models.orm import Diagnosis, Plot
from ..models.user import User
from ..services.assistant import answer_question

router = APIRouter(prefix="/assistant", tags=["assistant"])


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
