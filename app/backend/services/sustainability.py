"""Module D — Sustainability Score.

A pure, published formula so the score is fully reproducible:

    water_overuse%    = max(0, (used - recommended) / recommended * 100)
    water_deficit%    = max(0, (recommended - used) / recommended * 100)
    chemical_overuse% = max(0, (used - recommended) / recommended * 100)
    crop_health%      = 100                if healthy
                        100 - severity[cls] if a disease was diagnosed
    score = clamp(0..100, 100 - 0.4*water_overuse% - 0.4*water_deficit%
                           - 0.3*chemical_overuse% + 0.3*(crop_health% - 100))

water_overuse% and water_deficit% are mutually exclusive (usage is either at
or above the recommendation, or below it — never both), so exactly one of
them is nonzero for any given input; the two terms together make water
adequacy a two-sided band around 100% of the recommendation rather than a
one-sided "only penalise using too much" check. Weighted the same (0.4) as
overuse, since under-watering is not a lesser problem — it costs yield and
crop health the same way overuse costs water resources. A farmer applying
~90-110% of the recommendation lands within ~10 points either way, which is
a light, deliberately soft "optimal band" rather than a hard cutoff; severe
under-watering (e.g. 10% of requirement) costs a correspondingly large
90-point deficit term, matching how severe overuse was already penalised.

When ``GEMINI_API_KEY`` is set, the computed score and inputs are sent to
Gemini for sanity checking — it validates whether the numbers look realistic
and provides context-aware tips.

See ``docs/sustainability.md``.
"""

from __future__ import annotations

import logging

from ..models.modules import SustainabilityRequest, SustainabilityScore
from . import gemini as gemini_service

log = logging.getLogger(__name__)

FORMULA = (
    "score = clamp(0..100, 100 - 0.4*water_overuse% - 0.4*water_deficit% "
    "- 0.3*chemical_overuse% + 0.3*(crop_health% - 100))"
)

# how many health points a diagnosed disease removes (0 = cosmetic, 60 = severe)
_SEVERITY: dict[str, int] = {
    "late_blight": 60, "bacterial_spot": 45, "black_rot": 45, "early_blight": 35,
    # "leaf_mold": the model/disease_cards.json class is the American spelling
    # (Tomato___Leaf_Mold) — the British "leaf_mould" here never matched it
    # and always fell through to the generic default below (which happens to
    # be the same value, 30, so this was silent dead code rather than a
    # visibly wrong score).
    "leaf_mold": 30, "common_rust": 30, "gray_leaf_spot": 35, "scab": 30,
    "esca": 40, "leaf_blight": 35, "spider_mites": 25, "target_spot": 30,
    "mosaic_virus": 55, "yellow_leaf_curl_virus": 55, "powdery_mildew": 30,
}


def _severity(disease_class: str | None) -> int:
    if not disease_class:
        return 0
    key = disease_class.lower().replace(" ", "_").replace("-", "_")
    for name, sev in _SEVERITY.items():
        if name in key:
            return sev
    return 30  # unknown named disease -> moderate


def _overuse_pct(used: float, recommended: float) -> float:
    return round(max(0.0, (used - recommended) / recommended * 100), 1)


def _deficit_pct(used: float, recommended: float) -> float:
    return round(max(0.0, (recommended - used) / recommended * 100), 1)


def _formula_tips(
    water_over: float, water_deficit: float, chem_over: float, crop_health: float,
) -> list[str]:
    """Deterministic, hard-coded tips (used as fallback when Gemini is off)."""
    tips: list[str] = []
    if water_over > 10:
        tips.append(f"Irrigation is {water_over:.0f}% above the crop's need — "
                    "switch to soil‑moisture‑based scheduling or drip to cut waste.")
    if water_deficit > 10:
        tips.append(f"Irrigation is {water_deficit:.0f}% below the crop's need — "
                    "increase watering frequency or volume; sustained deficit risks "
                    "drought stress and yield loss even though it uses less water.")
    if chem_over > 10:
        tips.append(f"Agro‑chemical use is {chem_over:.0f}% above recommendation — "
                    "soil‑test before the next dose and use split/banded application.")
    if crop_health < 100:
        tips.append("Treat the current disease early and rotate crops next season to lift "
                    "crop‑health and the score.")
    if not tips:
        tips.append("Water, chemical use and crop health are all within target — keep it up.")
    return tips[:3]


