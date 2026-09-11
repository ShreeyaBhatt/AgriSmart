"""Module C (weather rules), D (sustainability formula), E (assistant fallback)."""

import pytest

from app.backend.models.modules import SustainabilityRequest
from app.backend.services.assistant import answer_question
from app.backend.services.sustainability import compute_score
from app.backend.services.weather import build_advice


def _forecast(*, rain_prob=0, rain_mm=0.0, humidity=50, tmax=30, tmin=18, wind=10):
    return {
        "hourly": {
            "relative_humidity_2m": [humidity] * 24,
            "precipitation": [rain_mm / 24] * 24,
        },
        "daily": {
            "precipitation_probability_max": [rain_prob, rain_prob, rain_prob],
            "precipitation_sum": [rain_mm, 0, 0],
            "temperature_2m_max": [tmax, tmax, tmax],
            "temperature_2m_min": [tmin, tmin, tmin],
            "wind_speed_10m_max": [wind, wind, wind],
        },
    }


# --- Module C ---------------------------------------------------------------
def test_weather_rain_defers_irrigation():
    adv = build_advice(1, 2, _forecast(rain_prob=80, rain_mm=12))
    assert any(a.headline == "Delay irrigation" and a.severity == "act" for a in adv.actions)


def test_weather_fungal_plus_humidity_triggers_spray():
    adv = build_advice(1, 2, _forecast(humidity=88), last_disease="Tomato___Late_blight")
    assert any("fungal" in a.headline.lower() and a.severity == "act" for a in adv.actions)


def test_weather_quiet_forecast_is_info_only():
    adv = build_advice(1, 2, _forecast())
    assert len(adv.actions) == 1 and adv.actions[0].severity == "info"


# --- Module D -------------------------------------------------------------
def test_sustainability_perfect_practice_scores_high():
    s = compute_score(SustainabilityRequest(
        water_used_mm=300, water_recommended_mm=300,
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.score == 100.0 and s.band == "excellent"
    assert s.water_overuse_pct == 0 and s.crop_health_pct == 100


def test_sustainability_overuse_and_disease_drag_score_down():
    s = compute_score(SustainabilityRequest(
        water_used_mm=600, water_recommended_mm=300,
        chemical_used_kg_ha=100, chemical_recommended_kg_ha=50,
        disease_class="Tomato___Late_blight"))
    assert s.score < 60 and s.band in {"poor", "fair"}
    assert s.water_overuse_pct == 100.0
    assert len(s.tips) >= 2 and "clamp" in s.formula


# --- Module E ------------------------------------------------------------
@pytest.mark.asyncio
async def test_assistant_fallback_is_grounded_without_key():
    ans = await answer_question("How do I control late blight on my tomato?", lang="en")
    assert ans.used_llm is False
    assert "Tomato___Late_blight" in ans.grounded_on
    assert "blight" in ans.answer.lower()


@pytest.mark.asyncio
async def test_assistant_handles_unknown_question():
    ans = await answer_question("what colour should the sky be", lang="en")
    assert ans.used_llm is False and isinstance(ans.answer, str) and ans.answer
