"""Module C — Weather Intelligence.

Pulls a 3‑day forecast from Open‑Meteo (free, no key) and runs a transparent
rule engine over it. Rules are documented in ``docs/weather_rules.md``.
"""

from __future__ import annotations

import logging
import time

import httpx

from ..config import get_settings
from ..models.modules import WeatherAction, WeatherAdvice
from .disease_cards import localized_label_for

log = logging.getLogger(__name__)

_FUNGAL = ("blight", "mould", "mold", "mildew", "rust", "scab", "rot", "spot", "leaf_spot")

# Rule messages, keyed the same as the `if` branches in build_advice() below.
# {placeholders} are filled with .format(**fields) — keep the field names in
# sync with the call sites.
_MESSAGES: dict[str, dict[str, tuple[str, str]]] = {
    "delay_irrigation": {
        "en": ("Delay irrigation",
               "Rain likely in the next 24 h ({rain_prob:.0f}% chance, ~{rain_24h:.0f} mm). "
               "Skip watering to save water and avoid waterlogging."),
        "hi": ("सिंचाई टालें",
               "अगले 24 घंटों में बारिश की संभावना है ({rain_prob:.0f}% संभावना, ~{rain_24h:.0f} मिमी)। "
               "पानी बचाने और जलभराव से बचने के लिए सिंचाई न करें।"),
        "gu": ("સિંચાઈ મુલતવી રાખો",
               "આગામી 24 કલાકમાં વરસાદની શક્યતા છે ({rain_prob:.0f}% શક્યતા, ~{rain_24h:.0f} મિમી). "
               "પાણી બચાવવા અને પાણી ભરાવાથી બચવા સિંચાઈ ટાળો."),
        "mr": ("सिंचन टाळा",
               "पुढील 24 तासांत पाऊस पडण्याची शक्यता आहे ({rain_prob:.0f}% शक्यता, ~{rain_24h:.0f} मिमी). "
               "पाणी वाचवण्यासाठी आणि पाणी साचणे टाळण्यासाठी सिंचन करू नका."),
        "ta": ("நீர்ப்பாசனத்தை தாமதப்படுத்துங்கள்",
               "அடுத்த 24 மணி நேரத்தில் மழை பெய்யும் வாய்ப்புள்ளது ({rain_prob:.0f}% வாய்ப்பு, ~{rain_24h:.0f} மிமீ). "
               "தண்ணீரை சேமிக்கவும், நீர் தேங்குவதைத் தவிர்க்கவும் நீர்ப்பாசனத்தைத் தவிர்க்கவும்."),
        "te": ("నీటిపారుదల వాయిదా వేయండి",
               "రాబోయే 24 గంటల్లో వర్షం పడే అవకాశం ఉంది ({rain_prob:.0f}% అవకాశం, ~{rain_24h:.0f} మిమీ). "
               "నీటిని ఆదా చేయడానికి మరియు నీరు నిలవకుండా ఉండటానికి నీరు పెట్టడం మానుకోండి."),
        "pa": ("ਸਿੰਚਾਈ ਟਾਲੋ",
               "ਅਗਲੇ 24 ਘੰਟਿਆਂ ਵਿੱਚ ਮੀਂਹ ਪੈਣ ਦੀ ਸੰਭਾਵਨਾ ਹੈ ({rain_prob:.0f}% ਸੰਭਾਵਨਾ, ~{rain_24h:.0f} ਮਿਮੀ)। "
               "ਪਾਣੀ ਬਚਾਉਣ ਅਤੇ ਪਾਣੀ ਖੜ੍ਹਾ ਹੋਣ ਤੋਂ ਬਚਣ ਲਈ ਸਿੰਚਾਈ ਨਾ ਕਰੋ।"),
    },
    "water_early_late": {
        "en": ("Water early or late",
               "Hot and dry (up to {tmax:.0f}°C, little rain). Irrigate at dawn or dusk to cut evaporation."),
        "hi": ("सुबह या शाम को सिंचाई करें",
               "गर्म और सूखा मौसम (अधिकतम {tmax:.0f}°C, कम बारिश)। वाष्पीकरण कम करने के लिए सुबह जल्दी या शाम को सिंचाई करें।"),
        "gu": ("વહેલી સવારે અથવા સાંજે પાણી આપો",
               "ગરમ અને સૂકું હવામાન (મહત્તમ {tmax:.0f}°C, ઓછો વરસાદ). બાષ્પીભવન ઘટાડવા વહેલી સવારે અથવા સાંજે સિંચાઈ કરો."),
        "mr": ("सकाळी लवकर किंवा संध्याकाळी पाणी द्या",
               "गरम आणि कोरडे हवामान (कमाल {tmax:.0f}°C, कमी पाऊस). बाष्पीभवन कमी करण्यासाठी पहाटे किंवा संध्याकाळी सिंचन करा."),
        "ta": ("அதிகாலையில் அல்லது மாலையில் நீர் பாய்ச்சுங்கள்",
               "வெப்பமான, வறண்ட வானிலை (அதிகபட்சம் {tmax:.0f}°C, குறைந்த மழை). ஆவியாதலைக் குறைக்க அதிகாலை அல்லது மாலை நேரத்தில் நீர்ப்பாசனம் செய்யுங்கள்."),
        "te": ("తెల్లవారుజామున లేదా సాయంత్రం నీరు పెట్టండి",
               "వేడి, పొడి వాతావరణం (గరిష్టంగా {tmax:.0f}°C, తక్కువ వర్షం). బాష్పీభవనాన్ని తగ్గించడానికి తెల్లవారుజామున లేదా సాయంత్రం నీటిపారుదల చేయండి."),
        "pa": ("ਸਵੇਰੇ ਜਾਂ ਸ਼ਾਮ ਨੂੰ ਪਾਣੀ ਦਿਓ",
               "ਗਰਮ ਅਤੇ ਖੁਸ਼ਕ ਮੌਸਮ (ਵੱਧ ਤੋਂ ਵੱਧ {tmax:.0f}°C, ਘੱਟ ਮੀਂਹ)। ਵਾਸ਼ਪੀਕਰਨ ਘਟਾਉਣ ਲਈ ਸਵੇਰੇ ਜਾਂ ਸ਼ਾਮ ਨੂੰ ਸਿੰਚਾਈ ਕਰੋ।"),
    },
    "spray_preventive": {
        "en": ("Spray preventively for fungal disease",
               "{disease} detected recently and humidity is high (~{humidity:.0f}%). "
               "Conditions favour rapid spread — apply a protective fungicide or bio-control."),
        "hi": ("फफूंद रोग के लिए बचाव छिड़काव करें",
               "हाल ही में {disease} पाया गया और नमी अधिक है (~{humidity:.0f}%)। "
               "ऐसी स्थिति में रोग तेज़ी से फैल सकता है — सुरक्षात्मक फफूंदनाशी या जैविक नियंत्रण का छिड़काव करें।"),
        "gu": ("ફૂગના રોગ માટે રક્ષણાત્મક છંટકાવ કરો",
               "તાજેતરમાં {disease} મળી આવ્યો અને ભેજ વધારે છે (~{humidity:.0f}%). "
               "આવી સ્થિતિમાં રોગ ઝડપથી ફેલાઈ શકે છે — રક્ષણાત્મક ફૂગનાશક અથવા જૈવિક નિયંત્રણનો છંટકાવ કરો."),
        "mr": ("बुरशीजन्य रोगासाठी प्रतिबंधात्मक फवारणी करा",
               "अलीकडेच {disease} आढळले आणि आर्द्रता जास्त आहे (~{humidity:.0f}%). "
               "अशा परिस्थितीत रोग वेगाने पसरू शकतो — संरक्षणात्मक बुरशीनाशक किंवा जैविक नियंत्रण फवारा."),
        "ta": ("பூஞ்சை நோய்க்கு தடுப்பு தெளிப்பு செய்யுங்கள்",
               "சமீபத்தில் {disease} கண்டறியப்பட்டது, ஈரப்பதமும் அதிகமாக உள்ளது (~{humidity:.0f}%). "
               "இந்த சூழல் வேகமான பரவலுக்கு உகந்தது — பாதுகாப்பு பூஞ்சைக்கொல்லி அல்லது உயிரியல் கட்டுப்பாட்டைப் பயன்படுத்துங்கள்."),
        "te": ("శిలీంధ్ర వ్యాధికి నివారణ స్ప్రే చేయండి",
               "ఇటీవల {disease} కనుగొనబడింది మరియు తేమ ఎక్కువగా ఉంది (~{humidity:.0f}%). "
               "ఈ పరిస్థితులు వేగంగా వ్యాప్తి చెందడానికి అనుకూలం — రక్షణ శిలీంధ్రనాశిని లేదా జీవ నియంత్రణను వాడండి."),
        "pa": ("ਉੱਲੀ ਰੋਗ ਲਈ ਰੋਕਥਾਮ ਵਾਲਾ ਛਿੜਕਾਅ ਕਰੋ",
               "ਹਾਲ ਹੀ ਵਿੱਚ {disease} ਮਿਲਿਆ ਹੈ ਅਤੇ ਨਮੀ ਜ਼ਿਆਦਾ ਹੈ (~{humidity:.0f}%)। "
               "ਅਜਿਹੇ ਹਾਲਾਤ ਵਿੱਚ ਰੋਗ ਤੇਜ਼ੀ ਨਾਲ ਫੈਲ ਸਕਦਾ ਹੈ — ਸੁਰੱਖਿਆਤਮਕ ਉੱਲੀਨਾਸ਼ਕ ਜਾਂ ਜੈਵਿਕ ਨਿਯੰਤਰਣ ਦਾ ਛਿੜਕਾਅ ਕਰੋ।"),
    },
    "watch_fungal": {
        "en": ("Watch for fungal disease",
               "Humidity is very high (~{humidity:.0f}%). Scout leaves for spots or mould and improve airflow."),
        "hi": ("फफूंद रोग पर नज़र रखें",
               "नमी बहुत अधिक है (~{humidity:.0f}%)। पत्तियों पर धब्बे या फफूंद के लिए जाँच करें और हवा का आवागमन बेहतर करें।"),
        "gu": ("ફૂગના રોગ પર નજર રાખો",
               "ભેજ ખૂબ વધારે છે (~{humidity:.0f}%). પાંદડાં પર ડાઘ કે ફૂગ માટે તપાસો અને હવાની અવરજવર સુધારો."),
        "mr": ("बुरशीजन्य रोगावर लक्ष ठेवा",
               "आर्द्रता खूप जास्त आहे (~{humidity:.0f}%). पानांवर डाग किंवा बुरशीसाठी तपासणी करा आणि हवा खेळती ठेवा."),
        "ta": ("பூஞ்சை நோயை கவனியுங்கள்",
               "ஈரப்பதம் மிக அதிகமாக உள்ளது (~{humidity:.0f}%). இலைகளில் புள்ளிகள் அல்லது பூஞ்சைக்காக பரிசோதித்து, காற்றோட்டத்தை மேம்படுத்துங்கள்."),
        "te": ("శిలీంధ్ర వ్యాధిని గమనించండి",
               "తేమ చాలా ఎక్కువగా ఉంది (~{humidity:.0f}%). ఆకులపై మచ్చలు లేదా బూజు కోసం పరిశీలించి గాలి ప్రసరణను మెరుగుపరచండి."),
        "pa": ("ਉੱਲੀ ਰੋਗ 'ਤੇ ਨਜ਼ਰ ਰੱਖੋ",
               "ਨਮੀ ਬਹੁਤ ਜ਼ਿਆਦਾ ਹੈ (~{humidity:.0f}%)। ਪੱਤਿਆਂ 'ਤੇ ਧੱਬਿਆਂ ਜਾਂ ਉੱਲੀ ਲਈ ਜਾਂਚ ਕਰੋ ਅਤੇ ਹਵਾ ਦਾ ਵਹਾਅ ਸੁਧਾਰੋ।"),
    },
    "heat_stress": {
        "en": ("Heat-stress risk",
               "Peak {tmax:.0f}°C expected. Mulch to keep roots cool and avoid spraying in the midday sun."),
        "hi": ("गर्मी के तनाव का खतरा",
               "अधिकतम {tmax:.0f}°C तापमान की उम्मीद है। जड़ों को ठंडा रखने के लिए मल्चिंग करें और दोपहर की धूप में छिड़काव न करें।"),
        "gu": ("ગરમીના તણાવનું જોખમ",
               "મહત્તમ {tmax:.0f}°C તાપમાનની શક્યતા છે. મૂળને ઠંડા રાખવા મલ્ચિંગ કરો અને બપોરના તડકામાં છંટકાવ ટાળો."),
        "mr": ("उष्णतेच्या ताणाचा धोका",
               "कमाल {tmax:.0f}°C तापमानाची शक्यता आहे. मुळे थंड ठेवण्यासाठी आच्छादन करा आणि दुपारच्या उन्हात फवारणी टाळा."),
        "ta": ("வெப்ப அழுத்த ஆபத்து",
               "அதிகபட்சம் {tmax:.0f}°C எதிர்பார்க்கப்படுகிறது. வேர்களை குளிர்ச்சியாக வைக்க மல்ச் செய்து, நண்பகல் வெயிலில் தெளிப்பதைத் தவிர்க்கவும்."),
        "te": ("వేడి ఒత్తిడి ప్రమాదం",
               "గరిష్టంగా {tmax:.0f}°C ఉండే అవకాశం ఉంది. వేర్లను చల్లగా ఉంచడానికి మల్చింగ్ చేయండి మరియు మధ్యాహ్నం ఎండలో స్ప్రే చేయవద్దు."),
        "pa": ("ਗਰਮੀ ਦੇ ਤਣਾਅ ਦਾ ਖ਼ਤਰਾ",
               "ਵੱਧ ਤੋਂ ਵੱਧ {tmax:.0f}°C ਹੋਣ ਦੀ ਉਮੀਦ ਹੈ। ਜੜ੍ਹਾਂ ਨੂੰ ਠੰਢਾ ਰੱਖਣ ਲਈ ਮਲਚਿੰਗ ਕਰੋ ਅਤੇ ਦੁਪਹਿਰ ਦੀ ਧੁੱਪ ਵਿੱਚ ਛਿੜਕਾਅ ਕਰਨ ਤੋਂ ਬਚੋ।"),
    },
    "cold_stress": {
        "en": ("Cold-stress risk",
               "Night lows near {tmin:.0f}°C. Protect seedlings and delay nitrogen top-dressing."),
        "hi": ("ठंड के तनाव का खतरा",
               "रात का तापमान लगभग {tmin:.0f}°C तक गिर सकता है। पौध को सुरक्षित रखें और नाइट्रोजन देना टालें।"),
        "gu": ("ઠંડીના તણાવનું જોખમ",
               "રાત્રિનું તાપમાન લગભગ {tmin:.0f}°C સુધી જઈ શકે છે. રોપાઓનું રક્ષણ કરો અને નાઇટ્રોજન આપવાનું ટાળો."),
        "mr": ("थंडीच्या ताणाचा धोका",
               "रात्रीचे किमान तापमान सुमारे {tmin:.0f}°C पर्यंत खाली जाऊ शकते. रोपांचे संरक्षण करा आणि नत्र खत देणे पुढे ढकला."),
        "ta": ("குளிர் அழுத்த ஆபத்து",
               "இரவு வெப்பநிலை {tmin:.0f}°C அளவிற்கு குறையக்கூடும். நாற்றுகளைப் பாதுகாத்து, நைட்ரஜன் உரமிடுவதை தாமதப்படுத்துங்கள்."),
        "te": ("చలి ఒత్తిడి ప్రమాదం",
               "రాత్రి ఉష్ణోగ్రత {tmin:.0f}°C వరకు పడిపోవచ్చు. మొలకలను రక్షించండి మరియు నత్రజని ఎరువు వేయడం వాయిదా వేయండి."),
        "pa": ("ਠੰਡ ਦੇ ਤਣਾਅ ਦਾ ਖ਼ਤਰਾ",
               "ਰਾਤ ਦਾ ਤਾਪਮਾਨ {tmin:.0f}°C ਤੱਕ ਡਿੱਗ ਸਕਦਾ ਹੈ। ਬੂਟਿਆਂ ਦੀ ਸੁਰੱਖਿਆ ਕਰੋ ਅਤੇ ਨਾਈਟ੍ਰੋਜਨ ਖਾਦ ਦੇਣਾ ਟਾਲੋ।"),
    },
    "delay_spray_wind": {
        "en": ("Delay spraying — wind",
               "Gusts up to {wind:.0f} km/h will cause spray drift. Spray on a calmer day."),
        "hi": ("छिड़काव टालें — तेज़ हवा",
               "{wind:.0f} किमी/घंटा तक की हवा के झोंकों से छिड़काव बिखर सकता है। शांत मौसम में छिड़काव करें।"),
        "gu": ("છંટકાવ મુલતવી રાખો — પવન",
               "{wind:.0f} કિમી/કલાક સુધીના પવનના ઝાપટાંથી છંટકાવ વિખેરાઈ શકે છે. શાંત વાતાવરણમાં છંટકાવ કરો."),
        "mr": ("फवारणी टाळा — वारा",
               "{wind:.0f} किमी/तास वेगाच्या वाऱ्यामुळे फवारणी विखुरली जाईल. शांत हवामान असताना फवारणी करा."),
        "ta": ("தெளிப்பதை தாமதப்படுத்துங்கள் — காற்று",
               "{wind:.0f} கிமீ/மணி வேகமுள்ள காற்று தெளிப்பை சிதறடிக்கும். அமைதியான நாளில் தெளிக்கவும்."),
        "te": ("స్ప్రే వాయిదా వేయండి — గాలి",
               "{wind:.0f} కిమీ/గంట వేగంతో వీచే గాలి స్ప్రేను చెదరగొడుతుంది. ప్రశాంతమైన రోజున స్ప్రే చేయండి."),
        "pa": ("ਛਿੜਕਾਅ ਟਾਲੋ — ਹਵਾ",
               "{wind:.0f} ਕਿਮੀ/ਘੰਟਾ ਤੱਕ ਦੀ ਤੇਜ਼ ਹਵਾ ਛਿੜਕਾਅ ਨੂੰ ਖਿੰਡਾ ਦੇਵੇਗੀ। ਸ਼ਾਂਤ ਮੌਸਮ ਵਿੱਚ ਛਿੜਕਾਅ ਕਰੋ।"),
    },
    "no_action": {
        "en": ("No weather action needed",
               "The next 3 days look steady for your farm. Carry on with your normal schedule."),
        "hi": ("मौसम संबंधी कोई कार्रवाई ज़रूरी नहीं",
               "अगले 3 दिन आपके खेत के लिए सामान्य रहेंगे। अपना सामान्य कार्यक्रम जारी रखें।"),
        "gu": ("હવામાન અંગે કોઈ પગલાંની જરૂર નથી",
               "આગામી 3 દિવસ તમારા ખેતર માટે સામાન્ય રહેશે. તમારું નિયમિત સમયપત્રક ચાલુ રાખો."),
        "mr": ("हवामानासंबंधी कोणतीही कारवाई आवश्यक नाही",
               "पुढील 3 दिवस तुमच्या शेतासाठी सामान्य राहतील. तुमचे नेहमीचे वेळापत्रक सुरू ठेवा."),
        "ta": ("வானிலை தொடர்பான நடவடிக்கை தேவையில்லை",
               "அடுத்த 3 நாட்கள் உங்கள் பண்ணைக்கு சீராக இருக்கும். உங்கள் வழக்கமான அட்டவணையைத் தொடருங்கள்."),
        "te": ("వాతావరణ చర్య అవసరం లేదు",
               "రాబోయే 3 రోజులు మీ పొలానికి సాధారణంగా ఉంటాయి. మీ మామూలు షెడ్యూల్ కొనసాగించండి."),
        "pa": ("ਮੌਸਮ ਸੰਬੰਧੀ ਕੋਈ ਕਾਰਵਾਈ ਜ਼ਰੂਰੀ ਨਹੀਂ",
               "ਅਗਲੇ 3 ਦਿਨ ਤੁਹਾਡੇ ਖੇਤ ਲਈ ਆਮ ਰਹਿਣਗੇ। ਆਪਣਾ ਆਮ ਸਮਾਂ-ਸਾਰਣੀ ਜਾਰੀ ਰੱਖੋ।"),
    },
    "secure_crops": {
        "en": ("Secure crops and structures",
               "Windy ({wind:.0f} km/h) with rain expected. Stake tall crops, "
               "secure poly tunnels, and ensure drains are clear."),
        "hi": ("फसलों व ढांचों को सुरक्षित करें",
               "हवा तेज़ है ({wind:.0f} किमी/घंटा) और बारिश की संभावना है। ऊँची फसलों को सहारा दें, "
               "पॉली टनल सुरक्षित करें, और नालियाँ साफ़ रखें।"),
        "gu": ("પાક અને માળખાંને સુરક્ષિત કરો",
               "પવન તેજ છે ({wind:.0f} કિમી/કલાક) અને વરસાદની શક્યતા છે. ઊંચા પાકને ટેકો આપો, "
               "પોલી ટનલ સુરક્ષિત કરો અને ગટરો સાફ રાખો."),
        "mr": ("पिके आणि संरचना सुरक्षित करा",
               "वारा वेगवान आहे ({wind:.0f} किमी/तास) आणि पावसाची शक्यता आहे. उंच पिकांना आधार द्या, "
               "पॉली टनेल सुरक्षित करा आणि नाले साफ ठेवा."),
        "ta": ("பயிர்கள் மற்றும் கட்டமைப்புகளை பாதுகாக்கவும்",
               "காற்று வேகமாக உள்ளது ({wind:.0f} கிமீ/மணி), மழையும் எதிர்பார்க்கப்படுகிறது. உயரமான பயிர்களுக்கு தூண் கொடுத்து, "
               "பாலிடன்னல்களை பாதுகாத்து, வடிகால்களை சுத்தமாக வைக்கவும்."),
        "te": ("పంటలు మరియు నిర్మాణాలను రక్షించండి",
               "గాలి వేగంగా ఉంది ({wind:.0f} కిమీ/గంట) మరియు వర్షం వచ్చే అవకాశం ఉంది. పొడవైన పంటలకు ఆధారం ఇవ్వండి, "
               "పాలీ టన్నెల్స్‌ను భద్రపరచండి మరియు కాలువలు క్లియర్‌గా ఉంచండి."),
        "pa": ("ਫ਼ਸਲਾਂ ਅਤੇ ਢਾਂਚਿਆਂ ਨੂੰ ਸੁਰੱਖਿਅਤ ਕਰੋ",
               "ਹਵਾ ਤੇਜ਼ ਹੈ ({wind:.0f} ਕਿਮੀ/ਘੰਟਾ) ਅਤੇ ਮੀਂਹ ਦੀ ਸੰਭਾਵਨਾ ਹੈ। ਉੱਚੀਆਂ ਫ਼ਸਲਾਂ ਨੂੰ ਸਹਾਰਾ ਦਿਓ, "
               "ਪੌਲੀ ਟਨਲ ਸੁਰੱਖਿਅਤ ਕਰੋ ਅਤੇ ਨਾਲੀਆਂ ਸਾਫ਼ ਰੱਖੋ।"),
    },
    "dry_spell": {
        "en": ("Dry spell ahead",
               "Less than 2 mm rain forecast over 3 days with highs of {tmax:.0f}°C. "
               "Consider deep watering and apply mulch to conserve soil moisture."),
        "hi": ("सूखे की स्थिति आगे",
               "अगले 3 दिनों में 2 मिमी से कम बारिश और अधिकतम {tmax:.0f}°C तापमान की संभावना है। "
               "गहरी सिंचाई करें और मिट्टी की नमी बनाए रखने के लिए मल्चिंग करें।"),
        "gu": ("આગળ સૂકો ગાળો",
               "આગામી 3 દિવસમાં 2 મિમીથી ઓછો વરસાદ અને મહત્તમ {tmax:.0f}°C તાપમાનની શક્યતા છે. "
               "ઊંડું પિયત આપો અને જમીનની ભેજ જાળવવા મલ્ચિંગ કરો."),
        "mr": ("पुढे कोरडा काळ",
               "पुढील 3 दिवसांत 2 मिमीपेक्षा कमी पाऊस आणि कमाल {tmax:.0f}°C तापमानाची शक्यता आहे. "
               "खोल सिंचन करा आणि मातीतील ओलावा टिकवण्यासाठी आच्छादन करा."),
        "ta": ("வறண்ட காலம் முன்னால்",
               "அடுத்த 3 நாட்களில் 2 மிமீக்கும் குறைவான மழை, அதிகபட்சம் {tmax:.0f}°C வெப்பநிலை எதிர்பார்க்கப்படுகிறது. "
               "ஆழமான நீர்ப்பாசனம் செய்து, மண் ஈரப்பதத்தை பாதுகாக்க மல்ச் செய்யுங்கள்."),
        "te": ("ముందు పొడి కాలం",
               "వచ్చే 3 రోజుల్లో 2 మిమీ కంటే తక్కువ వర్షం, గరిష్టంగా {tmax:.0f}°C ఉష్ణోగ్రత అంచనా. "
               "లోతైన నీటిపారుదల చేసి, నేల తేమను కాపాడటానికి మల్చింగ్ చేయండి."),
        "pa": ("ਅੱਗੇ ਖੁਸ਼ਕ ਦੌਰ",
               "ਅਗਲੇ 3 ਦਿਨਾਂ ਵਿੱਚ 2 ਮਿਮੀ ਤੋਂ ਘੱਟ ਮੀਂਹ ਅਤੇ ਵੱਧ ਤੋਂ ਵੱਧ {tmax:.0f}°C ਤਾਪਮਾਨ ਦੀ ਸੰਭਾਵਨਾ ਹੈ। "
               "ਡੂੰਘੀ ਸਿੰਚਾਈ ਕਰੋ ਅਤੇ ਮਿੱਟੀ ਦੀ ਨਮੀ ਬਚਾਉਣ ਲਈ ਮਲਚਿੰਗ ਕਰੋ।"),
    },
    "improve_ventilation": {
        "en": ("Improve crop ventilation",
               "Warm ({tmax:.0f}°C) with moderate-to-high humidity (~{humidity:.0f}%). "
               "Avoid overhead irrigation, prune dense canopy, and improve row spacing where possible."),
        "hi": ("फसल में हवा का आवागमन सुधारें",
               "गर्म मौसम ({tmax:.0f}°C) और मध्यम-से-उच्च नमी (~{humidity:.0f}%) है। "
               "ऊपर से सिंचाई से बचें, घनी पत्तियों की छंटाई करें, और जहाँ संभव हो पंक्तियों के बीच दूरी बढ़ाएँ।"),
        "gu": ("પાકમાં હવાની અવરજવર સુધારો",
               "ગરમ હવામાન ({tmax:.0f}°C) અને મધ્યમથી ઊંચો ભેજ (~{humidity:.0f}%) છે. "
               "ઉપરથી પિયત ટાળો, ગાઢ પર્ણસમૂહની કાપણી કરો અને શક્ય હોય ત્યાં હારો વચ્ચેનું અંતર સુધારો."),
        "mr": ("पिकातील हवा खेळती ठेवा",
               "उष्ण हवामान ({tmax:.0f}°C) आणि मध्यम-ते-उच्च आर्द्रता (~{humidity:.0f}%). "
               "वरून पाणी देणे टाळा, घनदाट पाने छाटा आणि शक्य असल्यास ओळींमधील अंतर वाढवा."),
        "ta": ("பயிரில் காற்றோட்டத்தை மேம்படுத்துங்கள்",
               "வெப்பமான வானிலை ({tmax:.0f}°C) நடுத்தர-முதல்-அதிக ஈரப்பதத்துடன் (~{humidity:.0f}%). "
               "மேலிருந்து நீர்ப்பாசனம் செய்வதைத் தவிர்த்து, அடர்ந்த இலைகளை கத்தரித்து, முடிந்தவரை வரிசை இடைவெளியை மேம்படுத்துங்கள்."),
        "te": ("పంటలో గాలి ప్రసరణను మెరుగుపరచండి",
               "వెచ్చని వాతావరణం ({tmax:.0f}°C) మధ్యస్థం నుండి అధిక తేమతో (~{humidity:.0f}%). "
               "పైనుండి నీరు పెట్టడం మానుకోండి, దట్టమైన ఆకులను కత్తిరించి, వీలైతే వరుసల మధ్య దూరం మెరుగుపరచండి."),
        "pa": ("ਫ਼ਸਲ ਵਿੱਚ ਹਵਾ ਦਾ ਵਹਾਅ ਸੁਧਾਰੋ",
               "ਗਰਮ ਮੌਸਮ ({tmax:.0f}°C) ਦਰਮਿਆਨੀ ਤੋਂ ਵੱਧ ਨਮੀ ਨਾਲ (~{humidity:.0f}%)। "
               "ਉੱਪਰੋਂ ਸਿੰਚਾਈ ਤੋਂ ਬਚੋ, ਸੰਘਣੇ ਪੱਤਿਆਂ ਦੀ ਛਾਂਟੀ ਕਰੋ ਅਤੇ ਜਿੱਥੇ ਸੰਭਵ ਹੋਵੇ ਕਤਾਰਾਂ ਵਿਚਕਾਰ ਦੂਰੀ ਸੁਧਾਰੋ।"),
    },
    "good_weather": {
        "en": ("Good weather — take action", "{recs}"),
        "hi": ("अच्छा मौसम — कार्रवाई करें", "{recs}"),
        "gu": ("સારું હવામાન — પગલાં લો", "{recs}"),
        "mr": ("चांगले हवामान — कारवाई करा", "{recs}"),
        "ta": ("நல்ல வானிலை — நடவடிக்கை எடுங்கள்", "{recs}"),
        "te": ("మంచి వాతావరణం — చర్య తీసుకోండి", "{recs}"),
        "pa": ("ਚੰਗਾ ਮੌਸਮ — ਕਾਰਵਾਈ ਕਰੋ", "{recs}"),
    },
    "plan_ahead": {
        "en": ("Plan ahead",
               "Between weather events, use calm windows for field maintenance, "
               "scouting for pests, and preparing inputs for the next application."),
        "hi": ("आगे की योजना बनाएं",
               "मौसम की घटनाओं के बीच, शांत समय का उपयोग खेत के रखरखाव, कीट निगरानी "
               "और अगले छिड़काव के लिए सामग्री तैयार करने में करें।"),
        "gu": ("આગળનું આયોજન કરો",
               "હવામાનની ઘટનાઓ વચ્ચે, શાંત સમયનો ઉપયોગ ખેતરની જાળવણી, જીવાત તપાસ "
               "અને આગામી છંટકાવ માટે સામગ્રી તૈયાર કરવામાં કરો."),
        "mr": ("पुढील नियोजन करा",
               "हवामानातील बदलांच्या दरम्यान, शांत वेळेचा वापर शेताची देखभाल, कीड तपासणी "
               "आणि पुढील फवारणीसाठी साहित्य तयार करण्यासाठी करा."),
        "ta": ("முன்கூட்டியே திட்டமிடுங்கள்",
               "வானிலை நிகழ்வுகளுக்கு இடையே, அமைதியான நேரத்தை வயல் பராமரிப்பு, பூச்சி கண்காணிப்பு "
               "மற்றும் அடுத்த தெளிப்புக்கான பொருட்களை தயார் செய்ய பயன்படுத்துங்கள்."),
        "te": ("ముందుగా ప్రణాళిక వేసుకోండి",
               "వాతావరణ మార్పుల మధ్య, పొలం నిర్వహణ, తెగుళ్ల పరిశీలన "
               "మరియు తదుపరి స్ప్రే కోసం సామాగ్రిని సిద్ధం చేయడానికి ప్రశాంతమైన సమయాన్ని వాడండి."),
        "pa": ("ਅੱਗੇ ਦੀ ਯੋਜਨਾ ਬਣਾਓ",
               "ਮੌਸਮ ਦੀਆਂ ਘਟਨਾਵਾਂ ਦੇ ਵਿਚਕਾਰ, ਸ਼ਾਂਤ ਸਮੇਂ ਦੀ ਵਰਤੋਂ ਖੇਤ ਦੀ ਸਾਂਭ-ਸੰਭਾਲ, ਕੀੜਿਆਂ ਦੀ ਜਾਂਚ "
               "ਅਤੇ ਅਗਲੇ ਛਿੜਕਾਅ ਲਈ ਸਮੱਗਰੀ ਤਿਆਰ ਕਰਨ ਵਿੱਚ ਕਰੋ।"),
    },
}

