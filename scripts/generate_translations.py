#!/usr/bin/env python3
"""One-time batch translator for Module A's rule tables.

/predict and Module C (weather) already localize their output — either via
pre-translated fields in data/disease_cards.json (crop/disease/precautions_<lang>)
or, for weather, hand-written per-language message dicts in services/weather.py.
Module A's crop_suitability.json / soil_amendments.json never got the same
treatment, so /recommend/crops and /recommend/amendments always answered in
English regardless of the UI language.

This script closes that gap using the SAME static-lookup pattern (not a live
per-request Gemini call): it adds "<field>_hi", "<field>_gu", etc. siblings to
every English string in the two rule tables, plus two new small files:

  data/texture_labels.json    localized names for the 12 USDA texture classes
  data/phrase_templates.json  the short sentence templates services/recommend.py
                               composes dynamically (e.g. "{texture} soil suits
                               this crop"), keyed the same way as weather.py's
                               _MESSAGES/_PHRASES dicts

Gemini (already configured for the assistant/sustainability modules) generates
the translations; every result is validated to preserve {placeholder} tokens
exactly, and any string that fails validation keeps its English text instead
of risking a broken/mistranslated placeholder reaching the API response.

Usage:
    python scripts/generate_translations.py              # translate + write
    python scripts/generate_translations.py --dry-run     # print, don't write
    python scripts/generate_translations.py --langs hi,gu # subset of languages
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

# Windows consoles default Python's stdout/stderr to cp1252, which can't
# encode the Devanagari/Gujarati/etc. text this script prints (in progress
# lines and, worse, inside exception messages) — that previously surfaced as
# a swallowed, seemingly-empty exception ("batch failed ()") instead of the
# real error. Force UTF-8 so failures are actually legible.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

LANGS = {
    "hi": "Hindi", "gu": "Gujarati", "mr": "Marathi",
    "ta": "Tamil", "te": "Telugu", "pa": "Punjabi",
}
_PLACEHOLDER_RE = re.compile(r"\{\w+\}")

AMENDMENTS_PATH = REPO_ROOT / "data" / "soil_amendments.json"
CROPS_PATH = REPO_ROOT / "data" / "crop_suitability.json"
TEXTURE_LABELS_PATH = REPO_ROOT / "data" / "texture_labels.json"
PHRASES_PATH = REPO_ROOT / "data" / "phrase_templates.json"

USDA_TEXTURES = [
    "sand", "loamy sand", "sandy loam", "loam", "silt loam", "silt",
    "sandy clay loam", "clay loam", "silty clay loam", "sandy clay",
    "silty clay", "clay",
]

# The dynamically-composed sentence fragments in services/recommend.py.
# English text here must stay byte-for-byte identical to what that module
# currently builds via f-strings, so translating only non-English keys
# never changes English-language output.
PHRASE_SOURCE: dict[str, str] = {
    "crop_texture_match": "{texture} soil suits this crop",
    "crop_texture_mismatch": "{texture} is not an ideal texture ({options})",
    "crop_ph_in_range": "pH {ph} is within the {lo}-{hi} range",
    "crop_ph_out_of_range": "pH {ph} is outside the preferred {lo}-{hi} range",
    "crop_ph_unknown": "soil pH unknown",
    "crop_season_match": "grown in {season}",
    "crop_season_mismatch": "not a typical {season} crop",
    "crop_note_base": "Ranked on soil texture and pH",
    "crop_note_and_season": " and season",
    "crop_note_suffix": ". Climate suitability (temperature, rainfall) is scored separately by Module C.",
    "amendment_gap_nitrogen": "No Soil Health Card nitrogen for this district - N advice is based on organic carbon only.",
    "amendment_gap_phosphorus": "No Soil Health Card phosphorus for this district - get a soil test before fixing P doses.",
    "amendment_gap_potassium": "No Soil Health Card potassium for this district - get a soil test before fixing K doses.",
    "amendment_low_oc_n_finding": "Low organic carbon implies low N-supplying capacity.",
    "amendment_low_oc_n_action": "Apply the crop's full recommended N in 3 splits until a soil test is available.",
    "amendment_texture_finding": "Soil texture is {texture}.",
}


def _placeholders(s: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(s))


_GEMINI_SEMAPHORE = asyncio.Semaphore(1)  # the free tier is ~20 req/day total; never fan out


async def _translate_groups(groups: dict[str, list[str]], lang_name: str) -> dict[str, list[str]] | None:
    """ONE Gemini call translating several named arrays at once (quota is the
    scarce resource here, not prompt size) — e.g. groups = {"amendments": [...],
    "crops": [...], ...}. Returns {group_name: [translated, ...]} or None."""
    from app.backend.config import get_settings

    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)

    payload = {name: texts for name, texts in groups.items()}
    prompt = (
        f"You are translating short farming-app UI text from English into {lang_name}, "
        "for smallholder Indian farmers using AgriSmart. Use natural, concise, everyday "
        "agricultural vocabulary a farmer would understand — not stiff literal dictionary "
        "translations. Keep units (kg/ha, t/ha, cmol(c)/kg, mm, %) and chemical/fertiliser "
        "names (FYM, DAP, SSP, MOP, P2O5, K2O, NPK) unchanged.\n\n"
        "CRITICAL: some strings contain placeholders like {value} or {texture} — copy every "
        "placeholder EXACTLY as-is (same braces, same name inside), in whatever position "
        "reads naturally in the translated sentence. Never translate or alter placeholder names.\n\n"
        f"Below is a JSON object whose values are arrays of English strings. Translate every "
        f"string in every array into {lang_name}, preserving each array's length and order. "
        "Reply with ONLY a JSON object with the exact same keys, each mapped to its translated "
        "array — no markdown fences, no commentary.\n\nINPUT:\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    async with _GEMINI_SEMAPHORE:
        try:
            resp = await asyncio.wait_for(model.generate_content_async(prompt), timeout=120)
            raw = (resp.text or "").strip()
            raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            out = json.loads(raw)
            if not isinstance(out, dict):
                print(f"  ! {lang_name}: bad shape (top-level {type(out).__name__}, expected object)",
                      file=sys.stderr)
                return None
            ok: dict[str, list[str]] = {}
            for name, texts in groups.items():
                got = out.get(name)
                if not isinstance(got, list) or len(got) != len(texts):
                    print(f"  ! {lang_name}.{name}: bad shape "
                          f"({len(got) if isinstance(got, list) else type(got).__name__} vs {len(texts)}) "
                          "— keeping English for this group", file=sys.stderr)
                    continue
                ok[name] = [str(x) for x in got]
            return ok
        except Exception as exc:
            print(f"  ! {lang_name}: request failed ({type(exc).__name__}: {exc}) — keeping English",
                  file=sys.stderr)
            return None


def _validated(english: str, translated: str, lang: str, where: str) -> str:
    if _placeholders(translated) != _placeholders(english):
        print(f"  ! {lang} {where}: placeholder mismatch, keeping English: {english!r} -> {translated!r}",
              file=sys.stderr)
        return english
    return translated


async def translate_all_groups(
    named_items: dict[str, list[tuple[str, str]]], lang: str, lang_name: str,
) -> dict[str, dict[str, str]]:
    """named_items: {group: [(where, english_text), ...]} -> {group: {where: translated}},
    via a single Gemini call for every group at once (quota-frugal)."""
    groups_texts = {name: [t for _, t in items] for name, items in named_items.items()}
    out = await _translate_groups(groups_texts, lang_name)
    if not out:
        return {}
    results: dict[str, dict[str, str]] = {}
    for name, items in named_items.items():
        translated_list = out.get(name)
        if not translated_list:
            continue
        results[name] = {
            where: _validated(english, translated, lang, f"{name}.{where}")
            for (where, english), translated in zip(items, translated_list)
        }
    return results


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--langs", default=",".join(LANGS), help="comma-separated subset, e.g. hi,gu")
    args = ap.parse_args()
    langs = {k: LANGS[k] for k in args.langs.split(",") if k in LANGS}

    amendments = json.loads(AMENDMENTS_PATH.read_text(encoding="utf-8"))
    crops_doc = json.loads(CROPS_PATH.read_text(encoding="utf-8"))
    texture_labels: dict[str, dict[str, str]] = {t: {"en": t} for t in USDA_TEXTURES}
    phrases: dict[str, dict[str, str]] = {k: {"en": v} for k, v in PHRASE_SOURCE.items()}

    # --- collect (where, english) pairs from the two rule tables ---
    amendment_items: list[tuple[str, str]] = [("citation", amendments["citation"])]
    for table_key, table in amendments.items():
        if table_key in ("citation", "texture_notes"):
            continue
        for band_name, rule in table.items():
            amendment_items.append((f"{table_key}.{band_name}.finding", rule["finding"]))
            amendment_items.append((f"{table_key}.{band_name}.action", rule["action"]))
    texture_note_items = [(f"texture_notes.{tex}", note) for tex, note in amendments["texture_notes"].items()]

    crop_items: list[tuple[str, str]] = [("citation", crops_doc["citation"])]
    for i, crop in enumerate(crops_doc["crops"]):
        crop_items.append((f"crops.{i}.name", crop["name"]))
        crop_items.append((f"crops.{i}.notes", crop["notes"]))

    texture_label_items = [(tex, tex) for tex in USDA_TEXTURES]
    phrase_items = list(PHRASE_SOURCE.items())

    for lang, lang_name in langs.items():
        print(f"=== {lang_name} ({lang}) ===")

        all_results = await translate_all_groups({
            "amendments": amendment_items,
            "texture_notes": texture_note_items,
            "crops": crop_items,
            "texture_labels": texture_label_items,
            "phrases": phrase_items,
        }, lang, lang_name)

        res = all_results.get("amendments", {})
        for table_key, table in amendments.items():
            if table_key in ("citation", "texture_notes"):
                continue
            for band_name, rule in table.items():
                if (v := res.get(f"{table_key}.{band_name}.finding")):
                    rule[f"finding_{lang}"] = v
                if (v := res.get(f"{table_key}.{band_name}.action")):
                    rule[f"action_{lang}"] = v
        if (v := res.get("citation")):
            amendments[f"citation_{lang}"] = v
        print(f"  amendments: {len(res)}/{len(amendment_items)} translated")

        res = all_results.get("texture_notes", {})
        tn_lang = {tex.split(".", 1)[1]: v for tex, v in res.items()}
        amendments.setdefault(f"texture_notes_{lang}", {}).update(tn_lang)
        print(f"  texture_notes: {len(res)}/{len(texture_note_items)} translated")

        res = all_results.get("crops", {})
        for i, crop in enumerate(crops_doc["crops"]):
            if (v := res.get(f"crops.{i}.name")):
                crop[f"name_{lang}"] = v
            if (v := res.get(f"crops.{i}.notes")):
                crop[f"notes_{lang}"] = v
        if (v := res.get("citation")):
            crops_doc[f"citation_{lang}"] = v
        print(f"  crops: {len(res)}/{len(crop_items)} translated")

        res = all_results.get("texture_labels", {})
        for tex, v in res.items():
            texture_labels[tex][lang] = v
        print(f"  texture_labels: {len(res)}/{len(texture_label_items)} translated")

        res = all_results.get("phrases", {})
        for key, v in res.items():
            phrases[key][lang] = v
        print(f"  phrase_templates: {len(res)}/{len(phrase_items)} translated")

    if args.dry_run:
        print("\n--dry-run: not writing any files")
        return

    AMENDMENTS_PATH.write_text(json.dumps(amendments, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CROPS_PATH.write_text(json.dumps(crops_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TEXTURE_LABELS_PATH.write_text(json.dumps(texture_labels, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PHRASES_PATH.write_text(json.dumps(phrases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {AMENDMENTS_PATH}, {CROPS_PATH}, {TEXTURE_LABELS_PATH}, {PHRASES_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
