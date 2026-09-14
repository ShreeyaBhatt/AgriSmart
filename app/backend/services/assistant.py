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

# Non-disease intents the offline fallback can still answer from local data
# instead of the single generic "no_card" message — checked (in this order)
# only when disease-card retrieval found nothing. "weather" also covers
# irrigation-timing questions: weather.build_advice's own rule set already
# includes "delay irrigation - rain is coming" (docs/weather_rules.md rule
# #1), so routing irrigation questions there reuses a real, grounded rule
# instead of a second bespoke implementation. Checked as plain substring
# containment across every language's keyword list regardless of the
# requested reply language — cheap, and a farmer occasionally typing in a
# different script than their UI setting should still route correctly.
_INTENT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "weather": {
        "en": ["rain", "weather", "temperature", "forecast", "wind", "humid", "irrigat", "water"],
        "hi": ["बारिश", "मौसम", "तापमान", "पूर्वानुमान", "हवा", "नमी", "सिंचाई", "पानी"],
        "gu": ["વરસાદ", "હવામાન", "તાપમાન", "આગાહી", "પવન", "ભેજ", "સિંચાઈ", "પાણી"],
        "mr": ["पाऊस", "हवामान", "तापमान", "अंदाज", "वारा", "आर्द्रता", "सिंचन", "पाणी"],
        "ta": ["மழை", "வானிலை", "வெப்பநிலை", "முன்னறிவிப்பு", "காற்று", "நீர்ப்பாசனம்", "தண்ணீர்"],
        "te": ["వర్షం", "వాతావరణం", "ఉష్ణోగ్రత", "సూచన", "గాలి", "నీటిపారుదల", "నీరు"],
        "pa": ["ਮੀਂਹ", "ਮੌਸਮ", "ਤਾਪਮਾਨ", "ਪੂਰਵ ਅਨੁਮਾਨ", "ਹਵਾ", "ਸਿੰਚਾਈ", "ਪਾਣੀ"],
    },
    "soil": {
        "en": ["fertiliz", "fertilis", "npk", "nitrogen", "phosphorus", "potassium", "manure", "compost", "nutrient"],
        "hi": ["खाद", "उर्वरक", "नाइट्रोजन", "पोषक", "कम्पोस्ट"],
        "gu": ["ખાતર", "પોષક", "નાઇટ્રોજન"],
        "mr": ["खत", "पोषक", "नत्र"],
        "ta": ["உரம்", "ஊட்டச்சத்து", "நைட்ரஜன்"],
        "te": ["ఎరువు", "పోషకాలు", "నత్రజని"],
        "pa": ["ਖਾਦ", "ਪੋਸ਼ਕ", "ਨਾਈਟ੍ਰੋਜਨ"],
    },
    "pest": {
        "en": ["pest", "insect", "aphid", "caterpillar"],
        "hi": ["कीट", "कीड़े", "इल्ली"],
        "gu": ["જીવાત", "કીટક"],
        "mr": ["कीड", "किडे", "अळी"],
        "ta": ["பூச்சி", "புழு"],
        "te": ["పురుగు", "పుర్వు"],
        "pa": ["ਕੀੜੇ", "ਸੁੰਡੀ"],
    },
    "sowing": {
        "en": ["sow", "sowing", "seed", "transplant", "nursery"],
        "hi": ["बुवाई", "बीज", "रोपाई", "नर्सरी"],
        "gu": ["વાવણી", "બીજ", "રોપણી"],
        "mr": ["पेरणी", "बियाणे", "लागवड"],
        "ta": ["விதைப்பு", "விதை", "நடவு"],
        "te": ["విత్తడం", "విత్తనం", "నాటడం"],
        "pa": ["ਬਿਜਾਈ", "ਬੀਜ", "ਲੁਆਈ"],
    },
}


def _detect_intent(question: str) -> str | None:
    q = question.lower()
    for intent, by_lang in _INTENT_KEYWORDS.items():
        for keywords in by_lang.values():
            if any(kw in q for kw in keywords):
                return intent
    return None


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