# Short recommendation phrases used inside the "good weather" detail text —
# joined together rather than shown as separate actions.
_PHRASES: dict[str, dict[str, str]] = {
    "spray_calm": {
        "en": "Conditions are ideal for spraying — calm and dry.",
        "hi": "छिड़काव के लिए स्थितियाँ आदर्श हैं — शांत और सूखा मौसम।",
        "gu": "છંટકાવ માટે સ્થિતિ આદર્શ છે — શાંત અને સૂકું હવામાન.",
        "mr": "फवारणीसाठी परिस्थिती आदर्श आहे — शांत आणि कोरडे हवामान.",
        "ta": "தெளிப்பதற்கு சூழ்நிலை சிறந்தது — அமைதியான, வறண்ட வானிலை.",
        "te": "స్ప్రే చేయడానికి పరిస్థితులు అనువుగా ఉన్నాయి — ప్రశాంతమైన, పొడి వాతావరణం.",
        "pa": "ਛਿੜਕਾਅ ਲਈ ਹਾਲਾਤ ਆਦਰਸ਼ ਹਨ — ਸ਼ਾਂਤ ਅਤੇ ਖੁਸ਼ਕ ਮੌਸਮ।",
    },
    "weed_sow": {
        "en": "Great weather for weeding, sowing, or transplanting.",
        "hi": "निराई, बुवाई या रोपाई के लिए बढ़िया मौसम है।",
        "gu": "નિંદામણ, વાવણી અથવા રોપણી માટે સરસ હવામાન છે.",
        "mr": "निंदणी, पेरणी किंवा पुनर्रोपणासाठी उत्तम हवामान आहे.",
        "ta": "களை எடுத்தல், விதைத்தல் அல்லது நடவு செய்வதற்கு சிறந்த வானிலை.",
        "te": "కలుపు తీయడానికి, విత్తడానికి లేదా నాటడానికి చక్కని వాతావరణం.",
        "pa": "ਗੋਡੀ, ਬਿਜਾਈ ਜਾਂ ਰੋਪਾਈ ਲਈ ਵਧੀਆ ਮੌਸਮ ਹੈ।",
    },
    "harvest_dry": {
        "en": "Good window for harvesting or drying produce in the sun.",
        "hi": "फसल कटाई या धूप में उपज सुखाने के लिए अच्छा समय है।",
        "gu": "લણણી અથવા તડકામાં ઉપજ સૂકવવા માટે સારો સમય છે.",
        "mr": "कापणी किंवा उन्हात उत्पादन वाळवण्यासाठी चांगली वेळ आहे.",
        "ta": "அறுவடை செய்யவோ அல்லது வெயிலில் விளைபொருட்களை உலர்த்தவோ சிறந்த நேரம்.",
        "te": "పంట కోతకు లేదా ఎండలో దిగుబడిని ఆరబెట్టడానికి మంచి సమయం.",
        "pa": "ਵਾਢੀ ਜਾਂ ਧੁੱਪ ਵਿੱਚ ਉਪਜ ਸੁਕਾਉਣ ਲਈ ਵਧੀਆ ਸਮਾਂ ਹੈ।",
    },
}


