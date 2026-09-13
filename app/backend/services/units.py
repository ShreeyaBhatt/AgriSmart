"""Land-area unit conversion, for display purposes only.

A plot's area is always stored and transmitted as hectares (see
``models.orm.Plot.area_ha`` / ``models.farm.PlotCreate.area_ha``) — nothing
downstream (crop recommendation, sustainability scoring, soil analysis)
reads any other unit, so there's nothing to migrate. This module exists so
the Farm Assistant can mention a plot's size in whatever unit the farmer
actually thinks in, instead of always saying hectares.

The frontend does the equivalent conversion for the UI itself
(app/frontend/src/units/convert.js) — keep the constants below in step with
that file if either changes.
"""

from __future__ import annotations

from typing import Literal

LandUnit = Literal["ha", "acre", "bigha", "guntha"]

HECTARE_PER_ACRE = 0.40468564224  # internationally defined acre
GUNTHA_PER_ACRE = 40  # standard revenue unit — Maharashtra, Karnataka, ...

# Bigha was never standardised — it varies by state, and sometimes by
# district within a state. These are commonly-cited reference values, not
# legal figures; a farmer relying on this for anything official should
# still confirm the exact local figure with their revenue office.
_BIGHA_ACRE: dict[str, float] = {
    "gujarat": 0.4,  # 17,424 sq ft
    "rajasthan_pucca": 0.625,  # 27,225 sq ft
    "rajasthan_kaccha": 0.4,  # 17,424 sq ft
    "up": 0.625,
    "bihar": 0.625,
    "punjab": 0.5,  # 21,780 sq ft
    "west_bengal": 14_400 / 43_560,
    "assam": 14_400 / 43_560,
}
_DEFAULT_BIGHA_REGION = "gujarat"

_UNIT_LABEL = {"ha": "hectares", "acre": "acres", "bigha": "bigha", "guntha": "guntha"}


def from_hectares(ha: float, unit: LandUnit, bigha_region: str | None = None) -> float:
    """Convert a stored hectare value into ``unit`` for display."""
    acres = ha / HECTARE_PER_ACRE
    if unit == "acre":
        return acres
    if unit == "guntha":
        return acres * GUNTHA_PER_ACRE
    if unit == "bigha":
        factor = _BIGHA_ACRE.get(bigha_region or _DEFAULT_BIGHA_REGION, _BIGHA_ACRE[_DEFAULT_BIGHA_REGION])
        return acres / factor
    return ha


def describe_area(ha: float | None, unit: LandUnit = "ha", bigha_region: str | None = None) -> str | None:
    """A short "<value> <unit>" string for the assistant's prompt context, in
    the farmer's preferred unit rather than always hectares. None if the plot
    has no recorded area."""
    if ha is None:
        return None
    value = from_hectares(ha, unit, bigha_region)
    decimals = 1 if unit in ("bigha", "guntha") else 2
    return f"{value:.{decimals}f} {_UNIT_LABEL.get(unit, 'hectares')}"
