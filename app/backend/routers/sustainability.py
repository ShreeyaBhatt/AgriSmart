"""Module D — Sustainability Score endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from ..models.modules import SustainabilityRequest, SustainabilityScore
from ..services.sustainability import compute_score

router = APIRouter(prefix="/sustainability", tags=["sustainability"])


@router.post("/score", response_model=SustainabilityScore)
async def sustainability_score(req: SustainabilityRequest) -> SustainabilityScore:
    return await compute_score(req)
