"""Pydantic schemas for plots, plantings, diagnoses and activity logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Plots
# --------------------------------------------------------------------------- #
class PlotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    area_ha: float | None = Field(default=None, ge=0)


class PlotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    area_ha: float | None = Field(default=None, ge=0)


class PlotOut(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    area_ha: float | None
    soil_snapshot: dict[str, Any] | None
    soil_fetched_at: datetime | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Plantings
# --------------------------------------------------------------------------- #
class PlantingCreate(BaseModel):
    plot_id: str
    name: str = Field(min_length=1, max_length=120)
    variety: str | None = None
    sowing_date: datetime | None = None
    stage: str | None = None


class PlantingUpdate(BaseModel):
    variety: str | None = None
    stage: str | None = None
    status: Literal["active", "harvested"] | None = None


class PlantingOut(BaseModel):
    id: str
    plot_id: str
    name: str
    variety: str | None
    sowing_date: datetime | None
    stage: str | None
    status: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Diagnoses
# --------------------------------------------------------------------------- #
class DiagnosisOut(BaseModel):
    id: str
    plot_id: str | None
    planting_id: str | None
    image_url: str
    gradcam_url: str | None
    predicted_class: str
    confidence: float
    abstained: bool
    precautions: list[str] | None
    model_version: str | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Activity logs
# --------------------------------------------------------------------------- #
class IrrigationCreate(BaseModel):
    plot_id: str
    at: datetime | None = None
    method: str | None = None
    amount_mm: float | None = Field(default=None, ge=0)
    trigger: Literal["manual", "weather_advice"] = "manual"
    note: str | None = None


class ActionCreate(BaseModel):
    plot_id: str
    at: datetime | None = None
    action_type: Literal["spray", "lime", "compost", "crop_change", "irrigation", "other"]
    details: str | None = None
    linked_diagnosis_id: str | None = None


class TimelineEntry(BaseModel):
    kind: Literal["diagnosis", "irrigation", "action"]
    at: datetime
    title: str
    detail: str | None = None
    ref_id: str


class Timeline(BaseModel):
    plot_id: str
    entries: list[TimelineEntry]
