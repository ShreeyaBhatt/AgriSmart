"""Soil-driven recommendation engines (Module A).

* :func:`recommend_amendments` — pH / organic-matter / CEC advice straight from
  SoilGrids, plus N-P-K dosing from the Soil Health Card enrichment when present.
  When district N-P-K is missing it degrades gracefully to a "get a soil test"
  data gap plus texture-based generic guidance.
* :func:`recommend_crops` — ranks crops in ``data/crop_suitability.json`` on soil
  texture + pH (+ optional season). Climate suitability is deferred to Module C.

All thresholds live in ``data/soil_amendments.json`` / ``data/crop_suitability.json``
so the logic stays transparent and reproducible.

Localization: /predict pre-translates via data/disease_cards.json's "<field>_<lang>"
siblings, and Module C (weather.py) hand-writes per-language message dicts in
Python. This module follows the *first* convention (translated content stays
data, not code) since that's what it already committed to: every user-facing
string here is either a "<field>_<lang>" sibling added to the rule tables by
scripts/generate_translations.py (English is the untouched original field —
translating never risks changing English output), or — for the handful of
sentences composed dynamically from those rules (e.g. "{texture} soil suits
this crop") — a template in data/phrase_templates.json, keyed and looked up the
same way. Every lookup falls back to English if a translation is missing.
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


@lru_cache
def _texture_labels() -> dict[str, dict[str, str]]:
    try:
        return json.loads(get_settings().texture_labels_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


@lru_cache
def _phrases() -> dict[str, dict[str, str]]:
    try:
        return json.loads(get_settings().phrase_templates_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def reset_cache() -> None:
    _amendment_rules.cache_clear()
    _crop_rules.cache_clear()
    _texture_labels.cache_clear()
    _phrases.cache_clear()


def _field(d: dict[str, Any], field: str, lang: str) -> Any:
    """d[<field>_<lang>] if present and lang != en, else the English d[field]."""
    if lang != "en":
        v = d.get(f"{field}_{lang}")
        if v:
            return v
    return d.get(field)


def _texture_label(texture: str | None, lang: str) -> str | None:
    if not texture:
        return texture
    entry = _texture_labels().get(texture)
    if not entry:
        return texture
    return entry.get(lang) or entry.get("en") or texture


def _phrase(key: str, lang: str, **fields: Any) -> str:
    """Look up a data/phrase_templates.json template and fill in {fields}."""
    entry = _phrases().get(key)
    if not entry:
        return ""
    template = entry.get(lang) or entry.get("en") or ""
    try:
        return template.format(**fields)
    except (KeyError, IndexError):
        return (entry.get("en") or "").format(**fields)


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


def recommend_amendments(profile: SoilProfile, lang: str = "en") -> AmendmentReport:
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
            finding=_fmt(_field(rule, "finding", lang), value),
            action=_field(rule, "action", lang),
        ))

    add("ph", profile.ph, "ph")
    add("organic_matter", profile.organic_carbon_pct, "organic_carbon_pct")
    add("cec", profile.cec_cmol_kg, "cec_cmol_kg")

    if profile.available_n_kg_ha is not None:
        add("nitrogen", profile.available_n_kg_ha, "available_n_kg_ha")
    else:
        gaps.append(_phrase("amendment_gap_nitrogen", lang))
        if profile.organic_carbon_pct is not None and profile.organic_carbon_pct < 0.5:
            out.append(Amendment(
                category="nitrogen", severity="low",
                finding=_phrase("amendment_low_oc_n_finding", lang),
                action=_phrase("amendment_low_oc_n_action", lang),
            ))

    if profile.available_p_kg_ha is not None:
        add("phosphorus", profile.available_p_kg_ha, "available_p_kg_ha")
    else:
        gaps.append(_phrase("amendment_gap_phosphorus", lang))

    if profile.available_k_kg_ha is not None:
        add("potassium", profile.available_k_kg_ha, "available_k_kg_ha")
    else:
        gaps.append(_phrase("amendment_gap_potassium", lang))

    if profile.texture_class:
        texture_notes = rules.get("texture_notes", {})
        texture_notes_lang = rules.get(f"texture_notes_{lang}", {}) if lang != "en" else {}
        note = texture_notes_lang.get(profile.texture_class) or texture_notes.get(profile.texture_class)
        if note:
            out.append(Amendment(
                category="texture", severity="info",
                finding=_phrase("amendment_texture_finding", lang,
                                texture=_texture_label(profile.texture_class, lang)),
                action=note,
            ))

    return AmendmentReport(
        profile=profile, amendments=out, data_gaps=gaps,
        citation=_field(rules, "citation", lang),
    )


def _score_crop(crop: dict[str, Any], profile: SoilProfile, season: str | None, lang: str) -> CropScore:
    reasons: list[str] = []
    caveats: list[str] = []
    score = 0.0

    texture_label = _texture_label(profile.texture_class, lang)
    texture_ok = profile.texture_class in crop.get("textures", [])
    if texture_ok:
        score += 0.55
        reasons.append(_phrase("crop_texture_match", lang, texture=texture_label))
    elif profile.texture_class:
        options = ", ".join(_texture_label(t, lang) for t in crop["textures"])
        caveats.append(_phrase("crop_texture_mismatch", lang, texture=texture_label, options=options))

    lo, hi = crop.get("ph", [0, 14])
    if profile.ph is not None:
        if lo <= profile.ph <= hi:
            score += 0.30
            reasons.append(_phrase("crop_ph_in_range", lang, ph=f"{profile.ph:g}", lo=lo, hi=hi))
        else:
            caveats.append(_phrase("crop_ph_out_of_range", lang, ph=f"{profile.ph:g}", lo=lo, hi=hi))
    else:
        caveats.append(_phrase("crop_ph_unknown", lang))

    if season:
        if season.lower() in [s.lower() for s in crop.get("seasons", [])]:
            score += 0.15
            reasons.append(_phrase("crop_season_match", lang, season=season))
        else:
            caveats.append(_phrase("crop_season_mismatch", lang, season=season))

    notes = _field(crop, "notes", lang)
    if notes:
        caveats.append(notes)

    return CropScore(
        crop=_field(crop, "name", lang),
        score=round(min(score, 1.0), 2), reasons=reasons, caveats=caveats,
    )


def recommend_crops(profile: SoilProfile, season: str | None = None, lang: str = "en") -> CropRecommendation:
    crops = _crop_rules()["crops"]
    ranked = sorted(
        (_score_crop(c, profile, season, lang) for c in crops),
        key=lambda cs: cs.score, reverse=True,
    )
    note = (
        _phrase("crop_note_base", lang)
        + (_phrase("crop_note_and_season", lang) if season else "")
        + _phrase("crop_note_suffix", lang)
    )
    return CropRecommendation(profile=profile, season=season, ranked=ranked, note=note)
