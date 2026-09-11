"""Module C — Weather Intelligence.

Pulls a 3‑day forecast from Open‑Meteo (free, no key) and runs a transparent
rule engine over it. Rules are documented in ``docs/weather_rules.md``.
"""

from __future__ import annotations

import logging

import httpx

from ..config import get_settings
from ..models.modules import WeatherAction, WeatherAdvice

log = logging.getLogger(__name__)

_FUNGAL = ("blight", "mould", "mold", "mildew", "rust", "scab", "rot", "spot", "leaf_spot")

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
    crop: str | None = None, stage: str | None = None,
) -> WeatherAdvice:
    s = _summarise(fc)
    actions: list[WeatherAction] = []

    rain_prob = s["rain_prob_24h_pct"] or 0
    rain_24h = s["rain_sum_24h_mm"] or 0
    humidity = s["humidity_mean_24h_pct"] or 0
    tmax = s["temp_max_c"]
    tmin = s["temp_min_c"]
    wind = s["wind_max_kmh"] or 0
    fungal = bool(last_disease) and any(k in last_disease.lower() for k in _FUNGAL)

    if rain_prob >= 60 or rain_24h >= 5:
        actions.append(WeatherAction(
            severity="act", headline="Delay irrigation",
            detail=f"Rain likely in the next 24 h ({rain_prob:.0f}% chance, ~{rain_24h:.0f} mm). "
                   "Skip watering to save water and avoid waterlogging.",
        ))
    elif tmax is not None and tmax >= 34:
        actions.append(WeatherAction(
            severity="watch", headline="Water early or late",
            detail=f"Hot and dry (up to {tmax:.0f}°C, little rain). Irrigate at dawn or dusk to cut evaporation.",
        ))

    if fungal and humidity >= 80:
        actions.append(WeatherAction(
            severity="act", headline="Spray preventively for fungal disease",
            detail=f"{last_disease} detected recently and humidity is high (~{humidity:.0f}%). "
                   "Conditions favour rapid spread — apply a protective fungicide or bio‑control.",
        ))
    elif humidity >= 85:
        actions.append(WeatherAction(
            severity="watch", headline="Watch for fungal disease",
            detail=f"Humidity is very high (~{humidity:.0f}%). Scout leaves for spots or mould and improve airflow.",
        ))

    if tmax is not None and tmax >= 38:
        actions.append(WeatherAction(
            severity="watch", headline="Heat‑stress risk",
            detail=f"Peak {tmax:.0f}°C expected. Mulch to keep roots cool and avoid spraying in the midday sun.",
        ))
    if tmin is not None and tmin <= 5:
        actions.append(WeatherAction(
            severity="watch", headline="Cold‑stress risk",
            detail=f"Night lows near {tmin:.0f}°C. Protect seedlings and delay nitrogen top‑dressing.",
        ))
    if wind >= 35:
        actions.append(WeatherAction(
            severity="watch", headline="Delay spraying — wind",
            detail=f"Gusts up to {wind:.0f} km/h will cause spray drift. Spray on a calmer day.",
        ))

    if not actions:
        actions.append(WeatherAction(
            severity="info", headline="No weather action needed",
            detail="The next 3 days look steady for your farm. Carry on with your normal schedule.",
        ))

    return WeatherAdvice(lat=lat, lon=lon, summary=s, actions=actions)
