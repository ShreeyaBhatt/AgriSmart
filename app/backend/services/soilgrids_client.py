"""Async client for SoilGrids data via ISRIC's official Web Coverage Service (WCS).

ISRIC's legacy REST API (``rest.isric.org``) has been paused/disabled upstream (HTTP 503).
This client directly queries ISRIC's high-availability MapServer WCS endpoints
(``https://maps.isric.org/mapserv``), retrieving 0-30 cm plough-zone properties and WRB
soil classification in parallel using GeoTIFF raster queries.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import httpx
import numpy as np
from PIL import Image

from ..config import get_settings

log = logging.getLogger(__name__)

# The nine properties the pipeline consumes, and the three shallow depth layers
# that make up the 0-30 cm plough zone.
PROPERTIES = ("phh2o", "soc", "nitrogen", "sand", "silt", "clay", "cec", "bdod", "cfvo")
DEPTHS = ("0-5cm", "5-15cm", "15-30cm")

# WRB Reference Soil Groups (0 to 29 in the SoilGrids MostProbable raster)
WRB_CLASSES = (
    "Acrisols", "Albeluvisols", "Alisols", "Andosols", "Arenosols",
    "Calcisols", "Cambisols", "Chernozems", "Cryosols", "Durisols",
    "Ferralsols", "Fluvisols", "Gleysols", "Gypsisols", "Histosols",
    "Kastanozems", "Leptosols", "Lixisols", "Luvisols", "Nitisols",
    "Phaeozems", "Planosols", "Plinthosols", "Podzols", "Regosols",
    "Solonchaks", "Solonetz", "Stagnosols", "Umbrisols", "Vertisols",
)

NODATA_VALUE = -32768


class SoilGridsError(RuntimeError):
    """Raised when SoilGrids cannot be reached or returns an unusable payload."""


def _d_factor(prop: str) -> int:
    """Fallback conversion divisor (d_factor) for SoilGrids properties."""
    return 100 if prop in ("nitrogen", "bdod") else 10


def properties_have_values(payload: dict[str, Any]) -> bool:
    """True if at least one property/depth carries a non-null mean."""
    for layer in (payload.get("properties") or {}).get("layers") or []:
        for depth in layer.get("depths") or []:
            if (depth.get("values") or {}).get("mean") is not None:
                return True
    return False


async def _fetch_wcs_pixel(
    client: httpx.AsyncClient,
    map_name: str,
    coverage_id: str,
    lat: float,
    lon: float,
    delta: float = 0.03,
) -> int | None:
    """Fetch a small GeoTIFF bounding box around (lat, lon) and extract the median valid value.

    A ~3 km delta (0.03 degrees) ensures urban asphalt or water mask pixels (common in
    city coordinates like Vadodara) gracefully resolve to surrounding agricultural soil.
    """
    settings = get_settings()
    params = {
        "map": f"/map/{map_name}.map",
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": coverage_id,
        "CRS": "EPSG:4326",
        "BBOX": f"{lon-delta},{lat-delta},{lon+delta},{lat+delta}",
        "WIDTH": "10",
        "HEIGHT": "10",
        "FORMAT": "GEOTIFF_INT16",
    }
    try:
        resp = await client.get(settings.soilgrids_wcs_url, params=params)
        if resp.status_code != 200 or "tiff" not in resp.headers.get("content-type", ""):
            return None
        img = Image.open(io.BytesIO(resp.content))
        arr = np.array(img)
        valid = arr[arr != NODATA_VALUE]
        if len(valid) == 0:
            return None
        return int(np.median(valid))
    except Exception as exc:
        log.debug("WCS fetch failed for %s (%s, %s): %s", coverage_id, lat, lon, exc)
        return None


async def fetch_properties(lat: float, lon: float) -> dict[str, Any]:
    """Return a GeoJSON Feature payload for a point with all 9 properties x 3 depths.

    Queries ISRIC's official WCS endpoint in parallel.
    Raises :class:`SoilGridsError` if all layers fail or time out.
    """
    settings = get_settings()
    timeout = httpx.Timeout(
        connect=8.0,
        read=settings.soilgrids_timeout_s,
        write=8.0,
        pool=5.0,
    )
    limits = httpx.Limits(max_connections=35, max_keepalive_connections=25)

    for attempt in range(1, settings.soilgrids_max_retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                headers={"User-Agent": settings.http_user_agent},
                http2=False,
            ) as client:
                tasks = [
                    (
                        prop,
                        depth,
                        asyncio.create_task(
                            _fetch_wcs_pixel(client, prop, f"{prop}_{depth}_mean", lat, lon)
                        ),
                    )
                    for prop in PROPERTIES
                    for depth in DEPTHS
                ]

                layers: dict[str, dict[str, Any]] = {
                    prop: {
                        "name": prop,
                        "unit_measure": {"d_factor": _d_factor(prop)},
                        "depths": [],
                    }
                    for prop in PROPERTIES
                }

                for prop, depth, task in tasks:
                    val = await task
                    layers[prop]["depths"].append({
                        "label": depth,
                        "values": {"mean": val, "uncertainty": None},
                    })

                payload = {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"layers": list(layers.values())},
                }

                if properties_have_values(payload):
                    return payload

                log.warning("SoilGrids WCS yielded all-null for (%s, %s) (attempt %d/%d)",
                            lat, lon, attempt, settings.soilgrids_max_retries)
        except Exception as exc:
            log.warning("SoilGrids WCS properties error (attempt %d/%d): %s",
                        attempt, settings.soilgrids_max_retries, exc)

        if attempt < settings.soilgrids_max_retries:
            await asyncio.sleep(1.0 * attempt)

    raise SoilGridsError(f"SoilGrids WCS has no usable data for ({lat}, {lon}) after retries")


async def fetch_classification(lat: float, lon: float, number_classes: int = 3) -> dict[str, Any]:
    """Return WRB Reference Soil Group and probabilities using ISRIC WCS ``MostProbable``."""
    settings = get_settings()
    timeout = httpx.Timeout(connect=8.0, read=settings.soilgrids_timeout_s, write=8.0, pool=5.0)
    delta = 0.03
    params = {
        "map": "/map/wrb.map",
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": "MostProbable",
        "CRS": "EPSG:4326",
        "BBOX": f"{lon-delta},{lat-delta},{lon+delta},{lat+delta}",
        "WIDTH": "10",
        "HEIGHT": "10",
        "FORMAT": "GEOTIFF_INT16",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": settings.http_user_agent},
            http2=False,
        ) as client:
            resp = await client.get(settings.soilgrids_wcs_url, params=params)
            if resp.status_code == 200 and "tiff" in resp.headers.get("content-type", ""):
                img = Image.open(io.BytesIO(resp.content))
                arr = np.array(img)
                valid = arr[arr >= 0]
                if len(valid) > 0:
                    vals, counts = np.unique(valid, return_counts=True)
                    best_idx = int(vals[np.argmax(counts)])
                    prob = float(np.max(counts) / len(valid))
                    name = WRB_CLASSES[best_idx] if best_idx < len(WRB_CLASSES) else "Vertisols"
                    return {
                        "wrb_class_name": name,
                        "wrb_class_probability": [[name, int(round(prob * 100))]],
                    }
    except Exception as exc:
        log.warning("SoilGrids WCS classification fetch failed for (%s, %s): %s", lat, lon, exc)

    return {}
