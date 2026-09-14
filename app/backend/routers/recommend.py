"""Module A — soil-driven crop and amendment recommendations."""

from __future__ import annotations

from fastapi import APIRouter

from ..models.recommend import AmendmentReport, CropRecommendation, RecommendRequest
from ..services.recommend import recommend_amendments, recommend_crops
from ..services.soil_profile import build_soil_profile

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("/amendments", response_model=AmendmentReport)
async def amendments(req: RecommendRequest) -> AmendmentReport:
    """Soil correction plan for a GPS point: lime / organic matter / CEC from
    SoilGrids, N-P-K dosing from the Soil Health Card enrichment when available."""
    profile = await build_soil_profile(req.lat, req.lon, texture_override=req.texture_override)
    return recommend_amendments(profile)


@router.post("/crops", response_model=CropRecommendation)
async def crops(req: RecommendRequest) -> CropRecommendation:
    """Rank candidate crops for a GPS point on soil texture + pH (+ season).
    Climate scoring is handled by Module C."""
    profile = await build_soil_profile(req.lat, req.lon, texture_override=req.texture_override)
    return recommend_crops(profile, req.season)