async def _ai_validate(
    req: SustainabilityRequest,
    score: float,
    band: str,
    water_over: float,
    water_deficit: float,
    chem_over: float,
    crop_health: float,
) -> tuple[list[str], str | None]:
    """Send inputs + computed score to Gemini for sanity checking.

    Returns ``(ai_tips, ai_notes)`` or ``([], None)`` on a missing key,
    timeout, or any other failure — ``gemini_service.generate`` never raises.
    """
    water_status = (
        f"{water_over:.1f}% above requirement" if water_over > 0
        else f"{water_deficit:.1f}% below requirement" if water_deficit > 0
        else "on target"
    )
    prompt = (
        "You are an agricultural sustainability analyst. A farmer submitted these inputs:\n\n"
        f"• Water applied: {req.water_used_mm} mm (recommended: {req.water_recommended_mm} mm) → {water_status}\n"
        f"• Chemicals used: {req.chemical_used_kg_ha} kg/ha (recommended: {req.chemical_recommended_kg_ha} kg/ha) → overuse: {chem_over:.1f}%\n"
        f"• Disease: {req.disease_class or 'None (healthy)'} → crop health: {crop_health:.0f}%\n"
        f"• Computed sustainability score: {score:.1f}/100 ({band})\n\n"
        "Tasks:\n"
        "1. Do these numbers look realistic for a typical Indian smallholder farm? "
        "If anything looks implausible (e.g., absurdly high water, severe under-watering "
        "that risks drought stress, or chemical use > 500 kg/ha), flag it briefly in a "
        "'NOTES' line.\n"
        "2. Provide exactly 3 short, actionable tips specific to these numbers to improve sustainability.\n\n"
        "Reply in this exact format (no markdown, no headings):\n"
        "NOTES: <your validation note or 'Inputs look reasonable.'>\n"
        "TIP1: <tip>\n"
        "TIP2: <tip>\n"
        "TIP3: <tip>"
    )
    text = await gemini_service.generate(prompt)
    if not text:
        return [], None

    ai_notes = None
    ai_tips = []
    for line in text.split("\n"):
        line = line.strip()
        if line.upper().startswith("NOTES:"):
            ai_notes = line[6:].strip()
        elif line.upper().startswith("TIP"):
            # TIP1: ..., TIP2: ..., TIP3: ...
            colon = line.find(":")
            if colon != -1:
                ai_tips.append(line[colon + 1:].strip())
    return ai_tips[:3] if ai_tips else [], ai_notes


async def compute_score(req: SustainabilityRequest) -> SustainabilityScore:
    water_over = _overuse_pct(req.water_used_mm, req.water_recommended_mm)
    water_deficit = _deficit_pct(req.water_used_mm, req.water_recommended_mm)
    chem_over = _overuse_pct(req.chemical_used_kg_ha, req.chemical_recommended_kg_ha)
    crop_health = 100 - _severity(req.disease_class)

    raw = (100 - 0.4 * water_over - 0.4 * water_deficit - 0.3 * chem_over
           + 0.3 * (crop_health - 100))
    score = round(max(0.0, min(100.0, raw)), 1)
    band = ("excellent" if score >= 80 else "good" if score >= 60
            else "fair" if score >= 40 else "poor")

    # Try AI validation
    ai_tips, ai_notes = await _ai_validate(
        req, score, band, water_over, water_deficit, chem_over, crop_health)
    if ai_tips:
        tips = ai_tips
        ai_validated = True
    else:
        tips = _formula_tips(water_over, water_deficit, chem_over, float(crop_health))
        ai_validated = False

    return SustainabilityScore(
        score=score, band=band, water_overuse_pct=water_over,
        water_deficit_pct=water_deficit,
        chemical_overuse_pct=chem_over, crop_health_pct=float(crop_health),
        formula=FORMULA, tips=tips,
        ai_validated=ai_validated, ai_notes=ai_notes,
    )
