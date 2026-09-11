"""Module D — Sustainability Score.

A pure, published formula so the score is fully reproducible:

    water_overuse%    = max(0, (used - recommended) / recommended * 100)
    chemical_overuse% = max(0, (used - recommended) / recommended * 100)
    crop_health%      = 100                if healthy
                        100 - severity[cls] if a disease was diagnosed
    score = clamp(0..100, 100 - 0.4*water_overuse% - 0.3*chemical_overuse% + 0.3*(crop_health% - 100))

See ``docs/sustainability.md``.
"""

from __future__ import annotations

from ..models.modules import SustainabilityRequest, SustainabilityScore

FORMULA = (
    "score = clamp(0..100, 100 - 0.4*water_overuse% - 0.3*chemical_overuse% "
    "+ 0.3*(crop_health% - 100))"
)

# how many health points a diagnosed disease removes (0 = cosmetic, 60 = severe)
_SEVERITY: dict[str, int] = {
    "late_blight": 60, "bacterial_spot": 45, "black_rot": 45, "early_blight": 35,
    "leaf_mould": 30, "common_rust": 30, "gray_leaf_spot": 35, "scab": 30,
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


def compute_score(req: SustainabilityRequest) -> SustainabilityScore:
    water_over = _overuse_pct(req.water_used_mm, req.water_recommended_mm)
    chem_over = _overuse_pct(req.chemical_used_kg_ha, req.chemical_recommended_kg_ha)
    crop_health = 100 - _severity(req.disease_class)

    raw = 100 - 0.4 * water_over - 0.3 * chem_over + 0.3 * (crop_health - 100)
    score = round(max(0.0, min(100.0, raw)), 1)
    band = ("excellent" if score >= 80 else "good" if score >= 60
            else "fair" if score >= 40 else "poor")

    tips: list[str] = []
    if water_over > 10:
        tips.append(f"Irrigation is {water_over:.0f}% above the crop's need — "
                    "switch to soil‑moisture‑based scheduling or drip to cut waste.")
    if chem_over > 10:
        tips.append(f"Agro‑chemical use is {chem_over:.0f}% above recommendation — "
                    "soil‑test before the next dose and use split/banded application.")
    if crop_health < 100:
        tips.append("Treat the current disease early and rotate crops next season to lift "
                    "crop‑health and the score.")
    if not tips:
        tips.append("Water, chemical use and crop health are all within target — keep it up.")

    return SustainabilityScore(
        score=score, band=band, water_overuse_pct=water_over,
        chemical_overuse_pct=chem_over, crop_health_pct=float(crop_health),
        formula=FORMULA, tips=tips[:3],
    )
