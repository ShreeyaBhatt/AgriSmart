"""Tests for Bonus Module G: Autonomous Agentic Advisor (ReAct loop & Decision Trace)."""

import pytest

from app.backend.services.agent import evaluate_advisory
from app.backend.services import weather as weather_service


def _dummy_forecast(*, rain_prob=0, rain_mm=0.0, humidity=50, tmax=30, tmin=18, wind=10):
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


def test_agent_fungal_and_rain_conflict():
    # Active fungal disease + high humidity + imminent rain
    advisory = evaluate_advisory(
        plot_id="p1",
        plot_name="Tomato Patch",
        crop="Tomato",
        stage="Vegetative",
        soil_snapshot={"ph": 6.8, "texture_class": "Clay Loam"},
        last_diagnosis={"predicted_class": "Tomato___Late_blight", "abstained": False},
        forecast=_dummy_forecast(rain_prob=80, rain_mm=15.0, humidity=85, wind=12),
        lang="en",
    )

    assert advisory.urgency == "critical"
    assert "Halt Irrigation" in advisory.headline
    assert any("HALT" in a.directive for a in advisory.decision_trace.action_plan)
    assert any("TIER1-RULE-401" in r for r in advisory.decision_trace.rules_applied)
    assert len(advisory.decision_trace.conflicts_detected) >= 1
    assert advisory.decision_trace.execution_time_ms > 0
    assert advisory.decision_trace.observations["diagnosis"]["fungal"] is True


def test_agent_wind_drift_hazard():
    # High wind should trigger the wind-drift rule and postpone spraying
    advisory = evaluate_advisory(
        plot_id="p2",
        plot_name="Grape Orchard",
        crop="Grape",
        stage="Fruiting",
        soil_snapshot=None,
        last_diagnosis={"predicted_class": "Grape___Black_rot", "abstained": False},
        forecast=_dummy_forecast(rain_prob=70, rain_mm=10.0, humidity=80, wind=32),
        lang="en",
    )

    assert advisory.urgency == "critical"
    assert any("TIER1-RULE-402" in r for r in advisory.decision_trace.rules_applied)
    assert any("Wind is too high" in a.directive for a in advisory.decision_trace.action_plan)


def test_agent_heat_stress_flowering_stage():
    # Flowering stage + extreme heat + zero rain
    advisory = evaluate_advisory(
        plot_id="p3",
        plot_name="Corn Field",
        crop="Corn",
        stage="Flowering",
        soil_snapshot=None,
        last_diagnosis=None,
        forecast=_dummy_forecast(tmax=38, rain_mm=0.0, humidity=30),
        lang="en",
    )

    assert advisory.urgency in ("critical", "warning")
    assert any("TIER1-RULE-404" in r for r in advisory.decision_trace.rules_applied)
    assert any("pre-dawn" in a.directive.lower() for a in advisory.decision_trace.action_plan)


def test_agent_soil_amendment_heavy_rain():
    # Acidic soil needing lime + heavy rain downpour
    advisory = evaluate_advisory(
        plot_id="p4",
        plot_name="Potato Block",
        crop="Potato",
        stage="Tuber Initiation",
        soil_snapshot={"ph": 4.8, "texture_class": "Sandy Loam"},
        last_diagnosis=None,
        forecast=_dummy_forecast(rain_prob=90, rain_mm=25.0),
        lang="en",
    )

    assert any("TIER1-RULE-405" in r for r in advisory.decision_trace.rules_applied)
    assert any("POSTPONE lime" in a.directive for a in advisory.decision_trace.action_plan)


@pytest.mark.asyncio
async def test_agent_api_endpoint(auth_client, monkeypatch):
    client, headers, user = auth_client

    async def _mock_fetch_forecast(lat, lon):
        return _dummy_forecast(rain_prob=10, rain_mm=0.0)

    async def _mock_soil_profile(lat, lon, **kw):
        from app.backend.models.soil import SoilProfile
        from datetime import datetime, timezone
        return SoilProfile(
            source="stub", fetched_at=datetime.now(timezone.utc), lat=lat, lon=lon,
            texture_class="clay loam", ph=6.4, organic_carbon_pct=0.7,
        )

    monkeypatch.setattr(weather_service, "fetch_forecast", _mock_fetch_forecast)
    monkeypatch.setattr("app.backend.routers.plots.build_soil_profile", _mock_soil_profile)

    # 1. Create a plot
    plot_res = await client.post("/api/plots", headers=headers, json={
        "name": "Orchard 1",
        "lat": 22.3,
        "lon": 73.2,
        "area_ha": 1.5,
        "main_crop": "Tomato",
    })
    assert plot_res.status_code == 201, plot_res.text
    plot_id = plot_res.json()["id"]

    # 2. Call the agent advisory endpoint
    adv_res = await client.get(f"/api/agent/plots/{plot_id}/advisory?lang=en", headers=headers)
    assert adv_res.status_code == 200, adv_res.text
    data = adv_res.json()

    assert data["plot_id"] == plot_id
    assert "decision_trace" in data
    assert "observations" in data["decision_trace"]
    assert "action_plan" in data["decision_trace"]
    assert len(data["decision_trace"]["action_plan"]) >= 1
