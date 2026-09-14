"""Per‑farmer plots — CRUD, soil snapshot, and the activity timeline."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import SessionLocal, get_session
from ..models.farm import PlotCreate, PlotOut, PlotUpdate, Timeline, TimelineEntry
from ..models.orm import Diagnosis, FarmerAction, IrrigationEvent, Plot
from ..models.user import User
from ..services.disease_cards import localized_label_for
from ..services.soil_profile import build_soil_profile

router = APIRouter(prefix="/plots", tags=["plots"])

# Small, self-contained translation table for the handful of fixed labels the
# timeline needs beyond disease names (those come from disease_cards.json via
# localized_label_for). Mirrors the frontend's own scan.*/logs.type.* strings
# in app/frontend/src/i18n/strings.js so the two stay in sync by inspection.
_TIMELINE_STRINGS = {
    "unclear": {"en": "Unclear photo", "hi": "अस्पष्ट फोटो", "gu": "અસ્પષ્ટ ફોટો"},
    "healthy": {"en": "Healthy leaf", "hi": "स्वस्थ पत्ती", "gu": "તંદુરસ્ત પાન"},
    "confidence": {"en": "confidence", "hi": "विश्वास", "gu": "વિશ્વાસ"},
    "irrigation": {"en": "Irrigation", "hi": "सिंचाई", "gu": "સિંચાઈ"},
}
_ACTION_TYPE_STRINGS = {
    "spray": {"en": "Spray", "hi": "छिड़काव", "gu": "છંટકાવ"},
    "lime": {"en": "Lime", "hi": "चूना", "gu": "ચૂનો"},
    "compost": {"en": "Compost", "hi": "खाद", "gu": "ખાતર"},
    "crop_change": {"en": "Crop change", "hi": "फसल परिवर्तन", "gu": "પાક બદલાવ"},
    "irrigation": {"en": "Irrigation", "hi": "सिंचाई", "gu": "સિંચાઈ"},
    "other": {"en": "Other", "hi": "अन्य", "gu": "અન્ય"},
}


def _tt(key: str, lang: str) -> str:
    return _TIMELINE_STRINGS.get(key, {}).get(lang) or _TIMELINE_STRINGS[key]["en"]


def _diagnosis_title(d: Diagnosis, lang: str) -> str:
    if d.abstained:
        return _tt("unclear", lang)
    if d.predicted_class.lower().endswith("healthy"):
        return _tt("healthy", lang)
    return localized_label_for(d.predicted_class, lang) or d.predicted_class


log = logging.getLogger(__name__)


async def get_owned_plot(plot_id: str, session: AsyncSession, user: User) -> Plot:
    plot = await session.get(Plot, plot_id)
    if plot is None or plot.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plot not found")
    return plot


async def _attach_soil(plot: Plot, use_cache: bool = True) -> None:
    profile = await build_soil_profile(plot.lat, plot.lon, use_cache=use_cache)
    plot.soil_snapshot = profile.model_dump(mode="json")
    plot.soil_fetched_at = datetime.now(timezone.utc)
    plot.soil_status = "ready"


async def _background_attach_soil(plot_id: str) -> None:
    """Background task: fetches soil without holding a DB session open during the wait."""
    # 1. Quickly read lat/lon
    async with SessionLocal() as session:
        plot = await session.get(Plot, plot_id)
        if plot is None:
            return
        lat, lon = plot.lat, plot.lon

    # 2. Network call (takes up to 45s) — no DB transaction held!
    try:
        # skip_offline_cache=True: a previous transient failure for these
        # coordinates (e.g. from an interactive /soil/lookup that hit a timeout)
        # must not shadow this background attempt, which has its own full budget.
        profile = await build_soil_profile(lat, lon, skip_offline_cache=True)
        snapshot = profile.model_dump(mode="json")
        status = "ready"
    except Exception:
        log.exception("Background soil fetch failed for plot %s", plot_id)
        snapshot = None
        status = "failed"

    # 3. Quickly write results
    async with SessionLocal() as session:
        plot = await session.get(Plot, plot_id)
        if plot is not None:
            if status == "ready":
                plot.soil_snapshot = snapshot
                plot.soil_fetched_at = datetime.now(timezone.utc)
            plot.soil_status = status
            await session.commit()


@router.get("", response_model=list[PlotOut])
async def list_plots(
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)
) -> list[Plot]:
    rows = await session.scalars(
        select(Plot).where(Plot.owner_id == user.id).order_by(Plot.created_at.desc())
    )
    return list(rows)


@router.post("", response_model=PlotOut, status_code=status.HTTP_201_CREATED)
async def create_plot(
    body: PlotCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Plot:
    plot = Plot(
        owner_id=user.id,
        name=body.name,
        lat=body.lat,
        lon=body.lon,
        area_ha=body.area_ha,
        main_crop=body.main_crop,
        soil_status="pending",
    )
    session.add(plot)
    await session.commit()
    await session.refresh(plot)
    # Fire soil fetch in the background — does NOT block the response.
    background_tasks.add_task(_background_attach_soil, plot.id)
    return plot


@router.get("/{plot_id}", response_model=PlotOut)
async def get_plot(
    plot_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Plot:
    return await get_owned_plot(plot_id, session, user)


@router.patch("/{plot_id}", response_model=PlotOut)
async def update_plot(
    plot_id: str,
    body: PlotUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Plot:
    plot = await get_owned_plot(plot_id, session, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plot, field, value)
    await session.commit()
    await session.refresh(plot)
    return plot


@router.get("/{plot_id}/soil-status")
async def get_soil_status(
    plot_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Lightweight polling endpoint for the frontend to check if background soil fetch is done."""
    plot = await get_owned_plot(plot_id, session, user)
    return {
        "ready": plot.soil_status == "ready",
        "failed": plot.soil_status == "failed",
        "soil_status": plot.soil_status,
        "soil_snapshot": plot.soil_snapshot,
        "soil_fetched_at": plot.soil_fetched_at,
    }


