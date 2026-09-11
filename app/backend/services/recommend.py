"""Soil-driven recommendation engines (Module A).

* :func:`recommend_amendments` — pH / organic-matter / CEC advice straight from
  SoilGrids, plus N-P-K dosing from the Soil Health Card enrichment when present.
  When district N-P-K is missing it degrades gracefully to a "get a soil test"
  data gap plus texture-based generic guidance.
* :func:`recommend_crops` — ranks crops in ``data/crop_suitability.json`` on soil
  texture + pH (+ optional season). Climate suitability is deferred to Module C.

All thresholds live in ``data/soil_amendments.json`` / ``data/crop_suitability.json``
so the logic stays transparent and reproducible.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..config import get_settings
from ..models.recommend import Amendment, AmendmentReport, CropRecommendation, CropScore
from ..models.soil import SoilProfile


@lru_cache
def _amendment_rules() -> dict[str, Any]:
    return json.loads(get_settings().soil_amendments_path.read_text(encoding="utf-8"))


@lru_cache
def _crop_rules() -> dict[str, Any]:
    return json.loads(get_settings().crop_suitability_path.read_text(encoding="utf-8"))


def reset_cache() -> None:
    _amendment_rules.cache_clear()
    _crop_rules.cache_clear()


def _band(value: float, table: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    """Return the first (band_name, rule) whose min/max window contains ``value``."""
    for name, rule in table.items():
        lo, hi = rule.get("min"), rule.get("max")
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return name, rule
    return None


_SEVERITY = {
    "strongly_acidic": "low", "acidic": "info", "neutral": "ok", "alkaline": "info",
    "strongly_alkaline": "high", "low": "low", "medium": "ok", "high": "high",
}


def _fmt(text: str, value: float) -> str:
    return text.replace("{value}", f"{value:g}")


def recommend_amendments(profile: SoilProfile) -> AmendmentReport:
    rules = _amendment_rules()
    out: list[Amendment] = []
    gaps: list[str] = []

    def add(category: str, value: float | None, table_key: str) -> None:
        if value is None:
            return
        hit = _band(value, rules[table_key])
        if not hit:
            return
        band, rule = hit
        out.append(Amendment(
            category=category,
            severity=_SEVERITY.get(band, "info"),
            finding=_fmt(rule["finding"], value),
            action=rule["action"],
        ))

    add("ph", profile.ph, "ph")
    add("organic_matter", profile.organic_carbon_pct, "organic_carbon_pct")
    add("cec", profile.cec_cmol_kg, "cec_cmol_kg")

    if profile.available_n_kg_ha is not None:
        add("nitrogen", profile.available_n_kg_ha, "available_n_kg_ha")
    else:
        gaps.append("No Soil Health Card nitrogen for this district - N advice is based on organic carbon only.")
        if profile.organic_carbon_pct is not None and profile.organic_carbon_pct < 0.5:
            out.append(Amendment(
                category="nitrogen", severity="low",
                finding="Low organic carbon implies low N-supplying capacity.",
                action="Apply the crop's full recommended N in 3 splits until a soil test is available.",
            ))

    if profile.available_p_kg_ha is not None:
        add("phosphorus", profile.available_p_kg_ha, "available_p_kg_ha")
    else:
        gaps.append("No Soil Health Card phosphorus for this district - get a soil test before fixing P doses.")

    if profile.available_k_kg_ha is not None:
        add("potassium", profile.available_k_kg_ha, "available_k_kg_ha")
    else:
        gaps.append("No Soil Health Card potassium for this district - get a soil test before fixing K doses.")

    if profile.texture_class:
        note = rules["texture_notes"].get(profile.texture_class)
        if note:
            out.append(Amendment(
                category="texture", severity="info",
                finding=f"Soil texture is {profile.texture_class}.", action=note,
            ))

    return AmendmentReport(
        profile=profile, amendments=out, data_gaps=gaps, citation=rules.get("citation"),
    )


def _score_crop(crop: dict[str, Any], profile: SoilProfile, season: str | None) -> CropScore:
    reasons: list[str] = []
    caveats: list[str] = []
    score = 0.0

    texture_ok = profile.texture_class in crop.get("textures", [])
    if texture_ok:
        score += 0.55
        reasons.append(f"{profile.texture_class} soil suits this crop")
    elif profile.texture_class:
        caveats.append(f"{profile.texture_class} is not an ideal texture ({', '.join(crop['textures'])})")

    lo, hi = crop.get("ph", [0, 14])
    if profile.ph is not None:
        if lo <= profile.ph <= hi:
            score += 0.30
            reasons.append(f"pH {profile.ph:g} is within the {lo}-{hi} range")
        else:
            caveats.append(f"pH {profile.ph:g} is outside the preferred {lo}-{hi} range")
    else:
        caveats.append("soil pH unknown")

    if season:
        if season.lower() in [s.lower() for s in crop.get("seasons", [])]:
            score += 0.15
            reasons.append(f"grown in {season}")
        else:
            caveats.append(f"not a typical {season} crop")

    if crop.get("notes"):
        caveats.append(crop["notes"])

    return CropScore(crop=crop["name"], score=round(min(score, 1.0), 2), reasons=reasons, caveats=caveats)


def recommend_crops(profile: SoilProfile, season: str | None = None) -> CropRecommendation:
    crops = _crop_rules()["crops"]
    ranked = sorted(
        (_score_crop(c, profile, season) for c in crops),
        key=lambda cs: cs.score, reverse=True,
    )
    return CropRecommendation(
        profile=profile,
        season=season,
        ranked=ranked,
        note="Ranked on soil texture and pH"
             + (" and season" if season else "")
             + ". Climate suitability (temperature, rainfall) is scored separately by Module C.",
    )
