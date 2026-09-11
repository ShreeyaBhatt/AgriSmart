"""Soil Health Card reference lookup.

SoilGrids has total N but no plant-available P or K. The Government of India Soil
Health Card scheme publishes district/block averages of available N / P2O5 / K2O.
Those are pre-loaded (see ``scripts/load_shc_reference.py``) into JSON files under
``data/shc_reference/`` and looked up here by district name.

File format (one file per state, ``data/shc_reference/<state>.json``)::

    {
      "state": "Gujarat",
      "source": "Soil Health Card portal (soilhealth.dac.gov.in), 2023-24 cycle",
      "districts": {
        "vadodara": {
          "available_n_kg_ha": 240, "available_p_kg_ha": 22, "available_k_kg_ha": 310
        },
        ...
      }
    }
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any, NamedTuple

from ..config import get_settings

log = logging.getLogger(__name__)


class ShcRecord(NamedTuple):
    available_n_kg_ha: float | None
    available_p_kg_ha: float | None
    available_k_kg_ha: float | None
    district: str
    state: str | None
    source: str | None


def _norm(name: str) -> str:
    """Lowercase, strip punctuation and a trailing 'district' so OSM and SHC names match."""
    name = name.lower().strip()
    name = re.sub(r"\bdistrict\b", "", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return name.strip()


@lru_cache
def _index() -> dict[str, ShcRecord]:
    """Build ``normalised district -> ShcRecord`` across every state file. Cached."""
    settings = get_settings()
    idx: dict[str, ShcRecord] = {}
    ref_dir = settings.shc_reference_dir
    if not ref_dir.is_dir():
        log.info("SHC reference dir %s not found; nutrient enrichment disabled", ref_dir)
        return idx

    for path in sorted(ref_dir.glob("*.json")):
        try:
            doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Skipping unreadable SHC file %s: %s", path, exc)
            continue
        state = doc.get("state")
        source = doc.get("source")
        for district, vals in doc.get("districts", {}).items():
            idx[_norm(district)] = ShcRecord(
                available_n_kg_ha=vals.get("available_n_kg_ha"),
                available_p_kg_ha=vals.get("available_p_kg_ha"),
                available_k_kg_ha=vals.get("available_k_kg_ha"),
                district=district,
                state=state,
                source=source,
            )
    log.info("Loaded SHC reference for %d districts", len(idx))
    return idx


def lookup(district: str | None) -> ShcRecord | None:
    """Return the SHC record for a district name, or None if not covered."""
    if not district:
        return None
    idx = _index()
    key = _norm(district)
    if key in idx:
        return idx[key]
    # tolerate 'X' vs 'X Rural' / 'Greater X' style variants
    for k, rec in idx.items():
        if k and (k in key or key in k):
            return rec
    return None


def reset_cache() -> None:
    """Clear the in-process index (used by tests / after reloading reference data)."""
    _index.cache_clear()
