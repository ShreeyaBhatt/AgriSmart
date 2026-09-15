"""Module E — GenAI Farmer Assistant.

Retrieval‑augmented: find the relevant disease card(s), add the farmer's live
plot / soil / last‑diagnosis context, then either ask Gemini (when
``GEMINI_API_KEY`` is set) or compose a grounded answer straight from the card.
Either way the answer is grounded in the same corpus.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from ..config import get_settings
from ..models.modules import ActionShortcut, AssistantAnswer
from . import gemini as gemini_service
from . import llm as llm_service
from .units import describe_area

log = logging.getLogger(__name__)
_WORD = re.compile(r"[^\s.,!?;:\-_/\\@#$%^&*()+=\[\]{}|<>~`।॥0-9]{2,}", re.UNICODE)
# Expanded stop words to reduce retrieval bias across English and 6 Indic languages.
_STOP = {
    "the", "and", "for", "with", "how", "what", "why", "when", "should", "does",
    "can", "are", "was", "were", "this", "that", "have", "has", "from", "into",
    "leaf", "leaves", "plant", "crop", "disease", "farm", "help", "please",
    "about", "tell", "more", "treat", "treatment", "cure", "cause", "prevent",
    "control", "spray", "apply", "use", "much", "often", "which", "best",
    "common", "affected", "infection", "infected", "damage", "damaged",
    "problem", "issue", "solution", "remedy", "organic", "chemical",
    "fungicide", "pesticide", "fertilizer", "fertiliser", "soil", "water",
    # Hindi
    "में", "का", "की", "के", "है", "हैं", "क्या", "कैसे", "को", "से", "पर", "और", "बताएं", "दीजिए",
    # Gujarati
    "માં", "નો", "ની", "નું", "ના", "છે", "કેવી", "રીતે", "શું", "કેમ", "અને", "પર", "જણાવો", "આપો",
    # Marathi
    "मध्ये", "चा", "ची", "चे", "आहे", "आहेत", "काय", "कसे", "आणि", "वर", "सांगा",
    # Tamil
    "என்ன", "எப்படி", "மற்றும்", "இல்", "க்கு", "சொல்லுங்கள்",
    # Telugu
    "లో", "యొక్క", "మరియు", "ఎలా", "ఏమిటి", "చెప్పండి",
    # Punjabi
    "ਵਿੱਚ", "ਦਾ", "ਦੀ", "ਦੇ", "ਹੈ", "ਹਨ", "ਕੀ", "ਕਿਵੇਂ", "ਅਤੇ", "ਦੱਸੋ",
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
    "spray_weather": {
        "en": [
            "should i spray", "can i spray", "spray today", "spray tomorrow",
            "spray today or tomorrow", "today or tomorrow", "when to spray",
            "when should i spray", "safe to spray", "is it safe to spray",
            "spray pesticide", "spray insecticide", "spray fungicide",
            "spray chemical", "time to spray", "wash off", "wash my spray",
            "spray drift", "spray in rain", "spray in wind", "rain after spray",
            "wind or rain", "wash away"
        ],
        "hi": [
            "स्प्रे करें या नहीं", "आज स्प्रे करें", "कल स्प्रे करें", "क्या आज छिड़काव",
            "छिड़काव करें या नहीं", "छिड़काव का सही समय", "कब स्प्रे करें",
            "दवा धुल", "धुल जाएगी", "बारिश में स्प्रे", "हवा में स्प्रे"
        ],
        "gu": [
            "આજે સ્પ્રે કરવો કે કાલે", "શું આજે સ્પ્રે કરી શકાય", "છંટકાવ કરવો કે નહીં",
            "છંટકાવ નો સમય", "ક્યારે સ્પ્રે કરવો", "દવા ધોવાઈ", "ધોવાઈ જશે",
            "વરસાદમાં સ્પ્રે", "પવનમાં સ્પ્રે"
        ],
        "mr": [
            "आज फवारणी करावी का", "उद्या फवारणी करावी का", "फवारणी कधी करावी",
            "फवारणी करावी की नाही", "औषध वाहून", "वाहून जाईल", "पावसात फवारणी", "वाऱ्यात फवारणी"
        ],
        "ta": [
            "இன்று தெளிக்கலாமா", "நாளை தெளிக்கலாமா", "மருந்து தெளிக்கலாமா",
            "எப்போது தெளிக்க வேண்டும்", "மருந்து வீணாகு", "மழையில் மருந்து", "காற்று மருந்து", "கழுவிச் செல்ல"
        ],
        "te": [
            "ఈ రోజు పిచికారీ చేయవచ్చా", "రేపు పిచికారీ చేయవచ్చా", "పిచికారీ ఎప్పుడు చేయాలి",
            "మందు కొట్టుకు", "కొట్టుకుపోతుందా", "వర్షంలో పిచికారీ"
        ],
        "pa": [
            "ਕੀ ਅੱਜ ਸਪਰੇਅ ਕਰੀਏ", "ਕੱਲ੍ਹ ਸਪਰੇਅ ਕਰੀਏ", "ਸਪਰੇਅ ਕਦੋਂ ਕਰੀਏ",
            "ਦਵਾਈ ਧੁੜ", "ਧੋਤੀ ਜਾਵੇਗੀ", "ਮੀਂਹ ਵਿੱਚ ਸਪਰੇਅ"
        ],
    },
    "heat_stress": {
        "en": ["heat stress", "heatwave", "high temperature", "protect from heat", "sunburn", "hot weather"],
        "hi": ["तेज धूप", "गर्मी", "लू", "तापमान से बचा", "धूप से बचा"],
        "gu": ["લૂ", "ગરમી", "વધારે તાપમાન", "ગરમીથી બચાવ"],
        "mr": ["उष्णता", "उन्हाळा", "जास्त तापमान", "उष्णतेपासून रक्षण"],
        "ta": ["வெப்ப அழுத்தம்", "அதிக வெப்பம்", "வெப்பத்திலிருந்து காக்க"],
        "te": ["ఎండ వేడిమి", "తీవ్ర ఉష్ణోగ్రత", "వేడి నుండి"],
        "pa": ["ਗਰਮੀ", "ਲੂ", "ਵੱਧ ਤਾਪਮਾਨ", "ਗਰਮੀ ਤੋਂ ਬਚਾਅ"],
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
    "agent": {
        "en": ["agent", "autonomous agent", "advisory", "directive", "what should i do", "what to do today", "farm advice", "recommendation for today", "action plan", "what actions"],
        "hi": ["एजेंट", "सलाह", "आज क्या करें", "खेत की सलाह", "कार्य योजना", "सुझाव"],
        "gu": ["એજન્ટ", "સલાહ", "આજે શું કરવું", "ખેતર સલાહ", "કાર્ય યોજના"],
        "mr": ["एजंट", "सल्ला", "आज काय करावे", "शेताचा सल्ला", "कार्य योजना"],
        "ta": ["ஏஜென்ட்", "ஆலோசனை", "இன்று என்ன செய்வது", "பண்ணை ஆலோசனை"],
        "te": ["ఏజెంట్", "సలహా", "ఈ రోజు ఏమి చేయాలి", "వ్యవసాయ సలహా"],
        "pa": ["ਏਜੰਟ", "ਸਲਾਹ", "ਅੱਜ ਕੀ ਕਰੀਏ", "ਖੇਤ ਦੀ ਸਲਾਹ"],
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


def _indic_norm(w: str) -> str:
    """Normalize common vowel variants across Indic scripts for robust root matching."""
    return (
        w.replace("ુ", "ૂ").replace("િ", "ી")
        .replace("ु", "ू").replace("ि", "ी")
        .replace("ி", "ீ").replace("ு", "ூ")
        .replace("ి", "ీ").replace("ు", "ూ")
        .replace("ਿ", "ੀ").replace("ੁ", "ੂ")
    )


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) >= 2}


def _is_disease_treatment_query(question: str) -> bool:
    q = question.lower()
    # Explicit operational/timing questions must NEVER be treated as disease card queries
    if any(phrase in q for phrase in [
        "should i spray", "can i spray", "spray today", "spray tomorrow",
        "today or tomorrow", "when to spray", "safe to spray", "is it safe to spray",
        "spray now", "spray or not", "should i water", "should i irrigate",
        "आज स्प्रे", "कल स्प्रे", "छिड़काव करें या नहीं",
        "આજે સ્પ્રે", "છંટકાવ કરવો કે નહીં",
        "आज फवारणी", "फवारणी करावी का",
        "இன்று தெளிக்கலாமா", "ఈ రోజు పిచికారీ", "ਕੀ ਅੱਜ ਸਪਰੇਅ",
    ]):
        return False

    disease_words = {
        "cure", "treat", "treatment", "medicine", "fungicide", "pesticide", "pesticides", "chemical",
        "remedy", "control", "symptom", "symptoms", "disease", "infection", "waiting period", "harvest",
        "pathogen", "blight", "rot", "rust", "scab", "mildew", "spot",
        "wilt", "curl", "smut", "mosaic", "yellowing", "chlorosis",
        "इलाज", "दवा", "उपचार", "रोग", "लक्षण", "फफूंद", "कीटनाशक", "तुड़ाई",
        "સારવાર", "દવા", "રોગ", "લક્ષણો", "જંતુનાશક", "વીણણી",
        "औषध", "उपचार", "रोग", "लक्षणे", "कीटकनाशक", "काढणी",
        "மருந்து", "சிகிச்சை", "நோய்", "அறிகுறிகள்", "பூச்சிக்கொல்லி", "அறுவடை",
        "మందు", "చికిత్స", "వ్యాధి", "లక్షణాలు", "పురుగుమందు", "కోత",
        "ਦਵਾਈ", "ਇਲਾਜ", "ਰੋਗ", "ਲੱਛਣ", "ਕੀਟਨਾਸ਼ਕ", "ਤੁੜਾਈ",
    }
    return any(w in q for w in disease_words)


def _retrieve(question: str, last_class: str | None) -> list[tuple[str, dict]]:
    cards = _cards()
    picked = []
    intent = _detect_intent(question)
    is_operational = intent in (
        "weather", "irrigation", "soil", "sowing", "weeding", "schemes",
        "greeting", "spray_weather", "heat_stress", "agent",
    )
    if last_class and last_class in cards and not is_operational:
        if _is_disease_treatment_query(question):
            picked = [(last_class, cards[last_class])]

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

        # Name score: exact match (+2) or stem/inflection match (+1)
        name_score = 0
        for q in qk:
            q_norm = _indic_norm(q)
            for h in hay_kw:
                h_norm = _indic_norm(h)
                if q_norm == h_norm:
                    name_score += 2
                    break
                elif len(q_norm) >= 3 and len(h_norm) >= 3 and (q_norm in h_norm or h_norm in q_norm):
                    name_score += 1
                    break

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
    "spray_weather": {
        "en": "Weather & Spraying Guidelines:\n1) Rain wash-off: Do not spray pesticides, fungicides, or foliar nutrients if rain is expected within 4 to 6 hours. Most chemical and organic sprays require 2 to 4 hours of dry foliage to absorb or adhere properly; rain earlier than that washes the active ingredients off leaves into the soil and runoff, wasting money and reducing pest control.\n2) Wind drift: Never spray when wind speed exceeds 15 km/h. High winds cause spray droplets to drift away from target foliage onto neighboring plots or into the air.\n3) Ideal spray window: Calm early mornings (after dew dries) or late afternoons with wind under 10 km/h and temperatures below 30°C.",
        "hi": "स्प्रे और मौसम संबंधी महत्वपूर्ण नियम:\n1) बारिश से धुलाई: यदि अगले 4-6 घंटों में बारिश की संभावना हो तो कीटनाशक, फफूंदनाशक या टॉनिक का छिड़काव न करें। दवा को पत्तियों में समाने के लिए 2-4 घंटे का सूखा समय चाहिए, अन्यथा बारिश पूरी दवा बहा देती है।\n2) हवा का बहाव: हवा की गति 15 किमी/घंटा से अधिक होने पर स्प्रे कभी न करें। तेज हवा से दवा उड़कर लक्ष्य से भटक जाती है।\n3) सर्वोत्तम समय: सुबह (ओस सूखने के बाद) या देर शाम, जब हवा 10 किमी/घंटा से कम हो और तापमान 30°C से नीचे रहे।",
        "gu": "સ્પ્રે અને હવામાન માર્ગદર્શિકા:\n1) વરસાદથી ધોવાણ: જો આગામી 4 થી 6 કલાકમાં વરસાદની શક્યતા હોય તો કીટનાશક કે ફૂગનાશકનો છંટકાવ ન કરવો. પાંદડા પર દવા ચોંટવા 2 થી 4 કલાક સૂકો સમય જરૂરી છે, નહીં તો વરસાદ દવા ધોઈ નાખશે.\n2) પવન: પવનની ગતિ 15 કિમી/કલાકથી વધુ હોય ત્યારે સ્પ્રે ટાળો જેથી દવાનું ડ્રિફ્ટિંગ ન થાય.\n3) શ્રેષ્ઠ સમય: વહેલી સવારે (ઝાકળ સુકાઈ ગયા પછી) અથવા સાંજે શાંત વાતાવરણમાં છંટકાવ કરવો.",
        "mr": "फवारणी आणि हवामान मार्गदर्शक:\n1) पावसामुळे वाहून जाणे: पुढील 4 ते 6 तासांत पावसाची शक्यता असल्यास कोणतीही फवारणी करू नका. औषध पानांवर शोषले जाण्यासाठी किमान 2-4 तास पाऊस नसावा, अन्यथा औषध वाहून जाते.\n2) वारा: वाऱ्याचा वेग ताशी 15 किमीपेक्षा जास्त असल्यास फवारणी टाळावी.\n3) योग्य वेळ: सकाळी (दव सुकल्यावर) किंवा संध्याकाळी शांत वाऱ्यात फवारणी करावी.",
        "ta": "தெளிப்பு மற்றும் வானிலை வழிகாட்டுதல்:\n1) மழை பாதிப்பு: அடுத்த 4-6 மணி நேரத்திற்குள் மழை பெய்யும் வாய்ப்பிருந்தால் பூச்சிக்கொல்லி தெளிக்க வேண்டாம். மருந்து இலையில் ஒட்ட 2-4 மணி நேரம் தேவை, மழை பெய்தால் மருந்து வீணாகும்.\n2) காற்று: காற்றின் வேகம் மணிக்கு 15 கிமீ மேல் இருந்தால் தெளிக்காதீர்கள்.\n3) சிறந்த நேரம்: அதிகாலை (பனி காய்ந்த பின்) அல்லது மாலையில் காற்று குறைவாக இருக்கும் போது தெளிக்கவும்.",
        "te": "స్ప్రే & వాతావరణ మార్గదర్శకాలు:\n1) వర్షం ప్రభావం: రాబోయే 4-6 గంటల్లో వర్షం కురిసే అవకాశం ఉంటే ఎటువంటి మందులు పిచికారీ చేయవద్దు. మందు ఆకులకు అంటుకోవడానికి 2-4 గంటల పొడి వాతావరణం అవసరం.\n2) గాలి: గంటకు 15 కి.మీ కంటే ఎక్కువ గాలి వేగం ఉన్నప్పుడు పిచికారీ చేయవద్దు.\n3) ఉత్తమ సమయం: ఉదయం (మంచు ఆరిన తర్వాత) లేదా సాయంత్రం వేళల్లో పిచికారీ చేయండి.",
        "pa": "ਸਪਰੇਅ ਅਤੇ ਮੌਸਮ ਨਿਯਮ:\n1) ਮੀਂਹ ਨਾਲ ਧੋਣਾ: ਜੇਕਰ ਅਗਲੇ 4-6 ਘੰਟਿਆਂ ਵਿੱਚ ਮੀਂਹ ਪੈਣ ਦੀ ਸੰਭਾਵਨਾ ਹੋਵੇ ਤਾਂ ਸਪਰੇਅ ਨਾ ਕਰੋ। ਦਵਾਈ ਪੱਤਿਆਂ ਵਿੱਚ ਰਚਣ ਲਈ 2-4 ਘੰਟੇ ਸੁੱਕਾ ਸਮਾਂ ਚਾਹੀਦਾ ਹੈ।\n2) ਹਵਾ: ਜੇਕਰ ਹਵਾ ਦੀ ਰਫ਼ਤਾਰ 15 ਕਿਲੋਮੀਟਰ/ਘੰਟਾ ਤੋਂ ਵੱਧ ਹੋਵੇ ਤਾਂ ਸਪਰੇਅ ਟਾਲੋ।\n3) ਸਹੀ ਸਮਾਂ: ਸਵੇਰੇ (ਤ੍ਰੇਲ ਸੁੱਕਣ ਤੋਂ ਬਾਅਦ) ਜਾਂ ਸ਼ਾਮ ਨੂੰ ਸ਼ਾਂਤ ਮੌਸਮ ਵਿੱਚ ਸਪਰੇਅ ਕਰੋ।",
    },
    "heat_stress": {
        "en": "Protecting Crops from Heat Stress:\n1) Water management: Apply light, frequent irrigations during pre-dawn (4:00-7:00 AM) or evening to cool the root zone.\n2) Mulching: Spread organic crop residues or straw mulch (5-7 cm layer) to lower soil temperatures by 3-5°C and conserve moisture.\n3) Foliar care: Avoid nitrogen fertilizers during peak heatwaves; spray 1% potassium nitrate (KNO3) or kaolin clay spray to protect canopy foliage from solar scorching.",
        "hi": "फसलों को तेज धूप व गर्मी से बचाने के उपाय:\n1) सिंचाई: सुबह 4 से 7 बजे के बीच हल्की सिंचाई करें ताकि जड़ों का तापमान कम रहे।\n2) मल्चिंग: खेत में पुआल या सूखी पत्तियों की 5-7 सेमी मोटी परत बिछाएं, इससे मिट्टी का तापमान 3-5°C कम रहता है।\n3) छिड़काव: लू के दौरान भारी नाइट्रोजन खाद न दें; पत्तियों पर पोटैशियम या सिलिकॉन आधारित स्प्रे से फसल सुरक्षित रखें।",
        "gu": "પાકને ગરમી અને લૂથી બચાવવાના ઉપાય:\n1) પિયત: વહેલી સવારે (4 થી 7 વાગ્યે) હળવું પિયત આપો જેથી મૂળ ઠંડા રહે.\n2) મલ્ચિંગ: જમીન પર સૂકા ઘાસ કે પાંદડાનું 5-7 સેમી મલ્ચિંગ કરો જેથી જમીનનું તાપમાન 3-5°C ઓછું રહે.\n3) બપોરના સમયે કોઈ સ્પ્રે ન કરવો.",
        "mr": "पिकांना उष्णतेच्या लाटेपासून वाचवण्यासाठी उपाय:\n1) सिंचन: सकाळी 4 ते 7 च्या दरम्यान हलके पाणी द्या जेणेकरून मुळांचा भाग थंड राहील.\n2) आच्छादन (मल्चिंग): पिकांच्या बुंध्याशी पाचट किंवा गवताचे आच्छादन करा, यामुळे जमिनीचे तापमान 3-5°C कमी राहते.\n3) भर उन्हात कोणतीही फवारणी करू नका.",
        "ta": "வெப்ப அழுத்தத்திலிருந்து பயிர்களை பாதுகாக்கும் முறைகள்:\n1) பாசனம்: அதிகாலையில் (4-7 மணி) லேசான பாசனம் செய்து வேர் பகுதியை குளிர்ச்சியாக வைக்கவும்.\n2) மூடாக்கு: வைக்கோல் கொண்டு மூடாக்கு இடுவதால் மண் வெப்பநிலை 3-5°C குறையும்.\n3) கடுமையான வெயில் நேரத்தில் தெளிப்பு செய்யாதீர்கள்.",
        "te": "ఎండ వేడిమి నుండి పంటలను కాపాడే చర్యలు:\n1) నీరు: ఉదయం 4 నుండి 7 గంటల మధ్య తేలికపాటి తడులు ఇవ్వండి.\n2) మల్చింగ్: ఎండుగడ్డితో మల్చింగ్ చేయడం వల్ల నేల ఉష్ణోగ్రత 3-5°C తగ్గుతుంది.\n3) తీవ్రమైన ఎండలో స్ప్రే చేయవద్దు.",
        "pa": "ਫ਼ਸਲਾਂ ਨੂੰ ਗਰਮੀ ਤੋਂ ਬਚਾਉਣ ਦੇ ਤਰੀਕੇ:\n1) ਸਿੰਚਾਈ: ਸਵੇਰੇ 4 ਤੋਂ 7 ਵਜੇ ਦਰਮਿਆਨ ਹਲਕਾ ਪਾਣੀ ਲਾਓ ਤਾਂ ਜੋ ਜੜ੍ਹਾਂ ਠੰਢੀਆਂ ਰਹਿਣ।\n2) ਮਲਚਿੰਗ: ਪਰਾਲੀ ਨਾਲ ਮਲਚਿੰਗ ਕਰੋ, ਇਸ ਨਾਲ ਜ਼ਮੀਨ ਦਾ ਤਾਪਮਾਨ 3-5°C ਘਟਦਾ ਹੈ।\n3) ਦੁਪਹਿਰ ਦੀ ਤੇਜ਼ ਧੁੱਪ ਵਿੱਚ ਸਪਰੇਅ ਨਾ ਕਰੋ।",
    },
    "weather": {
        "en": "Weather Advisory Guidance: Weather conditions directly govern irrigation timing, disease development, and spray efficacy. To view live 3-day temperature, rain probabilities, wind speeds, and smart advisories tailored specifically to your farm, add a plot with GPS coordinates or select your plot in the header above.",
        "hi": "मौसम सलाह: मौसम की स्थिति सिंचाई के समय, रोग फैलाव और दवा छिड़काव को सीधे प्रभावित करती है। अपने खेत के लिए सटीक 3-दिवसीय पूर्वानुमान, बारिश की संभावना और मौसम सलाह पाने के लिए जीपीएस स्थान सहित खेत जोड़ें या ऊपर खेत चुनें।",
        "gu": "હવામાન સલાહ: હવામાન પિયત, રોગચાળો અને સ્પ્રે પર સીધી અસર કરે છે. તમારા ખેતર માટે 3-દિવસીય સચોટ વરસાદ અને પવનની આગાહી મેળવવા પ્લોટ પસંદ કરો.",
        "mr": "हवामान सल्ला: हवामानाचा सिंचन, रोगप्रसार आणि फवारणीवर थेट परिणाम होतो. आपल्या शेताचा थेट 3 दिवसांचा अंदाज आणि सल्ला पाहण्यासाठी स्थानासह शेत जोडा.",
        "ta": "வானிலை ஆலோசனை: உங்கள் நிலத்திற்கான நேரடி 3-நாள் வானிலை முன்னறிவிப்பு மற்றும் பாசன ஆலோசனைகளைப் பெற இருப்பிடத்துடன் வயலைச் சேர்க்கவும்.",
        "te": "వాతావరణ సలహా: మీ పొలానికి సంబంధించిన ప్రత్యక్ష 3 రోజుల సూచనలు మరియు నీటిపారుదల సలహాల కోసం స్థానంతో పొలాన్ని ఎంచుకోండి.",
        "pa": "ਮੌਸਮ ਸਲਾਹ: ਆਪਣੇ ਖੇਤ ਲਈ ਲਾਈਵ 3-ਦਿਨਾ ਮੌਸਮ ਅਤੇ ਸਿੰਚਾਈ ਸਲਾਹ ਲਈ ਟਿਕਾਣੇ ਸਮੇਤ ਖੇਤ ਜੋੜੋ।",
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
    "agent": {
        "en": "AgriSmart Autonomous Agent (Module G) evaluates live weather, soil profile, crop growth stage, and leaf scan diagnoses into real-time operational directives. To run the autonomous agent for your fields, please select or create a plot in the Plots tab.",
        "hi": "एग्रीस्मार्ट स्वायत्त एजेंट (Module G) मौसम, मिट्टी, फसल अवस्था और पत्ती रोग स्कैन को मिलाकर रीयल-टाइम कृषि निर्देश देता है। अपने खेत के लिए स्वायत्त एजेंट चलाने के लिए, कृपया 'खेत' टैब में खेत चुनें या जोड़ें।",
        "gu": "એગ્રીસ્માર્ટ સ્વાયત્ત એજન્ટ હવામાન, જમીન, પાક વૃદ્ધિ અને પાંદડા રોગ નિદાનને જોડીને રીઅલ-ટાઇમ ખેતી નિર્દેશો આપે છે. તમારા ખેતર માટે સ્વાયત્ત એજન્ટ ચલાવવા માટે, 'પ્લોટ' ટેબમાં પ્લોટ પસંદ કરો અથવા ઉમેરો.",
        "mr": "अ‍ॅग्रीस्मार्ट स्वायत्त एजंट हवामान, माती, पिकाची वाढ आणि रोग निदान एकत्र करून थेट शेती सल्ला देतो. आपल्या शेतासाठी स्वायत्त एजंट चालवण्यासाठी, 'शेत' टॅबमध्ये शेत निवडा किंवा जोडा.",
        "ta": "அக்ரிஸ்மார்ட் தன்னாட்சி முகவர் வானிலை, மண், பயிர் வளர்ச்சி நிலை மற்றும் இலை நோய் கண்டறிதலை இணைத்து நிகழ்நேர வழிகாட்டுதலை வழங்குகிறது. உங்கள் நிலத்திற்கு தன்னாட்சி முகவரை இயக்க, 'நிலம்' பக்கத்தில் நிலத்தைத் தேர்ந்தெடுக்கவும்.",
        "te": "అగ్రిస్మార్ట్ అటానమస్ ఏజెంట్ వాతావరణం, నేల, పంట దశ మరియు ఆకు వ్యాధి నిర్ధారణను కలిపి ప్రత్యక్ష వ్యవసాయ ఆదేశాలను అందిస్తుంది. మీ పొలం కోసం అటానమస్ ఏజెంట్‌ను నడపడానికి, దయచేసి 'పొలం' ట్యాబ్‌లో పొలాన్ని ఎంచుకోండి.",
        "pa": "ਐਗਰੀਸਮਾਰਟ ਖ਼ੁਦਮੁਖ਼ਤਿਆਰ ਏਜੰਟ ਮੌਸਮ, ਮਿੱਟੀ, ਫ਼ਸਲ ਦੇ ਵਾਧੇ ਅਤੇ ਪੱਤਾ ਰੋਗ ਜਾਂਚ ਨੂੰ ਜੋੜ ਕੇ ਰੀਅਲ-ਟਾਈਮ ਖੇਤੀ ਨਿਰਦੇਸ਼ ਦਿੰਦਾ ਹੈ। ਆਪਣੇ ਖੇਤ ਲਈ ਖ਼ੁਦਮੁਖ਼ਤਿਆਰ ਏਜੰਟ ਚਲਾਉਣ ਲਈ, ਕਿਰਪਾ ਕਰਕੇ 'ਖੇਤ' ਟੈਬ ਵਿੱਚ ਖੇਤ ਚੁਣੋ ਜਾਂ ਸ਼ਾਮਲ ਕਰੋ।",
    },
}


async def _weather_or_agent_intent_answer(
    plot: dict | None,
    last_class: str | None,
    lang: str,
    question: str = "",
) -> str | None:
    """Grounded in the Bonus Module G Autonomous Agent (ReAct Decision Loop)
    and Module C Weather rule engine. Gathers live weather, crop stage, soil,
    and pathogen risks to formulate precision operational directives.
    Returns None if there's no plot location to fetch a forecast for."""
    if not plot or plot.get("lat") is None or plot.get("lon") is None:
        return None
    try:
        from . import weather as weather_service
        from . import agent as agent_service

        fc = await weather_service.fetch_forecast(plot["lat"], plot["lon"])

        crop_name = (
            plot.get("main_crop")
            or (plot.get("planting") or {}).get("crop")
            or (plot.get("active_planting") or {}).get("crop")
            or "Crop"
        )
        stage_name = (
            (plot.get("planting") or {}).get("stage")
            or (plot.get("active_planting") or {}).get("stage")
        )
        diag = plot.get("latest_diagnosis") or (
            {"predicted_class": last_class, "abstained": False} if last_class else None
        )
        advisory = agent_service.evaluate_advisory(
            plot_id=str(plot.get("id") or "plot"),
            plot_name=plot.get("name") or "Your Farm",
            crop=crop_name,
            stage=stage_name,
            soil_snapshot=plot.get("soil_snapshot"),
            last_diagnosis=diag,
            forecast=fc,
            lang=lang,
        )

        advice = weather_service.build_advice(
            plot["lat"], plot["lon"], fc, last_disease=last_class, lang=lang
        )
    except Exception as exc:
        log.warning("Weather/Agent intent lookup failed, falling through: %s", exc)
        return None

    urgency_badges = {
        "critical": "🚨 CRITICAL",
        "warning": "⚠️ ATTENTION",
        "advisory": "ℹ️ ADVISORY",
        "normal": "✅ OPTIMAL",
    }
    badge = urgency_badges.get(advisory.urgency, "🤖 ADVISORY")

    headers = {
        "en": f"🤖 **Autonomous Farm Agent Directive** ({advisory.plot_name} — {advisory.crop}):\n{badge}: **{advisory.headline}** ({advisory.time_window})",
        "hi": f"🤖 **स्वायत्त कृषि एजेंट निर्देश** ({advisory.plot_name} — {advisory.crop}):\n{badge}: **{advisory.headline}** ({advisory.time_window})",
        "gu": f"🤖 **સ્વાયત્ત કૃષિ એજન્ટ નિર્દેશ** ({advisory.plot_name} — {advisory.crop}):\n{badge}: **{advisory.headline}** ({advisory.time_window})",
        "mr": f"🤖 **स्वायत्त कृषी एजंट सल्ला** ({advisory.plot_name} — {advisory.crop}):\n{badge}: **{advisory.headline}** ({advisory.time_window})",
        "ta": f"🤖 **தன்னாட்சி பண்ணை முகவர் வழிகாட்டுதல்** ({advisory.plot_name} — {advisory.crop}):\n{badge}: **{advisory.headline}** ({advisory.time_window})",
        "te": f"🤖 **స్వయంప్రతిపత్తి గల వ్యవసాయ ఏజెంట్ ఆదేశం** ({advisory.plot_name} — {advisory.crop}):\n{badge}: **{advisory.headline}** ({advisory.time_window})",
        "pa": f"🤖 **ਖ਼ੁਦਮੁਖ਼ਤਿਆਰ ਖੇਤੀ ਏਜੰਟ ਨਿਰਦੇਸ਼** ({advisory.plot_name} — {advisory.crop}):\n{badge}: **{advisory.headline}** ({advisory.time_window})",
    }
    header_text = headers.get(lang, headers["en"])

    actions = [f"{i}. {act.directive}" for i, act in enumerate(advisory.decision_trace.action_plan, 1)]
    actions_block = "\n".join(actions)

    w_details = []
    for wa in advice.actions[:2]:
        w_line = f"• {wa.headline} — {wa.detail}"
        if not any(wa.headline.lower() in a.lower() for a in actions):
            w_details.append(w_line)

    trace_lines = []
    if advisory.decision_trace.conflicts_detected:
        for c in advisory.decision_trace.conflicts_detected:
            trace_lines.append(f"• Conflict Detected: {c}")
    for r in advisory.decision_trace.rules_applied:
        trace_lines.append(f"• Rule Applied: {r}")
    trace_lines.append(f"• Decision Latency: {advisory.decision_trace.execution_time_ms:.1f}ms (Tier 1 ReAct Core)")
    trace_block = "\n".join(trace_lines)

    result_parts = [
        header_text,
        f"**Directives:**\n{actions_block}",
    ]
    if w_details:
        result_parts.append(f"**Field Telemetry:**\n" + "\n".join(w_details))
    result_parts.append(f"**Agent Decision Trace:**\n{trace_block}")

    return "\n\n".join(result_parts)


