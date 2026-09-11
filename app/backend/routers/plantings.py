"""Plantings (a crop growing on a plot)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models.farm import PlantingCreate, PlantingOut, PlantingUpdate
from ..models.orm import Planting, Plot
from ..models.user import User

router = APIRouter(prefix="/plantings", tags=["plantings"])


@router.get("", response_model=list[PlantingOut])
async def list_plantings(
    plot_id: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[Planting]:
    q = select(Planting).where(Planting.owner_id == user.id).order_by(Planting.created_at.desc())
    if plot_id:
        q = q.where(Planting.plot_id == plot_id)
    return list(await session.scalars(q))


@router.post("", response_model=PlantingOut, status_code=status.HTTP_201_CREATED)
async def create_planting(
    body: PlantingCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Planting:
    plot = await session.get(Plot, body.plot_id)
    if plot is None or plot.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plot not found")
    planting = Planting(owner_id=user.id, **body.model_dump())
    session.add(planting)
    await session.commit()
    await session.refresh(planting)
    return planting


@router.patch("/{planting_id}", response_model=PlantingOut)
async def update_planting(
    planting_id: str,
    body: PlantingUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Planting:
    planting = await session.get(Planting, planting_id)
    if planting is None or planting.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planting not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(planting, field, value)
    await session.commit()
    await session.refresh(planting)
    return planting
