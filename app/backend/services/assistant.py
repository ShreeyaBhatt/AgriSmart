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
from . import gemini as gemini_service
from .units import describe_area

log = logging.getLogger(__name__)
_WORD = re.compile(r"[a-z]{3,}")
# Expanded stop words to reduce retrieval bias. Generic crop and disease terms
# that appear in *many* cards should not drive retrieval — they'd give
# artificially high match scores to cards that simply mention them often
# (e.g. "Maize — Common Rust" was always winning because "common" and "rust"
# are generic words).
_STOP = {
    "the", "and", "for", "with", "how", "what", "why", "when", "should", "does",
    "can", "are", "was", "were", "this", "that", "have", "has", "from", "into",
    "leaf", "leaves", "plant", "crop", "disease", "farm", "help", "please",
    "about", "tell", "more", "treat", "treatment", "cure", "cause", "prevent",
    "control", "spray", "apply", "use", "much", "often", "which", "best",
    "common", "affected", "infection", "infected", "damage", "damaged",
    "problem", "issue", "solution", "remedy", "organic", "chemical",
    "fungicide", "pesticide", "fertilizer", "fertiliser", "soil", "water",
}


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
    if not qk:
        # All tokens were stop words — fall back to the last-class card or nothing
        return picked[:2]
    scored = []
    for key, card in cards.items():
        hay = f"{key} {card.get('crop','')} {card.get('disease','')}"
        hay_kw = _keywords(hay)
        # Require at least one keyword match in the card name / crop / disease
        name_score = len(qk & hay_kw)
        if not name_score:
            continue
        # Bonus from symptom text, but capped to avoid symptom text dominating
        symptom_kw = _keywords(card.get("symptoms", ""))
        symptom_bonus = min(len(qk & symptom_kw), 2)
        total = name_score + symptom_bonus
        scored.append((total, key, card))
    scored.sort(reverse=True)

    # Deduplicate: avoid picking two cards from the same crop unless they're
    # clearly different diseases
    crops_seen: dict[str, int] = {}
    for _, key, card in scored:
        if all(key != k for k, _ in picked):
            crop = card.get("crop", "").lower()
            if crops_seen.get(crop, 0) >= 1 and len(picked) >= 1:
                continue  # skip second card from the same crop
            picked.append((key, card))
            crops_seen[crop] = crops_seen.get(crop, 0) + 1
        if len(picked) >= 2:
            break
    return picked[:2]


def _plot_context(plot: dict | None, land_unit: str = "ha", bigha_region: str | None = None) -> str:
    if not plot:
        return ""
    s = plot.get("soil_snapshot") or {}
    bits = [f"Plot '{plot.get('name')}' at {plot.get('lat')},{plot.get('lon')}"]
    area_label = describe_area(plot.get("area_ha"), land_unit, bigha_region)
    if area_label:
        bits.append(f"size: {area_label}")
    if s.get("texture_class"):
        bits.append(f"soil: {s['texture_class']}, pH {s.get('ph')}, "
                    f"organic carbon {s.get('organic_carbon_pct')}%")
        try:
            from .recommend import recommend_crops
            from ..models.soil import SoilProfile
            sp = SoilProfile(**s)
            rec = recommend_crops(sp, season="Any")
            if rec and rec.ranked:
                top_crops = [c.crop for c in rec.ranked[:3]]
                bits.append(f"best crops to grow here: {', '.join(top_crops)}")
        except Exception as e:
            log.warning("Could not add crops to context: %s", e)
    return "; ".join(bits)