async def _weather_intent_answer(plot: dict | None, last_class: str | None, lang: str) -> str | None:
    return await _weather_or_agent_intent_answer(plot, last_class, lang)


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


def _format_disease_card_aspect(
    question: str,
    picked: list[tuple[str, dict]],
    plot_ctx: str,
    lang: str = "en",
) -> str:
    key, c = picked[0]
    tmpl = _FALLBACK_TEMPLATES.get(lang, _FALLBACK_TEMPLATES["en"])
    q_low = question.lower()

    if lang != "en":
        crop_val = c.get(f"crop_{lang}") or c.get("crop", "")
        disease_val = c.get(f"disease_{lang}") or c.get("disease") or f"healthy {crop_val}"
    else:
        crop_val = c.get("crop", "")
        disease_val = c.get("disease") or f"healthy {crop_val}"

    precautions_list = c.get(f"precautions_{lang}")
    if precautions_list and isinstance(precautions_list, list):
        prevention_text = "\n".join(f"• {p}" for p in precautions_list)
    else:
        prevention_text = c.get("prevention", "Maintain field hygiene and crop rotation.")

    organic_text = c.get("organic", "Neem-based organic protectant or bio-fungicide.")
    chemical_text = c.get("chemical", "Standard protective fungicide.")
    symptoms_text = c.get("symptoms", "Inspect foliage and stems for lesions or spots.")

    # Detect specific query aspect
    is_waiting_period = any(w in q_low for w in [
        "waiting period", "safety waiting", "before harvest", "pre-harvest", "phi", "withdrawal",
        "तुड़ाई", "प्रतीक्षा अवधि", "કાપણી", "પ્રતીક્ષા", "काढणी", "அறுவடை", "కోత", "ਵਾਢੀ"
    ])

    is_pesticide_query = not is_waiting_period and any(w in q_low for w in [
        "what pesticide", "which pesticide", "what chemical", "which chemical",
        "pesticides should i use", "pesticide should i use", "chemical control",
        "what fungicide", "which fungicide", "what medicine", "which medicine",
        "dose", "कीटनाशक", "कौन सी दवा", "रासायनिक दवा", "જંતુનાશક", "કઈ દવા",
        "कीटकनाशक", "कोणते औषध", "பூச்சிக்கொல்லி", "என்ன மருந்து", "పురుగుమందు", "ఏ మందు", "ਕੀਟਨਾਸ਼ਕ"
    ])

    is_organic_query = not is_waiting_period and not is_pesticide_query and any(w in q_low for w in [
        "organic alternative", "organic control", "organic cure", "biological control",
        "natural alternative", "जैविक विकल्प", "जैविक उपाय", "જૈવિક વિકલ્પ", "सेंद्रિય पर्याय",
        "இயற்கை மாற்று", "సేంద్రీయ ప్రత్యామ్నాయం", "ਜੈਵਿਕ ਬਦਲ"
    ])

    is_symptom_query = not is_waiting_period and not is_pesticide_query and not is_organic_query and any(w in q_low for w in [
        "symptom", "symptoms", "signs", "identify", "look for", "look like",
        "लक्षण", "पहचान", "लक्षणे", "અறிகுறிகள்", "లక్షణాలు", "ਲੱਛਣ"
    ])

    is_prevention_query = not is_waiting_period and not is_pesticide_query and not is_organic_query and not is_symptom_query and any(w in q_low for w in [
        "how to prevent", "prevention", "preventive measure", "how to avoid",
        "रोकथाम", "बचाव", "અટકાવ", "નિવારણ", "प्रतिबंध", "தடுப்பு", "నివారణ", "ਰੋਕਥਾਮ"
    ])

    # 1. ASPECT: Safety Waiting Period before Harvest
    if is_waiting_period:
        titles = {
            "en": f"⏱️ Safety Waiting Period (Pre-Harvest Interval) for {crop_val} — {disease_val}:",
            "hi": f"⏱️ {crop_val} — {disease_val} के लिए तुड़ाई पूर्व प्रतीक्षा अवधि (Waiting Period):",
            "gu": f"⏱️ {crop_val} — {disease_val} માટે વીણણી પહેલાનો સુરક્ષા સમય (Waiting Period):",
            "mr": f"⏱️ {crop_val} — {disease_val} साठी काढणीपूर्वीचा सुरक्षा कालावधी (Waiting Period):",
            "ta": f"⏱️ {crop_val} — {disease_val} அறுவடைக்கு முந்தைய பாதுகாப்பு காத்திருப்பு காலம்:",
            "te": f"⏱️ {crop_val} — {disease_val} కోతకు ముందు వేచి ఉండాల్సిన సమయం (Waiting Period):",
            "pa": f"⏱️ {crop_val} — {disease_val} ਲਈ ਤੁੜਾਈ ਤੋਂ ਪਹਿਲਾਂ ਉਡੀਕ ਸਮਾਂ (Waiting Period):",
        }
        title = titles.get(lang, titles["en"])

        details = {
            "en": (
                f"• Chemical Treatments ({chemical_text}):\n"
                f"  Maintain a strict waiting period of 7–10 days after spraying before harvesting edible fruits or leaves to avoid chemical residues.\n"
                f"• Copper / Contact Protectants:\n"
                f"  Wait at least 3–5 days after application before picking produce.\n"
                f"• Organic / Bio-solutions ({organic_text}):\n"
                f"  Safe to harvest within 1–2 days after application as bio-protectants leave minimal residue.\n"
                f"• Harvesting Advice:\n"
                f"  Never spray immediately before harvest. Always wash all harvested produce thoroughly with clean running water before consumption or taking to market."
            ),
            "hi": (
                f"• रासायनिक कीटनाशक/फफूंदनाशक ({chemical_text}):\n"
                f"  दवा छिड़कने के बाद फल या पत्तियां तोडऩे से पहले कम से कम 7 से 10 दिन का अंतराल अवश्य रखें ताकि कीटनाशक अवशेष समाप्त हो सकें।\n"
                f"• कॉपर फफूंदनाशक:\n"
                f"  छिड़काव के कम से कम 3 से 5 दिन बाद ही तुड़ाई करें।\n"
                f"• जैविक उपचार ({organic_text}):\n"
                f"  जैविक या नीम आधारित स्प्रे के 1-2 दिन बाद तुड़ाई करना सुरक्षित है।\n"
                f"• सुरक्षा सलाह:\n"
                f"  तुड़ाई के 48 घंटे पहले कोई भी रासायनिक स्प्रे न करें। उपयोग या बिक्री से पहले फल-सब्जियों को साफ पानी से अच्छी तरह धोएं।"
            ),
            "gu": (
                f"• રાસાયણિક છંટકાવ ({chemical_text}):\n"
                f"  દવા છાંટ્યા પછી વીણણી કરતાં પહેલાં ઓછામાં ઓછા 7 થી 10 દિવસનો ગાળો રાખો જેથી રાસાયણિક અંશ દૂર થાય.\n"
                f"• કોપર દવાઓ:\n"
                f"  છંટકાવના 3 થી 5 દિવસ પછી વીણણી કરવી.\n"
                f"• જૈવિક ઉપાયો ({organic_text}):\n"
                f"  જૈવિક દવાઓ માટે 1 થી 2 દિવસનો સમય સલામત છે.\n"
                f"• સલાહ: હંમેશાં ઉપજને વાપરતાં પહેલાં ચોખ્ખા પાણીથી બરાબર ધોઈ લો."
            ),
            "mr": (
                f"• रासायनिक फवारणी ({chemical_text}):\n"
                f"  औषध फवारल्यानंतर काढणीपूर्वी किमान 7 ते 10 दिवसांचा सुरक्षा कालावधी ठेवावा.\n"
                f"• तांबे/कॉपर बुरशीनाशके:\n"
                f"  फवारणीनंतर किमान 3 ते 5 दिवसांनी काढणी करावी.\n"
                f"• सेंद्रिय उपचार ({organic_text}):\n"
                f"  सेंद्रिय फवारणीनंतर 1-2 दिवसांत काढणी करणे सुरक्षित असते.\n"
                f"• सल्ला: काढणीनंतर फळे/भाज्या स्वच्छ पाण्याने धुऊनच बाजारात न्याव्यात."
            ),
            "ta": (
                f"• வேதியியல் மருந்துகள் ({chemical_text}):\n"
                f"  மருந்து தெளித்த பிறகு அறுவடை செய்வதற்கு முன் 7 முதல் 10 நாட்கள் காத்திருக்க வேண்டும்.\n"
                f"• காப்பர் மருந்துகள்: தெளித்த 3-5 நாட்களுக்குப் பின் அறுவடை செய்யவும்.\n"
                f"• இயற்கை வழிகள் ({organic_text}): 1-2 நாட்களில் அறுவடை செய்யலாம்.\n"
                f"• ஆலோசனை: விளைபொருட்களைப் பயன்படுத்துவதற்கு முன் நல்ல தண்ணீரில் நன்கு கழுவவும்."
            ),
            "te": (
                f"• రసాయన మందులు ({chemical_text}):\n"
                f"  మందు పిచికారీ చేసిన తర్వాత పంట కోయడానికి కనీసం 7 నుండి 10 రోజుల విరామం పాటించాలి.\n"
                f"• కాపర్ మందులు: పిచికారీ చేసిన 3-5 రోజుల తర్వాత కోత కోయండి.\n"
                f"• సేంద్రీయ పద్ధతులు ({organic_text}): 1-2 రోజుల తర్వాత కోయడం సురక్షితం.\n"
                f"• సలహా: మార్కెట్‌కు తీసుకెళ్లే ముందు పంటను శుభ్రమైన నీటితో కడగాలి."
            ),
            "pa": (
                f"• ਰਸਾਇਣਕ ਦਵਾਈਆਂ ({chemical_text}):\n"
                f"  ਸਪਰੇਅ ਕਰਨ ਤੋਂ ਬਾਅਦ ਤੁੜਾਈ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ ਘੱਟੋ-ਘੱਟ 7 ਤੋਂ 10 ਦਿਨਾਂ ਦਾ ਸਮਾਂ ਰੱਖੋ।\n"
                f"• ਕਾਪਰ ਸਪਰੇਅ: ਸਪਰੇਅ ਦੇ 3-5 ਦਿਨਾਂ ਬਾਅਦ ਤੁੜਾਈ ਕਰੋ।\n"
                f"• ਜੈਵਿਕ ਇਲਾਜ ({organic_text}): 1-2 ਦਿਨਾਂ ਬਾਅਦ ਤੁੜਾਈ ਕਰਨਾ ਸੁਰੱਖਿਅਤ ਹੈ।\n"
                f"• ਸਲਾਹ: ਵਰਤੋਂ ਤੋਂ ਪਹਿਲਾਂ ਫਲਾਂ ਅਤੇ ਸਬਜ਼ੀਆਂ ਨੂੰ ਸਾਫ਼ ਪਾਣੀ ਨਾਲ ਧੋਵੋ।"
            ),
        }
        return f"{title}\n\n{details.get(lang, details['en'])}"

    # 2. ASPECT: Targeted Chemical / Pesticide Guidance
    if is_pesticide_query:
        titles = {
            "en": f"💊 Recommended Chemical & Pesticide Control for {crop_val} — {disease_val}:",
            "hi": f"💊 {crop_val} — {disease_val} के लिए अनुशंसित रासायनिक कीटनाशक/दवा नियंत्रण:",
            "gu": f"💊 {crop_val} — {disease_val} માટે ભલામણ કરેલ રાસાયણિક/કીટનાશક નિયંત્રણ:",
            "mr": f"💊 {crop_val} — {disease_val} साठी शिफारस केलेले रासायनिक/कीटकनाशक नियंत्रण:",
            "ta": f"💊 {crop_val} — {disease_val} க்கான பரிந்துரைக்கப்பட்ட வேதியியல்/பூச்சிக்கொல்லி கட்டுப்பாடு:",
            "te": f"💊 {crop_val} — {disease_val} కోసం సిఫార్సు చేయబడిన రసాయన/పురుగుమందు నియంత్రణ:",
            "pa": f"💊 {crop_val} — {disease_val} ਲਈ ਸਿਫ਼ਾਰਸ਼ ਕੀਤੀਆਂ ਰਸਾਇਣਕ/ਕੀਟਨਾਸ਼ਕ ਦਵਾਈਆਂ:",
        }
        title = titles.get(lang, titles["en"])

        spray_window = {
            "en": "Spray in early morning (6:00–9:00 AM) or late afternoon (4:00–6:00 PM) on calm, dry days (wind <15 km/h) with no rain expected within 4 hours.",
            "hi": "शांत मौसम में सुबह (6:00–9:00 बजे) या शाम (4:00–6:00 बजे) छिड़काव करें। यदि 4 घंटे में बारिश की संभावना हो तो छिड़काव टालें।",
            "gu": "શાંત અને સૂકા વાતાવરણમાં સવારે કે સાંજે છંટકાવ કરવો. આગામી 4 કલાકમાં વરસાદની શક્યતા હોય તો છંટકાવ મોકૂફ રાખવો.",
            "mr": "सकाळी किंवा संध्याकाळी कोरड्या हवामानात फवारणी करावी. पाऊस येणार असल्यास फवारणी करू नये.",
            "ta": "அமைதியான, வறண்ட வானிலையில் காலையில் அல்லது மாலையில் தெளிக்கவும். மழை வர வாய்ப்பிருந்தால் தெளிக்க வேண்டாம்.",
            "te": "ఉదయం లేదా సాయంత్రం వేళల్లో పిచికారీ చేయండి. వర్షం పడే అవకాశం ఉంటే పిచికారీ వాయిదా వేయండి.",
            "pa": "ਸਵੇਰੇ ਜਾਂ ਸ਼ਾਮ ਨੂੰ ਸ਼ਾਂਤ ਮੌਸਮ ਵਿੱਚ ਸਪਰੇਅ ਕਰੋ। ਜੇਕਰ ਮੀਂਹ ਪੈਣ ਦੀ ਸੰਭਾਵਨਾ ਹੋਵੇ ਤਾਂ ਸਪਰੇਅ ਨਾ ਕਰੋ।",
        }.get(lang, "Spray in early morning or late afternoon on calm days.")

        chem_line = f"• {tmpl['chemical']}: {chemical_text}"
        app_line = f"• Application Window: {spray_window}" if lang == "en" else f"• छिड़काव का समय: {spray_window}"
        org_line = f"• Organic Alternative: {organic_text}" if lang == "en" else f"• जैविक विकल्प: {organic_text}"
        return f"{title}\n\n{chem_line}\n\n{app_line}\n\n{org_line}"

    # 3. ASPECT: Targeted Organic Control
    if is_organic_query:
        titles = {
            "en": f"🌿 Organic & Biological Measures for {crop_val} — {disease_val}:",
            "hi": f"🌿 {crop_val} — {disease_val} के लिए जैविक व प्राकृतिक उपाय:",
            "gu": f"🌿 {crop_val} — {disease_val} માટે જૈવિક અને કુદરતી ઉપાયો:",
            "mr": f"🌿 {crop_val} — {disease_val} साठी सेंद्रिय व जैविक उपाय:",
            "ta": f"🌿 {crop_val} — {disease_val} க்கான இயற்கை மற்றும் உயிரியல் முறைகள்:",
            "te": f"🌿 {crop_val} — {disease_val} కోసం సేంద్రీయ నివారణ పద్ధతులు:",
            "pa": f"🌿 {crop_val} — {disease_val} ਲਈ ਜੈਵਿਕ ਅਤੇ ਕੁਦਰਤੀ ਉਪਾਅ:",
        }
        title = titles.get(lang, titles["en"])
        lines = [
            title,
            f"• {tmpl['organic']}: {organic_text}",
            f"• {tmpl['prevention']}:\n{prevention_text}",
        ]
        return "\n\n".join(lines)

    # 4. ASPECT: Targeted Symptoms & Field Signs
    if is_symptom_query:
        titles = {
            "en": f"🔍 Field Signs & Symptom Identification for {crop_val} — {disease_val}:",
            "hi": f"🔍 {crop_val} — {disease_val} के लक्षण व खेत में पहचान:",
            "gu": f"🔍 {crop_val} — {disease_val} ના લક્ષણો અને ખેતરમાં ઓળખ:",
            "mr": f"🔍 {crop_val} — {disease_val} ची लक्षणे व शेतातील ओळख:",
            "ta": f"🔍 {crop_val} — {disease_val} அறிகுறிகள் மற்றும் கள அடையாளம்:",
            "te": f"🔍 {crop_val} — {disease_val} లక్షణాలు మరియు గుర్తింపు:",
            "pa": f"🔍 {crop_val} — {disease_val} ਦੇ ਲੱਛਣ ਅਤੇ ਖੇਤ ਵਿੱਚ ਪਛਾਣ:",
        }
        title = titles.get(lang, titles["en"])
        lines = [
            title,
            f"• {tmpl['signs']}: {symptoms_text}",
            f"• Scouting Tip: Inspect leaf undersides and stems weekly. Take a photo in the 'Scan' tab for instant AI confirmation." if lang == "en" else f"• सलाह: पत्तियों के नीचे और तनों की जांच करें। रोग पुष्टि के लिए 'स्कैन' टैब में फोटो लें।",
        ]
        return "\n\n".join(lines)

    # 5. ASPECT: Targeted Prevention & Field Hygiene
    if is_prevention_query:
        titles = {
            "en": f"🛡️ Prevention & Field Sanitation for {crop_val} — {disease_val}:",
            "hi": f"🛡️ {crop_val} — {disease_val} से बचाव व खेत की स्वच्छता:",
            "gu": f"🛡️ {crop_val} — {disease_val} થી બચાવ અને ખેતરની સ્વચ્છતા:",
            "mr": f"🛡️ {crop_val} — {disease_val} पासून बचाव व शेताची स्वच्छता:",
            "ta": f"🛡️ {crop_val} — {disease_val} தடுப்பு முறைகள் மற்றும் பண்ணை தூய்மை:",
            "te": f"🛡️ {crop_val} — {disease_val} నివారణ చర్యలు మరియు పరిశుభ్రత:",
            "pa": f"🛡️ {crop_val} — {disease_val} ਤੋਂ ਬਚਾਅ ਅਤੇ ਖੇਤ ਦੀ ਸਫ਼ਾਈ:",
        }
        title = titles.get(lang, titles["en"])
        lines = [
            title,
            f"• {tmpl['prevention']}:\n{prevention_text}",
            f"• Cultural Hygiene: Avoid overhead watering; space plants to ensure good airflow; remove and safely destroy diseased leaves." if lang == "en" else f"• मुख्य नियम: पौधों में हवा के लिए उचित दूरी रखें, ऊपर से पानी न दें, और संक्रमित पत्तियों को नष्ट करें।",
        ]
        return "\n\n".join(lines)

    # 6. DEFAULT: Comprehensive Disease Card Overview (for general queries like 'Tell me about...')
    lines = [f"{crop_val} — {disease_val}".strip(" —")]
    if symptoms_text:
        lines.append(f"{tmpl['signs']}: {symptoms_text}")
    if organic_text:
        lines.append(f"{tmpl['organic']}: {organic_text}")
    if chemical_text and chemical_text.lower() not in ("none needed.", "none needed"):
        lines.append(f"{tmpl['chemical']}: {chemical_text}")
    if prevention_text:
        lines.append(f"{tmpl['prevention']}:\n{prevention_text}" if isinstance(precautions_list, list) else f"{tmpl['prevention']}: {prevention_text}")
    if plot_ctx:
        lines.append(tmpl["plot_advice"].format(ctx=plot_ctx))
    return "\n\n".join(lines)