def _msg(key: str, lang: str, **fields) -> tuple[str, str]:
    headline, detail = _MESSAGES[key].get(lang) or _MESSAGES[key]["en"]
    return headline, detail.format(**fields)


def _phrase(key: str, lang: str) -> str:
    return _PHRASES[key].get(lang) or _PHRASES[key]["en"]


def _friendly_disease(raw: str, lang: str) -> str:
    """"Crop — Disease" in the requested language; falls back to a prettified
    raw model label when there's no card (e.g. an already-pretty name)."""
    label = localized_label_for(raw, lang)
    if label:
        return label
    if "___" in raw:
        crop, rest = raw.split("___", 1)
        return f"{crop.replace('_', ' ')} — {rest.replace('_', ' ').strip()}"
    return raw

_HOURLY = "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability"
_DAILY = (
    "temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "precipitation_probability_max,wind_speed_10m_max"
)


_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=settings.open_meteo_timeout_s,
            headers={"User-Agent": settings.http_user_agent},
        )
    return _client


# Raw forecast dicts, keyed by rounded lat/lon — every open of the Weather
# tab was re-doing a full TLS handshake + Open-Meteo round trip even for the
# same spot a minute apart. A short TTL keeps forecasts fresh (Open-Meteo's
# own data doesn't update much faster than this) while collapsing repeat
# lookups within a browsing session.
_forecast_cache: dict[str, tuple[float, dict]] = {}