# Localized fallback answer templates for when Gemini is unavailable
_FALLBACK_TEMPLATES = {
    "en": {
        "no_card": (
            "I don't have a specific card for that yet. In general: scout your crop "
            "weekly, keep foliage dry, rotate crops, and match fertiliser to a soil test. "
            "Scan an affected leaf for a specific diagnosis."
        ),
        "signs": "Signs",
        "organic": "Organic control",
        "chemical": "Chemical control",
        "prevention": "Prevention",
        "plot_advice": "For your plot ({ctx}) follow the soil advice in the plot page too.",
        "crops_answer": "Based on your soil profile, the best crops to grow here are: {crops}. {plot_advice}",
    },
    "hi": {
        "no_card": (
            "इसके लिए मेरे पास अभी कोई विशेष जानकारी नहीं है। सामान्य सुझाव: हर हफ्ते फसल की जांच करें, "
            "पत्तियां सूखी रखें, फसल चक्र अपनाएं, और मिट्टी परीक्षण के अनुसार खाद डालें। "
            "सटीक निदान के लिए प्रभावित पत्ती को स्कैन करें।"
        ),
        "signs": "लक्षण",
        "organic": "जैविक नियंत्रण",
        "chemical": "रासायनिक नियंत्रण",
        "prevention": "रोकथाम",
        "plot_advice": "आपके खेत ({ctx}) के लिए, प्लॉट पेज पर मिट्टी की सलाह भी देखें।",
        "crops_answer": "आपकी मिट्टी के अनुसार, यहाँ उगाने के लिए सबसे अच्छी फसलें हैं: {crops}। {plot_advice}",
    },
    "gu": {
        "no_card": (
            "આ માટે મારી પાસે હજુ સુધી કોઈ ચોક્કસ માહિતી નથી. સામાન્ય સૂચનાઓ: દર અઠવાડિયે "
            "પાકની તપાસ કરો, પાંદડા સૂકા રાખો, પાક ફેરફાર કરો, અને માટી પરીક્ષણ પ્રમાણે ખાતર નાખો. "
            "ચોક્કસ નિદાન માટે અસરગ્રસ્ત પાંદડાને સ્કેન કરો."
        ),
        "signs": "લક્ષણો",
        "organic": "જૈવિક નિયંત્રણ",
        "chemical": "રાસાયણિક નિયંત્રણ",
        "prevention": "નિવારણ",
        "plot_advice": "તમારા ખેતર ({ctx}) માટે, પ્લોટ પેજ પર માટી સલાહ પણ જુઓ.",
        "crops_answer": "તમારી માટી પ્રમાણે, અહીં ઉગાડવા માટે શ્રેષ્ઠ પાક છે: {crops}. {plot_advice}",
    },
    "mr": {
        "no_card": (
            "यासाठी माझ्याकडे अद्याप विशिष्ट माहिती नाही. सर्वसाधारणपणे: दर आठवड्याला पिकाची तपासणी करा, "
            "पाने कोरडी ठेवा, पीक फेरपालट करा, आणि माती परीक्षणानुसार खत द्या. "
            "नेमक्या निदानासाठी प्रभावित पान स्कॅन करा."
        ),
        "signs": "लक्षणे",
        "organic": "सेंद्रिय नियंत्रण",
        "chemical": "रासायनिक नियंत्रण",
        "prevention": "प्रतिबंध",
        "plot_advice": "तुमच्या शेतासाठी ({ctx}) प्लॉट पेजवरील मातीचा सल्लाही पहा.",
        "crops_answer": "तुमच्या मातीनुसार, इथे वाढवण्यासाठी सर्वोत्तम पिके आहेत: {crops}. {plot_advice}",
    },
    "ta": {
        "no_card": (
            "இதற்கு எனக்கு இன்னும் குறிப்பிட்ட தகவல் இல்லை. பொதுவாக: வாரந்தோறும் பயிரை பரிசோதிக்கவும், "
            "இலைகளை உலர்ந்து வைக்கவும், பயிர் சுழற்சி செய்யவும், மண் பரிசோதனைக்கு ஏற்ப உரமிடவும். "
            "துல்லியமான கண்டறிதலுக்கு பாதிக்கப்பட்ட இலையை ஸ்கேன் செய்யவும்."
        ),
        "signs": "அறிகுறிகள்",
        "organic": "இயற்கை கட்டுப்பாடு",
        "chemical": "இரசாயன கட்டுப்பாடு",
        "prevention": "தடுப்பு",
        "plot_advice": "உங்கள் வயலுக்கு ({ctx}) பிளாட் பக்கத்திலுள்ள மண் ஆலோசனையையும் பின்பற்றவும்.",
        "crops_answer": "உங்கள் மண் வகைப்படி, இங்கு வளர்ப்பதற்கு சிறந்த பயிர்கள்: {crops}. {plot_advice}",
    },
    "te": {
        "no_card": (
            "దీనికి నా వద్ద ఇంకా నిర్దిష్ట సమాచారం లేదు. సాధారణంగా: ప్రతి వారం పంటను పరిశీలించండి, "
            "ఆకులను పొడిగా ఉంచండి, పంట మార్పిడి చేయండి, నేల పరీక్ష ప్రకారం ఎరువు వేయండి. "
            "ఖచ్చితమైన నిర్ధారణ కోసం ప్రభావిత ఆకును స్కాన్ చేయండి."
        ),
        "signs": "లక్షణాలు",
        "organic": "సేంద్రీయ నియంత్రణ",
        "chemical": "రసాయన నియంత్రణ",
        "prevention": "నివారణ",
        "plot_advice": "మీ పొలం కోసం ({ctx}) ప్లాట్ పేజీలోని నేల సలహాను కూడా అనుసరించండి.",
        "crops_answer": "మీ నేల ప్రొఫైల్ ప్రకారం, ఇక్కడ పండించడానికి ఉత్తమ పంటలు: {crops}. {plot_advice}",
    },
    "pa": {
        "no_card": (
            "ਇਸ ਲਈ ਮੇਰੇ ਕੋਲ ਅਜੇ ਕੋਈ ਖਾਸ ਜਾਣਕਾਰੀ ਨਹੀਂ ਹੈ। ਆਮ ਤੌਰ 'ਤੇ: ਹਰ ਹਫ਼ਤੇ ਫ਼ਸਲ ਦੀ ਜਾਂਚ ਕਰੋ, "
            "ਪੱਤਿਆਂ ਨੂੰ ਸੁੱਕਾ ਰੱਖੋ, ਫ਼ਸਲੀ ਚੱਕਰ ਅਪਣਾਓ, ਅਤੇ ਮਿੱਟੀ ਦੀ ਜਾਂਚ ਅਨੁਸਾਰ ਖਾਦ ਪਾਓ। "
            "ਸਹੀ ਨਿਦਾਨ ਲਈ ਪ੍ਰਭਾਵਿਤ ਪੱਤੇ ਨੂੰ ਸਕੈਨ ਕਰੋ।"
        ),
        "signs": "ਲੱਛਣ",
        "organic": "ਜੈਵਿਕ ਨਿਯੰਤਰਣ",
        "chemical": "ਰਸਾਇਣਕ ਨਿਯੰਤਰਣ",
        "prevention": "ਰੋਕਥਾਮ",
        "plot_advice": "ਤੁਹਾਡੇ ਖੇਤ ({ctx}) ਲਈ, ਪਲਾਟ ਪੇਜ 'ਤੇ ਮਿੱਟੀ ਦੀ ਸਲਾਹ ਵੀ ਦੇਖੋ।",
        "crops_answer": "ਤੁਹਾਡੀ ਮਿੱਟੀ ਅਨੁਸਾਰ, ਇੱਥੇ ਉਗਾਉਣ ਲਈ ਸਭ ਤੋਂ ਵਧੀਆ ਫ਼ਸਲਾਂ ਹਨ: {crops}। {plot_advice}",
    },
}