# Project-authored general agronomy guidance (not sourced from any specific
# external dataset — labelled "general-best-practice" deliberately, see the
# agentic-advisor data-sourcing note in project history for why that
# distinction matters). Used when the offline assistant can't ground an
# answer in a specific disease card, live weather, or the farmer's own soil
# data — e.g. a general "when should I sow" question with no plot selected.
_LOCAL_FAQ = {
    "pest": {
        "en": "General pest control: check the underside of leaves weekly for eggs or larvae, remove and destroy heavily infested leaves, and avoid broad-spectrum sprays so natural predators can help keep numbers down. Neem oil or a mild soap-water spray is a reasonable first step before stronger pesticides.",
        "hi": "सामान्य कीट नियंत्रण: हर हफ्ते पत्तियों के नीचे अंडे या इल्ली जांचें, बुरी तरह प्रभावित पत्तियों को हटाकर नष्ट करें, और व्यापक स्प्रे से बचें ताकि प्राकृतिक शिकारी कीटों की संख्या कम रखने में मदद करें। तेज़ कीटनाशक से पहले नीम तेल या हल्का साबुन-पानी स्प्रे आज़माएं।",
        "gu": "સામાન્ય જીવાત નિયંત્રણ: દર અઠવાડિયે પાંદડાની નીચે ઈંડા કે જીવાત તપાસો, ખરાબ રીતે અસરગ્રસ્ત પાંદડાં દૂર કરી નષ્ટ કરો, અને વ્યાપક સ્પ્રે ટાળો જેથી કુદરતી શિકારી જીવાતોની સંખ્યા ઘટાડવામાં મદદ કરે. તીવ્ર કીટનાશક પહેલાં લીમડાનું તેલ કે હળવો સાબુ-પાણી સ્પ્રે અજમાવો.",
        "mr": "सर्वसाधारण कीड नियंत्रण: दर आठवड्याला पानांच्या खालच्या बाजूला अंडी किंवा अळी तपासा, गंभीरपणे प्रभावित पाने काढून नष्ट करा, आणि व्यापक फवारणी टाळा जेणेकरून नैसर्गिक भक्षक किडींची संख्या कमी ठेवण्यास मदत करतील. तीव्र कीटकनाशकाआधी कडुलिंब तेल किंवा सौम्य साबण-पाणी फवारणी वापरून पहा.",
        "ta": "பொது பூச்சி கட்டுப்பாடு: வாரந்தோறும் இலைகளின் அடிப்பகுதியில் முட்டைகள் அல்லது புழுக்களை சோதிக்கவும், கடுமையாக பாதிக்கப்பட்ட இலைகளை அகற்றி அழிக்கவும், இயற்கை வேட்டையாடிகள் உதவும்படி பரவலான தெளிப்புகளை தவிர்க்கவும். வலுவான பூச்சிக்கொல்லிக்கு முன் வேப்ப எண்ணெய் அல்லது மென்மையான சோப்பு-நீர் தெளிப்பு முயற்சிக்கவும்.",
        "te": "సాధారణ పురుగు నియంత్రణ: ప్రతి వారం ఆకుల కింద గుడ్లు లేదా లార్వాలను పరిశీలించండి, తీవ్రంగా ప్రభావితమైన ఆకులను తీసివేసి నాశనం చేయండి, సహజ శత్రు కీటకాలకు సహాయపడేలా విస్తృత-స్పెక్ట్రం స్ప్రేలను నివారించండి. బలమైన పురుగుమందుకు ముందు వేప నూనె లేదా తేలికపాటి సబ్బు-నీటి స్ప్రే ప్రయత్నించండి.",
        "pa": "ਆਮ ਕੀੜੇ ਨਿਯੰਤਰਣ: ਹਰ ਹਫ਼ਤੇ ਪੱਤਿਆਂ ਦੇ ਹੇਠਾਂ ਆਂਡੇ ਜਾਂ ਸੁੰਡੀਆਂ ਦੀ ਜਾਂਚ ਕਰੋ, ਬੁਰੀ ਤਰ੍ਹਾਂ ਪ੍ਰਭਾਵਿਤ ਪੱਤਿਆਂ ਨੂੰ ਹਟਾ ਕੇ ਨਸ਼ਟ ਕਰੋ, ਅਤੇ ਵਿਆਪਕ ਸਪਰੇਅ ਤੋਂ ਬਚੋ ਤਾਂ ਜੋ ਕੁਦਰਤੀ ਸ਼ਿਕਾਰੀ ਕੀੜਿਆਂ ਦੀ ਗਿਣਤੀ ਘਟਾਉਣ ਵਿੱਚ ਮਦਦ ਕਰਨ। ਤੇਜ਼ ਕੀਟਨਾਸ਼ਕ ਤੋਂ ਪਹਿਲਾਂ ਨਿੰਮ ਦਾ ਤੇਲ ਜਾਂ ਹਲਕਾ ਸਾਬਣ-ਪਾਣੀ ਸਪਰੇਅ ਅਜ਼ਮਾਓ।",
    },
    "sowing": {
        "en": "Sowing time depends on the crop and your local season: as a rule, sow kharif crops after the first reliable monsoon rains, and rabi crops at the start of the cool season. Use certified seed, treat it against soil-borne disease before sowing, and keep row spacing wide enough for airflow.",
        "hi": "बुवाई का समय फसल और स्थानीय मौसम पर निर्भर करता है: सामान्यतः खरीफ फसलें पहली भरोसेमंद मानसून बारिश के बाद और रबी फसलें ठंड शुरू होते ही बोएं। प्रमाणित बीज का उपयोग करें, बुवाई से पहले मिट्टी-जनित रोगों से बचाव हेतु बीज उपचार करें, और पंक्तियों के बीच हवा के लिए पर्याप्त दूरी रखें।",
        "gu": "વાવણીનો સમય પાક અને સ્થાનિક ઋતુ પર આધારિત છે: સામાન્ય રીતે ખરીફ પાક પ્રથમ વિશ્વસનીય ચોમાસાના વરસાદ પછી અને રવિ પાક ઠંડીની શરૂઆતમાં વાવો. પ્રમાણિત બિયારણનો ઉપયોગ કરો, વાવણી પહેલાં માટીજન્ય રોગો સામે બીજ સારવાર કરો, અને હવાની અવરજવર માટે હાર વચ્ચે પૂરતું અંતર રાખો.",
        "mr": "पेरणीची वेळ पीक आणि स्थानिक हंगामावर अवलंबून असते: साधारणपणे खरीप पिके पहिल्या विश्वासार्ह पावसानंतर आणि रब्बी पिके थंडीच्या सुरुवातीला पेरा. प्रमाणित बियाणे वापरा, पेरणीपूर्वी मातीजन्य रोगांपासून बचावासाठी बीजप्रक्रिया करा, आणि हवा खेळण्यासाठी ओळींमध्ये पुरेसे अंतर ठेवा.",
        "ta": "விதைப்பு நேரம் பயிர் மற்றும் உங்கள் உள்ளூர் பருவத்தைப் பொறுத்தது: பொதுவாக காரீஃப் பயிர்களை முதல் நம்பகமான பருவமழைக்குப் பிறகும், ரபி பயிர்களை குளிர்காலம் தொடங்கும்போதும் விதைக்கவும். சான்றளிக்கப்பட்ட விதைகளைப் பயன்படுத்தவும், விதைப்பதற்கு முன் மண் வழி நோய்களிலிருந்து பாதுகாக்க விதை சிகிச்சை செய்யவும், காற்றோட்டத்திற்காக வரிசைகளுக்கு இடையே போதுமான இடைவெளி வைக்கவும்.",
        "te": "విత్తే సమయం పంట మరియు మీ స్థానిక సీజన్‌పై ఆధారపడి ఉంటుంది: సాధారణంగా ఖరీఫ్ పంటలను మొదటి నమ్మదగిన వర్షాల తర్వాత మరియు రబీ పంటలను చలికాలం మొదట్లో విత్తండి. ధృవీకరించిన విత్తనాలను వాడండి, విత్తే ముందు నేల ద్వారా వ్యాపించే వ్యాధుల నుండి రక్షణకు విత్తన శుద్ధి చేయండి, గాలి ప్రసరణ కోసం వరుసల మధ్య తగినంత అంతరం ఉంచండి.",
        "pa": "ਬਿਜਾਈ ਦਾ ਸਮਾਂ ਫ਼ਸਲ ਅਤੇ ਤੁਹਾਡੇ ਸਥਾਨਕ ਮੌਸਮ 'ਤੇ ਨਿਰਭਰ ਕਰਦਾ ਹੈ: ਆਮ ਤੌਰ 'ਤੇ ਸਾਉਣੀ ਦੀਆਂ ਫ਼ਸਲਾਂ ਪਹਿਲੀ ਭਰੋਸੇਯੋਗ ਮਾਨਸੂਨ ਬਾਰਿਸ਼ ਤੋਂ ਬਾਅਦ ਅਤੇ ਹਾੜ੍ਹੀ ਦੀਆਂ ਫ਼ਸਲਾਂ ਠੰਢ ਸ਼ੁਰੂ ਹੁੰਦੇ ਹੀ ਬੀਜੋ। ਪ੍ਰਮਾਣਿਤ ਬੀਜ ਵਰਤੋ, ਬਿਜਾਈ ਤੋਂ ਪਹਿਲਾਂ ਮਿੱਟੀ-ਜਨਿਤ ਰੋਗਾਂ ਤੋਂ ਬਚਾਅ ਲਈ ਬੀਜ ਸੋਧ ਕਰੋ, ਅਤੇ ਹਵਾ ਲਈ ਕਤਾਰਾਂ ਵਿਚਕਾਰ ਲੋੜੀਂਦੀ ਦੂਰੀ ਰੱਖੋ।",
    },
    "irrigation": {
        "en": "As a general rule, water deeply but less often rather than little and often — this grows deeper roots and wastes less water. Irrigate early morning or evening to cut evaporation, and check soil moisture a few inches down before watering again. Add a plot with a location to get a live, rain-based irrigation recommendation instead of this general rule.",
        "hi": "सामान्य नियम: कम बार लेकिन गहरी सिंचाई करें, बार-बार थोड़ा पानी देने से बेहतर — इससे जड़ें गहरी होती हैं और पानी कम बर्बाद होता है। वाष्पीकरण कम करने के लिए सुबह या शाम सिंचाई करें, और दोबारा पानी देने से पहले कुछ इंच नीचे मिट्टी की नमी जांचें। इस सामान्य सलाह की जगह लाइव, बारिश-आधारित सिंचाई सुझाव पाने के लिए स्थान सहित एक खेत जोड़ें।",
        "gu": "સામાન્ય નિયમ: વારંવાર થોડું પાણી આપવાને બદલે ઓછી વાર પણ ઊંડું પાણી આપો — આનાથી મૂળ ઊંડા જાય છે અને પાણીનો બગાડ ઓછો થાય છે. બાષ્પીભવન ઘટાડવા સવારે અથવા સાંજે સિંચાઈ કરો, અને ફરી પાણી આપતા પહેલા થોડા ઇંચ નીચે માટીની ભેજ તપાસો. આ સામાન્ય સલાહને બદલે લાઇવ, વરસાદ-આધારિત સિંચાઈ સૂચન મેળવવા સ્થાન સાથે ખેતર ઉમેરો.",
        "mr": "सर्वसाधारण नियम: वारंवार थोडे पाणी देण्याऐवजी कमी वेळा पण खोलवर पाणी द्या — यामुळे मुळे खोलवर जातात आणि पाण्याचा अपव्यय कमी होतो. बाष्पीभवन कमी करण्यासाठी सकाळी किंवा संध्याकाळी सिंचन करा, आणि पुन्हा पाणी देण्यापूर्वी काही इंच खाली मातीतील ओलावा तपासा. या सर्वसाधारण सल्ल्याऐवजी थेट, पावसावर आधारित सिंचन सूचना मिळवण्यासाठी स्थानासह शेत जोडा.",
        "ta": "பொது விதி: அடிக்கடி குறைவாக நீர் பாய்ச்சுவதை விட, குறைவான முறை ஆனால் ஆழமாக நீர் பாய்ச்சவும் — இது வேர்களை ஆழமாகச் செல்ல வைத்து நீர் விரயத்தைக் குறைக்கும். ஆவியாதலைக் குறைக்க காலை அல்லது மாலையில் நீர் பாய்ச்சவும், மீண்டும் நீர் பாய்ச்சும் முன் சில அங்குலம் கீழே மண் ஈரப்பதத்தை சரிபார்க்கவும். இந்த பொது ஆலோசனைக்குப் பதிலாக நேரடி, மழை அடிப்படையிலான நீர்ப்பாசன பரிந்துரை பெற இருப்பிடத்துடன் ஒரு வயலைச் சேர்க்கவும்.",
        "te": "సాధారణ నియమం: తరచుగా కొద్దిగా నీరు పెట్టడం కంటే, తక్కువసార్లు కానీ లోతుగా నీరు పెట్టండి — దీనివల్ల వేర్లు లోతుగా పెరిగి నీరు వృథా తగ్గుతుంది. ఆవిరైపోవడం తగ్గించడానికి ఉదయం లేదా సాయంత్రం నీరు పెట్టండి, మళ్ళీ నీరు పెట్టే ముందు కొన్ని అంగుళాల లోతులో నేల తేమను తనిఖీ చేయండి. ఈ సాధారణ సూచనకు బదులుగా ప్రత్యక్ష, వర్షం-ఆధారిత నీటిపారుదల సూచన పొందడానికి స్థానంతో ఒక పొలాన్ని జోడించండి.",
        "pa": "ਆਮ ਨਿਯਮ: ਵਾਰ-ਵਾਰ ਥੋੜ੍ਹਾ ਪਾਣੀ ਦੇਣ ਦੀ ਬਜਾਏ, ਘੱਟ ਵਾਰ ਪਰ ਡੂੰਘਾ ਪਾਣੀ ਦਿਓ — ਇਸ ਨਾਲ ਜੜ੍ਹਾਂ ਡੂੰਘੀਆਂ ਜਾਂਦੀਆਂ ਹਨ ਅਤੇ ਪਾਣੀ ਦੀ ਬਰਬਾਦੀ ਘਟਦੀ ਹੈ। ਭਾਫ਼ ਬਣਨਾ ਘਟਾਉਣ ਲਈ ਸਵੇਰੇ ਜਾਂ ਸ਼ਾਮ ਸਿੰਚਾਈ ਕਰੋ, ਅਤੇ ਦੁਬਾਰਾ ਪਾਣੀ ਦੇਣ ਤੋਂ ਪਹਿਲਾਂ ਕੁਝ ਇੰਚ ਹੇਠਾਂ ਮਿੱਟੀ ਦੀ ਨਮੀ ਜਾਂਚੋ। ਇਸ ਆਮ ਸਲਾਹ ਦੀ ਬਜਾਏ ਲਾਈਵ, ਮੀਂਹ-ਅਧਾਰਿਤ ਸਿੰਚਾਈ ਸੁਝਾਅ ਲਈ ਟਿਕਾਣੇ ਸਮੇਤ ਇੱਕ ਖੇਤ ਜੋੜੋ।",
    },
}


