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


def test_weather_good_conditions_get_a_proactive_recommendation():
    # Calm, dry, moderate weather hits all three "good window" conditions at
    # once (ideal for spraying, weeding/sowing, and harvesting) — the rule
    # engine leads with that positive nudge rather than a bland "nothing to
    # do", so this isn't the info-only case.
    adv = build_advice(1, 2, _forecast())
    assert len(adv.actions) == 1 and adv.actions[0].severity == "recommend"
    assert adv.actions[0].headline == "Good weather — take action"


def test_weather_mediocre_forecast_is_info_only():
    # Nothing bad enough to warn about, but not clearly good either (cool and
    # a bit breezy) — no rule fires either way, so this is the actual
    # info-only fallback.
    adv = build_advice(1, 2, _forecast(tmax=15, wind=20))
    assert len(adv.actions) == 1 and adv.actions[0].severity == "info"


# --- Module D -------------------------------------------------------------
@pytest.mark.asyncio
async def test_sustainability_perfect_practice_scores_high():
    s = await compute_score(SustainabilityRequest(
        water_used_mm=300, water_recommended_mm=300,
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.score == 100.0
    assert s.band == "excellent"
    assert s.water_deviation_pct == 0 and s.crop_health_pct == 100


@pytest.mark.asyncio
async def test_sustainability_overuse_and_disease_drag_score_down():
    s = await compute_score(SustainabilityRequest(
        water_used_mm=600, water_recommended_mm=300,
        chemical_used_kg_ha=100, chemical_recommended_kg_ha=50,
        disease_class="Tomato___Late_blight"))
    assert s.score < 60 and s.band in {"poor", "fair"}
    assert s.water_overuse_pct == 100.0
    assert s.water_deficit_pct == 0
    assert len(s.tips) >= 2 and "clamp" in s.formula


@pytest.mark.asyncio
async def test_sustainability_under_irrigation_is_penalised_not_rewarded():
    """A farmer applying 50mm against a 500mm requirement (severe under-
    watering) used to score a perfect 100 with an "all within target"
    message, because the formula only ever penalised *excess* water — a
    deficit clamped to 0% overuse and was invisible to the score."""
    s = await compute_score(SustainabilityRequest(
        water_used_mm=50, water_recommended_mm=500,
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.water_overuse_pct == 0
    assert s.water_deficit_pct == 90.0  # (500-50)/500 * 100
    assert s.score < 80  # must not read "excellent" while 90% under-watered
    assert s.band != "excellent"
    assert any("below the crop's need" in tip for tip in s.tips)
    assert not any("all within target" in tip for tip in s.tips)


@pytest.mark.asyncio
async def test_sustainability_within_optimal_irrigation_band_scores_well():
    """90-110% of the recommendation is the soft 'optimal band' — neither
    side of the two-sided formula should meaningfully penalise it."""
    s = await compute_score(SustainabilityRequest(
        water_used_mm=280, water_recommended_mm=300,  # ~93%
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.water_overuse_pct == 0
    assert 0 < s.water_deficit_pct <= 10


# --- moisture_stress_risk: a separate indicator from score/band (PR #37
# fixed under-watering being invisible to the *score*; this covers the
# follow-up bug where a real, moderate-to-severe deviation still shows an
# "Excellent" band right next to it with nothing flagging the contradiction) ---
@pytest.mark.asyncio
async def test_moisture_stress_risk_is_severe_while_score_still_reads_excellent():
    """The reported case: -30% water deviation only costs 0.4*30=12 score
    points, nowhere near enough to drop out of 'excellent' (>=80) on its
    own — score/band and moisture_stress_risk are expected to disagree."""
    s = await compute_score(SustainabilityRequest(
        water_used_mm=210, water_recommended_mm=300,  # -30% deviation
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.water_deviation_pct == -30.0
    assert s.moisture_stress_risk == "severe"
    assert s.band == "excellent"  # confirms the two really are independent
    assert s.score >= 80


@pytest.mark.asyncio
async def test_moisture_stress_risk_is_severe_for_overuse_too_and_signed_positive():
    s = await compute_score(SustainabilityRequest(
        water_used_mm=400, water_recommended_mm=300,  # +33% deviation
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.water_deviation_pct > 0  # positive = overuse, not deficit
    assert s.moisture_stress_risk == "severe"


@pytest.mark.asyncio
async def test_moisture_stress_risk_is_moderate_between_10_and_25_percent():
    s = await compute_score(SustainabilityRequest(
        water_used_mm=250, water_recommended_mm=300,  # -16.7% deviation
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.moisture_stress_risk == "moderate"


@pytest.mark.asyncio
async def test_moisture_stress_risk_is_none_within_the_optimal_band():
    s = await compute_score(SustainabilityRequest(
        water_used_mm=300, water_recommended_mm=300,  # on target
        chemical_used_kg_ha=50, chemical_recommended_kg_ha=50, disease_class=None))
    assert s.water_deviation_pct == 0.0
    assert s.moisture_stress_risk == "none"
    assert s.band == "excellent"


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


# --- Module E, offline intent router (issue: assistant degrades to a
# single canned response for any non-disease question without a Gemini
# key) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_assistant_offline_pest_question_gets_pest_faq_not_generic():
    ans = await answer_question("How do I control pests on my crop?", lang="en")
    assert ans.used_llm is False
    assert "faq:pest" in ans.grounded_on
    assert "pest" in ans.answer.lower()
    assert "i don't have a specific card" not in ans.answer.lower()


@pytest.mark.asyncio
async def test_assistant_offline_sowing_question_gets_sowing_faq():
    ans = await answer_question("When should I sow my seeds this season?", lang="en")
    assert ans.used_llm is False
    assert "faq:sowing" in ans.grounded_on
    assert "sow" in ans.answer.lower()


@pytest.mark.asyncio
async def test_assistant_offline_weather_question_without_plot_gets_irrigation_faq():
    """No plot -> no coordinates for a live forecast -> falls back to the
    general irrigation-principles FAQ (which itself nudges the farmer to
    add a plot for live advice) instead of the fully generic no_card."""
    ans = await answer_question("Will it rain today?", lang="en")
    assert ans.used_llm is False
    assert "faq:irrigation" in ans.grounded_on
    assert "add a plot" in ans.answer.lower()


@pytest.mark.asyncio
async def test_assistant_offline_weather_question_with_plot_uses_live_forecast(monkeypatch):
    """With a plot location, the weather intent must be grounded in a real
    forecast + Module C's own rule engine, not a canned message."""
    from app.backend.services import weather as weather_service

    async def fake_forecast(lat, lon):
        return _forecast(rain_prob=80, rain_mm=10)

    monkeypatch.setattr(weather_service, "fetch_forecast", fake_forecast)

    plot = {"name": "Test plot", "lat": 22.3, "lon": 73.2, "area_ha": 1.0, "soil_snapshot": None}
    ans = await answer_question("Should I irrigate today?", lang="en", plot=plot)
    assert ans.used_llm is False
    assert "weather" in ans.grounded_on
    assert "delay irrigation" in ans.answer.lower()


@pytest.mark.asyncio
async def test_assistant_offline_soil_question_uses_plots_own_soil_data():
    plot = {
        "name": "Test plot", "lat": 22.3, "lon": 73.2, "area_ha": 1.0,
        "soil_snapshot": {
            "fetched_at": "2026-01-01T00:00:00Z", "lat": 22.3, "lon": 73.2,
            "texture_class": "clay", "ph": 8.6, "organic_carbon_pct": 0.3,
            "sand_pct": 20, "silt_pct": 30, "clay_pct": 50,
        },
    }
    ans = await answer_question("What fertilizer should I use for my soil?", lang="en", plot=plot)
    assert ans.used_llm is False
    assert "soil" in ans.grounded_on