def _fallback_answer(question: str, picked: list[tuple[str, dict]], plot_ctx: str, lang: str = "en") -> str:
    tmpl = _FALLBACK_TEMPLATES.get(lang, _FALLBACK_TEMPLATES["en"])
    
    if not picked:
        q_low = question.lower()
        en_match = re.search(r"\b(what|which|best|suggest|recommend|suitable|top)\s+(crop|plant|seed)s?\b|\bwhat\s+to\s+(grow|plant|sow)\b|\bbest\s+(crop|plant)s?\s+to\s+(grow|plant)\b", q_low)
        hi_match = re.search(r"(कौन\s*सी|क्या|सबसे\s*अच्छी|सुझाव).*(फसल|उगा|लगा)", q_low)
        gu_match = re.search(r"(કયો|કઈ|શું|શ્રેષ્ઠ|સૂચન).*(પાક|વાવ|ઉગાડ)", q_low)
        mr_match = re.search(r"(कोणत[ेी]|सर्वोत्तम|सुचवा).*(पीक|पेरा|लावा)", q_low)
        ta_match = re.search(r"(எந்த|சிறந்த|பரிந்துரை).*(பயிர்|வளர்|நடவு)", q_low)
        te_match = re.search(r"(ఏ|ఉత్తమ|సూచించు).*(పంట|పండించు|వేయాలి)", q_low)
        pa_match = re.search(r"(ਕਿਹੜੀ|ਸਭ ਤੋਂ ਵਧੀਆ|ਸੁਝਾਅ).*(ਫ਼ਸਲ|ਬੀਜਣਾ|ਲਾਉਣਾ)", q_low)
        disease_match = re.search(
            r"\b(not|isnt|isn't|arent|aren't|dying|sick|disease|pest|bug|yellow|rot|problem)\b"
            r"|रोग|बीमारी|खराब|आजार"  # hi/mr
            r"|રોગ|જીવાત"  # gu
            r"|நோய்|பூச்சி|கெட்டு"  # ta
            r"|వ్యాధి|పురుగు|పాడైంది"  # te
            r"|ਰੋਗ|ਬਿਮਾਰੀ|ਖ਼ਰਾਬ",  # pa
            q_low,
        )

        asking_crops = (
            en_match or hi_match or gu_match or mr_match or ta_match or te_match or pa_match
        ) and not disease_match

        if asking_crops and plot_ctx and "best crops to grow here: " in plot_ctx:
            crops = plot_ctx.split("best crops to grow here: ")[-1]
            base_plot = plot_ctx.split(";")[0]
            plot_advice = tmpl["plot_advice"].format(ctx=base_plot)
            return tmpl["crops_answer"].format(crops=crops, plot_advice=plot_advice)
        return tmpl["no_card"]
    key, c = picked[0]
    name = c.get("disease") or f"healthy {c.get('crop', 'crop')}"
    lines = [f"{c.get('crop', '')} — {name}".strip(" —")]
    if c.get("symptoms"):
        lines.append(f"{tmpl['signs']}: {c['symptoms']}")
    if c.get("organic"):
        lines.append(f"{tmpl['organic']}: {c['organic']}")
    if c.get("chemical") and c["chemical"].lower() not in ("none needed.", "none needed"):
        lines.append(f"{tmpl['chemical']}: {c['chemical']}")
    if c.get("prevention"):
        lines.append(f"{tmpl['prevention']}: {c['prevention']}")
    if plot_ctx:
        lines.append(tmpl["plot_advice"].format(ctx=plot_ctx))
    return "\n\n".join(lines)


