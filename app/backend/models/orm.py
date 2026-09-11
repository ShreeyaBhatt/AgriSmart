"""SQLAlchemy ORM models — the per‑farmer app database (SQLite).

Accounts (``User``) live in MongoDB instead (see ``models/user.py`` and
``services/users.py``) — every table here carries a plain ``owner_id``
string (not a SQL foreign key, since it points at a different database) and
every query is filtered by the current user in application code.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Plot(Base):
    __tablename__ = "plots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)  # a Mongo User.id
    name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    area_ha: Mapped[float | None] = mapped_column(Float, default=None)
    soil_snapshot: Mapped[dict | None] = mapped_column(JSON, default=None)  # a SoilProfile dict
    soil_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Planting(Base):
    __tablename__ = "plantings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)  # a Mongo User.id
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    variety: Mapped[str | None] = mapped_column(String(120), default=None)
    sowing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    stage: Mapped[str | None] = mapped_column(String(40), default=None)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | harvested
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)  # a Mongo User.id
    plot_id: Mapped[str | None] = mapped_column(ForeignKey("plots.id"), index=True, default=None)
    planting_id: Mapped[str | None] = mapped_column(ForeignKey("plantings.id"), default=None)
    image_path: Mapped[str] = mapped_column(String(255))
    gradcam_path: Mapped[str | None] = mapped_column(String(255), default=None)
    predicted_class: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float)
    abstained: Mapped[bool] = mapped_column(default=False)
    precautions: Mapped[list | None] = mapped_column(JSON, default=None)
    model_version: Mapped[str | None] = mapped_column(String(60), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class IrrigationEvent(Base):
    __tablename__ = "irrigation_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)  # a Mongo User.id
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    method: Mapped[str | None] = mapped_column(String(40), default=None)
    amount_mm: Mapped[float | None] = mapped_column(Float, default=None)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual | weather_advice
    note: Mapped[str | None] = mapped_column(Text, default=None)


class FarmerAction(Base):
    __tablename__ = "farmer_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)  # a Mongo User.id
    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    action_type: Mapped[str] = mapped_column(String(40))  # spray | lime | compost | crop_change | other
    details: Mapped[str | None] = mapped_column(Text, default=None)
    linked_diagnosis_id: Mapped[str | None] = mapped_column(ForeignKey("diagnoses.id"), default=None)
