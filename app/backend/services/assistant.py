"""Module E — GenAI Farmer Assistant.

Retrieval‑augmented: find the relevant disease card(s), add the farmer's live
plot / soil / last‑diagnosis context, then either ask Gemini (when
``GEMINI_API_KEY`` is set) or compose a grounded answer straight from the card.
Either way the answer is grounded in the same corpus.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

from ..config import get_settings
from ..models.modules import AssistantAnswer

log = logging.getLogger(__name__)
_WORD = re.compile(r"[a-z]{3,}")
_STOP = {"the", "and", "for", "with", "how", "what", "why", "when", "should", "does",
         "can", "are", "was", "were", "this", "that", "have", "has", "from", "into",
         "leaf", "leaves", "plant", "crop", "disease", "farm", "help", "please"}


@lru_cache
def _cards() -> dict[str, dict[str, Any]]:
    doc = json.loads(get_settings().disease_cards_path.read_text(encoding="utf-8"))
    return doc.get("cards", {})


def reset_cache() -> None:
    _cards.cache_clear()


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def _retrieve(question: str, last_class: str | None) -> list[tuple[str, dict]]:
    cards = _cards()
    if last_class and last_class in cards:
        picked = [(last_class, cards[last_class])]
    else:
        picked = []
    qk = _keywords(question)
    scored = []
    for key, card in cards.items():
        hay = f"{key} {card.get('crop','')} {card.get('disease','')} {card.get('symptoms','')}"
        score = len(qk & _keywords(hay))
        if score:
            scored.append((score, key, card))
    scored.sort(reverse=True)
    for _, key, card in scored:
        if all(key != k for k, _ in picked):
            picked.append((key, card))
        if len(picked) >= 2:
            break
    return picked[:2]


def _plot_context(plot: dict | None) -> str:
    if not plot:
        return ""
    s = plot.get("soil_snapshot") or {}
    bits = [f"Plot '{plot.get('name')}' at {plot.get('lat')},{plot.get('lon')}"]
    if s.get("texture_class"):
        bits.append(f"soil: {s['texture_class']}, pH {s.get('ph')}, "
                    f"organic carbon {s.get('organic_carbon_pct')}%")
    return "; ".join(bits)


def _fallback_answer(question: str, picked: list[tuple[str, dict]], plot_ctx: str) -> str:
    if not picked:
        return ("I don't have a specific card for that yet. In general: scout your crop "
                "weekly, keep foliage dry, rotate crops, and match fertiliser to a soil test. "
                "Scan an affected leaf for a specific diagnosis.")
    key, c = picked[0]
    name = c.get("disease") or f"healthy {c.get('crop','crop')}"
    lines = [f"{c.get('crop','')} — {name}".strip(" —")]
    if c.get("symptoms"):
        lines.append(f"Signs: {c['symptoms']}")
    if c.get("organic"):
        lines.append(f"Organic control: {c['organic']}")
    if c.get("chemical") and c["chemical"].lower() not in ("none needed.", "none needed"):
        lines.append(f"Chemical control: {c['chemical']}")
    if c.get("prevention"):
        lines.append(f"Prevention: {c['prevention']}")
    if plot_ctx:
        lines.append(f"For your plot ({plot_ctx}) follow the soil advice in the plot page too.")
    return "\n\n".join(lines)


async def _gemini_answer(question: str, context: str, lang: str) -> str | None:
    s = get_settings()
    lang_name = {"en": "English", "hi": "Hindi", "gu": "Gujarati"}.get(lang, "English")
    try:
        import google.generativeai as genai

        genai.configure(api_key=s.gemini_api_key)
        model = genai.GenerativeModel(s.gemini_model)
        prompt = (
            "You are a careful, practical agricultural advisor for small farmers in India. "
            "Answer ONLY using the CONTEXT below. If the context does not cover it, say so briefly. "
            f"Reply in {lang_name}, in plain language, 4-6 short sentences, no markdown headings.\n\n"
            f"CONTEXT:\n{context}\n\nQUESTION: {question}"
        )
        resp = await model.generate_content_async(prompt)
        return (resp.text or "").strip() or None
    except Exception as exc:  # missing key, quota, network, SDK change
        log.warning("Gemini call failed, using offline fallback: %s", exc)
        return None


async def answer_question(
    question: str, *, lang: str = "en", plot: dict | None = None, last_class: str | None = None
) -> AssistantAnswer:
    picked = _retrieve(question, last_class)
    plot_ctx = _plot_context(plot)
    grounded_on = [k for k, _ in picked] + (["plot"] if plot_ctx else [])

    context_parts = []
    for key, card in picked:
        context_parts.append(f"[{key}] " + json.dumps(card, ensure_ascii=False))
    if plot_ctx:
        context_parts.append(f"[plot] {plot_ctx}")
    context = "\n".join(context_parts) or "(no matching card)"

    used_llm = False
    if get_settings().gemini_api_key:
        llm = await _gemini_answer(question, context, lang)
        if llm:
            return AssistantAnswer(answer=llm, grounded_on=grounded_on, used_llm=True, lang=lang)
    answer = _fallback_answer(question, picked, plot_ctx)
    return AssistantAnswer(answer=answer, grounded_on=grounded_on, used_llm=used_llm, lang=lang)
