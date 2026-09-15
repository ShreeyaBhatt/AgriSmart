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
from ..models.modules import ActionShortcut, AssistantAnswer
from . import gemini as gemini_service
from . import llm as llm_service
from .units import describe_area

log = logging.getLogger(__name__)
_WORD = re.compile(r"[\w]{2,}", re.UNICODE)
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

# Rich intents the offline fallback answers with practical guidance instead of
# a repetitive generic card-missing message. Checked in this order.
_INTENT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "greeting": {
        "en": ["hi", "hello", "hey", "namaste", "namaskar", "greetings", "good morning", "good evening", "who are you", "what can you do", "introduce"],
        "hi": ["नमस्ते", "नमस्कार", "प्रणाम", "हाय", "हेलो", "तुम कौन हो", "क्या कर सकते हो", "परिचय"],
        "gu": ["નમસ્તે", "નમસ્કાર", "કેમ છો", "હેલો", "હાય", "તમે કોણ છો", "શું કરી શકો"],
        "mr": ["नमस्ते", "नमस्कार", "कसे आहात", "हॅलो", "तुम्ही कोण आहात", "काय करू शकता"],
        "ta": ["வணக்கம்", "ஹலோ", "நீ யார்", "என்ன செய்ய முடியும்"],
        "te": ["నమస్కారం", "హలో", "హాయ్", "నువ్వు ఎవరు", "ఏం చేయగలవు"],
        "pa": ["ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "ਨਮਸਤੇ", "ਹੈਲੋ", "ਤੁਸੀਂ ਕੌਣ ਹੋ", "ਕੀ ਕਰ ਸਕਦੇ ਹੋ"],
    },
    "weather": {
        "en": ["rain", "weather", "temperature", "forecast", "wind", "humid", "irrigat", "water"],
        "hi": ["बारिश", "मौसम", "तापमान", "पूर्वानुमान", "हवा", "नमी", "सिंचाई", "पानी"],
        "gu": ["વરસાદ", "હવામાન", "તાપમાન", "આગાહી", "પવન", "ભેજ", "સિંચાઈ", "પાણી"],
        "mr": ["पाऊस", "हवामान", "तापमान", "अंदाज", "वारा", "आर्द्रता", "सिंचन", "पाणी"],
        "ta": ["மழை", "வானிலை", "வெப்பநிலை", "முன்னறிவிப்பு", "காற்று", "நீர்ப்பாசனம்", "தண்ணீர்"],
        "te": ["వర్షం", "వాతావరణం", "ఉష్ణోగ్రత", "సూచన", "గాలి", "నీటిపారుదల", "నీరు"],
        "pa": ["ਮੀਂਹ", "ਮੌਸਮ", "ਤਾਪਮਾਨ", "ਪੂਰਵ ਅਨੁਮਾਨ", "ਹਵਾ", "ਸਿੰਚਾਈ", "ਪਾਣੀ"],
    },
    "concoctions": {
        "en": ["jeevamrut", "jeevamrutha", "recipe", "concoction", "neem spray", "neem oil", "agniastra", "dashparni", "bio-pesticide", "organic spray", "kashayam"],
        "hi": ["जीवामृत", "नीम तेल", "अग्नियास्त्र", "दशपर्णी", "जैविक कीटनाशक", "काढ़ा", "नुस्खा"],
        "gu": ["જીવામૃત", "લીમડાનું તેલ", "અગ્નિસ્ત્ર", "દશપર્ણી", "જૈવિક દવા"],
        "mr": ["जीवामृत", "कडुलिंब तेल", "अग्निअस्त्र", "दशपर्णी अर्क", "सेंद्रिय कीटकनाशक"],
        "ta": ["ஜீவாமிர்தம்", "வேப்ப எண்ணெய்", "அக்னி அஸ்திரம்", "தசபர்ணி", "இயற்கை பூச்சிக்கொல்லி"],
        "te": ["జీవామృతం", "వేప నూనె", "అగ్ని అస్త్రం", "దశపర్ణి కషాయం", "సేంద్రీయ పురుగుమందు"],
        "pa": ["ਜੀਵਾਮ੍ਰਿਤ", "ਨਿੰਮ ਦਾ ਤੇਲ", "ਅਗਨੀਅਸਤਰ", "ਦਸ਼ਪਰਣੀ", "ਜੈਵਿਕ ਕੀਟਨਾਸ਼ਕ"],
    },
    "soil": {
        "en": ["fertiliz", "fertilis", "npk", "nitrogen", "phosphorus", "potassium", "nutrient"],
        "hi": ["खाद", "उर्वरक", "नाइट्रोजन", "पोषक"],
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
    "weeding": {
        "en": ["weed", "weeds", "weeding", "unwanted grass", "hoeing"],
        "hi": ["खरपतवार", "निराई", "घास", "गुड़ाई", "खुरपी"],
        "gu": ["નીંદણ", "ખડ", "નિંદામણ"],
        "mr": ["तण", "खुरपणी", "तणनियंत्रण"],
        "ta": ["களை", "களைக்கொல்லி", "களை எடுத்தல்"],
        "te": ["కలుపు", "కలుపుతీత", "కలుపు మందు"],
        "pa": ["ਨਦੀਨ", "ਗੋਡੀ", "ਘਾਹ"],
    },
    "organic": {
        "en": ["organic", "compost", "fym", "vermicompost", "dung", "manure"],
        "hi": ["जैविक", "कम्पोस्ट", "गोबर", "पंचगव्य", "वर्मीकम्पोस्ट", "देसी खाद"],
        "gu": ["જૈવિક", "કમ્પોસ્ટ", "છાણ", "વર્મીકમ્પોસ્ટ"],
        "mr": ["सेंद्रिय", "कंपोस्ट", "शेणखत", "गांडूळखत"],
        "ta": ["இயற்கை", "மக்கும் உரம்", "சாணம்", "மண்புழு உரம்"],
        "te": ["సేంద్రీయ", "కంపోస్ట్", "పేడ", "వర్మీ కంపోస్ట్"],
        "pa": ["ਜੈਵਿਕ", "ਕੰਪੋਸਟ", "ਰੂੜੀ", "ਗੰਡੋਆ ਖਾਦ"],
    },
    "yellow_leaves": {
        "en": ["yellow", "yellow leaf", "yellow leaves", "yellowing", "pale leaves", "chlorosis"],
        "hi": ["पीला", "पीली", "पीले", "पीली पत्ती", "पीले पत्ते", "पत्तियां पीली", "पीलापन"],
        "gu": ["પીળા", "પીળું", "પીળા પાન", "પાંદડા પીળા", "પીળાશ"],
        "mr": ["पिवळी", "पिवळे", "पिवळा", "पिवळी पाने", "पाने पिवळी", "पिवळेपणा"],
        "ta": ["மஞ்சள்", "மஞ்சள் இலை", "இலை மஞ்சள்", "மஞ்சளாதல்"],
        "te": ["పసుపు", "పసుపు ఆకులు", "ఆకులు పసుపు", "పసుపు రంగు"],
        "pa": ["ਪੀਲਾ", "ਪੀਲੇ", "ਪੀਲੇ ਪੱਤੇ", "ਪੱਤੇ ਪੀਲੇ", "ਪੀਲਾਪਣ"],
    },
    "schemes": {
        "en": ["pm kisan", "pm-kisan", "fasal bima", "subsidy", "insurance", "soil health card", "government scheme", "yojana"],
        "hi": ["पीएम किसान", "फसल बीमा", "सब्सिडी", "सरकारी योजना", "मृदा स्वास्थ्य कार्ड", "योजना"],
        "gu": ["પીએમ કિસાન", "પાક વીમો", "સબસિડી", "સરકારી યોજના", "સોઇલ હેલ્થ કાર્ડ"],
        "mr": ["पीएम किसान", "पीक विमा", "अनुदान", "शासकीय योजना", "सॉईल हेल्थ कार्ड"],
        "ta": ["பிஎம் கிசான்", "பயிர் காப்பீடு", "மானியம்", "அரசு திட்டம்", "மண் நல அட்டை"],
        "te": ["పీఎం కిసాన్", "పంట బీమా", "సబ్సిడీ", "ప్రభుత్వ పథకం", "సాయిల్ హెల్త్ కార్డు"],
        "pa": ["ਪੀਐਮ ਕਿਸਾਨ", "ਫ਼ਸਲ ਬੀਮਾ", "ਸਬਸਿਡੀ", "ਸਰਕਾਰੀ ਸਕੀਮ", "ਸੋਇਲ ਹੈਲਥ ਕਾਰਡ"],
    },
}


def _detect_intent(question: str) -> str | None:
    q = question.lower()
    for intent, by_lang in _INTENT_KEYWORDS.items():
        for keywords in by_lang.values():
            for kw in keywords:
                if len(kw) <= 3:
                    pattern = rf"(?:^|[\s.,!?;:\-_'\"()]){re.escape(kw)}(?:$|[\s.,!?;:\-_'\"()])"
                    if re.search(pattern, q):
                        return intent
                else:
                    if kw in q:
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
        hay = (
            f"{key} {card.get('crop','')} {card.get('disease','')} "
            f"{card.get('crop_hi','')} {card.get('disease_hi','')} "
            f"{card.get('crop_gu','')} {card.get('disease_gu','')} "
            f"{card.get('crop_mr','')} {card.get('disease_mr','')} "
            f"{card.get('crop_ta','')} {card.get('disease_ta','')} "
            f"{card.get('crop_te','')} {card.get('disease_te','')} "
            f"{card.get('crop_pa','')} {card.get('disease_pa','')}"
        )
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
    if plot.get("main_crop"):
        bits.append(f"crop: {plot['main_crop']}")
    planting = plot.get("planting")
    if planting:
        bits.append(f"growth stage: {planting.get('stage')} ({planting.get('crop')})")
    diag = plot.get("latest_diagnosis")
    if diag:
        bits.append(f"recent scan: {diag.get('disease')}")
    weather = plot.get("weather_summary")
    if weather:
        bits.append(f"weather: rain {weather.get('rain_prob', 0)}% (~{weather.get('rain_mm', 0)}mm), max {weather.get('tmax')}°C, wind {weather.get('wind', 0)}km/h")
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
            "I am here to support your farm decisions. For general plant health: ensure proper soil drainage, "
            "inspect leaf undersides weekly for early pests or discoloration, and maintain balanced nutrition. "
            "You can also use the Leaf Scanner on the Scan page to get an instant AI diagnosis with visual explainability, "
            "or check your Plot page for tailored soil and weather advice."
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
            "मैं आपके खेत से जुड़े हर सवाल में सहायता के लिए तैयार हूँ। बेहतर फसल के लिए: खेत में जल निकासी अच्छी रखें, "
            "शुरुआती कीट या धब्बों के लिए पत्तियों के नीचे नियमित जांच करें, और संतुलित खाद दें। "
            "सटीक बीमारी पहचान के लिए 'स्कैन' पेज पर पत्ती की फोटो लें, या अपने 'प्लॉट' पेज पर मौसम व मिट्टी सलाह देखें।"
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
            "હું તમારા ખેતીના દરેક પ્રશ્નમાં સહાય કરવા તૈયાર છું. પાકની તંદુરસ્તી માટે: ખેતરમાં પાણીના નિકાલની યોગ્ય વ્યવસ્થા રાખો, "
            "જીવાત કે ડાઘ માટે પાંદડાની નીચે નિયમિત તપાસ કરો, અને સંતુલિત ખાતર આપો. "
            "ચોક્કસ રોગ નિદાન માટે 'સ્કેન' પેજ પર પાંદડાનો ફોટો લો, અથવા પ્લોટ પેજ પર માટી અને હવામાન સલાહ જુઓ."
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
            "मी आपल्या शेतीच्या प्रत्येक निर्णयात मदत करण्यास तयार आहे. चांगल्या पीक आरोग्यासाठी: शेतात पाण्याचा निचरा चांगला ठेवा, "
            "कीड किंवा डागांसाठी पानांच्या खाली नियमित तपासा, आणि संतुलित खते द्या. "
            "अचूक रोग निदानासाठी 'स्कॅन' पेजवर पानाचा फोटो घ्या, किंवा प्लॉट पेजवर माती व हवामान सल्ला पहा."
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
            "உங்கள் பண்ணை முடிவுகளுக்கு உதவ நான் தயாராக உள்ளேன். பயிர் ஆரோக்கியத்திற்கு: சரியான வடிகால் வசதியை உறுதி செய்யுங்கள், "
            "பூச்சிகள் அல்லது புள்ளிகளுக்கு இலைகளின் அடிப்பகுதியை வாரம் ஒருமுறை ஆய்வு செய்யுங்கள், மற்றும் சமச்சீர் உரமிடுங்கள். "
            "துல்லியமான நோயறிதலுக்கு 'ஸ்கேன்' பக்கத்தில் இலை புகைப்படத்தை எடுக்கவும், அல்லது மண்/வானிலை ஆலோசனையைப் பார்க்கவும்."
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
            "మీ వ్యవసాయ నిర్ణయాలలో సహాయం చేయడానికి నేను సిద్ధంగా ఉన్నాను. పంట ఆరోగ్యానికి: పొలంలో సరైన నీటి పారుదల ఉండేలా చూడండి, "
            "పురుగులు లేదా మచ్చల కోసం ఆకుల కింద వారానికోసారి పరిశీలించండి, మరియు సమతుల్య ఎరువులను వాడండి. "
            "ఖచ్చితమైన రోగ నిర్ధారణ కోసం 'స్కాన్' పేజీలో ఆకు ఫోటో తీయండి, లేదా నేల & వాతావరణ సలహాలను చూడండి."
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
            "ਮੈਂ ਤੁਹਾਡੇ ਖੇਤ ਦੇ ਹਰ ਫੈਸਲੇ ਵਿੱਚ ਮਦਦ ਕਰਨ ਲਈ ਤਿਆਰ ਹਾਂ। ਚੰਗੀ ਫ਼ਸਲ ਲਈ: ਖੇਤ ਵਿੱਚ ਪਾਣੀ ਦੀ ਨਿਕਾਸੀ ਠੀਕ ਰੱਖੋ, "
            "ਕੀੜਿਆਂ ਜਾਂ ਧੱਬਿਆਂ ਲਈ ਪੱਤਿਆਂ ਦੇ ਹੇਠਾਂ ਨਿਯਮਿਤ ਜਾਂਚ ਕਰੋ, ਅਤੇ ਸੰਤੁਲਿਤ ਖਾਦਾਂ ਵਰਤੋ। "
            "ਸਹੀ ਰੋਗ ਪਛਾਣ ਲਈ 'ਸਕੈਨ' ਪੇਜ 'ਤੇ ਪੱਤੇ ਦੀ ਫੋਟੋ ਲਓ, ਜਾਂ ਪਲਾਟ ਪੇਜ 'ਤੇ ਮਿੱਟੀ ਅਤੇ ਮੌਸਮ ਸਲਾਹ ਦੇਖੋ।"
        ),
        "signs": "ਲੱਛਣ",
        "organic": "ਜੈਵਿਕ ਨਿਯੰਤਰਣ",
        "chemical": "ਰਸਾਇਣਕ ਨਿਯੰਤਰਣ",
        "prevention": "ਰੋਕਥਾਮ",
        "plot_advice": "ਤੁਹਾਡੇ ਖੇਤ ({ctx}) ਲਈ, ਪਲਾਟ ਪੇਜ 'ਤੇ ਮਿੱਟੀ ਦੀ ਸਲਾਹ ਵੀ ਦੇਖੋ।",
        "crops_answer": "ਤੁਹਾਡੀ ਮਿੱਟੀ ਅਨੁਸਾਰ, ਇੱਥੇ ਉਗਾਉਣ ਲਈ ਸਭ ਤੋਂ ਵਧੀਆ ਫ਼ਸਲਾਂ ਹਨ: {crops}। {plot_advice}",
    },
}


