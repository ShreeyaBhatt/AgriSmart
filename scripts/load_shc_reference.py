#!/usr/bin/env python3
"""Build ``data/shc_reference/<state>.json`` files from a Soil Health Card export.

The SHC portal (soilhealth.dac.gov.in) publishes district-wise average nutrient
status. Export it to a CSV with (at least) these columns::

    state, district, available_n_kg_ha, available_p_kg_ha, available_k_kg_ha

then::

    python scripts/load_shc_reference.py --csv shc_export.csv
    python scripts/load_shc_reference.py --validate      # sanity-check existing files

Column names are matched case-insensitively; common aliases are accepted
(``N``/``avail_n``/``available_nitrogen`` -> ``available_n_kg_ha``, etc.).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REF_DIR = REPO_ROOT / "data" / "shc_reference"

_ALIASES = {
    "state": {"state", "state_name"},
    "district": {"district", "district_name", "dist"},
    "available_n_kg_ha": {"available_n_kg_ha", "n", "avail_n", "available_nitrogen", "nitrogen"},
    "available_p_kg_ha": {"available_p_kg_ha", "p", "avail_p", "available_phosphorus", "phosphorus"},
    "available_k_kg_ha": {"available_k_kg_ha", "k", "avail_k", "available_potassium", "potassium"},
}


def _resolve_columns(header: list[str]) -> dict[str, str]:
    lower = {h.lower().strip(): h for h in header}
    resolved: dict[str, str] = {}
    for canonical, names in _ALIASES.items():
        match = next((lower[n] for n in names if n in lower), None)
        if match is None and canonical in ("state", "district"):
            sys.exit(f"error: CSV is missing a '{canonical}' column (got {header})")
        if match is not None:
            resolved[canonical] = match
    return resolved


def _num(value: str) -> float | None:
    value = (value or "").strip().replace(",", "")
    try:
        return round(float(value), 1)
    except ValueError:
        return None


def build_from_csv(csv_path: Path) -> None:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    if not rows:
        sys.exit(f"error: {csv_path} has no data rows")
    cols = _resolve_columns(list(rows[0].keys()))

    by_state: dict[str, dict[str, dict[str, float | None]]] = defaultdict(dict)
    for row in rows:
        state = row[cols["state"]].strip()
        district = row[cols["district"]].strip()
        if not state or not district:
            continue
        by_state[state][district] = {
            "available_n_kg_ha": _num(row[cols["available_n_kg_ha"]]) if "available_n_kg_ha" in cols else None,
            "available_p_kg_ha": _num(row[cols["available_p_kg_ha"]]) if "available_p_kg_ha" in cols else None,
            "available_k_kg_ha": _num(row[cols["available_k_kg_ha"]]) if "available_k_kg_ha" in cols else None,
        }

    REF_DIR.mkdir(parents=True, exist_ok=True)
    for state, districts in sorted(by_state.items()):
        out = REF_DIR / f"{state.lower().replace(' ', '_')}.json"
        doc = {
            "state": state,
            "source": f"Soil Health Card portal export ({csv_path.name})",
            "units": "available N, P, K in kg/ha",
            "districts": dict(sorted(districts.items())),
        }
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {out.relative_to(REPO_ROOT)}  ({len(districts)} districts)")


def validate() -> None:
    files = sorted(REF_DIR.glob("*.json"))
    if not files:
        sys.exit(f"no reference files in {REF_DIR}")
    total = 0
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        n = len(doc.get("districts", {}))
        total += n
        assert doc.get("state"), f"{path.name}: missing 'state'"
        for district, vals in doc["districts"].items():
            for key in ("available_n_kg_ha", "available_p_kg_ha", "available_k_kg_ha"):
                v = vals.get(key)
                assert v is None or v >= 0, f"{path.name}/{district}: bad {key}={v}"
        print(f"ok  {path.name}  ({n} districts)")
    print(f"\n{len(files)} file(s), {total} districts total")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, help="Soil Health Card CSV export to import")
    ap.add_argument("--validate", action="store_true", help="check existing reference files")
    args = ap.parse_args()

    if args.csv:
        build_from_csv(args.csv)
    if args.validate or not args.csv:
        validate()


if __name__ == "__main__":
    main()
