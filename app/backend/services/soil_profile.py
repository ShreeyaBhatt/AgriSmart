"""Normalise raw SoilGrids + SHC data into a single :class:`SoilProfile`, and
orchestrate the full ``POST /soil/lookup`` pipeline (fetch -> normalise ->
enrich -> cache -> offline fallback).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from functools import lru_cache
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..models.soil import SoilProfile, SoilUncertainty
from .geocode import Admin, reverse_admin
from .shc import ShcRecord
from .shc import lookup as shc_lookup
from .soil_texture import usda_texture
from .soilgrids_client import PROPERTIES, SoilGridsError, fetch_classification, fetch_properties

log = logging.getLogger(__name__)

# Depth layers that make up the 0-30 cm plough zone, and their thickness (cm).
_DEPTH_WEIGHTS = {"0-5cm": 5.0, "5-15cm": 10.0, "15-30cm": 15.0}

# Fallback conversion divisors if a layer omits ``unit_measure.d_factor``.
_FALLBACK_D_FACTOR = {
    "phh2o": 10, "soc": 10, "nitrogen": 100, "sand": 10, "silt": 10,
    "clay": 10, "cec": 10, "bdod": 100, "cfvo": 10,
}
# SoilGrids uncertainty layers are reported x10.
_UNCERTAINTY_D_FACTOR = 10.0


# --------------------------------------------------------------------------- #
# raw payload -> numbers
# --------------------------------------------------------------------------- #
def _layers_by_name(feature: dict[str, Any]) -> dict[str, dict[str, Any]]:
    layers = (feature.get("properties") or {}).get("layers") or []
    return {layer.get("name"): layer for layer in layers if layer.get("name")}


def _depth_weighted(layer: dict[str, Any], key: str) -> float | None:
    """Thickness-weighted mean of ``values[key]`` over the 0-30 cm layers present."""
    num = den = 0.0
    for depth in layer.get("depths") or []:
        weight = _DEPTH_WEIGHTS.get(depth.get("label"))
        if weight is None:
            continue
        value = (depth.get("values") or {}).get(key)
        if value is None:
            continue
        num += float(value) * weight
        den += weight
    return num / den if den else None


def _d_factor(layer: dict[str, Any], name: str) -> float:
    raw = (layer.get("unit_measure") or {}).get("d_factor")
    return float(raw) if raw else float(_FALLBACK_D_FACTOR[name])


def normalise_properties(feature: dict[str, Any]) -> tuple[dict[str, float | None], dict[str, float | None]]:
    """Return ``(values, uncertainty)`` dicts keyed by SoilGrids property name,
    each already converted to target units (0-30 cm depth-weighted)."""
    layers = _layers_by_name(feature)
    values: dict[str, float | None] = {}
    uncertainty: dict[str, float | None] = {}
    for name in PROPERTIES:
        layer = layers.get(name)
        if not layer:
            values[name] = uncertainty[name] = None
            continue
        factor = _d_factor(layer, name)
        mean = _depth_weighted(layer, "mean")
        unc = _depth_weighted(layer, "uncertainty")
        values[name] = mean / factor if mean is not None else None
        uncertainty[name] = unc / _UNCERTAINTY_D_FACTOR if unc is not None else None
    return values, uncertainty


def parse_classification(payload: dict[str, Any]) -> tuple[str | None, float | None]:
    """Return ``(wrb_class_name, top_probability_0_1)`` from ``/classification/query``."""
    name = payload.get("wrb_class_name")
    probs = payload.get("wrb_class_probability") or []
    top: float | None = None
    if probs and isinstance(probs[0], (list, tuple)) and len(probs[0]) >= 2:
        name = name or probs[0][0]
        p = float(probs[0][1])
        top = p / 100.0 if p > 1 else p
    return name, top


def _round(value: float | None, ndigits: int = 3) -> float | None:
    return round(value, ndigits) if value is not None else None


# --------------------------------------------------------------------------- #
# numbers -> SoilProfile
# --------------------------------------------------------------------------- #
def assemble_profile(
    *,
    lat: float,
    lon: float,
    properties_payload: dict[str, Any],
    classification_payload: dict[str, Any],
    admin: Admin,
    shc: ShcRecord | None,
    source_prefix: str,
) -> SoilProfile:
    values, uncertainty = normalise_properties(properties_payload)
    wrb_name, wrb_p = parse_classification(classification_payload)

    sand, silt, clay = values.get("sand"), values.get("silt"), values.get("clay")
    texture = usda_texture(sand, silt, clay) if None not in (sand, silt, clay) else None

    soc = values.get("soc")
    has_shc = shc is not None and any(
        v is not None for v in (shc.available_n_kg_ha, shc.available_p_kg_ha, shc.available_k_kg_ha)
    )
    source = source_prefix
    if has_shc and source_prefix == "SoilGrids v2.0":
        source = f"SoilGrids v2.0 + SHC ({shc.district})"

    return SoilProfile(
        source=source,
        fetched_at=datetime.now(timezone.utc),
        lat=lat,
        lon=lon,
        texture_class=texture,
        wrb_class=wrb_name,
        wrb_probability=_round(wrb_p, 3),
        sand_pct=_round(sand, 1),
        silt_pct=_round(silt, 1),
        clay_pct=_round(clay, 1),
        ph=_round(values.get("phh2o"), 2),
        organic_carbon_g_kg=_round(soc, 2),
        organic_carbon_pct=_round(soc / 10.0, 3) if soc is not None else None,
        total_nitrogen_g_kg=_round(values.get("nitrogen"), 3),
        cec_cmol_kg=_round(values.get("cec"), 2),
        bulk_density_kg_dm3=_round(values.get("bdod"), 3),
        coarse_fragments_pct=_round(values.get("cfvo"), 1),
        available_n_kg_ha=shc.available_n_kg_ha if shc else None,
        available_p_kg_ha=shc.available_p_kg_ha if shc else None,
        available_k_kg_ha=shc.available_k_kg_ha if shc else None,
        shc_district=(shc.district if shc else admin.district),
        shc_state=(shc.state if shc else admin.state),
        uncertainty=SoilUncertainty(
            ph=_round(uncertainty.get("phh2o"), 2),
            clay_pct=_round(uncertainty.get("clay"), 1),
            sand_pct=_round(uncertainty.get("sand"), 1),
            silt_pct=_round(uncertainty.get("silt"), 1),
            organic_carbon_g_kg=_round(uncertainty.get("soc"), 2),
            total_nitrogen_g_kg=_round(uncertainty.get("nitrogen"), 3),
            cec_cmol_kg=_round(uncertainty.get("cec"), 2),
            bulk_density_kg_dm3=_round(uncertainty.get("bdod"), 3),
            coarse_fragments_pct=_round(uncertainty.get("cfvo"), 1),
        ),
        raw={
            "properties": properties_payload,
            "classification": classification_payload,
            "reverse_geocode": {
                "district": admin.district, "state": admin.state, "country": admin.country,
            },
        },
    )


# --------------------------------------------------------------------------- #
# cache + orchestration
# --------------------------------------------------------------------------- #
class _TTLCache:
    def __init__(self, ttl_s: int) -> None:
        self._ttl_s = ttl_s
        self._store: dict[str, tuple[float, SoilProfile]] = {}

    def get(self, key: str) -> SoilProfile | None:
        hit = self._store.get(key)
        if not hit:
            return None
        ts, profile = hit
        if time.monotonic() - ts > self._ttl_s:
            self._store.pop(key, None)
            return None
        return profile

    def set(self, key: str, profile: SoilProfile) -> None:
        self._store[key] = (time.monotonic(), profile)

    def clear(self) -> None:
        self._store.clear()


_cache = _TTLCache(get_settings().soil_cache_ttl_s)
# Separate, short-TTL cache for offline-fallback results — see build_soil_profile.
_offline_cache = _TTLCache(get_settings().soil_offline_cache_ttl_s)


def _cache_key(lat: float, lon: float) -> str:
    p = get_settings().soil_cache_precision
    return f"{round(lat, p)},{round(lon, p)}"


@lru_cache
def _sample_doc() -> dict[str, Any]:
    return json.loads(get_settings().soilgrids_sample_path.read_text(encoding="utf-8"))


async def build_soil_profile(lat: float, lon: float, *, use_cache: bool = True) -> SoilProfile:
    """Full pipeline: SoilGrids ``properties`` + ``classification`` -> 0-30 cm
    normalisation -> USDA texture -> Soil Health Card nutrient enrichment -> cache.

    Resilient to SoilGrids' intermittent all-null responses: if the properties
    call yields no usable data, the bundled sample fixture stands in for the
    physical/chemical values (``source = "sample (offline)"``) while any
    classification and SHC data that *did* resolve are still used.

    All external calls (properties, classification, reverse geocode) run
    concurrently to minimise wall time, capped by ``soilgrids_deadline_s`` —
    profiling during an ISRIC slowdown measured single requests taking
    20-30s each, sometimes timing out, compounding through retries into
    50-60s+ for one lookup. Past the deadline this gives up and falls back
    rather than let a farmer's plot-creation flow hang on it indefinitely.
    """
    key = _cache_key(lat, lon)
    if use_cache and (cached := _cache.get(key)) is not None:
        return cached
    if use_cache and (cached := _offline_cache.get(key)) is not None:
        return cached

    # --- Run all external calls concurrently ---
    async def _safe_properties():
        try:
            return await fetch_properties(lat, lon)
        except SoilGridsError as exc:
            log.warning("SoilGrids properties unavailable for (%s, %s): %s", lat, lon, exc)
            return None

    async def _safe_classification():
        try:
            return await fetch_classification(lat, lon)
        except SoilGridsError as exc:
            log.warning("SoilGrids classification unavailable for (%s, %s): %s", lat, lon, exc)
            return {}

    try:
        properties_payload, classification_payload, admin = await asyncio.wait_for(
            asyncio.gather(_safe_properties(), _safe_classification(), reverse_admin(lat, lon)),
            timeout=get_settings().soilgrids_deadline_s,
        )
    except asyncio.TimeoutError:  # asyncio.TimeoutError, not the builtin — README targets Python 3.10+,
        # where they're still distinct classes (aliased together only from 3.11)
        log.warning("SoilGrids phase exceeded the %ss deadline for (%s, %s); using offline sample",
                    get_settings().soilgrids_deadline_s, lat, lon)
        properties_payload, classification_payload, admin = None, {}, Admin(None, None, None)

    shc = shc_lookup(admin.district)

    if properties_payload is None:
        source_prefix = "sample (offline)"
        properties_payload = _sample_doc()["properties"]
        classification_payload = classification_payload or _sample_doc().get("classification", {})
    else:
        source_prefix = "SoilGrids v2.0"

    profile = assemble_profile(
        lat=lat,
        lon=lon,
        properties_payload=properties_payload,
        classification_payload=classification_payload,
        admin=admin,
        shc=shc,
        source_prefix=source_prefix,
    )
    if source_prefix == "SoilGrids v2.0":
        _cache.set(key, profile)
    else:
        # Short TTL: without this, every request for a location SoilGrids is
        # currently failing on pays the full retry-and-possibly-timeout cost
        # again, even the same coordinates queried twice in a row — this is
        # what actually made repeated lookups slow during an outage, not
        # just the one-off cold cost.
        _offline_cache.set(key, profile)
    return profile


def clear_cache() -> None:
    _cache.clear()
    _offline_cache.clear()
