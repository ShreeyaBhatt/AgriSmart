"""Core task — crop-disease detection from a leaf photo."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..config import get_settings
from ..db import get_session
from ..models.farm import DiagnosisOut
from ..models.orm import Diagnosis, Planting, Plot
from ..models.user import User

log = logging.getLogger(__name__)
router = APIRouter(tags=["predict"])
_ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024  # a phone photo is a few MB; 15MB is generous — matches /assistant/transcribe's cap


def _diag_out(d: Diagnosis, predicted_label: str | None = None) -> DiagnosisOut:
    return DiagnosisOut(
        id=d.id, plot_id=d.plot_id, planting_id=d.planting_id,
        image_url=f"/uploads/{Path(d.image_path).relative_to(get_settings().uploads_dir).as_posix()}",
        gradcam_url=(
            f"/uploads/{Path(d.gradcam_path).relative_to(get_settings().uploads_dir).as_posix()}"
            if d.gradcam_path else None
        ),
        predicted_class=d.predicted_class, predicted_label=predicted_label,
        confidence=d.confidence, abstained=d.abstained,
        precautions=d.precautions, model_version=d.model_version, created_at=d.created_at,
    )


@router.post("/predict", response_model=DiagnosisOut)
async def predict(
    file: UploadFile = File(...),
    plot_id: str | None = Form(default=None),
    planting_id: str | None = Form(default=None),
    lang: str = Form(default="en"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> DiagnosisOut:
    if file.content_type not in _ALLOWED:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a JPEG, PNG or WebP image")

    if plot_id:
        plot = await session.get(Plot, plot_id)
        if plot is None or plot.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Plot not found")
    if planting_id:
        planting = await session.get(Planting, planting_id)
        if planting is None or planting.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Planting not found")

    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image too large")

    settings = get_settings()
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/bmp": ".bmp"}[file.content_type]
    scan_id = uuid.uuid4().hex
    user_dir = settings.uploads_dir / user.id
    user_dir.mkdir(parents=True, exist_ok=True)
    image_path = user_dir / f"{scan_id}{ext}"
    image_path.write_bytes(data)
    gradcam_path = user_dir / f"{scan_id}_gradcam.png"

    try:
        from model.infer import run_inference  # lazy: torch only loaded when scanning
        # run_inference is a synchronous, CPU-bound torch forward pass — off the
        # event loop so one person's scan doesn't stall every other request
        # (weather, soil, everything) for its whole duration.
        result = await asyncio.to_thread(run_inference, str(image_path), gradcam_out=gradcam_path, lang=lang)
        # Prevent treatment advice for predictions that don't match
        # the crop registered for the plot.
        if plot_id and plot.main_crop and not result["abstained"]:
            predicted_crop = result["raw_class"].split("___", 1)[0].strip().lower()
            registered_crop = plot.main_crop.strip().lower()

            if predicted_crop != registered_crop:
                log.warning(
                "Crop mismatch: registered=%s predicted=%s",
                registered_crop,
                predicted_crop,
            )
            result["precautions"] = []
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"The disease model is not trained yet. {exc}")
    except Exception as exc:  # pragma: no cover
        log.exception("inference failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Inference failed: {exc}")

    diagnosis = Diagnosis(
        owner_id=user.id, plot_id=plot_id, planting_id=planting_id,
        image_path=str(image_path),
        gradcam_path=result.get("gradcam_path"),
        predicted_class=result["predicted_class"],
        confidence=result["confidence"],
        abstained=result["abstained"],
        precautions=result["precautions"],
        model_version=result["model_version"],
    )
    session.add(diagnosis)
    await session.commit()
    await session.refresh(diagnosis)
    return _diag_out(diagnosis, predicted_label=result.get("predicted_label"))