async def _gemini_answer(question: str, context: str, lang: str) -> str | None:
    lang_name = {
        "en": "English", "hi": "Hindi", "gu": "Gujarati",
        "mr": "Marathi", "ta": "Tamil", "te": "Telugu", "pa": "Punjabi",
    }.get(lang, "English")
    prompt = (
        "You are a careful, practical agricultural advisor for small farmers in India. "
        "Use the CONTEXT below to ground your answer if relevant. If the context does not cover it, provide general, safe agronomic advice based on your own knowledge. "
        "If you mention this plot's size, use the figure and unit given in the context as-is — don't convert it to a different unit. "
        f"Reply in {lang_name}, in plain language, 4-6 short sentences, no markdown headings.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    )
    return await gemini_service.generate(prompt)


async def answer_question(
    question: str, *, lang: str = "en", plot: dict | None = None, last_class: str | None = None,
    land_unit: str = "ha", bigha_region: str | None = None,
) -> AssistantAnswer:
    picked = _retrieve(question, last_class)
    plot_ctx = _plot_context(plot, land_unit, bigha_region)
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
    answer = _fallback_answer(question, picked, plot_ctx, lang)
    return AssistantAnswer(answer=answer, grounded_on=grounded_on, used_llm=used_llm, lang=lang)


async def warm_up() -> None:
    """Delegates to the shared gemini service — see its warm_up() for what
    this pays for and why. A missing/invalid key or a flaky network just
    means it's skipped; the assistant still works, just slower on the
    first question."""
    await gemini_service.warm_up()
