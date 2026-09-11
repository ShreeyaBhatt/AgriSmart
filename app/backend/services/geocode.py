"""Reverse geocoding via Nominatim (OpenStreetMap) — lat/lon -> district + state.

Used only to key the Soil Health Card enrichment lookup. Failure is non-fatal:
the soil profile is still complete from SoilGrids, just without SHC nutrients.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)


class Admin(NamedTuple):
    district: str | None
    state: str | None
    country: str | None


# Nominatim splits Indian districts across several address keys depending on OSM tagging.
_DISTRICT_KEYS = ("state_district", "county", "district", "region")
_STATE_KEYS = ("state", "province")


async def reverse_admin(lat: float, lon: float) -> Admin:
    settings = get_settings()
    params = {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "addressdetails": 1}
    try:
        async with httpx.AsyncClient(
            timeout=settings.nominatim_timeout_s,
            headers={"User-Agent": settings.http_user_agent, "Accept": "application/json"},
        ) as client:
            resp = await client.get(f"{settings.nominatim_base_url}/reverse", params=params)
            resp.raise_for_status()
            addr = resp.json().get("address", {})
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Nominatim reverse geocode failed for (%s, %s): %s", lat, lon, exc)
        return Admin(None, None, None)

    district = next((addr[k] for k in _DISTRICT_KEYS if addr.get(k)), None)
    state = next((addr[k] for k in _STATE_KEYS if addr.get(k)), None)
    return Admin(district=district, state=state, country=addr.get("country"))