async def _weather_intent_answer(plot: dict | None, last_class: str | None, lang: str) -> str | None:
    """Grounded in the same rule engine as Module C (weather.build_advice) —
    covers both weather questions and irrigation-timing questions (its rule
    set already includes "delay irrigation, rain is coming"). None if there's
    no plot location to fetch a forecast for."""
    if not plot or plot.get("lat") is None or plot.get("lon") is None:
        return None
    try:
        from . import weather as weather_service

        fc = await weather_service.fetch_forecast(plot["lat"], plot["lon"])
        advice = weather_service.build_advice(
            plot["lat"], plot["lon"], fc, last_disease=last_class, lang=lang)
    except Exception as exc:
        log.warning("Weather intent lookup failed, falling through: %s", exc)
        return None
    lines = [f"{a.headline} — {a.detail}" for a in advice.actions[:2]]
    return "\n\n".join(lines) if lines else None


async def _soil_intent_answer(plot: dict | None) -> str | None:
    """Grounded in the plot's own fetched soil profile (Module A) — None if
    no plot is selected or its soil hasn't been fetched yet, so the caller
    can fall through to the general fertilizer-principles FAQ entry instead.
    Amendment text is currently English-only regardless of `lang` (a known
    gap in services/recommend.py, tracked separately) — not claimed as
    localized here."""
    if not plot:
        return None
    snapshot = plot.get("soil_snapshot")
    if not snapshot or not snapshot.get("texture_class"):
        return None
    try:
        from ..models.soil import SoilProfile
        from .recommend import recommend_amendments

        report = recommend_amendments(SoilProfile(**snapshot))
    except Exception as exc:
        log.warning("Soil intent lookup failed, falling through: %s", exc)
        return None
    if not report.amendments:
        return None
    lines = [f"{a.finding} {a.action}".strip() for a in report.amendments[:2]]
    return "\n\n".join(lines) if lines else None


