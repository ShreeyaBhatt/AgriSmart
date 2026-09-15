"""Pydantic schemas for Modules C (weather), D (sustainability), E (assistant)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Module C — Weather Intelligence
# --------------------------------------------------------------------------- #
class WeatherAdviceRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    crop: str | None = None
    stage: str | None = None
    last_disease: str | None = None
    lang: Literal["en", "hi", "gu", "mr", "ta", "te", "pa"] = "en"


class WeatherAction(BaseModel):
    severity: Literal["info", "watch", "act", "recommend"]
    headline: str
    detail: str


class WeatherAdvice(BaseModel):
    source: str = "Open-Meteo"
    lat: float
    lon: float
    summary: dict
    actions: list[WeatherAction]


# --------------------------------------------------------------------------- #
# Module D — Sustainability Score
# --------------------------------------------------------------------------- #
class SustainabilityRequest(BaseModel):
    water_used_mm: float = Field(ge=0, description="season irrigation applied, mm")
    water_recommended_mm: float = Field(gt=0, description="crop water requirement, mm")
    chemical_used_kg_ha: float = Field(ge=0, description="fertiliser + pesticide active, kg/ha")
    chemical_recommended_kg_ha: float = Field(gt=0)
    disease_class: str | None = Field(default=None, description="latest diagnosis, or null if healthy")
    lang: Literal["en", "hi", "gu", "mr", "ta", "te", "pa"] = "en"


class SustainabilityScore(BaseModel):
    score: float
    band: Literal["poor", "fair", "good", "excellent"]
    water_overuse_pct: float
    water_deficit_pct: float
    chemical_overuse_pct: float
    crop_health_pct: float
    formula: str
    tips: list[str]
    ai_validated: bool = False
    ai_notes: str | None = None


# --------------------------------------------------------------------------- #
# Module E — GenAI Farmer Assistant
# --------------------------------------------------------------------------- #
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ActionShortcut(BaseModel):
    label: str
    icon: str
    route: str


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    plot_id: str | None = None
    lang: Literal["en", "hi", "gu", "mr", "ta", "te", "pa"] = "en"
    land_unit: Literal["ha", "acre", "bigha", "guntha"] = "ha"
    bigha_region: str | None = None  # only meaningful when land_unit == "bigha"
    history: list[ChatMessage] | None = None


class AssistantAnswer(BaseModel):
    answer: str
    grounded_on: list[str]  # disease-card ids / context keys used
    used_llm: bool
    lang: str
    engine: str = "Tier 1 Deterministic Core"
    suggested_followups: list[str] = Field(default_factory=list)
    action_shortcuts: list[ActionShortcut] = Field(default_factory=list)


class TranscribeOut(BaseModel):
    text: str