async def _fallback_answer(
    question: str, picked: list[tuple[str, dict]], plot: dict | None, plot_ctx: str,
    last_class: str | None, lang: str = "en",
) -> str:
    tmpl = _FALLBACK_TEMPLATES.get(lang, _FALLBACK_TEMPLATES["en"])

    if not picked:
        intent = _detect_intent(question)

        # Heatwave & crop thermal stress protection
        if intent == "heat_stress":
            faq = _LOCAL_FAQ.get("heat_stress")
            if faq:
                return faq.get(lang, faq["en"])

        # Weather / irrigation-timing, spray weather & Autonomous Agent directives — grounded
        # in Module G ReAct loop + live forecast when a plot location is known.
        if intent in ("weather", "spray_weather", "agent"):
            weather_answer = await _weather_or_agent_intent_answer(plot, last_class, lang, question)
            if weather_answer:
                return weather_answer
            faq_key = "spray_weather" if intent == "spray_weather" else ("irrigation" if intent == "weather" else "agent")
            faq = _LOCAL_FAQ.get(faq_key, _LOCAL_FAQ["irrigation"])
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
                "te": f"ఈ పొలంలోని మీ {crop_name} పంట కోసం: నీరు నిలవకుండా చూడండి, ఆకుల కింద పురుగులు లేదా మచ్చల కోసం వారానికోసారి తనిఖీ చేయండి. 'స్కాన్' ట్యాబ్‌లో ఆకు ఫోటో తీసి పరీక్షించండి.",
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

    return _format_disease_card_aspect(question, picked, plot_ctx, lang)


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
    for c in cards_map.values():
        for lang_code in ["hi", "gu", "mr", "ta", "te", "pa"]:
            c_val = c.get(f"crop_{lang_code}")
            if c_val:
                crops_known.add(c_val.lower())

    diseases_known = {c.get("disease", "").lower() for c in cards_map.values() if c.get("disease")} | {
        "rust", "blight", "rot", "scab", "mildew", "spot", "mosaic", "curl", "smut", "wilt",
    }
    for c in cards_map.values():
        for lang_code in ["hi", "gu", "mr", "ta", "te", "pa"]:
            d_val = c.get(f"disease_{lang_code}")
            if d_val:
                diseases_known.add(d_val.lower())

    pronouns = {
        "it", "this", "that", "same", "also", "too", "these", "those",
        "इसका", "इसकी", "इसके", "यह", "ये", "वही", "उसी",
        "આનો", "આની", "આનું", "આ", "તે", "એનો", "એની",
        "याचा", "याची", "याचे", "हे", "ते", "त्याचा", "त्याची",
        "இதன்", "இதற்கு", "இந்த", "அதை",
        "దీని", "దీనికి", "ఈ", "దాన్ని",
        "ਇਸਦਾ", "ਇਸਦੀ", "ਇਸਦੇ", "ਇਹ", "ਉਸਦਾ",
    }

    # If user already asked about a specific crop or disease without pronouns, don't contaminate
    has_own_crop = any(crop in q_low for crop in crops_known if len(crop) >= 3)
    has_own_disease = any(dis in q_low for dis in diseases_known if len(dis) >= 3)
    has_pronoun = any(p in q_low.split() or p in q_low for p in pronouns)
    if (has_own_crop or has_own_disease) and not has_pronoun:
        return question

    intent = _detect_intent(question)
    is_operational = intent in (
        "weather", "irrigation", "soil", "sowing", "weeding", "schemes",
        "greeting", "spray_weather", "heat_stress", "agent",
    )
    if is_operational and not has_pronoun and not any(w in q_low for w in ["disease", "cure", "treat", "symptom"]):
        return question

    needs_context = (
        len(question.split()) <= 6
        or has_pronoun
        or any(w in q_low for w in [
            "the disease", "cure", "spray", "treat", "dose", "chemical", "waiting period", "pesticide", "pesticides",
            "दवा", "इलाज", "छिड़काव", "દવા", "સારવાર", "ઔષધ", "औषध", "फवारणी", "மருந்து", "மందు", "ਦਵਾਈ"
        ])
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
    question: str, intent: str | None, picked: list[tuple[str, dict]], plot: dict | None, lang: str = "en"
) -> list[ActionShortcut]:
    labels = {
        "scan": {
            "en": "Scan Leaf Diagnosis",
            "hi": "पत्ती रोग स्कैन",
            "gu": "પાંદડા રોગ સ્કેન",
            "mr": "पानांचे रोग स्कॅन",
            "ta": "இலை நோய் ஸ்கேன்",
            "te": "ఆకు వ్యాధి స్కాన్",
            "pa": "ਪੱਤਾ ਰੋਗ ਸਕੈਨ",
        },
        "weather": {
            "en": "3-Day Weather Advisory",
            "hi": "3-दिवसीय मौसम सलाह",
            "gu": "3-દિવસીય હવામાન સલાહ",
            "mr": "3-दिवसीय हवामान सल्ला",
            "ta": "3-நாள் வானிலை ஆலோசனை",
            "te": "3-రోజుల వాతావరణ సలహా",
            "pa": "3-ਦਿਨਾ ਮੌਸਮ ਸਲਾਹ",
        },
        "soil": {
            "en": "Soil Analysis & NPK",
            "hi": "मिट्टी परीक्षण व NPK",
            "gu": "જમીન ચકાસણી અને NPK",
            "mr": "माती परीक्षण आणि NPK",
            "ta": "மண் பரிசோதனை & NPK",
            "te": "నేల పరీక్ష & NPK",
            "pa": "ਮਿੱਟੀ ਪਰਖ ਅਤੇ NPK",
        },
        "plot_prefix": {
            "en": "Plot",
            "hi": "खेत",
            "gu": "પ્લોટ",
            "mr": "शेत",
            "ta": "வயல்",
            "te": "పొలం",
            "pa": "ਖੇਤ",
        },
    }

    shortcuts: list[ActionShortcut] = []
    q_low = question.lower()

    scan_lbl = labels["scan"].get(lang, labels["scan"]["en"])
    weather_lbl = labels["weather"].get(lang, labels["weather"]["en"])
    soil_lbl = labels["soil"].get(lang, labels["soil"]["en"])
    plot_prefix = labels["plot_prefix"].get(lang, labels["plot_prefix"]["en"])

    if picked or intent in ("pest", "yellow_leaves") or any(w in q_low for w in ["leaf", "spot", "disease", "rot", "blight", "rust", "scan", "photo", "रोग", "बीमारी", "રોગ", "कीड", "நோய்", "వ్యాధి", "ਬਿਮਾਰੀ"]):
        shortcuts.append(ActionShortcut(label=scan_lbl, icon="camera", route="/scan"))

    if intent in ("weather", "irrigation", "agent") or any(w in q_low for w in ["weather", "rain", "temperature", "wind", "spray", "water", "मौसम", "हवाમાન", "हवामान", "வானிலை", "వాతావరణం", "ਮੌਸਮ", "सिंचाई", "પાણી", "पाणी", "agent", "advisory"]):
        shortcuts.append(ActionShortcut(label=weather_lbl, icon="sun", route="/weather"))

    if intent in ("soil", "organic") or any(w in q_low for w in ["soil", "fertiliz", "npk", "ph", "compost", "manure", "मिट्टी", "माती", "જમીન", "மண்", "నేల", "ਮਿੱਟੀ", "खाद", "खत", "જીવામૃત", "జీవామృతం"]):
        shortcuts.append(ActionShortcut(label=soil_lbl, icon="flask", route="/soil"))

    if plot and plot.get("id"):
        plot_name = plot.get("name") or "Farm"
        shortcuts.append(ActionShortcut(label=f"{plot_prefix}: {plot_name}", icon="sprout", route=f"/plots/{plot['id']}"))

    if not shortcuts:
        shortcuts.append(ActionShortcut(label=scan_lbl, icon="camera", route="/scan"))
        shortcuts.append(ActionShortcut(label=weather_lbl, icon="sun", route="/weather"))

    return shortcuts[:3]


