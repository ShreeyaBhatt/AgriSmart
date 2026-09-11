"""Activity logging — irrigation events and farmer actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models.farm import ActionCreate, IrrigationCreate
from ..models.orm import FarmerAction, IrrigationEvent, Plot
from ..models.user import User

router = APIRouter(tags=["logs"])


async def _assert_owns_plot(plot_id: str, session: AsyncSession, user: User) -> None:
    plot = await session.get(Plot, plot_id)
    if plot is None or plot.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plot not found")


@router.post("/irrigation", status_code=status.HTTP_201_CREATED)
async def log_irrigation(
    body: IrrigationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    await _assert_owns_plot(body.plot_id, session, user)
    payload = body.model_dump(exclude_none=True)
    event = IrrigationEvent(owner_id=user.id, **payload)
    session.add(event)
    await session.commit()
    return {"id": event.id}


@router.post("/actions", status_code=status.HTTP_201_CREATED)
async def log_action(
    body: ActionCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    await _assert_owns_plot(body.plot_id, session, user)
    action = FarmerAction(owner_id=user.id, **body.model_dump(exclude_none=True))
    session.add(action)
    await session.commit()
    return {"id": action.id}
