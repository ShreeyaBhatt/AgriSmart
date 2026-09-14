"""Module A — GPS -> SoilGrids soil profile."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from ..models.soil import SoilLookupRequest, SoilProfile
from ..services.soil_profile import build_soil_profile

log = logging.getLogger(__name__)
router = APIRouter(prefix="/soil", tags=["soil"])


@router.post("/lookup", response_model=SoilProfile, response_model_exclude_none=False)
async def soil_lookup(req: SoilLookupRequest) -> SoilProfile:
    """Resolve a farm's soil profile from its GPS point.

    Pipeline: SoilGrids ``properties`` + ``classification`` -> 0-30 cm
    depth-weighted normalisation -> USDA texture -> Soil Health Card nutrient
    enrichment (by district). Always returns a full profile; if SoilGrids is
    unreachable the bundled offline sample is returned with
    ``source = "sample (offline)"``.
    """
    profile = await build_soil_profile(req.lat, req.lon, texture_override=req.texture_override)

    if req.plot_id:
        # TODO(app-db): persist `profile` into Plot(id=req.plot_id).soil_snapshot
        #   once Beanie/Mongo is wired (build plan, Day 3). The profile shape is
        #   already a superset of Plot.soil_snapshot.
        log.info("plot_id=%s supplied; soil_snapshot persistence not yet wired", req.plot_id)

    return profile