def _forecast_cache_key(lat: float, lon: float) -> str:
    p = get_settings().weather_cache_precision
    return f"{round(lat, p)},{round(lon, p)}"


async def fetch_forecast(lat: float, lon: float) -> dict:
    s = get_settings()
    key = _forecast_cache_key(lat, lon)
    hit = _forecast_cache.get(key)
    if hit is not None:
        ts, forecast = hit
        if time.monotonic() - ts <= s.weather_cache_ttl_s:
            return forecast
        _forecast_cache.pop(key, None)

    params = {
        "latitude": lat, "longitude": lon, "hourly": _HOURLY, "daily": _DAILY,
        "forecast_days": 3, "timezone": "auto",
    }
    resp = await _get_client().get(s.open_meteo_base_url, params=params)
    resp.raise_for_status()
    forecast = resp.json()
    _forecast_cache[key] = (time.monotonic(), forecast)
    return forecast


def _summarise(fc: dict) -> dict:
    hourly = fc.get("hourly", {})
    daily = fc.get("daily", {})
    rh = [v for v in hourly.get("relative_humidity_2m", [])[:24] if v is not None]
    return {
        "rain_prob_24h_pct": _first(daily.get("precipitation_probability_max")),
        "rain_sum_24h_mm": round(sum(v or 0 for v in hourly.get("precipitation", [])[:24]), 1),
        "rain_sum_3d_mm": round(sum(v or 0 for v in daily.get("precipitation_sum", [])), 1),
        "humidity_mean_24h_pct": round(sum(rh) / len(rh), 0) if rh else None,
        "temp_max_c": _first(daily.get("temperature_2m_max")),
        "temp_min_c": _first(daily.get("temperature_2m_min")),
        "wind_max_kmh": _first(daily.get("wind_speed_10m_max")),
    }