@router.delete("/{plot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plot(
    plot_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    plot = await get_owned_plot(plot_id, session, user)
    await session.delete(plot)
    await session.commit()


@router.post("/{plot_id}/refresh-soil", response_model=PlotOut)
async def refresh_soil(
    plot_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Plot:
    plot = await get_owned_plot(plot_id, session, user)
    await _attach_soil(plot, use_cache=False)
    await session.commit()
    await session.refresh(plot)
    return plot


@router.get("/{plot_id}/timeline", response_model=Timeline)
async def plot_timeline(
    plot_id: str,
    lang: str = "en",
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Timeline:
    await get_owned_plot(plot_id, session, user)
    entries: list[TimelineEntry] = []

    for d in await session.scalars(select(Diagnosis).where(Diagnosis.plot_id == plot_id)):
        entries.append(TimelineEntry(
            kind="diagnosis", at=d.created_at, ref_id=d.id,
            title=_diagnosis_title(d, lang),
            detail=f"{_tt('confidence', lang)} {d.confidence:.0%}",
        ))
    for e in await session.scalars(select(IrrigationEvent).where(IrrigationEvent.plot_id == plot_id)):
        entries.append(TimelineEntry(
            kind="irrigation", at=e.at, ref_id=e.id, title=_tt("irrigation", lang),
            # amount_mm=0 is a valid, meaningful reading ("checked, no water
            # applied") — `if e.amount_mm` treated it as falsy and silently
            # dropped it, so check for None instead of truthiness.
            detail=(e.note or e.method or (f"{e.amount_mm} mm" if e.amount_mm is not None else None)),
        ))
    for a in await session.scalars(select(FarmerAction).where(FarmerAction.plot_id == plot_id)):
        entries.append(TimelineEntry(
            kind="action", at=a.at, ref_id=a.id,
            title=_ACTION_TYPE_STRINGS.get(a.action_type, {}).get(lang)
            or _ACTION_TYPE_STRINGS.get(a.action_type, {}).get("en")
            or a.action_type.replace("_", " ").title(),
            detail=a.details,
        ))

    entries.sort(key=lambda x: x.at, reverse=True)
    return Timeline(plot_id=plot_id, entries=entries)
