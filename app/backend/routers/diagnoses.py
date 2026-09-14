"""Diagnosis history (auth-scoped)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..config import get_settings
from ..db import get_session
from ..models.farm import DiagnosisOut
from ..models.orm import Diagnosis
from ..models.user import User
from ..services.disease_cards import localized_label_for, precautions_for

router = APIRouter(prefix="/diagnoses", tags=["diagnoses"])


def _url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/uploads/{Path(path).relative_to(get_settings().uploads_dir).as_posix()}"


def _out(d: Diagnosis, lang: str = "en") -> DiagnosisOut:
    label = None if d.abstained else localized_label_for(d.predicted_class, lang)
    return DiagnosisOut(
        id=d.id, plot_id=d.plot_id, planting_id=d.planting_id,
        image_url=_url(d.image_path), gradcam_url=_url(d.gradcam_path),
        predicted_class=d.predicted_class, predicted_label=label,
        confidence=d.confidence, abstained=d.abstained,
        precautions=precautions_for(d.predicted_class, lang, d.precautions),
        model_version=d.model_version, crop_warning=d.crop_warning, created_at=d.created_at,
    )


@router.get("", response_model=list[DiagnosisOut])
async def list_diagnoses(
    plot_id: str | None = None,
    limit: int = 50,
    lang: str = "en",
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[DiagnosisOut]:
    q = select(Diagnosis).where(Diagnosis.owner_id == user.id).order_by(Diagnosis.created_at.desc()).limit(limit)
    if plot_id:
        q = q.where(Diagnosis.plot_id == plot_id)
    return [_out(d, lang) for d in await session.scalars(q)]


@router.get("/{diagnosis_id}", response_model=DiagnosisOut)
async def get_diagnosis(
    diagnosis_id: str,
    lang: str = "en",
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> DiagnosisOut:
    d = await session.get(Diagnosis, diagnosis_id)
    if d is None or d.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnosis not found")
    return _out(d, lang)