_TTS_CACHE: dict[tuple[str, str], bytes] = {}
_IN_FLIGHT_TTS: dict[tuple[str, str], asyncio.Future] = {}
_MAX_TTS_CACHE = 512


def _clean_text_for_speech(text: str, max_chars: int = 240) -> str:
    """Format agricultural answer into a natural, concise spoken message
    suitable for immediate single-request speech synthesis."""
    if not text:
        return "AgriSmart"
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    cleaned = re.sub(r"[*_`#•]+", " ", cleaned)
    # Strip list item prefixes e.g. "1. " or "2. " safely without touching decimals like "2.5 g/L"
    cleaned = re.sub(r"(?:(?<=\s)|^)\d+\.\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) <= max_chars:
        return cleaned

    # Split on sentence terminals: period, danda (Hindi/Indic), question mark, exclamation mark
    sentences = re.split(r"([.।?!]+(?:\s+|$))", cleaned)
    acc = ""
    i = 0
    while i < len(sentences):
        part = sentences[i]
        punct = sentences[i + 1] if i + 1 < len(sentences) else ""
        candidate = (acc + " " + part + punct).strip() if acc else (part + punct).strip()
        if len(candidate) <= max_chars:
            acc = candidate
            i += 2
        else:
            break

    if acc and len(acc) >= 30:
        return acc

    # Fallback to word boundary
    truncated = cleaned[:max_chars].rsplit(" ", 1)[0]
    return truncated.rstrip(".,:;।") + "."


def stream_tts_audio(text: str, lang: str = "en") -> Iterator[bytes]:
    """Stream audio chunks from gTTS with low first-chunk latency (~400ms)
    and cache the complete audio upon completion."""
    valid_langs = {"en", "hi", "gu", "mr", "ta", "te", "pa"}
    normalized = (lang or "en").lower().split("-")[0].split("_")[0].strip()
    tts_lang = normalized if normalized in valid_langs else "en"

    clean = _clean_text_for_speech(text)
    cache_key = (clean, tts_lang)
    if cache_key in _TTS_CACHE:
        yield _TTS_CACHE[cache_key]
        return

    from gtts import gTTS

    chunks: list[bytes] = []
    try:
        tts = gTTS(text=clean, lang=tts_lang, tld="co.in" if tts_lang == "en" else "com")
        for chunk in tts.stream():
            chunks.append(chunk)
            yield chunk
    except Exception:
        try:
            tts = gTTS(text=clean, lang=tts_lang)
            for chunk in tts.stream():
                chunks.append(chunk)
                yield chunk
        except Exception:
            return

    if chunks:
        full_audio = b"".join(chunks)
        if len(_TTS_CACHE) >= _MAX_TTS_CACHE:
            _TTS_CACHE.pop(next(iter(_TTS_CACHE)))
        _TTS_CACHE[cache_key] = full_audio


def generate_tts_audio(text: str, lang: str = "en") -> bytes:
    valid_langs = {"en", "hi", "gu", "mr", "ta", "te", "pa"}
    normalized = (lang or "en").lower().split("-")[0].split("_")[0].strip()
    tts_lang = normalized if normalized in valid_langs else "en"

    clean = _clean_text_for_speech(text)
    cache_key = (clean, tts_lang)
    if cache_key in _TTS_CACHE:
        return _TTS_CACHE[cache_key]

    fp = io.BytesIO()
    try:
        from gtts import gTTS
        tts = gTTS(text=clean, lang=tts_lang, tld="co.in" if tts_lang == "en" else "com")
        tts.write_to_fp(fp)
    except Exception:
        fp = io.BytesIO()
        from gtts import gTTS
        tts = gTTS(text=clean, lang=tts_lang)
        tts.write_to_fp(fp)

    audio_bytes = fp.getvalue()
    if len(_TTS_CACHE) >= _MAX_TTS_CACHE:
        _TTS_CACHE.pop(next(iter(_TTS_CACHE)))
    _TTS_CACHE[cache_key] = audio_bytes
    return audio_bytes


async def prewarm_tts(text: str, lang: str = "en") -> bytes:
    """Asynchronously pre-warm TTS cache so frontend audio request hits instantly."""
    valid_langs = {"en", "hi", "gu", "mr", "ta", "te", "pa"}
    normalized = (lang or "en").lower().split("-")[0].split("_")[0].strip()
    tts_lang = normalized if normalized in valid_langs else "en"

    clean = _clean_text_for_speech(text)
    cache_key = (clean, tts_lang)
    if cache_key in _TTS_CACHE:
        return _TTS_CACHE[cache_key]
    if cache_key in _IN_FLIGHT_TTS:
        return await _IN_FLIGHT_TTS[cache_key]

    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(None, generate_tts_audio, clean, tts_lang)
    _IN_FLIGHT_TTS[cache_key] = fut
    try:
        data = await fut
        return data
    except Exception as exc:
        log.warning("TTS prewarm background task failed: %s", exc)
        return b""
    finally:
        _IN_FLIGHT_TTS.pop(cache_key, None)


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
                action_shortcuts=_generate_shortcuts(question, intent, picked, plot, lang),
                speech_text=_clean_text_for_speech(llm_text),
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
                action_shortcuts=_generate_shortcuts(question, intent, picked, plot, lang),
                speech_text=_clean_text_for_speech(llm_text),
            )

    # Tier 3: Zero-Latency Circuit Breaker Fallback
    answer = await _fallback_answer(question, picked, plot, plot_ctx, last_class, lang)
    if not picked:
        if intent in ("weather", "spray_weather", "agent") and plot and plot.get("lat") is not None:
            grounded_on.append("weather")
            grounded_on.append("agent")
        elif intent == "soil" and plot and (plot.get("soil_snapshot") or {}).get("texture_class"):
            grounded_on.append("soil")
        elif intent in _LOCAL_FAQ or intent in ("weather", "spray_weather", "agent"):
            faq_key = "irrigation" if intent == "weather" else intent
            grounded_on.append(f"faq:{faq_key}")
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
        action_shortcuts=_generate_shortcuts(question, intent, picked, plot, lang),
        speech_text=_clean_text_for_speech(answer),
    )



async def warm_up() -> None:
    """Delegates to shared gemini service and pre-warms common starter prompt TTS."""
    await gemini_service.warm_up()
    try:
        starters = [
            ("Welcome to AgriSmart. Ask about crop diseases, weather alerts, and soil health.", "en"),
            ("एग्रीस्मार्ट में आपका स्वागत है। फसल रोग, मौसम और खाद की जानकारी के लिए पूछें।", "hi"),
        ]
        for s_text, s_lang in starters:
            asyncio.create_task(prewarm_tts(s_text, s_lang))
    except Exception:
        pass
