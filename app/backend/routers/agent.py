"""Router for Module G — Autonomous Agentic Advisor."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models.orm import Diagnosis, Planting, Plot
from ..models.user import User
from ..services import agent as agent_service
from ..services import weather as weather_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/plots/{plot_id}/advisory", response_model=agent_service.AgentAdvisory)
@router.post("/plots/{plot_id}/advisory", response_model=agent_service.AgentAdvisory)
async def get_plot_agent_advisory(
    plot_id: str,
    lang: str = Query("en", pattern="^(en|hi|gu|mr|ta|te|pa)$"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> agent_service.AgentAdvisory:
    """Evaluates multi-stream agricultural data for a plot and returns an actionable
    advisory with an inspectable Decision Trace."""
    plot = await session.get(Plot, plot_id)
    if plot is None or plot.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plot not found")

    # 1. Fetch active planting for growth stage
    planting_query = (
        select(Planting)
        .where(Planting.plot_id == plot_id, Planting.status == "active")
        .order_by(Planting.created_at.desc())
        .limit(1)
    )
    res = await session.execute(planting_query)
    planting = res.scalar_one_or_none()

    crop = (planting.name if planting else plot.main_crop) or "General Crop"
    stage = planting.stage if planting else None

    # 2. Fetch latest diagnosis
    diag_query = (
        select(Diagnosis)
        .where(Diagnosis.plot_id == plot_id)
        .order_by(Diagnosis.created_at.desc())
        .limit(1)
    )
    res = await session.execute(diag_query)
    diag = res.scalar_one_or_none()
    diag_dict = {
        "predicted_class": diag.predicted_class,
        "abstained": diag.abstained,
        "confidence": diag.confidence,
    } if diag else None

    # 3. Fetch live weather forecast
    try:
        forecast = await weather_service.fetch_forecast(plot.lat, plot.lon)
    except Exception as exc:
        log.warning("Could not fetch forecast for agent advisory: %s. Using default baseline.", exc)
        forecast = {}

    return agent_service.evaluate_advisory(
        plot_id=plot.id,
        plot_name=plot.name,
        crop=crop,
        stage=stage,
        soil_snapshot=plot.soil_snapshot,
        last_diagnosis=diag_dict,
        forecast=forecast,
        lang=lang,
    )
