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
    from .predict import ARTIFACTS_DIR, TAU, _model, predict_detailed
    from .labels import ABSTAIN_LABEL
    from .dataset import eval_transform
    from .gradcam import overlay
except ImportError:
    from predict import ARTIFACTS_DIR, TAU, _model, predict_detailed
    from labels import ABSTAIN_LABEL
    from dataset import eval_transform
    from gradcam import overlay

log = logging.getLogger(__name__)

_ABSTAIN_PRECAUTIONS = {
    "en": [
        "The photo was unclear — take another in good daylight",
        "Fill the frame with a single affected leaf on a plain background",
        "Hold the phone steady and tap to focus",
    ],
    "hi": [
        "फोटो साफ़ नहीं थी — अच्छी रोशनी में दोबारा फोटो लें",
        "सादे background पर एक प्रभावित पत्ती से पूरा फ्रेम भरें",
        "फोन को स्थिर रखें और फोकस के लिए टैप करें",
    ],
    "gu": [
        "ફોટો સ્પષ્ટ ન હતો — સારા દિવસના પ્રકાશમાં ફરી ફોટો લો",
        "સાદા બેકગ્રાઉન્ડ પર એક અસરગ્રસ્ત પાનથી આખી ફ્રેમ ભરો",
        "ફોનને સ્થિર રાખો અને ફોકસ માટે ટૅપ કરો",
    ],
}
_GENERIC_PRECAUTIONS = {
    "en": [
        "Scout the crop again in 2-3 days",
        "Remove and destroy badly affected leaves",
        "Keep foliage dry — water at the base, early in the day",
    ],
    "hi": [
        "2-3 दिन बाद फिर से फसल की जाँच करें",
        "बुरी तरह प्रभावित पत्तियों को हटाकर नष्ट करें",
        "पत्तियों को सूखा रखें — सुबह जड़ में पानी दें",
    ],
    "gu": [
        "2-3 દિવસ પછી ફરી પાકનું નિરીક્ષણ કરો",
        "ખરાબ રીતે અસરગ્રસ્ત પાંદડાં દૂર કરી નષ્ટ કરો",
        "પાંદડાં સૂકાં રાખો — સવારે મૂળમાં પાણી આપો",
    ],
}


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


def precautions_for(label: str, abstained: bool, lang: str = "en") -> list[str]:
    if abstained:
        return _ABSTAIN_PRECAUTIONS.get(lang, _ABSTAIN_PRECAUTIONS["en"])
    card = _cards().get(label) or {}
    localized = card.get(f"precautions_{lang}") if lang != "en" else None
    return localized or card.get("precautions") or _GENERIC_PRECAUTIONS.get(lang, _GENERIC_PRECAUTIONS["en"])


def localized_label_for(label: str, lang: str) -> str | None:
    """"Crop — Disease" in the requested language, or None for healthy/unknown
    classes (the frontend already renders those via its own i18n strings)."""
    card = _cards().get(label) or {}
    disease = card.get(f"disease_{lang}") if lang != "en" else card.get("disease")
    if not disease:
        return None
    crop = card.get(f"crop_{lang}") if lang != "en" else card.get("crop")
    crop = crop or card.get("crop") or ""
    return f"{crop} — {disease}".strip(" —")


def run_inference(image_path: str, gradcam_out: Path | None = None, lang: str = "en") -> dict:
    result = predict_detailed(image_path)  # {predicted_class, raw_class, confidence, abstained, top3}
    result["model_version"] = model_version()
    result["precautions"] = precautions_for(result["raw_class"], result["abstained"], lang)
    result["predicted_label"] = (
        None if result["abstained"] else localized_label_for(result["raw_class"], lang)
    )
    result["gradcam_path"] = None
    result["pretty_top3"] = result["top3"]

    if gradcam_out is not None and not result["abstained"]:
        try:
            tm = _model()  # reuse predict.py's cached singleton, not a fresh disk load
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
