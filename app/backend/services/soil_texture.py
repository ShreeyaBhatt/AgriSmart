"""USDA soil textural triangle — classify a sand/silt/clay mix into one of the
12 USDA texture classes.

SoilGrids returns particle-size fractions but no texture *name*; this pure
function derives it. Inputs are percentages (any positive scale works — they are
renormalised to sum to 100). Boundaries follow the USDA-NRCS Soil Texture
Calculator decision tree; hairline cases may differ from a polygon lookup but the
result is agronomically correct.
"""

from __future__ import annotations

USDA_CLASSES = (
    "sand",
    "loamy sand",
    "sandy loam",
    "loam",
    "silt loam",
    "silt",
    "sandy clay loam",
    "clay loam",
    "silty clay loam",
    "sandy clay",
    "silty clay",
    "clay",
)


def usda_texture(sand: float, silt: float, clay: float) -> str:
    """Return the USDA texture class for the given fractions.

    Raises ValueError if the fractions are non-positive.
    """
    total = sand + silt + clay
    if total <= 0:
        raise ValueError(f"sand+silt+clay must be > 0 (got {sand}, {silt}, {clay})")

    sand = sand * 100.0 / total
    silt = silt * 100.0 / total
    clay = clay * 100.0 / total

    if clay >= 40:
        if silt >= 40:
            return "silty clay"
        if sand <= 45:
            return "clay"
        return "sandy clay"

    if clay >= 27:
        if clay >= 35 and sand > 45:
            return "sandy clay"
        if sand <= 20:
            return "silty clay loam"
        if sand <= 45:
            return "clay loam"
        return "sandy clay loam"

    # clay < 27
    if silt >= 50:
        if clay >= 12:
            return "silt loam"
        if silt >= 80:
            return "silt"
        return "silt loam"

    if silt >= 28:  # silt 28..50, clay < 27
        if clay >= 7 and sand <= 52:
            return "loam"
        return "sandy loam"

    # silt < 28, clay < 27  -> the sandy corner
    if sand >= 85 and (silt + 1.5 * clay) < 15:
        return "sand"
    if sand >= 70 and (silt + 2 * clay) < 30:
        return "loamy sand"
    if clay >= 20:
        return "sandy clay loam"
    return "sandy loam"
