"""Read-only, dependency-light access to data/disease_cards.json for routers
that need a localized label/precautions without loading the ML stack.

Deliberately duplicates the small lookup logic in model/infer.py rather than
importing it: model/ must stay importable standalone (its own CLI, no
FastAPI/pydantic-settings dependency) and importing it here would pull torch
into every request to a plain listing endpoint (the whole point of lazily
importing model.infer only inside routers/predict.py).
"""

from __future__ import annotations

import json
from functools import lru_cache

from ..config import get_settings


@lru_cache
def _cards() -> dict:
    try:
        return json.loads(get_settings().disease_cards_path.read_text(encoding="utf-8"))["cards"]
    except Exception:
        return {}


def localized_label_for(label: str, lang: str) -> str | None:
    """"Crop — Disease" in the requested language, or None for healthy/unknown
    classes (the frontend renders those via its own i18n strings instead)."""
    card = _cards().get(label) or {}
    disease = card.get(f"disease_{lang}") if lang != "en" else card.get("disease")
    if not disease:
        return None
    crop = (card.get(f"crop_{lang}") if lang != "en" else card.get("crop")) or card.get("crop") or ""
    return f"{crop} — {disease}".strip(" —")


def precautions_for(label: str, lang: str, fallback: list[str] | None) -> list[str] | None:
    """Precautions in the requested language, falling back to the (English)
    value stored on the diagnosis at scan time if no translation exists."""
    if lang != "en":
        localized = (_cards().get(label) or {}).get(f"precautions_{lang}")
        if localized:
            return localized
    return fallback