async def _fallback_answer(
    question: str, picked: list[tuple[str, dict]], plot: dict | None, plot_ctx: str,
    last_class: str | None, lang: str = "en",
) -> str:
    tmpl = _FALLBACK_TEMPLATES.get(lang, _FALLBACK_TEMPLATES["en"])

    if not picked:
        intent = _detect_intent(question)

        # Weather / irrigation-timing — grounded in a live forecast + the
        # same rule engine Module C uses, when a plot location is known.
        if intent == "weather":
            weather_answer = await _weather_intent_answer(plot, last_class, lang)
            if weather_answer:
                return weather_answer
            # No plot location to fetch a forecast for — the irrigation FAQ
            # entry already covers this exact case (general watering
            # principles + a nudge to add a plot for live advice), and most
            # non-plot weather questions from a farmer are practically
            # "should I water" questions anyway.
            faq = _LOCAL_FAQ["irrigation"]
            return faq.get(lang, faq["en"])

        # Soil & fertilizer — grounded in the plot's own fetched soil
        # profile when available.
        if intent == "soil":
            soil_answer = await _soil_intent_answer(plot)
            if soil_answer:
                return soil_answer
            # Falls through to the crop-question check and eventually
            # no_card below, which already mentions matching fertiliser to
            # a soil test — no dedicated ungrounded fertilizer FAQ exists,
            # since specific dosing advice without real soil data would be
            # a guess, not grounded guidance.

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

        # General agronomy FAQ (pest control / sowing) — project-authored,
        # not grounded in the farmer's own data, but still relevant local
        # guidance instead of the single generic canned response.
        if intent in _LOCAL_FAQ:
            faq = _LOCAL_FAQ[intent]
            return faq.get(lang, faq["en"])

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
    answer = await _fallback_answer(question, picked, plot, plot_ctx, last_class, lang)
    if not picked:
        # Surface which offline data source actually answered a non-disease
        # question (weather/soil grounded in the farmer's own live data;
        # faq:* is project-authored general guidance, not farm-specific) —
        # same transparency AssistantAnswer already gives for disease cards.
        intent = _detect_intent(question)
        if intent == "weather" and plot and plot.get("lat") is not None:
            grounded_on.append("weather")
        elif intent == "soil" and plot and (plot.get("soil_snapshot") or {}).get("texture_class"):
            grounded_on.append("soil")
        elif intent in _LOCAL_FAQ or intent == "weather":
            grounded_on.append(f"faq:{intent if intent != 'weather' else 'irrigation'}")
    return AssistantAnswer(answer=answer, grounded_on=grounded_on, used_llm=used_llm, lang=lang)


async def warm_up() -> None:
    """Delegates to the shared gemini service — see its warm_up() for what
    this pays for and why. A missing/invalid key or a flaky network just
    means it's skipped; the assistant still works, just slower on the
    first question."""
    await gemini_service.warm_up()