# Project-authored general agronomy guidance (labelled "general-best-practice"
# deliberately). Used when the offline assistant handles non-disease or open questions.
_LOCAL_FAQ = {
    "greeting": {
        "en": "Hello! I am your AgriSmart farm assistant. I can help you: 1) Diagnose crop diseases from leaf scans with Grad-CAM explainability, 2) Check real-time weather alerts and irrigation timing, 3) Analyze your plot's soil profile (pH, NPK, texture), and 4) Provide expert crop advice. What would you like to know today?",
        "hi": "नमस्ते! मैं आपका एग्रीस्मार्ट (AgriSmart) कृषि सहायक हूँ। मैं आपकी सहायता कर सकता हूँ: 1) पत्ती की फोटो स्कैन करके रोग पहचानना, 2) लाइव मौसम व सिंचाई सलाह देना, 3) मिट्टी परीक्षण (pH, NPK, बनावट) का विश्लेषण, और 4) फसल देखभाल सुझाव। आज आप क्या जानना चाहते हैं?",
        "gu": "નમસ્તે! હું તમારો એગ્રીસ્માર્ટ (AgriSmart) ખેતી સહાયક છું. હું તમને મદદ કરી શકું છું: 1) પાંદડાના ફોટાથી પાકના રોગનું સચોટ નિદાન, 2) લાઇવ હવામાન અને સિંચાઈ સમયની સલાહ, 3) માટી ચકાસણી (pH, NPK) વિશ્લેષણ, અને 4) પાક સંભાળની માહિતી. આજે તમે શું જાણવા માંગો છો?",
        "mr": "नमस्कार! मी आपला अ‍ॅग्रीस्मार्ट (AgriSmart) शेती सहाय्यक आहे. मी तुम्हाला मदत करू शकतो: 1) पानांच्या फोटोवरून पीक रोगांचे अचूक निदान, 2) हवामान व सिंचन सल्ला, 3) माती परीक्षण (pH, NPK) विश्लेषण, आणि 4) पीक संवर्धनाचे मार्गदर्शन. आज आपल्याला काय जाणून घ्यायचे आहे?",
        "ta": "வணக்கம்! நான் உங்கள் அக்ரிஸ்மார்ட் (AgriSmart) பண்ணை உதவியாளர். நான் உதவ முடியும்: 1) இலை ஸ்கேன் மூலம் பயிர் நோய் கண்டறிதல், 2) வானிலை மற்றும் பாசன ஆலோசனை, 3) மண் பரிசோதனை (pH, NPK) பகுப்பாய்வு, மற்றும் 4) பயிர் மேலாண்மை வழிகாட்டல். இன்று உங்களுக்கு என்ன தகவல் வேண்டும்?",
        "te": "నమస్కారం! నేను మీ అగ్రిస్మార్ట్ (AgriSmart) వ్యవసాయ సహాయకుడిని. నేను మీకు సహాయం చేయగలను: 1) ఆకు ఫోటోతో పంట తెగుళ్ల గుర్తింపు, 2) వాతావరణం & నీటిపారుదల సలహాలు, 3) నేల పరీక్ష (pH, NPK) విశ్లేషణ, మరియు 4) పంట సంరక్షణ సూచనలు. ఈరోజు మీరు ఏమి తెలుసుకోవాలనుకుంటున్నారు?",
        "pa": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡਾ ਐਗਰੀਸਮਾਰਟ (AgriSmart) ਖੇਤੀ ਸਹਾਇਕ ਹਾਂ। ਮੈਂ ਤੁਹਾਡੀ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ: 1) ਪੱਤੇ ਦੀ ਫੋਟੋ ਤੋਂ ਫ਼ਸਲ ਦੇ ਰੋਗਾਂ ਦੀ ਪਛਾਣ, 2) ਲਾਈਵ ਮੌਸਮ ਅਤੇ ਸਿੰਚਾਈ ਸਲਾਹ, 3) ਮਿੱਟੀ ਪਰਖ (pH, NPK) ਵਿਸ਼ਲੇਸ਼ਣ, ਅਤੇ 4) ਫ਼ਸਲ ਪ੍ਰਬੰਧਨ ਸੁਝਾਅ। ਅੱਜ ਤੁਸੀਂ ਕੀ ਪੁੱਛਣਾ ਚਾਹੁੰਦੇ ਹੋ?",
    },
    "weeding": {
        "en": "Weed management: The first 20-30 days after sowing are the critical weed-competition period. Perform shallow hoeing or hand weeding to loosen the topsoil and remove weeds before they flower. Using straw or plastic mulch conserves moisture and stops weed emergence naturally.",
        "hi": "खरपतवार नियंत्रण: बुवाई के पहले 20-30 दिन खरपतवार नियंत्रण के लिए सबसे महत्वपूर्ण होते हैं। खुरपी या कल्टीवेटर से उथली गुड़ाई करें ताकि खरपतवार फूल आने से पहले नष्ट हो जाएं। पुआल या सूखी घास की मल्चिंग करने से नमी बनी रहती है और नए खरपतवार नहीं उगते।",
        "gu": "નીંદણ વ્યવસ્થાપન: વાવણી પછીના પ્રથમ 20-30 દિવસ નીંદણ નિયંત્રણ માટે ખૂબ મહત્વના છે. ખુરપી વડે છીછરી ગોડ કરો જેથી નીંદણમાં બીજ બનતા પહેલા તેનો નાશ થાય. સૂકા ઘાસ કે પાંદડાનું મલ્ચિંગ કરવાથી જમીનમાં ભેજ ટકે છે અને નીંદણ અટકે છે.",
        "mr": "तण नियंत्रण: पेरणीनंतरचे पहिले 20-30 दिवस तण नियंत्रणासाठी अत्यंत महत्त्वाचे असतात. खुरपणी करून मुळासह तण काढा जेणेकरून मुख्य पिकाशी स्पर्धा होणार नाही. गवताचे किंवा पेंढ्याचे आच्छादन (मल्चिंग) केल्यास ओलावा टिकून राहतो आणि तण उगवत नाही.",
        "ta": "களை மேலாண்மை: விதைத்த முதல் 20-30 நாட்கள் பயிருக்கு மிக முக்கியமான களைக்காலம். களைகள் பூப்பதற்கு முன் கைக்களை அல்லது இடை உழவு மூலம் அகற்றவும். வைக்கோல் அல்லது காய்ந்த இலைகளைக் கொண்டு மூடாக்கு இடுவதால் ஈரப்பதம் காக்கப்பட்டு களைகள் கட்டுப்படும்.",
        "te": "కలుపు నిర్వహణ: విత్తిన మొదటి 20-30 రోజులు పంటకు కీలకమైన కలుపు కాలం. కలుపు పూతకు రాకముందే చేతితో లేదా గుంటుకతో తీసివేయండి. ఎండుగడ్డితో మల్చింగ్ చేయడం వల్ల నేలలో తేమ నిలిచి ఉండి కలుపు మొలకెత్తకుండా ఉంటుంది.",
        "pa": "ਨਦੀਨ ਪ੍ਰਬੰਧਨ: ਬਿਜਾਈ ਤੋਂ ਬਾਅਦ ਪਹਿਲੇ 20-30 ਦਿਨ ਨਦੀਨਾਂ ਦੀ ਰੋਕਥਾਮ ਲਈ ਸਭ ਤੋਂ ਅਹਿਮ ਹੁੰਦੇ ਹਨ। ਗੋਡੀ ਕਰਕੇ ਨਦੀਨਾਂ ਨੂੰ ਫੁੱਲ ਆਉਣ ਤੋਂ ਪਹਿਲਾਂ ਜੜ੍ਹੋਂ ਪੁੱਟੋ। ਪਰਾਲੀ ਜਾਂ ਸੁੱਕੇ ਘਾਹ ਦੀ ਮਲਚਿੰਗ ਕਰਨ ਨਾਲ ਨਮੀ ਬਚਦੀ ਹੈ ਅਤੇ ਨਦੀਨ ਨਹੀਂ ਉੱਗਦੇ।",
    },
    "organic": {
        "en": "Organic soil building: Apply 5-10 tonnes/ha of well-decomposed farmyard manure (FYM) or 2.5 tonnes of vermicompost before final land preparation. Applying liquid Jeevamrut (200 L/acre with irrigation water every 15 days) multiplies beneficial soil microbes and enhances nutrient uptake.",
        "hi": "जैविक पोषण: खेत की अंतिम जुताई से पहले 5-10 टन/हेक्टेयर अच्छी तरह सड़ी गोबर की खाद या 2.5 टन केंचुआ खाद (वर्मीकम्पोस्ट) मिलाएं। हर 15 दिन में सिंचाई के पानी के साथ जीवामृत (200 लीटर/एकड़) देने से मिट्टी के सूक्ष्मजीव बढ़ते हैं और पोषक तत्व आसानी से मिलते हैं।",
        "gu": "જૈવિક ખાતર અને પોષણ: જમીનની છેલ્લી ખેડ વખતે હેક્ટર દીઠ 5-10 ટન સારું કોહવાયેલું છાણિયું ખાતર અથવા 2.5 ટન અળસિયાનું ખાતર (વર્મીકમ્પોસ્ટ) નાખો. દર 15 દિવસે સિંચાઈ સાથે જીવામૃત (200 લિટર/એકર) આપવાથી જમીનમાં સૂક્ષ્મજીવાણુઓ વધે છે.",
        "mr": "सेंद्रिय खत व्यवस्थापन: शेवटच्या नांगरणीच्या वेळी हेक्टरी 5-10 टन चांगले कुजलेले शेणखत किंवा 2.5 टन गांडूळखत जमिनीत मिसळा. दर 15 दिवसांनी सिंचनाच्या पाण्यासोबत जीवामृत (200 लिटर/एकर) दिल्यास जमिनीतील उपयुक्त जीवाणूंची संख्या वाढते.",
        "ta": "இயற்கை ஊட்டச்சத்து: கடைசி உழவின் போது ஒரு ஹெக்டேருக்கு 5-10 டன் மக்கிய தொழு உரம் அல்லது 2.5 டன் மண்புழு உரம் இடுங்கள். 15 நாட்களுக்கு ஒருமுறை பாசன நீருடன் ஜீவாமிர்தம் (200 லிட்டர்/ஏக்கர்) கொடுப்பது மண் நுண்ணுயிரிகளைப் பெருக்கும்.",
        "te": "సేంద్రీయ పోషణ: ఆఖరి దుక్కిలో హెక్టారుకు 5-10 టన్నుల బాగా కుళ్ళిన పశువుల ఎరువు లేదా 2.5 టన్నుల వర్మీ కంపోస్ట్ వేయండి. ప్రతి 15 రోజులకు నీటిపారుదలతో పాటు జీవామృతం (ఎకరానికి 200 లీటర్లు) అందించడం వల్ల నేలలో మేలు చేసే సూక్ష్మజీవులు పెరుగుతాయి.",
        "pa": "ਜੈਵਿਕ ਖਾਦ ਪ੍ਰਬੰਧਨ: ਜ਼ਮੀਨ ਦੀ ਆਖ਼ਰੀ ਤਿਆਰੀ ਵੇਲੇ 5-10 ਟਨ ਪ੍ਰਤੀ ਹੈਕਟੇਅਰ ਚੰਗੀ ਗਲੀ-ਸੜੀ ਰੂੜੀ ਖਾਦ ਜਾਂ 2.5 ਟਨ ਗੰਡੋਆ ਖਾਦ ਪਾਓ। ਹਰ 15 ਦਿਨਾਂ ਬਾਅਦ ਸਿੰਚਾਈ ਦੇ ਪਾਣੀ ਨਾਲ ਜੀਵਾਮ੍ਰਿਤ (200 ਲੀਟਰ/ਏਕੜ) ਦੇਣ ਨਾਲ ਮਿੱਟੀ ਦੀ ਉਪਜਾਊ ਸ਼ਕਤੀ ਵਧਦੀ ਹੈ।",
    },
    "yellow_leaves": {
        "en": "Leaf yellowing diagnostics: 1) If older lower leaves turn yellow first, it indicates Nitrogen deficiency — apply balanced urea or compost tea. 2) If young top leaves turn yellow while veins stay green, it is Iron or Zinc deficiency — spray micronutrient foliar solution. 3) Waterlogging or root rot also causes yellowing — ensure beds drain well. 4) Check undersides for sucking pests like whiteflies or mites. Use the Leaf Scanner to confirm.",
        "hi": "पत्तियों में पीलापन पहचान: 1) यदि पुरानी निचली पत्तियां पहले पीली हों, तो यह नाइट्रोजन की कमी है — संतुलित खाद दें। 2) यदि नई ऊपरी पत्तियां पीली हों और नसें हरी रहें, तो यह सूक्ष्म पोषक (आयरन/जिंक) की कमी है। 3) जलभराव या जड़ सड़न से भी पीलापन आता है — जल निकासी ठीक करें। 4) पत्तियों के नीचे सफेद मक्खी या रस चूसक कीटों की जांच करें। सटीक पहचान के लिए 'स्कैन' से फोटो लें।",
        "gu": "પાંદડા પીળા પડવાના કારણો: 1) જો નીચેના જૂના પાન પહેલા પીળા પડે તો તે નાઇટ્રોજનની ઉણપ છે — સંતુલિત ખાતર આપો. 2) જો ઉપરના નવા પાન પીળા થાય અને નસો લીલી રહે તો તે ઝિંક અથવા આયર્નની ઉણપ છે. 3) વધારે પડતું પાણી ભરાઈ રહેવાથી પણ પાન પીળા પડે છે — પાણીનો નિકાલ કરો. 4) પાંદડાની પાછળ સફેદ માખી કે ચૂસિયા જીવાત તપાસો.",
        "mr": "पाने पिवळी पडण्याची कारणे: 1) खालची जुनी पाने प्रथम पिवळी पडल्यास नत्राची (Nitrogen) कमतरता असू शकते — संतुलित खत द्या. 2) वरची नवीन पाने पिवळी होऊन शिरा हिरव्या राहिल्यास जस्त/लोहाची कमतरता असते — सूक्ष्म अन्नद्रव्यांची फवारणी करा. 3) शेतात पाणी साचल्याने मुळे कुजूनही पाने पिवळी पडतात. 4) पानांखाली पांढरी माशी किंवा कीड तपासा.",
        "ta": "இலைகள் மஞ்சள் நிறமாதல்: 1) கீழ் பழைய இலைகள் முதலில் மஞ்சள் நிறமானால் அது நைட்ரஜன் பற்றாக்குறை — சமச்சீர் உரம் இடவும். 2) இளம் மேல் இலைகள் மஞ்சள் நிறமாகி நரம்புகள் பச்சையாக இருந்தால் இரும்பு/துத்தநாக பற்றாக்குறை. 3) அதிக நீர் தேங்குவதால் வேர் அழுகி இலைகள் மஞ்சளாகலாம் — வடிகால் அமைக்கவும். 4) இலைகளின் அடியில் சாறு உறிஞ்சும் பூச்சிகளைச் சோதிக்கவும்.",
        "te": "ఆకులు పసుపు రంగులోకి మారడానికి కారణాలు: 1) పాత కింది ఆకులు పసుపు రంగులోకి మారితే అది నత్రజని లోపం — సమతుల్య ఎరువు వేయండి. 2) కొత్త పై ఆకులు పసుపు రంగులోకి మారి ఈనెలు ఆకుపచ్చగా ఉంటే జింక్/ఇనుము లోపం — సూక్ష్మపోషకాల స్ప్రే చేయండి. 3) నీరు నిలవడం వల్ల వేరు కుళ్లుతో ఆకులు పసుపు కావచ్చు. 4) ఆకుల కింద తెల్లదోమ లేదా రసం పీల్చే పురుగులను పరిశీలించండి.",
        "pa": "ਪੱਤੇ ਪੀਲੇ ਪੈਣ ਦੇ ਕਾਰਨ: 1) ਜੇਕਰ ਹੇਠਲੇ ਪੁਰਾਣੇ ਪੱਤੇ ਪਹਿਲਾਂ ਪੀਲੇ ਪੈਣ ਤਾਂ ਇਹ ਨਾਈਟ੍ਰੋਜਨ ਦੀ ਘਾਟ ਹੈ — ਸੰਤੁਲਿਤ ਖਾਦ ਪਾਓ। 2) ਜੇਕਰ ਨਵੇਂ ਉੱਪਰਲੇ ਪੱਤੇ ਪੀਲੇ ਪੈਣ ਅਤੇ ਨਾੜੀਆਂ ਹਰੀਆਂ ਰਹਿਣ ਤਾਂ ਇਹ ਜ਼ਿੰਕ ਜਾਂ ਲੋਹੇ ਦੀ ਘਾਟ ਹੈ। 3) ਪਾਣੀ ਖੜ੍ਹਨ ਨਾਲ ਜੜ੍ਹ ਗਲਣ ਕਰਕੇ ਵੀ ਪੱਤੇ ਪੀਲੇ ਪੈ ਸਕਦੇ ਹਨ — ਨਿਕਾਸੀ ਸੁਧਾਰੋ। 4) ਪੱਤਿਆਂ ਹੇਠਾਂ ਚਿੱਟੀ ਮੱਖੀ ਜਾਂ ਰਸ ਚੂਸਣ ਵਾਲੇ ਕੀੜਿਆਂ ਦੀ ਜਾਂਚ ਕਰੋ।",
    },
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
    "concoctions": {
        "en": "Organic Concoctions & Biopesticides:\n1) Neem Oil Spray: Mix 5 ml cold-pressed neem oil with 1 ml mild liquid soap in 1 L water. Spray early morning every 7-10 days against sucking pests (aphids, thrips, whiteflies).\n2) Jeevamrut: In 200 L water, mix 10 kg fresh cow dung, 10 L cow urine, 2 kg jaggery, 2 kg gram flour, and a handful of virgin forest/farm soil. Ferment in shade for 48 hours stirring twice daily. Apply 200 L/acre with irrigation.\n3) Dashparni Ark: Extract of 10 local bitter/medicinal leaves fermented with cow urine and dung — potent broad-spectrum natural pest repellent.",
        "hi": "प्राकृतिक फसल सुरक्षा काढ़ा व घोल:\n1) नीम तेल स्प्रे: 1 लीटर पानी में 5 मिली नीम तेल और 1 मिली हल्का तरल साबुन मिलाएं। रस चूसक कीटों और इल्लियों के लिए सुबह-सुबह हर 7-10 दिन में छिड़कें।\n2) जीवामृत: 200 लीटर पानी में 10 किलो ताजा गोबर, 10 लीटर गोमूत्र, 2 किलो गुड़, 2 किलो बेसन और मुट्ठी भर उपजाऊ खेत की मिट्टी मिलाएं। छाया में 48 घंटे किण्वन करें और दिन में दो बार चलाएं। 200 लीटर/एकड़ सिंचाई के साथ दें।\n3) दशपर्णी अर्क: 10 कड़वी व औषधीय पत्तियों का गोमूत्र में तैयार अर्क — व्यापक जैविक कीट निवारक।",
        "gu": "કુદરતી જૈવિક કીટનાશક અને જીવામૃત:\n1) લીમડાનું તેલ: 1 લિટર પાણીમાં 5 મિલી લીમડાનું તેલ અને 1 મિલી પ્રવાહી સાબુ મેળવી વહેલી સવારે છંટકાવ કરો.\n2) જીવામૃત: 200 લિટર પાણી, 10 કિલો છાણ, 10 લિટર ગૌમૂત્ર, 2 કિલો ગોળ, 2 કિલો બેસન અને મુઠ્ઠીભર વડ નીચેની માટી મેળવી 48 કલાક આથો લાવી પિયત સાથે આપો.\n3) દશપર્ણી અર્ક: 10 કડવા પાંદડાંમાંથી બનેલો અર્ક જે ચૂસિયા જીવાતો સામે અસરકારક છે.",
        "mr": "नैसर्गिक कीटकनाशक व जीवामृत:\n1) निंबोळी अर्क/तेल: 1 लिटर पाण्यात 5 मिली कडुलिंब तेल आणि 1 मिली सौम्य साबण मिसळून रस शोषणाऱ्या किडींवर फवारा.\n2) जीवामृत: 200 लिटर पाण्यात 10 किलो ताजे शेण, 10 लिटर गोमूत्र, 2 किलो गूळ, 2 किलो बेसन आणि एक मूठ बांधाची माती एकत्र करून सावलीत 48 तास आंबवून सिंचनासोबत द्या.\n3) दशपर्णी अर्क: 10 प्रकारच्या कडवट वनस्पतींच्या पानांचा अर्क — नैसर्गिक कीड नियंत्रक.",
        "ta": "இயற்கை பூச்சிவிரட்டி மற்றும் ஜீவாமிர்தம்:\n1) வேப்ப எண்ணெய் கரைசல்: 1 லிட்டர் தண்ணீரில் 5 மிலி வேப்ப எண்ணெய் + 1 மிலி திரவ சோப் கலந்து சாறு உறிஞ்சும் பூச்சிகளுக்கு தெளிக்கவும்.\n2) ஜீவாமிர்தம்: 200 லிட்டர் தண்ணீர், 10 கிலோ பசுஞ்சாணம், 10 லிட்டர் கோமியம், 2 கிலோ வெல்லம், 2 கிலோ பயறு மாவு, ஒரு கைப்பிடி வரப்பு மண் சேர்த்து 48 மணி நேரம் நொதிக்க வைத்து பாசனத்துடன் இடவும்.\n3) தசபர்ணி அசாறு: 10 மூலிகை இலைகளின் சாறு — சிறந்த இயற்கை பூச்சிவிரட்டி.",
        "te": "సేంద్రీయ కషాయాలు & జీవామృతం:\n1) వేప నూనె స్ప్రే: 1 లీటరు నీటిలో 5 మి.లీ వేప నూనె + 1 మి.లీ సబ్బు ద్రవం కలిపి రసం పీల్చే పురుగుల నివారణకు పిచికారీ చేయండి.\n2) జీవామృతం: 200 లీటర్ల నీరు, 10 కిలోల ఆవు పేడ, 10 లీటర్ల ఆవు మూత్రం, 2 కిలోల బెల్లం, 2 కిలోల శనగపిండి, పిడికెడు పుట్టమట్టి కలిపి 48 గంటలు నిల్వ ఉంచి నీటితో పాటు అందించండి.\n3) దశపర్ణి కషాయం: 10 రకాల ఆకులతో తయారు చేసిన సహజ పురుగు నివారిణి.",
        "pa": "ਜੈਵਿਕ ਕੀਟਨਾਸ਼ਕ ਅਤੇ ਜੀਵਾਮ੍ਰਿਤ:\n1) ਨਿੰਮ ਦਾ ਤੇਲ: 1 ਲੀਟਰ ਪਾਣੀ ਵਿੱਚ 5 ਮਿਲੀਲੀਟਰ ਨਿੰਮ ਦਾ ਤੇਲ + 1 ਮਿਲੀਲੀਟਰ ਹਲਕਾ ਸਾਬਣ ਘੋਲ ਕੇ ਰਸ ਚੂਸਣ ਵਾਲੇ ਕੀੜਿਆਂ 'ਤੇ ਸਪਰੇਅ ਕਰੋ।\n2) ਜੀਵਾਮ੍ਰਿਤ: 200 ਲੀਟਰ ਪਾਣੀ, 10 ਕਿਲੋ ਗਾਂ ਦਾ ਗੋਹਾ, 10 ਲੀਟਰ ਗਊਮੂਤਰ, 2 ਕਿਲੋ ਗੁੜ, 2 ਕਿਲੋ ਬੇਸਣ ਅਤੇ ਮੁੱਠੀ ਭਰ ਉਪਜਾਊ ਮਿੱਟੀ ਰਲਾ ਕੇ 48 ਘੰਟੇ ਛਾਂ ਵਿੱਚ ਰੱਖੋ ਅਤੇ ਸਿੰਚਾਈ ਨਾਲ ਵਰਤੋ।\n3) ਦਸ਼ਪਰਣੀ ਅਰਕ: 10 ਕੌੜੇ ਪੱਤਿਆਂ ਦਾ ਅਰਕ — ਸ਼ਕਤੀਸ਼ਾਲੀ ਕੁਦਰਤੀ ਕੀੜੇ ਮਾਰ ਘੋਲ।",
    },
    "schemes": {
        "en": "Key Agricultural Support Schemes:\n1) PM-KISAN: Direct income support of Rs 6,000 per year in 3 equal installments of Rs 2,000 directly to farmer bank accounts.\n2) PM Fasal Bima Yojana (PMFBY): Low-cost crop insurance against weather, drought, flooding, and pest risks (1.5% premium for Rabi, 2% for Kharif).\n3) Soil Health Card: Periodic free soil fertility reports with personalized fertilizer advisories. Contact your local KVK or agricultural office for registration.",
        "hi": "प्रमुख किसान कल्याण योजनाएं:\n1) पीएम-किसान (PM-KISAN): सभी पात्र किसान परिवारों को प्रति वर्ष 6,000 रुपये की वित्तीय सहायता (2,000 रुपये की 3 किस्तों में बैंक खाते में)।\n2) प्रधानमंत्री फसल बीमा योजना (PMFBY): प्राकृतिक आपदाओं व कीट प्रकोप से फसल क्षति पर सुरक्षा (खरीफ 2%, रबी 1.5% प्रीमियम)।\n3) मृदा स्वास्थ्य कार्ड (Soil Health Card): खेत की मिट्टी की जांच और संतुलित खाद सिफारिशें। नजदीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।",
        "gu": "ખેડૂત કલ્યાણકારી સરકારી યોજનાઓ:\n1) પીએમ-કિસાન: ખેડૂતોને વાર્ષિક રૂ. 6,000 ની સહાય (રૂ. 2,000 ના 3 હપ્તામાં સીધા ખાતામાં).\n2) પ્રધાનમંત્રી પાક વીમા યોજના (PMFBY): કુદરતી આપત્તિઓ સામે પાક સુરક્ષા (ખરીફ 2%, રવિ 1.5% પ્રીમિયમ).\n3) સોઇલ હેલ્થ કાર્ડ: જમીન ચકાસણી અને ખાતર માર્ગદર્શન માટે સ્થાનિક કેવીકે (KVK) નો સંપર્ક કરો.",
        "mr": "शेतकरी कल्याणकारी शासकीय योजना:\n1) पीएम-किसान: पात्र शेतकरी कुटुंबांना दरवर्षी 6,000 रुपये थेट बँक खात्यात (2,000 रुपयांच्या 3 हप्त्यांमध्ये).\n2) प्रधानमंत्री पीक विमा योजना (PMFBY): नैसर्गिक आपत्ती आणि रोगराईपासून पिकांचे संरक्षण (खरीप 2%, रब्बी 1.5% हप्ता).\n3) सॉईल हेल्थ कार्ड: मोफत माती परीक्षण व संतुलित खत सल्ला. जवळच्या कृषी विज्ञान केंद्राशी संपर्क साधा.",
        "ta": "முக்கிய விவசாய நலத்திட்டங்கள்:\n1) பிஎம்-கிசான்: விவசாயிகளுக்கு ஆண்டுதோறும் ரூ. 6,000 நிதி உதவி (ரூ. 2,000 வீதம் 3 தவணைகளில்).\n2) பிரதமரின் பயிர் காப்பீட்டுத் திட்டம் (PMFBY): இயற்கை இடர்பாடுகளிலிருந்து பயிர் பாதுகாப்பு (காரீஃப் 2%, ரபி 1.5% பிரீமியம்).\n3) மண் நல அட்டை: மண் பரிசோதனை மற்றும் உர பரிந்துரைகள் பெற வேளாண்மை அலுவலரை அணுகவும்.",
        "te": "ప్రభుత్వ రైతు సంక్షేమ పథకాలు:\n1) పీఎం-కిసాన్: అర్హులైన రైతులకు ఏటా రూ. 6,000 ఆర్థిక సాయం (రూ. 2,000 చొప్పున 3 విడతల్లో).\n2) ప్రధానమంత్రి ఫసల్ బీమా యోజన (PMFBY): ప్రకృతి వైపరీత్యాల నుండి పంట రక్షణ (ఖరీఫ్ 2%, రబీ 1.5% ప్రీమియం).\n3) సాయిల్ హెల్త్ కార్డు: ఉచిత నేల పరీక్ష మరియు ఎరువుల సిఫార్సులు. స్థానిక వ్యవసాయ అధికారిని సంప్రదించండి.",
        "pa": "ਮੁੱਖ ਕਿਸਾਨ ਭਲਾਈ ਸਕੀਮਾਂ:\n1) ਪੀਐਮ-ਕਿਸਾਨ: ਕਿਸਾਨਾਂ ਨੂੰ ਸਾਲਾਨਾ 6,000 ਰੁਪਏ ਦੀ ਵਿੱਤੀ ਸਹਾਇਤਾ (2,000 ਰੁਪਏ ਦੀਆਂ 3 ਕਿਸ਼ਤਾਂ ਵਿੱਚ)।\n2) ਪ੍ਰਧਾਨ ਮੰਤਰੀ ਫ਼ਸਲ ਬੀਮਾ ਯੋਜਨਾ (PMFBY): ਕੁਦਰਤੀ ਆਫ਼ਤਾਂ ਤੋਂ ਫ਼ਸਲ ਦਾ ਬੀਮਾ (ਸਾਉਣੀ 2%, ਹਾੜ੍ਹੀ 1.5% ਪ੍ਰੀਮੀਅਮ)।\n3) ਸੋਇਲ ਹੈਲਥ ਕਾਰਡ: ਮੁਫ਼ਤ ਮਿੱਟੀ ਜਾਂਚ ਅਤੇ ਸੰਤੁਲਿਤ ਖਾਦਾਂ ਦੀ ਸਲਾਹ। ਨੇੜਲੇ ਕੇਵੀਕੇ (KVK) ਨਾਲ ਸੰਪਰਕ ਕਰੋ।",
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
            faq = _LOCAL_FAQ.get("organic")
            if faq:
                return faq.get(lang, faq["en"])

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

        # General agronomy FAQ (pest control / sowing / greeting / weeding / organic / yellow_leaves)
        if intent in _LOCAL_FAQ:
            faq = _LOCAL_FAQ[intent]
            return faq.get(lang, faq["en"])

        # Plot-contextual guidance if a plot has a main crop or planting declared
        if plot and (plot.get("main_crop") or plot.get("planting") or plot.get("active_planting")):
            crop_name = plot.get("main_crop") or (plot.get("planting") or {}).get("crop") or (plot.get("active_planting") or {}).get("crop") or "crop"
            crop_guidance = {
                "en": f"For your {crop_name} crop on this plot: maintain steady soil moisture, inspect leaves weekly for signs of spots or wilting, and follow balanced nutrient applications. You can scan a leaf in the Scan tab for an instant disease diagnosis, or check your Plot page for tailored weather and soil advice.",
                "hi": f"आपके इस खेत की {crop_name} फसल के लिए: उचित जल निकासी रखें, पत्तियों के नीचे नियमित रूप से कीड़े या धब्बे जांचें, और संतुलित खाद दें। रोग पहचान के लिए 'स्कैन' टैब में पत्ती की फोटो लें।",
                "gu": f"તમારા આ પ્લોટના {crop_name} પાક માટે: જમીનમાં યોગ્ય ભેજ રાખો, પાંદડા નીચે નિયમિતપણે જીવાત કે ડાઘ તપાસો, અને સંતુલિત ખાતર આપો. સચોટ રોગ તપાસ માટે 'સ્કેન' ટેબમાં પાનનો ફોટો લો.",
                "mr": f"तुमच्या या शेतातील {crop_name} पिकासाठी: पाण्याचा योग्य निचरा ठेवा, पानांखाली कीड किंवा डाग नियमित तपासा, आणि संतुलित खते द्या. अचूक रोग निदानासाठी 'स्कॅन' टॅबमध्ये पानाचा फोटो घ्या.",
                "ta": f"இந்த நிலத்தின் {crop_name} பயிருக்கு: நல்ல வடிகால் வசதி செய்யுங்கள், இலைகளின் அடியில் பூச்சிகள் உள்ளதா என வாரந்தோறும் பாருங்கள், காலையில் நீர் பாய்ச்சுங்கள். நோய் பரிசோதனைக்கு 'ஸ்கேன்' பக்கத்தில் புகைப்படம் எடுக்கவும்.",
                "te": f"ఈ పొలంలోని మీ {crop_name} పంట కోసం: నీరు నిలవకుండా చూడండి, ఆకుల కింద పురుగులు లేదా మచ్చల కోసం వారానికోసారి తనిਖీ చేయండి. 'స్కాన్' ట్యాబ్‌లో ఆకు ఫోటో తీసి పరీక్షించండి.",
                "pa": f"ਤੁਹਾਡੇ ਇਸ ਖੇਤ ਦੀ {crop_name} ਫ਼ਸਲ ਲਈ: ਪਾਣੀ ਦੀ ਨਿਕਾਸੀ ਚੰਗੀ ਰੱਖੋ, ਪੱਤਿਆਂ ਹੇਠਾਂ ਕੀੜੇ ਜਾਂ ਧੱਬੇ ਨਿਯਮਿਤ ਦੇਖੋ, ਅਤੇ ਸਵੇਰੇ ਪਾਣੀ ਦਿਓ। ਰੋਗ ਜਾਂਚ ਲਈ 'ਸਕੈਨ' ਟੈਬ ਵਿੱਚ ਪੱਤੇ ਦੀ ਫੋਟੋ ਲਓ.",
            }
            base = crop_guidance.get(lang, crop_guidance["en"])
            extra: list[str] = []
            planting = plot.get("planting") or plot.get("active_planting")
            if planting and planting.get("stage"):
                extra.append(f"Current growth stage: {planting['stage']}.")
            diag = plot.get("latest_diagnosis")
            if diag and diag.get("disease"):
                extra.append(f"Latest leaf scan: {diag['disease']}.")
            weather = plot.get("weather_summary")
            if weather:
                extra.append(f"Weather alert: {weather.get('rain_prob', 0)}% rain probability (~{weather.get('rain_mm', 0)} mm).")
            if extra:
                return base + "\n\n" + " ".join(extra)
            return base

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


_FOLLOWUP_MAP: dict[str, dict[str, list[str]]] = {
    "disease": {
        "en": ["What is the safety waiting period before harvest?", "Is it safe to spray in today's weather?", "What organic alternatives can I use?"],
        "hi": ["दवा छिड़कने के कितने दिन बाद तुड़ाई करें?", "क्या आज के मौसम में छिड़काव करना सुरक्षित है?", "क्या कोई जैविक विकल्प है?"],
        "gu": ["દવા છાંટ્યા પછી કેટલા દિવસે વીણણી કરવી?", "શું આજના હવામાનમાં છંટકાવ કરવો યોગ્ય છે?", "શું કોઈ જૈવિક વિકલ્પ છે?"],
        "mr": ["फवारणीनंतर किती दिवसांनी काढणी करावी?", "आजच्या हवामानात फवारणी करणे सुरक्षित आहे का?", "काही सेंद्रिय पर्याय आहे का?"],
        "ta": ["மருந்து தெளித்த எத்தனை நாட்கள் கழித்து அறுவடை செய்ய வேண்டும்?", "இன்றைய வானிலையில் மருந்து தெளிப்பது பாதுகாப்பானதா?", "இயற்கை வழி முறை உள்ளதா?"],
        "te": ["మందు పిచికారీ చేసిన ఎన్ని రోజులకు కోత కోయాలి?", "ఈ రోజు వాతావరణంలో పిచికారీ చేయడం సురక్షితమేనా?", "ఏదైనా సేంద్రీయ నివారణ ఉందా?"],
        "pa": ["ਦਵਾਈ ਛਿੜਕਣ ਤੋਂ ਕਿੰਨੇ ਦਿਨ ਬਾਅਦ ਤੁੜਾਈ ਕਰੀਏ?", "ਕੀ ਅੱਜ ਦੇ ਮੌਸਮ ਵਿੱਚ ਸਪਰੇਅ ਕਰਨਾ ਸਹੀ ਹੈ?", "ਕੀ ਕੋਈ ਜੈਵਿਕ ਬਦਲ ਹੈ?"],
    },
    "greeting": {
        "en": ["What crop should I plant this season?", "How to prepare organic Jeevamrut?", "Why are my leaves turning yellow?"],
        "hi": ["इस मौसम में कौन सी फसल लगाएं?", "जीवामृत कैसे बनाएं?", "पत्तियां पीली क्यों पड़ रही हैं?"],
        "gu": ["આ ઋતુમાં કયો પાક વાવવો?", "જીવામૃત કેવી રીતે બનાવવું?", "પાંદડા કેમ પીળા પડે છે?"],
        "mr": ["या हंगामात कोणते पीक घ्यावे?", "जीवामृत कसे तयार करावे?", "पाने पिवळी का पडत आहेत?"],
        "ta": ["இந்த பருவத்தில் என்ன பயிர் நடலாம்?", "ஜீவாமிர்தம் தயாரிப்பது எப்படி?", "இலைகள் ஏன் மஞ்சளாகின்றன?"],
        "te": ["ఈ సీజన్‌లో ఏ పంట వేయాలి?", "జీవామృతం ఎలా తయారు చేయాలి?", "ఆకులు ఎందుకు పసుపు రంగులోకి మారుతున్నాయి?"],
        "pa": ["ਇਸ ਮੌਸਮ ਵਿੱਚ ਕਿਹੜੀ ਫ਼ਸਲ ਬੀਜੀਏ?", "ਜੀਵਾਮ੍ਰਿਤ ਕਿਵੇਂ ਬਣਾਈਏ?", "ਪੱਤੇ ਪੀਲੇ ਕਿਉਂ ਪੈ ਰਹੇ ਹਨ?"],
    },
    "weather": {
        "en": ["Is wind or rain going to wash off my spray?", "When is the best time to irrigate?", "How to protect crops from heat stress?"],
        "hi": ["क्या बारिश या तेज हवा से दवा धुल जाएगी?", "सिंचाई का सबसे अच्छा समय कौन सा है?", "फसल को तेज धूप व गर्मी से कैसे बचाएं?"],
        "gu": ["શું વરસાદ કે પવનથી દવા ધોવાઈ જશે?", "પિયત આપવાનો શ્રેષ્ઠ સમય કયો છે?", "પાકને ગરમીથી કેવી રીતે બચાવવો?"],
        "mr": ["पाऊस किंवा वाऱ्यामुळे औषध वाहून जाईल का?", "पाणी देण्याची सर्वोत्तम वेळ कोणती?", "उष्णतेपासून पिकाचे रक्षण कसे करावे?"],
        "ta": ["மழை அல்லது காற்றால் மருந்து வீணாகுமா?", "நீர்ப்பாசனம் செய்ய சிறந்த நேரம் எது?", "வெப்ப அழுத்தத்திலிருந்து பயிரை காப்பது எப்படி?"],
        "te": ["వర్షం లేదా గాలి వల్ల మందు కొట్టుకుపోతుందా?", "నీరు పెట్టడానికి ఉత్తమ సమయం ఏది?", "ఎండ వేడిమి నుండి పంటను ఎలా కాపాడాలి?"],
        "pa": ["ਕੀ ਮੀਂਹ ਜਾਂ ਹਵਾ ਨਾਲ ਦਵਾਈ ਧੁੜ ਜਾਵੇਗੀ?", "ਸਿੰਚਾਈ ਦਾ ਸਭ ਤੋਂ ਵਧੀਆ ਸਮਾਂ ਕਿਹੜਾ ਹੈ?", "ਫ਼ਸਲ ਨੂੰ ਗਰਮੀ ਤੋਂ ਕਿਵੇਂ ਬਚਾਈਏ?"],
    },
    "soil": {
        "en": ["How to test soil pH and texture?", "How much vermicompost per acre?", "Which crops suit my soil type?"],
        "hi": ["मिट्टी का pH और बनावट कैसे जांचें?", "प्रति एकड़ कितना वर्मीकम्पोस्ट डालें?", "मेरी मिट्टी के लिए कौन सी फसल उत्तम है?"],
        "gu": ["જમીનનું pH અને પ્રકાર કેવી રીતે તપાસવું?", "એકર દીઠ કેટલું અળસિયાનું ખાતર નાખવું?", "મારી જમીન માટે કયો પાક શ્રેષ્ઠ છે?"],
        "mr": ["मातीचा सामू (pH) कसा तपासावा?", "एकरला किती गांडूळखत द्यावे?", "माझ्या जमिनीसाठी कोणते पीक योग्य आहे?"],
        "ta": ["மண் pH மற்றும் வகையை எப்படி அறிவது?", "ஒரு ஏக்கருக்கு எவ்வளவு மண்புழு உரம்?", "என் மண்ணுக்கு ஏற்ற பயிர் எது?"],
        "te": ["నేల pH మరియు రకాన్ని ఎలా పరీక్షించాలి?", "ఎకరానికి ఎంత వర్మీ కంపోస్ట్ వేయాలి?", "నా నేలకు ఏ పంట అనుకూలం?"],
        "pa": ["ਮਿੱਟੀ ਦਾ pH ਕਿਵੇਂ ਜਾਂਚੀਏ?", "ਪ੍ਰਤੀ ਏਕੜ ਕਿੰਨੀ ਗੰਡੋਆ ਖਾਦ ਪਾਈਏ?", "ਮੇਰੀ ਜ਼ਮੀਨ ਲਈ ਕਿਹੜੀ ਫ਼ਸਲ ਚੰਗੀ ਹੈ?"],
    },
    "yellow_leaves": {
        "en": ["How to treat nitrogen deficiency?", "Could it be root rot or waterlogging?", "Recommend foliar micronutrient spray"],
        "hi": ["नाइट्रोजन की कमी कैसे दूर करें?", "क्या यह जड़ सड़न या जलभराव हो सकता है?", "सूक्ष्म पोषक तत्वों का स्प्रे बताएं"],
        "gu": ["નાઇટ્રોજનની ઉણપ કેવી રીતે દૂર કરવી?", "શું આ મૂળનો સડો હોઈ શકે?", "સૂક્ષ્મ પોષકતત્વોનો સ્પ્રે જણાવો"],
        "mr": ["नत्राची कमतरता कशी भरून काढावी?", "हा मुळकूज किंवा अतिपाण्याचा परिणाम आहे का?", "सूक्ष्म अन्नद्रव्यांची फवारणी सांगा"],
        "ta": ["நைட்ரஜன் பற்றாக்குறையை எப்படி சரிசெய்வது?", "இது வேர் அழுகல் காரணமா?", "நுண்ணூட்டச்சத்து தெளிப்பு பரிந்துரைக்கவும்"],
        "te": ["నత్రజని లోపాన్ని ఎలా సరిదిద్దాలి?", "ఇది వేరు కుళ్లు లేదా నీరు నిలవడం వలనా?", "సూక్ష్మపోషకాల స్ప్రే సూచించండి"],
        "pa": ["ਨਾਈਟ੍ਰੋਜਨ ਦੀ ਘਾਟ ਕਿਵੇਂ ਪੂਰੀ ਕਰੀਏ?", "ਕੀ ਇਹ ਜੜ੍ਹ ਗਲਣ ਕਾਰਨ ਹੋ ਸਕਦਾ ਹੈ?", "ਸੂਖ਼ਮ ਤੱਤਾਂ ਦੀ ਸਪਰੇਅ ਦੱਸੋ"],
    },
    "concoctions": {
        "en": ["How to make Jeevamrut for 1 acre?", "What is the dilution ratio of neem oil?", "How to make Dashparni ark repellent?"],
        "hi": ["1 एकड़ के लिए जीवामृत कैसे तैयार करें?", "नीम के तेल का सही अनुपात क्या है?", "दशपर्णी अर्क कैसे बनाएं?"],
        "gu": ["1 એકર માટે જીવામૃત કેવી રીતે બનાવવું?", "લીમડાના તેલનું યોગ્ય પ્રમાણ શું છે?", "દશપર્ણી અર્ક કેવી રીતે બનાવવો?"],
        "mr": ["1 एकरासाठी जीवामृत कसे बनवावे?", "कडुलिंब तेलाचे योग्य प्रमाण काय आहे?", "दशपर्णी अर्क कसा तयार करावा?"],
        "ta": ["1 ஏக்கருக்கு ஜீவாமிர்தம் செய்வது எப்படி?", "வேப்ப எண்ணெய் கலவை விகிதம் என்ன?", "தசபர்ணி அசாறு தயாரிப்பது எப்படி?"],
        "te": ["1 ఎకరానికి జీవామృతం ఎలా చేయాలి?", "వేప నూనె మోతాదు ఎంత?", "దశపర్ణి కషాయం తయారీ విధానం ఏమిటి?"],
        "pa": ["1 ਏਕੜ ਲਈ ਜੀਵਾਮ੍ਰਿਤ ਕਿਵੇਂ ਬਣਾਈਏ?", "ਨਿੰਮ ਦੇ ਤੇਲ ਦੀ ਸਹੀ ਮਾਤਰਾ ਕੀ ਹੈ?", "ਦਸ਼ਪਰਣੀ ਅਰਕ ਕਿਵੇਂ ਤਿਆਰ ਕਰੀਏ?"],
    },
    "schemes": {
        "en": ["How to check PM-KISAN beneficiary status?", "What documents are needed for PMFBY crop insurance?", "How to get a Soil Health Card?"],
        "hi": ["पीएम-किसान लाभार्थी स्थिति कैसे जांचें?", "फसल बीमा (PMFBY) के लिए कौन से दस्तावेज चाहिए?", "मृदा स्वास्थ्य कार्ड कैसे प्राप्त करें?"],
        "gu": ["પીએમ-કિસાન સ્ટેટસ કેવી રીતે ચેક કરવું?", "પીએમ પાક વીમા માટે કયા દસ્તાવેજો જોઈએ?", "સોઇલ હેલ્થ કાર્ડ કેવી રીતે મેળવવું?"],
        "mr": ["पीएम-किसान लाभार्थी स्थिती कशी तपासावी?", "पीक विम्यासाठी कोणती कागदपत्रे लागतात?", "सॉईल हेल्थ कार्ड कसे मिळवावे?"],
        "ta": ["பிஎம் கிசான் நிலையை எப்படி சரிபார்ப்பது?", "பயிர் காப்பீட்டிற்கு என்ன ஆவணங்கள் தேவை?", "மண் நல அட்டை பெறுவது எப்படி?"],
        "te": ["పీఎం కిసాన్ స్టేటస్ ఎలా తనిఖీ చేయాలి?", "పంట బీమాకు ఏ పత్రాలు అవసరం?", "సాయిల్ హెల్త్ కార్డు ఎలా పొందాలి?"],
        "pa": ["ਪੀਐਮ ਕਿਸਾਨ ਸਥਿਤੀ ਕਿਵੇਂ ਦੇਖੀਏ?", "ਫ਼ਸਲ ਬੀਮੇ ਲਈ ਕਿਹੜੇ ਕਾਗਜ਼ਾਤ ਚਾਹੀਦੇ ਹਨ?", "ਸੋਇਲ ਹੈਲਥ ਕਾਰਡ ਕਿਵੇਂ ਬਣਵਾਈਏ?"],
    },
    "general": {
        "en": ["What disease symptoms should I look for?", "When is the next irrigation needed?", "What organic fertiliser is recommended?"],
        "hi": ["फसल में किन रोग लक्षणों पर नजर रखें?", "अगली सिंचाई कब करनी चाहिए?", "कौन सी जैविक खाद उत्तम रहेगी?"],
        "gu": ["પાકમાં કયા રોગના લક્ષણો જોવા મળે છે?", "આગામી સિંચાઈ ક્યારે કરવી?", "કયું જૈવિક ખાતર વાપરવું?"],
        "mr": ["पिकात कोणत्या रोगाची लक्षणे पहावीत?", "पुढील पाणी कधी द्यावे?", "कोणते सेंद्रिय खत योग्य राहील?"],
        "ta": ["பயிரில் என்ன நோய் அறிகுறிகளைப் பார்க்க வேண்டும்?", "அடுத்த பாசனம் எப்போது?", "என்ன இயற்கை உரம் பரிந்துரைக்கப்படுகிறது?"],
        "te": ["పంటలో ఎలాంటి తెగుళ్ల లక్షణాలు చూడాలి?", "తదుపరి నీరు ఎప్పుడు పెట్టాలి?", "ఏ సేంద్రీయ ఎరువు సిఫార్సు చేయబడింది?"],
        "pa": ["ਫ਼ਸਲ ਵਿੱਚ ਕਿਹੜੇ ਰੋਗਾਂ ਦੇ ਲੱਛਣ ਦੇਖਣੇ ਚਾਹੀਦੇ ਹਨ?", "ਅਗਲਾ ਪਾਣੀ ਕਦੋਂ ਲਾਈਏ?", "ਕਿਹੜੀ ਜੈਵਿਕ ਖਾਦ ਪਾਉਣੀ ਚਾਹੀਦੀ ਹੈ?"],
    },
}


def _resolve_context_query(question: str, history: list | None = None) -> str:
    """If the question is brief or uses pronouns ('how to treat it', 'what dose', 'can I spray'),
    extract crop and disease context from previous turns in the conversation."""
    if not history:
        return question

    q_low = question.lower()
    cards_map = _cards()
    crops_known = {c.get("crop", "").lower() for c in cards_map.values() if c.get("crop")} | {
        "wheat", "rice", "paddy", "cotton", "sugarcane", "maize", "mustard", "chilli", "onion",
        "garlic", "groundnut", "soybean", "potato", "tomato", "gram", "bajra", "jowar", "barley",
    }
    diseases_known = {c.get("disease", "").lower() for c in cards_map.values() if c.get("disease")} | {
        "rust", "blight", "rot", "scab", "mildew", "spot", "mosaic", "curl", "smut", "wilt",
    }

    # If the user already asked about a specific crop or disease without pronouns, don't contaminate
    has_own_crop = any(crop in q_low for crop in crops_known if len(crop) >= 4)
    has_own_disease = any(dis in q_low for dis in diseases_known if len(dis) >= 4)
    has_pronoun = any(p in q_low.split() for p in ["it", "this", "that", "same", "also", "too", "these", "those"])
    if (has_own_crop or has_own_disease) and not has_pronoun:
        return question

    needs_context = (
        len(question.split()) <= 6
        or has_pronoun
        or any(w in q_low for w in ["the disease", "cure", "spray", "treat", "dose", "chemical", "waiting period"])
    )
    if not needs_context:
        return question

    context_words: list[str] = []
    for msg in reversed(history[-4:]):
        if isinstance(msg, dict):
            content = (msg.get("content") or msg.get("text") or msg.get("answer") or "").lower()
        else:
            content = (getattr(msg, "content", None) or getattr(msg, "text", None) or getattr(msg, "answer", None) or "").lower()

        for crop in crops_known:
            if crop and crop in content and crop not in context_words and not has_own_crop:
                context_words.append(crop)
        for dis in diseases_known:
            if dis and dis in content and dis not in context_words and not has_own_disease:
                context_words.append(dis)
        if len(context_words) >= 2:
            break

    if context_words:
        return f"{question} {' '.join(context_words)}"
    return question


def _generate_followups(
    question: str, intent: str | None, picked: list[tuple[str, dict]], plot: dict | None, lang: str = "en"
) -> list[str]:
    key = "general"
    if picked:
        key = "disease"
    elif intent in _FOLLOWUP_MAP:
        key = intent
    elif intent == "organic":
        key = "soil"
    elif intent == "weeding":
        key = "general"

    lang_map = _FOLLOWUP_MAP.get(key, _FOLLOWUP_MAP["general"])
    return lang_map.get(lang, lang_map["en"])


def _generate_shortcuts(
    question: str, intent: str | None, picked: list[tuple[str, dict]], plot: dict | None
) -> list[ActionShortcut]:
    shortcuts: list[ActionShortcut] = []
    q_low = question.lower()

    if picked or intent in ("pest", "yellow_leaves") or any(w in q_low for w in ["leaf", "spot", "disease", "rot", "blight", "rust", "scan", "photo"]):
        shortcuts.append(ActionShortcut(label="Scan Leaf Diagnosis", icon="camera", route="/scan"))

    if intent in ("weather", "irrigation") or any(w in q_low for w in ["weather", "rain", "temperature", "wind", "spray", "water"]):
        shortcuts.append(ActionShortcut(label="3-Day Weather Advisory", icon="sun", route="/weather"))

    if intent in ("soil", "organic") or any(w in q_low for w in ["soil", "fertiliz", "npk", "ph", "compost", "manure"]):
        shortcuts.append(ActionShortcut(label="Soil Analysis & NPK", icon="flask", route="/soil"))

    if plot and plot.get("id"):
        shortcuts.append(ActionShortcut(label=f"Plot: {plot.get('name', 'Farm')}", icon="sprout", route=f"/plots/{plot['id']}"))

    if not shortcuts:
        shortcuts.append(ActionShortcut(label="Scan Leaf Diagnosis", icon="camera", route="/scan"))
        shortcuts.append(ActionShortcut(label="Weather Forecast", icon="sun", route="/weather"))

    return shortcuts[:3]


async def answer_question(
    question: str, *, lang: str = "en", plot: dict | None = None, last_class: str | None = None,
    land_unit: str = "ha", bigha_region: str | None = None,
    history: list[dict] | None = None,
) -> AssistantAnswer:
    resolved_q = _resolve_context_query(question, history)
    picked = _retrieve(resolved_q, last_class)
    plot_ctx = _plot_context(plot, land_unit, bigha_region)
    grounded_on = [k for k, _ in picked] + (["plot"] if plot_ctx else [])

    context_parts = []
    for key, card in picked:
        context_parts.append(f"[{key}] " + json.dumps(card, ensure_ascii=False))
    if plot_ctx:
        context_parts.append(f"[plot] {plot_ctx}")
    context = "\n".join(context_parts) or "(no matching card)"

    s = get_settings()
    intent = _detect_intent(question) or _detect_intent(resolved_q)

    # Tier 2: Local SLM Provider (CPU in-process)
    if s.llm_provider in ("local", "auto"):
        prompt = llm_service.build_grounded_prompt(question, context, lang=lang)
        llm_text = await llm_service.generate(prompt)
        if llm_text:
            return AssistantAnswer(
                answer=llm_text,
                grounded_on=grounded_on,
                used_llm=True,
                lang=lang,
                engine="Local SLM (Qwen2.5-0.5B)",
                suggested_followups=_generate_followups(question, intent, picked, plot, lang),
                action_shortcuts=_generate_shortcuts(question, intent, picked, plot),
            )

    # Gemini Cloud LLM (optional fallback or when explicitly chosen)
    if (s.llm_provider == "gemini" or s.llm_provider == "auto") and s.gemini_api_key:
        llm_text = await _gemini_answer(question, context, lang)
        if llm_text:
            return AssistantAnswer(
                answer=llm_text,
                grounded_on=grounded_on,
                used_llm=True,
                lang=lang,
                engine="Gemini Cloud",
                suggested_followups=_generate_followups(question, intent, picked, plot, lang),
                action_shortcuts=_generate_shortcuts(question, intent, picked, plot),
            )

    # Tier 3: Zero-Latency Circuit Breaker Fallback
    answer = await _fallback_answer(question, picked, plot, plot_ctx, last_class, lang)
    if not picked:
        if intent == "weather" and plot and plot.get("lat") is not None:
            grounded_on.append("weather")
        elif intent == "soil" and plot and (plot.get("soil_snapshot") or {}).get("texture_class"):
            grounded_on.append("soil")
        elif intent in _LOCAL_FAQ or intent == "weather":
            grounded_on.append(f"faq:{intent if intent != 'weather' else 'irrigation'}")
        elif intent == "soil":
            grounded_on.append("faq:organic")
        elif plot and plot.get("main_crop"):
            grounded_on.append("plot:crop")

    return AssistantAnswer(
        answer=answer,
        grounded_on=grounded_on,
        used_llm=False,
        lang=lang,
        engine="Tier 1 Deterministic Core",
        suggested_followups=_generate_followups(question, intent, picked, plot, lang),
        action_shortcuts=_generate_shortcuts(question, intent, picked, plot),
    )



async def warm_up() -> None:
    """Delegates to the shared gemini service — see its warm_up() for what
    this pays for and why. A missing/invalid key or a flaky network just
    means it's skipped; the assistant still works, just slower on the
    first question."""
    await gemini_service.warm_up()
