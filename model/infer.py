"""Shared inference for the API: predict + Grad-CAM + farmer precautions.

Keeps ``predict.py`` a thin CLI; the FastAPI ``/predict`` route calls
:func:`run_inference` here.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

import torch
from PIL import Image, ImageOps

try:
    from .predict import ARTIFACTS_DIR, TAU, _model, predict_detailed
    from .labels import ABSTAIN_LABEL
    from .dataset import eval_transform
    from .gradcam import overlay
except ImportError:
    from predict import ARTIFACTS_DIR, TAU, _model, predict_detailed
    from labels import ABSTAIN_LABEL
    from dataset import eval_transform
    from gradcam import overlay

log = logging.getLogger(__name__)

_ABSTAIN_PRECAUTIONS = {
    "en": [
        "The photo was unclear — take another in good daylight",
        "Fill the frame with a single affected leaf on a plain background",
        "Hold the phone steady and tap to focus",
    ],
    "hi": [
        "फोटो साफ़ नहीं थी — अच्छी रोशनी में दोबारा फोटो लें",
        "सादे background पर एक प्रभावित पत्ती से पूरा फ्रेम भरें",
        "फोन को स्थिर रखें और फोकस के लिए टैप करें",
    ],
    "gu": [
        "ફોટો સ્પષ્ટ ન હતો — સારા દિવસના પ્રકાશમાં ફરી ફોટો લો",
        "સાદા બેકગ્રાઉન્ડ પર એક અસરગ્રસ્ત પાનથી આખી ફ્રેમ ભરો",
        "ફોનને સ્થિર રાખો અને ફોકસ માટે ટૅપ કરો",
    ],
    "mr": [
        "फोटो अस्पष्ट होता — चांगल्या दिवसाच्या प्रकाशात पुन्हा फोटो घ्या",
        "साध्या पार्श्वभूमीवर एका प्रभावित पानाने संपूर्ण फ्रेम भरा",
        "फोन स्थिर धरा आणि फोकससाठी टॅप करा",
    ],
    "ta": [
        "புகைப்படம் தெளிவாக இல்லை — நல்ல பகல் வெளிச்சத்தில் மீண்டும் எடுக்கவும்",
        "எளிய பின்னணியில் ஒரு பாதிக்கப்பட்ட இலையால் முழு சட்டகத்தையும் நிரப்பவும்",
        "மொபைலை நிலையாக பிடித்து, கவனம் செலுத்த தட்டவும்",
    ],
    "te": [
        "ఫోటో స్పష్టంగా లేదు — మంచి పగటి వెలుతురులో మళ్లీ తీయండి",
        "సాదా నేపథ్యంలో ఒక్క ప్రభావిత ఆకుతో ఫ్రేమ్‌ను నింపండి",
        "ఫోన్‌ను స్థిరంగా పట్టుకుని ఫోకస్ కోసం నొక్కండి",
    ],
    "pa": [
        "ਫੋਟੋ ਸਾਫ਼ ਨਹੀਂ ਸੀ — ਚੰਗੀ ਦਿਨ ਦੀ ਰੌਸ਼ਨੀ ਵਿੱਚ ਦੁਬਾਰਾ ਫੋਟੋ ਲਓ",
        "ਸਾਦੇ ਬੈਕਗ੍ਰਾਊਂਡ 'ਤੇ ਇੱਕ ਪ੍ਰਭਾਵਿਤ ਪੱਤੇ ਨਾਲ ਪੂਰਾ ਫਰੇਮ ਭਰੋ",
        "ਫੋਨ ਨੂੰ ਸਥਿਰ ਰੱਖੋ ਅਤੇ ਫੋਕਸ ਲਈ ਟੈਪ ਕਰੋ",
    ],
}
_NOT_A_LEAF_PRECAUTIONS = {
    "en": [
        "The uploaded photo does not appear to be a plant leaf — no disease detected",
        "No chemical or organic treatments should be applied to non-leaf objects",
        "To scan a crop, take a clear photo of an affected leaf on a plain background",
    ],
    "hi": [
        "अपलोड की गई फोटो किसी पौधे की पत्ती नहीं लग रही है — कोई बीमारी नहीं पाई गई",
        "गैर-पत्ती वस्तुओं पर कोई रासायनिक या जैविक उपचार लागू न करें",
        "फसल स्कैन करने के लिए, सादे background पर एक प्रभावित पत्ती की साफ़ फोटो लें",
    ],
    "gu": [
        "અપલોડ કરેલો ફોટો છોડના પાન જેવો લાગતો નથી — કોઈ રોગ જણાયો નથી",
        "બિન-પાન વસ્તુઓ પર કોઈ રાસાયણિક કે જૈવિક સારવાર લાગુ કરશો નહીં",
        "પાક સ્કેન કરવા માટે, સાદા બેકગ્રાઉન્ડ પર અસરગ્રસ્ત પાંદડાનો સ્પષ્ટ ફોટો લો",
    ],
    "mr": [
        "अपलोड केलेला फोटो वनस्पतीचे पान दिसत नाही — कोणताही रोग आढळला नाही",
        "गैर-पानांच्या वस्तूंवर कोणतेही रासायनिक किंवा सेंद्रिय उपचार करू नका",
        "पीक स्कॅन करण्यासाठी, साध्या पार्श्वभूमीवर एका प्रभावित पानाचा स्पष्ट फोटो घ्या",
    ],
    "ta": [
        "பதிவேற்றப்பட்ட புகைப்படம் தாவர இலையாகத் தெரியவில்லை — நோய் எதுவும் கண்டறியப்படவில்லை",
        "இலை அல்லாத பொருட்களுக்கு எந்த இரசாயன அல்லது கரிம சிகிச்சைகளையும் பயன்படுத்த வேண்டாம்",
        "பயிரை ஸ்கேன் செய்ய, எளிய பின்னணியில் பாதிக்கப்பட்ட இலையின் தெளிவான புகைப்படத்தை எடுக்கவும்",
    ],
    "te": [
        "అప్‌లోడ్ చేసిన ఫోటో మొక్క ఆకులా కనిపించడం లేదు — ఎటువంటి వ్యాధి కనుగొనబడలేదు",
        "ఆకులు కాని వస్తువులకు ఎటువంటి రసాయన లేదా సేంద్రీయ చికిత్సలను వర్తించవద్దు",
        "పంటను స్కాన్ చేయడానికి, సాదా నేపథ్యంలో ఒక ప్రభావిత ఆకు స్పష్టమైన ఫోటో తీయండి",
    ],
    "pa": [
        "ਅੱਪਲੋਡ ਕੀਤੀ ਫੋਟੋ ਕਿਸੇ ਪੌਦੇ ਦੇ ਪੱਤੇ ਵਰਗੀ ਨਹੀਂ ਲੱਗਦੀ — ਕੋਈ ਬਿਮਾਰੀ ਨਹੀਂ ਲੱਭੀ",
        "ਗੈਰ-ਪੱਤੇ ਵਾਲੀਆਂ ਵਸਤੂਆਂ 'ਤੇ ਕੋਈ ਰਸਾਇਣਕ ਜਾਂ ਜੈਵਿਕ ਇਲਾਜ ਲਾਗੂ ਨਾ ਕਰੋ",
        "ਫ਼ਸਲ ਸਕੈਨ ਕਰਨ ਲਈ, ਸਾਦੇ ਬੈਕਗ੍ਰਾਊਂਡ 'ਤੇ ਪ੍ਰਭਾਵਿਤ ਪੱਤੇ ਦੀ ਸਾਫ਼ ਫੋਟੋ ਲਓ",
    ],
}
_UNSUPPORTED_CROP_PRECAUTIONS = {
    "en": [
        "This leaf is not recognized as one of the 6 supported crops (Apple, Bell Pepper, Corn, Grape, Potato, Tomato)",
        "No treatments shown: Treatments are only displayed for verified diseases of supported crops to prevent harmful chemical misapplication",
        "Please scan a leaf from a supported crop, or consult your local agricultural extension service (KVK)",
    ],
    "hi": [
        "यह पत्ती 6 समर्थित फसलों (टमाटर, आलू, मक्का, सेब, अंगूर, शिमला मिर्च) में से किसी की नहीं पहचानी गई",
        "कोई उपचार नहीं दिखाया गया: रासायनिक गलत उपयोग रोकने के लिए केवल समर्थित फसलों के सत्यापित रोगों का उपचार दिया जाता है",
        "कृपया किसी समर्थित फसल की पत्ती स्कैन करें, या स्थानीय कृषि विज्ञान केंद्र (KVK) से परामर्श लें",
    ],
    "gu": [
        "આ પાંદડું 6 સમર્થિત પાકો (ટામેટાં, બટાકા, મકાઈ, સફરજન, દ્રાક્ષ, કેપ્સિકમ) માંથી ઓળખાતું નથી",
        "કોઈ સારવાર બતાવાઈ નથી: હાનિકારક રસાયણોના ખોટા ઉપયોગથી બચવા માટે માત્ર સમર્થિત પાકો માટે જ સારવાર આપવામાં આવે છે",
        "કૃપા કરીને સમર્થિત પાકનું પાંદડું સ્કેન કરો, અથવા સ્થાનિક કૃષિ વિજ્ઞાન કેન્દ્ર (KVK) નો સંપર્ક કરો",
    ],
    "mr": [
        "हे पान 6 समर्थित पिकांपैकी (टोमॅटो, बटाटा, मका, सफरचंद, द्राक्ष, शिमला मिरची) ओळखले गेले नाही",
        "उपचार दाखवले नाहीत: रासायनिक फवारणीचा गैरवापर टाळण्यासाठी केवळ समर्थित पिकांसाठीच उपचार दिले जातात",
        "कृपया समर्थित पिकाचे पान स्कॅन करा किंवा स्थानिक कृषी विज्ञान केंद्राचा (KVK) सल्ला घ्या",
    ],
    "ta": [
        "இந்த இலை 6 ஆதரிக்கப்படும் பயிர்களில் (தக்காளி, உருளைக்கிழங்கு, சோளம், ஆப்பிள், திராட்சை, குடைமிளகாய்) ஒன்றாக அடையாளம் காணப்படவில்லை",
        "சிகிச்சைகள் காட்டப்படவில்லை: தவறான இரசாயனப் பயன்பாட்டைத் தடுக்க, ஆதரிக்கப்படும் பயிர்களுக்கு மட்டுமே சிகிச்சைகள் வழங்கப்படுகின்றன",
        "தயவுசெய்து ஆதரிக்கப்படும் பயிரின் இலையை ஸ்கேன் செய்யவும் அல்லது உள்ளூர் வேளாண்மை அறிவியல் மையத்தை (KVK) அணுகவும்",
    ],
    "te": [
        "ఈ ఆకు 6 మద్దతు ఉన్న పంటలలో (టమోటా, బంగాళాదుంప, మొక్కజొన్న, యాపిల్, ద్రాక్ష, బెల్ పెప్పర్) ఒకటిగా గుర్తించబడలేదు",
        "చికిత్సలు చూపబడలేదు: రసాయన దుర్వినియోగాన్ని నివారించడానికి, కేవలం మద్దతు ఉన్న పంటలకు మాత్రమే చికిత్సలు అందించబడతాయి",
        "దయచేసి మద్దతు ఉన్న పంట ఆకును స్కాన్ చేయండి లేదా స్థానిక కృషి విజ్ఞాన కేంద్రాన్ని (KVK) సంప్రదించండి",
    ],
    "pa": [
        "ਇਹ ਪੱਤਾ 6 ਸਮਰਥਿਤ ਫ਼ਸਲਾਂ (ਟਮਾਟਰ, ਆਲੂ, ਮੱਕੀ, ਸੇਬ, ਅੰਗੂਰ, ਸ਼ਿਮਲਾ ਮਿਰਚ) ਵਿੱਚੋਂ ਨਹੀਂ ਪਛਾਣਿਆ ਗਿਆ",
        "ਕੋਈ ਇਲਾਜ ਨਹੀਂ ਦਿਖਾਇਆ ਗਿਆ: ਨੁਕਸਾਨਦੇਹ ਰਸਾਇਣਕ ਵਰਤੋਂ ਤੋਂ ਬਚਣ ਲਈ ਸਿਰਫ਼ ਸਮਰਥਿਤ ਫ਼ਸਲਾਂ ਲਈ ਹੀ ਇਲਾਜ ਦਿੱਤੇ ਜਾਂਦੇ ਹਨ",
        "ਕਿਰਪਾ ਕਰਕੇ ਸਮਰਥਿਤ ਫ਼ਸਲ ਦੇ ਪੱਤੇ ਨੂੰ ਸਕੈਨ ਕਰੋ, ਜਾਂ ਸਥਾਨਕ ਕ੍ਰਿਸ਼ੀ ਵਿਗਿਆਨ ਕੇਂਦਰ (KVK) ਨਾਲ ਸੰਪਰਕ ਕਰੋ",
    ],
}
_GENERIC_PRECAUTIONS = {
    "en": [
        "Scout the crop again in 2-3 days",
        "Remove and destroy badly affected leaves",
        "Keep foliage dry — water at the base, early in the day",
    ],
    "hi": [
        "2-3 दिन बाद फिर से फसल की जाँच करें",
        "बुरी तरह प्रभावित पत्तियों को हटाकर नष्ट करें",
        "पत्तियों को सूखा रखें — सुबह जड़ में पानी दें",
    ],
    "gu": [
        "2-3 દિવસ પછી ફરી પાકનું નિરીક્ષણ કરો",
        "ખરાબ રીતે અસરગ્રસ્ત પાંદડાં દૂર કરી નષ્ટ કરો",
        "પાંદડાં સૂકાં રાખો — સવારે મૂળમાં પાણી આપો",
    ],
    "mr": [
        "2-3 दिवसांनी पुन्हा पिकाची तपासणी करा",
        "गंभीरपणे प्रभावित पाने काढून नष्ट करा",
        "पाने कोरडी ठेवा — सकाळी मुळाशी पाणी द्या",
    ],
    "ta": [
        "2-3 நாட்களில் மீண்டும் பயிரை பரிசோதிக்கவும்",
        "கடுமையாக பாதிக்கப்பட்ட இலைகளை அகற்றி அழிக்கவும்",
        "இலைகளை உலர்ந்து வைக்கவும் — காலையில் வேரடியில் நீர் ஊற்றவும்",
    ],
    "te": [
        "2-3 రోజుల్లో పంటను మళ్లీ పరిశీలించండి",
        "తీవ్రంగా ప్రభావితమైన ఆకులను తీసివేసి నాశనం చేయండి",
        "ఆకులను పొడిగా ఉంచండి — ఉదయం వేరు వద్ద నీరు పెట్టండి",
    ],
    "pa": [
        "2-3 ਦਿਨਾਂ ਬਾਅਦ ਫ਼ਸਲ ਦੀ ਦੁਬਾਰਾ ਜਾਂਚ ਕਰੋ",
        "ਬੁਰੀ ਤਰ੍ਹਾਂ ਪ੍ਰਭਾਵਿਤ ਪੱਤਿਆਂ ਨੂੰ ਹਟਾ ਕੇ ਨਸ਼ਟ ਕਰੋ",
        "ਪੱਤਿਆਂ ਨੂੰ ਸੁੱਕਾ ਰੱਖੋ — ਸਵੇਰੇ ਜੜ੍ਹ ਵਿੱਚ ਪਾਣੀ ਦਿਓ",
    ],
}


@lru_cache
def _cards() -> dict:
    root = Path(__file__).resolve().parents[1]
    try:
        return json.loads((root / "data" / "disease_cards.json").read_text(encoding="utf-8"))["cards"]
    except Exception:
        return {}


@lru_cache
def _meta() -> dict:
    try:
        return json.loads((ARTIFACTS_DIR / "class_map.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def model_version() -> str:
    m = _meta()
    return f"{m.get('backbone', 'efficientnet_b0')}-{len(m.get('classes', []))}c"


# --- Crop-aware guard rail --------------------------------------------------
# The trained model only covers the crops in data/disease_cards.json (6 in
# this build: Apple, Bell pepper, Grape, Maize, Potato, Tomato) — softmax
# still forces a confident-looking prediction from that list for any other
# crop (e.g. Cotton, Wheat), since there's no reject/background class. True
# feature-space OOD detection (Mahalanobis distance on embeddings, or a
# calibrated/temperature-scaled rejection threshold) needs statistics
# computed at training time that this build doesn't have — that's real
# future work, not something to fake here. What's implemented instead is the
# practical mitigation the app already has the data for: compare the
# prediction's crop against the farmer's own declared crop (Plot.main_crop
# or their profile's primary_crop) and, on a mismatch, warn instead of
# staying silent, and hide the specific chemical/organic dosing (which may
# not even apply to the actual plant) in favour of generic precautions.
_CROP_ALIASES = {
    "corn": "maize", "sweet corn": "maize",
    "pepper": "bell pepper", "capsicum": "bell pepper", "bell peppers": "bell pepper",
}


def _normalize_crop(name: str) -> str:
    n = name.strip().lower()
    return _CROP_ALIASES.get(n, n)


def _crop_for_label(label: str) -> str | None:
    return (_cards().get(label) or {}).get("crop")


def known_crops(lang: str = "en") -> list[str]:
    """Distinct crop names the trained model actually covers, in the
    requested language — derived from the same card corpus used for labels/
    precautions, so this list can never drift from what the model really
    supports."""
    seen: dict[str, str] = {}
    for card in _cards().values():
        en = card.get("crop")
        if not en or en in seen:
            continue
        seen[en] = (card.get(f"crop_{lang}") if lang != "en" else en) or en
    return [seen[k] for k in sorted(seen)]


_CROP_MISMATCH_WARNING = {
    "en": "This scanner currently supports {supported}. Your recorded crop is '{expected}', which doesn't match this photo's prediction — the result may be unreliable, so specific treatment steps are hidden below.",
    "hi": "यह स्कैनर फ़िलहाल {supported} को सपोर्ट करता है। आपकी दर्ज फसल '{expected}' है, जो इस फोटो के अनुमान से मेल नहीं खाती — परिणाम अविश्वसनीय हो सकता है, इसलिए नीचे विशिष्ट उपचार के चरण छुपा दिए गए हैं।",
    "gu": "આ સ્કેનર હાલમાં {supported} ને સપોર્ટ કરે છે. તમારો નોંધાયેલ પાક '{expected}' છે, જે આ ફોટોની આગાહી સાથે મેળ ખાતો નથી — પરિણામ અવિશ્વસનીય હોઈ શકે છે, તેથી નીચે ચોક્કસ સારવારના પગલાં છુપાવાયા છે.",
    "mr": "हे स्कॅनर सध्या {supported} ला सपोर्ट करते. तुमचे नोंदवलेले पीक '{expected}' आहे, जे या फोटोच्या अंदाजाशी जुळत नाही — निकाल अविश्वसनीय असू शकतो, त्यामुळे खाली विशिष्ट उपचार पायऱ्या लपवल्या आहेत.",
    "ta": "இந்த ஸ்கேனர் தற்போது {supported} ஆகியவற்றை ஆதரிக்கிறது. உங்கள் பதிவுசெய்யப்பட்ட பயிர் '{expected}', இது இந்த புகைப்படத்தின் கணிப்புடன் பொருந்தவில்லை — முடிவு நம்பகமாக இல்லாமல் இருக்கலாம், எனவே கீழே உள்ள குறிப்பிட்ட சிகிச்சை படிகள் மறைக்கப்பட்டுள்ளன.",
    "te": "ఈ స్కానర్ ప్రస్తుతం {supported} మద్దతు ఇస్తుంది. మీ నమోదైన పంట '{expected}', ఇది ఈ ఫోటో అంచనాతో సరిపోలడం లేదు — ఫలితం నమ్మదగనిది కావచ్చు, కాబట్టి క్రింద నిర్దిష్ట చికిత్స దశలు దాచబడ్డాయి.",
    "pa": "ਇਹ ਸਕੈਨਰ ਇਸ ਸਮੇਂ {supported} ਦਾ ਸਮਰਥਨ ਕਰਦਾ ਹੈ। ਤੁਹਾਡੀ ਦਰਜ ਫ਼ਸਲ '{expected}' ਹੈ, ਜੋ ਇਸ ਫੋਟੋ ਦੀ ਭਵਿੱਖਬਾਣੀ ਨਾਲ ਮੇਲ ਨਹੀਂ ਖਾਂਦੀ — ਨਤੀਜਾ ਭਰੋਸੇਯੋਗ ਨਹੀਂ ਹੋ ਸਕਦਾ, ਇਸ ਲਈ ਹੇਠਾਂ ਖਾਸ ਇਲਾਜ ਦੇ ਕਦਮ ਲੁਕਾਏ ਗਏ ਹਨ।",
}


def crop_warning_for(predicted_label: str, expected_crop: str | None, lang: str = "en") -> str | None:
    """None if there's nothing to warn about (no declared crop, or it
    matches the prediction); otherwise a localized warning naming the
    supported crops, for the caller to also use as a signal to suppress
    crop-specific treatment steps."""
    if not expected_crop:
        return None
    predicted_crop = _crop_for_label(predicted_label)
    if not predicted_crop or _normalize_crop(predicted_crop) == _normalize_crop(expected_crop):
        return None
    supported = ", ".join(known_crops(lang))
    tmpl = _CROP_MISMATCH_WARNING.get(lang, _CROP_MISMATCH_WARNING["en"])
    return tmpl.format(supported=supported, expected=expected_crop)


def precautions_for(
    label: str, abstained: bool, lang: str = "en", rejection_reason: str | None = None
) -> list[str]:
    if rejection_reason == "not_a_leaf":
        return _NOT_A_LEAF_PRECAUTIONS.get(lang, _NOT_A_LEAF_PRECAUTIONS["en"])
    if rejection_reason == "unsupported_crop":
        return _UNSUPPORTED_CROP_PRECAUTIONS.get(lang, _UNSUPPORTED_CROP_PRECAUTIONS["en"])
    if abstained:
        return _ABSTAIN_PRECAUTIONS.get(lang, _ABSTAIN_PRECAUTIONS["en"])
    card = _cards().get(label) or {}
    localized = card.get(f"precautions_{lang}") if lang != "en" else None
    return localized or card.get("precautions") or _GENERIC_PRECAUTIONS.get(lang, _GENERIC_PRECAUTIONS["en"])


def localized_label_for(label: str, lang: str) -> str | None:
    """"Crop — Disease" in the requested language, or None for healthy/unknown
    classes (the frontend already renders those via its own i18n strings)."""
    card = _cards().get(label) or {}
    disease = card.get(f"disease_{lang}") if lang != "en" else card.get("disease")
    if not disease:
        return None
    crop = card.get(f"crop_{lang}") if lang != "en" else card.get("crop")
    crop = crop or card.get("crop") or ""
    return f"{crop} — {disease}".strip(" —")


def run_inference(
    image_path: str, gradcam_out: Path | None = None, lang: str = "en",
    expected_crop: str | None = None,
) -> dict:
    result = predict_detailed(image_path)  # {predicted_class, raw_class, confidence, abstained, top3, rejection_reason, is_leaf}
    result["model_version"] = model_version()
    rejection = result.get("rejection_reason")
    result["precautions"] = precautions_for(
        result["raw_class"], result["abstained"], lang, rejection_reason=rejection
    )
    result["predicted_label"] = (
        None if result["abstained"] else localized_label_for(result["raw_class"], lang)
    )
    result["crop_warning"] = None
    if not result["abstained"]:
        warning = crop_warning_for(result["raw_class"], expected_crop, lang)
        if warning:
            result["crop_warning"] = warning
            result["precautions"] = _GENERIC_PRECAUTIONS.get(lang, _GENERIC_PRECAUTIONS["en"])
    result["gradcam_path"] = None
    result["pretty_top3"] = result["top3"]

    if gradcam_out is not None and not result["abstained"]:
        try:
            tm = _model()  # reuse predict.py's cached singleton, not a fresh disk load
            img_size = _meta().get("img_size", 192)
            img = Image.open(image_path).convert("RGB")
            tf = eval_transform(img_size)
            batch = torch.stack([tf(img), tf(ImageOps.mirror(img))])
            cls_idx = tm.classes.index(result["raw_class"])
            vis = overlay(tm.model, batch, img, cls_idx, img_size)
            if vis is not None:
                gradcam_out.parent.mkdir(parents=True, exist_ok=True)
                vis.save(gradcam_out)
                result["gradcam_path"] = str(gradcam_out)
        except Exception as exc:
            log.warning("Grad-CAM generation skipped: %s", exc)

    return result