def _first(seq: list | None):
    return seq[0] if seq else None


def build_advice(
    lat: float, lon: float, fc: dict, *, last_disease: str | None = None,
    crop: str | None = None, stage: str | None = None, lang: str = "en",
) -> WeatherAdvice:
    s = _summarise(fc)
    actions: list[WeatherAction] = []

    rain_prob = s["rain_prob_24h_pct"] or 0
    rain_24h = s["rain_sum_24h_mm"] or 0
    rain_3d = s["rain_sum_3d_mm"] or 0
    humidity = s["humidity_mean_24h_pct"] or 0
    tmax = s["temp_max_c"]
    tmin = s["temp_min_c"]
    wind = s["wind_max_kmh"] or 0
    fungal = bool(last_disease) and any(k in last_disease.lower() for k in _FUNGAL)
    disease_name = _friendly_disease(last_disease, lang) if last_disease else ""

    # --- Alert / Watch rules ---
    if rain_prob >= 60 or rain_24h >= 5:
        headline, detail = _msg("delay_irrigation", lang, rain_prob=rain_prob, rain_24h=rain_24h)
        actions.append(WeatherAction(severity="act", headline=headline, detail=detail))
    elif tmax is not None and tmax >= 34:
        headline, detail = _msg("water_early_late", lang, tmax=tmax)
        actions.append(WeatherAction(severity="watch", headline=headline, detail=detail))

    if fungal and humidity >= 80:
        headline, detail = _msg("spray_preventive", lang, disease=disease_name, humidity=humidity)
        actions.append(WeatherAction(severity="act", headline=headline, detail=detail))
    elif humidity >= 85:
        headline, detail = _msg("watch_fungal", lang, humidity=humidity)
        actions.append(WeatherAction(severity="watch", headline=headline, detail=detail))

    if tmax is not None and tmax >= 38:
        headline, detail = _msg("heat_stress", lang, tmax=tmax)
        actions.append(WeatherAction(severity="watch", headline=headline, detail=detail))
    if tmin is not None and tmin <= 5:
        headline, detail = _msg("cold_stress", lang, tmin=tmin)
        actions.append(WeatherAction(severity="watch", headline=headline, detail=detail))
    if wind >= 35:
        headline, detail = _msg("delay_spray_wind", lang, wind=wind)
        actions.append(WeatherAction(severity="watch", headline=headline, detail=detail))

    # --- Wind + rain combined ---
    if wind >= 25 and (rain_24h >= 5 or rain_prob >= 50):
        headline, detail = _msg("secure_crops", lang, wind=wind)
        actions.append(WeatherAction(severity="watch", headline=headline, detail=detail))

    # --- Dry spell advisory ---
    if rain_3d < 2 and tmax is not None and tmax > 30 and rain_prob < 20:
        headline, detail = _msg("dry_spell", lang, tmax=tmax)
        actions.append(WeatherAction(severity="watch", headline=headline, detail=detail))

    # --- High humidity + warm but not extreme ---
    if 75 <= humidity < 85 and tmax is not None and 25 <= tmax < 38:
        headline, detail = _msg("improve_ventilation", lang, tmax=tmax, humidity=humidity)
        actions.append(WeatherAction(severity="recommend", headline=headline, detail=detail))

    # --- Proactive positive recommendations ---
    if not actions:
        # Good weather window
        recs: list[str] = []
        if rain_prob < 30 and wind < 20:
            recs.append(_phrase("spray_calm", lang))
        if tmax is not None and 20 <= tmax <= 33 and humidity < 75:
            recs.append(_phrase("weed_sow", lang))
        if rain_3d < 3 and wind < 15:
            recs.append(_phrase("harvest_dry", lang))
        if recs:
            headline, detail = _msg("good_weather", lang, recs=" ".join(recs))
            actions.append(WeatherAction(severity="recommend", headline=headline, detail=detail))
        else:
            headline, detail = _msg("no_action", lang)
            actions.append(WeatherAction(severity="info", headline=headline, detail=detail))
    else:
        # Even when there are warnings, add one positive recommendation if weather has good windows
        if rain_prob < 40 and wind < 25 and tmax is not None and tmax < 38:
            headline, detail = _msg("plan_ahead", lang)
            actions.append(WeatherAction(severity="recommend", headline=headline, detail=detail))

    return WeatherAdvice(lat=lat, lon=lon, summary=s, actions=actions)
