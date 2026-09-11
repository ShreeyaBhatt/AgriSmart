"""Pydantic schemas for the Module A soil pipeline.

`SoilProfile` is the single normalised shape returned by `POST /soil/lookup` and
cached (embedded) into `Plot.soil_snapshot`. It is a superset of the
`soil_snapshot` fields in the build plan's data model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SoilLookupRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    # Optional: when the app is wired to Mongo, the resolved profile is cached
    # into this plot's `soil_snapshot`.
    plot_id: str | None = None


class SoilUncertainty(BaseModel):
    """Per-property uncertainty as reported by SoilGrids (`value=uncertainty`),
    already divided by the property's `d_factor`. All optional."""

    ph: float | None = None
    clay_pct: float | None = None
    sand_pct: float | None = None
    silt_pct: float | None = None
    organic_carbon_g_kg: float | None = None
    total_nitrogen_g_kg: float | None = None
    cec_cmol_kg: float | None = None
    bulk_density_kg_dm3: float | None = None
    coarse_fragments_pct: float | None = None


SoilProfileSource = Literal[
    "SoilGrids v2.0",
    "SoilGrids v2.0 + SHC",
    "cached",
    "sample (offline)",
]


class SoilProfile(BaseModel):
    # provenance
    source: str = "SoilGrids v2.0"
    fetched_at: datetime
    lat: float
    lon: float
    depth_basis: str = "0-30cm depth-weighted"

    # texture / classification
    texture_class: str | None = None  # USDA, derived
    wrb_class: str | None = None
    wrb_probability: float | None = None  # 0..1

    # physical / chemical (0-30 cm depth-weighted means)
    sand_pct: float | None = None
    silt_pct: float | None = None
    clay_pct: float | None = None
    ph: float | None = None
    organic_carbon_g_kg: float | None = None
    organic_carbon_pct: float | None = None
    total_nitrogen_g_kg: float | None = None
    cec_cmol_kg: float | None = None
    bulk_density_kg_dm3: float | None = None
    coarse_fragments_pct: float | None = None

    # plant-available nutrients — Soil Health Card enrichment (nullable)
    available_n_kg_ha: float | None = None
    available_p_kg_ha: float | None = None
    available_k_kg_ha: float | None = None
    shc_district: str | None = None
    shc_state: str | None = None

    uncertainty: SoilUncertainty | None = None

    # full upstream payloads, kept verbatim for transparency
    raw: dict[str, Any] = Field(default_factory=dict)
