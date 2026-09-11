"""Shared inference for the API: predict + Grad-CAM + farmer precautions.

Keeps ``predict.py`` a thin CLI; the FastAPI ``/predict`` route calls
:func:`run_inference` here.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

import torch
from PIL import Image, ImageOps

try:
    from .predict import ARTIFACTS_DIR, TAU, predict_detailed
    from .net import load_trained
    from .labels import ABSTAIN_LABEL
    from .dataset import eval_transform
    from .gradcam import overlay
except ImportError:
    from predict import ARTIFACTS_DIR, TAU, predict_detailed
    from net import load_trained
    from labels import ABSTAIN_LABEL
    from dataset import eval_transform
    from gradcam import overlay

log = logging.getLogger(__name__)

_ABSTAIN_PRECAUTIONS = [
    "The photo was unclear — take another in good daylight",
    "Fill the frame with a single affected leaf on a plain background",
    "Hold the phone steady and tap to focus",
]
_GENERIC_PRECAUTIONS = [
    "Scout the crop again in 2-3 days",
    "Remove and destroy badly affected leaves",
    "Keep foliage dry — water at the base, early in the day",
]


@lru_cache
def _cards() -> dict:
    root = Path(__file__).resolve().parents[1]
    try:
        return json.loads((root / "data" / "disease_cards.json").read_text(encoding="utf-8"))["cards"]
    except Exception:
        return {}


@lru_cache
def _meta() -> dict:
    try:
        return json.loads((ARTIFACTS_DIR / "class_map.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def model_version() -> str:
    m = _meta()
    return f"{m.get('backbone', 'efficientnet_b0')}-{len(m.get('classes', []))}c"


def precautions_for(label: str, abstained: bool) -> list[str]:
    if abstained:
        return _ABSTAIN_PRECAUTIONS
    card = _cards().get(label)
    return (card or {}).get("precautions") or _GENERIC_PRECAUTIONS


def run_inference(image_path: str, gradcam_out: Path | None = None) -> dict:
    result = predict_detailed(image_path)  # {predicted_class, raw_class, confidence, abstained, top3}
    result["model_version"] = model_version()
    result["precautions"] = precautions_for(result["raw_class"], result["abstained"])
    result["gradcam_path"] = None
    result["pretty_top3"] = result["top3"]

    if gradcam_out is not None and not result["abstained"]:
        try:
            tm = load_trained(ARTIFACTS_DIR)
            img_size = _meta().get("img_size", 192)
            img = Image.open(image_path).convert("RGB")
            tf = eval_transform(img_size)
            batch = torch.stack([tf(img), tf(ImageOps.mirror(img))])
            cls_idx = tm.classes.index(result["raw_class"])
            vis = overlay(tm.model, batch, img, cls_idx, img_size)
            if vis is not None:
                gradcam_out.parent.mkdir(parents=True, exist_ok=True)
                vis.save(gradcam_out)
                result["gradcam_path"] = str(gradcam_out)
        except Exception as exc:
            log.warning("Grad-CAM generation skipped: %s", exc)

    return result
