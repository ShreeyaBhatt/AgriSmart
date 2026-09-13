"""Schemas for the soil-driven recommendation endpoints (Module A)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .soil import SoilProfile


class RecommendRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    season: str | None = Field(None, description="kharif | rabi | zaid (optional)")
    lang: Literal["en", "hi", "gu"] = "en"


class Amendment(BaseModel):
    category: str            # ph | organic_matter | phosphorus | potassium | nitrogen | texture | cec
    severity: str            # ok | low | high | info
    finding: str             # measured vs. ideal, plain language
    action: str              # concrete step + rate


class AmendmentReport(BaseModel):
    profile: SoilProfile
    amendments: list[Amendment]
    data_gaps: list[str] = Field(default_factory=list)
    citation: str | None = None


class CropScore(BaseModel):
    crop: str
    score: float             # 0..1
    reasons: list[str]
    caveats: list[str] = Field(default_factory=list)


class CropRecommendation(BaseModel):
    profile: SoilProfile
    season: str | None
    ranked: list[CropScore]
    note: str
