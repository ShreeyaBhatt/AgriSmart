"""Module C — Weather Intelligence.

Pulls a 3‑day forecast from Open‑Meteo (free, no key) and runs a transparent
rule engine over it. Rules are documented in ``docs/weather_rules.md``.
"""

from __future__ import annotations

import logging

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
    },
    "water_early_late": {
        "en": ("Water early or late",
               "Hot and dry (up to {tmax:.0f}°C, little rain). Irrigate at dawn or dusk to cut evaporation."),
        "hi": ("सुबह या शाम को सिंचाई करें",
               "गर्म और सूखा मौसम (अधिकतम {tmax:.0f}°C, कम बारिश)। वाष्पीकरण कम करने के लिए सुबह जल्दी या शाम को सिंचाई करें।"),
        "gu": ("વહેલી સવારે અથવા સાંજે પાણી આપો",
               "ગરમ અને સૂકું હવામાન (મહત્તમ {tmax:.0f}°C, ઓછો વરસાદ). બાષ્પીભવન ઘટાડવા વહેલી સવારે અથવા સાંજે સિંચાઈ કરો."),
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
    },
    "watch_fungal": {
        "en": ("Watch for fungal disease",
               "Humidity is very high (~{humidity:.0f}%). Scout leaves for spots or mould and improve airflow."),
        "hi": ("फफूंद रोग पर नज़र रखें",
               "नमी बहुत अधिक है (~{humidity:.0f}%)। पत्तियों पर धब्बे या फफूंद के लिए जाँच करें और हवा का आवागमन बेहतर करें।"),
        "gu": ("ફૂગના રોગ પર નજર રાખો",
               "ભેજ ખૂબ વધારે છે (~{humidity:.0f}%). પાંદડાં પર ડાઘ કે ફૂગ માટે તપાસો અને હવાની અવરજવર સુધારો."),
    },
    "heat_stress": {
        "en": ("Heat-stress risk",
               "Peak {tmax:.0f}°C expected. Mulch to keep roots cool and avoid spraying in the midday sun."),
        "hi": ("गर्मी के तनाव का खतरा",
               "अधिकतम {tmax:.0f}°C तापमान की उम्मीद है। जड़ों को ठंडा रखने के लिए मल्चिंग करें और दोपहर की धूप में छिड़काव न करें।"),
        "gu": ("ગરમીના તણાવનું જોખમ",
               "મહત્તમ {tmax:.0f}°C તાપમાનની શક્યતા છે. મૂળને ઠંડા રાખવા મલ્ચિંગ કરો અને બપોરના તડકામાં છંટકાવ ટાળો."),
    },
    "cold_stress": {
        "en": ("Cold-stress risk",
               "Night lows near {tmin:.0f}°C. Protect seedlings and delay nitrogen top-dressing."),
        "hi": ("ठंड के तनाव का खतरा",
               "रात का तापमान लगभग {tmin:.0f}°C तक गिर सकता है। पौध को सुरक्षित रखें और नाइट्रोजन देना टालें।"),
        "gu": ("ઠંડીના તણાવનું જોખમ",
               "રાત્રિનું તાપમાન લગભગ {tmin:.0f}°C સુધી જઈ શકે છે. રોપાઓનું રક્ષણ કરો અને નાઇટ્રોજન આપવાનું ટાળો."),
    },
    "delay_spray_wind": {
        "en": ("Delay spraying — wind",
               "Gusts up to {wind:.0f} km/h will cause spray drift. Spray on a calmer day."),
        "hi": ("छिड़काव टालें — तेज़ हवा",
               "{wind:.0f} किमी/घंटा तक की हवा के झोंकों से छिड़काव बिखर सकता है। शांत मौसम में छिड़काव करें।"),
        "gu": ("છંટકાવ મુલતવી રાખો — પવન",
               "{wind:.0f} કિમી/કલાક સુધીના પવનના ઝાપટાંથી છંટકાવ વિખેરાઈ શકે છે. શાંત વાતાવરણમાં છંટકાવ કરો."),
    },
    "no_action": {
        "en": ("No weather action needed",
               "The next 3 days look steady for your farm. Carry on with your normal schedule."),
        "hi": ("मौसम संबंधी कोई कार्रवाई ज़रूरी नहीं",
               "अगले 3 दिन आपके खेत के लिए सामान्य रहेंगे। अपना सामान्य कार्यक्रम जारी रखें।"),
        "gu": ("હવામાન અંગે કોઈ પગલાંની જરૂર નથી",
               "આગામી 3 દિવસ તમારા ખેતર માટે સામાન્ય રહેશે. તમારું નિયમિત સમયપત્રક ચાલુ રાખો."),
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
    },
    "good_weather": {
        "en": ("Good weather — take action", "{recs}"),
        "hi": ("अच्छा मौसम — कार्रवाई करें", "{recs}"),
        "gu": ("સારું હવામાન — પગલાં લો", "{recs}"),
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
    },
}

# Short recommendation phrases used inside the "good weather" detail text —
# joined together rather than shown as separate actions.
_PHRASES: dict[str, dict[str, str]] = {
    "spray_calm": {
        "en": "Conditions are ideal for spraying — calm and dry.",
        "hi": "छिड़काव के लिए स्थितियाँ आदर्श हैं — शांत और सूखा मौसम।",
        "gu": "છંટકાવ માટે સ્થિતિ આદર્શ છે — શાંત અને સૂકું હવામાન.",
    },
    "weed_sow": {
        "en": "Great weather for weeding, sowing, or transplanting.",
        "hi": "निराई, बुवाई या रोपाई के लिए बढ़िया मौसम है।",
        "gu": "નિંદામણ, વાવણી અથવા રોપણી માટે સરસ હવામાન છે.",
    },
    "harvest_dry": {
        "en": "Good window for harvesting or drying produce in the sun.",
        "hi": "फसल कटाई या धूप में उपज सुखाने के लिए अच्छा समय है।",
        "gu": "લણણી અથવા તડકામાં ઉપજ સૂકવવા માટે સારો સમય છે.",
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


async def fetch_forecast(lat: float, lon: float) -> dict:
    s = get_settings()
    params = {
        "latitude": lat, "longitude": lon, "hourly": _HOURLY, "daily": _DAILY,
        "forecast_days": 3, "timezone": "auto",
    }
    async with httpx.AsyncClient(
        timeout=s.open_meteo_timeout_s, headers={"User-Agent": s.http_user_agent}
    ) as client:
        resp = await client.get(s.open_meteo_base_url, params=params)
        resp.raise_for_status()
        return resp.json()


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
