"""Plot CRUD, soil snapshot, timeline, and per-farmer isolation."""

import uuid
from datetime import datetime, timezone

import pytest

from app.backend.models.soil import SoilProfile

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _stub_soil(monkeypatch):
    async def fake_build(lat, lon, **kw):
        return SoilProfile(
            source="stub",
            fetched_at=datetime.now(timezone.utc),
            lat=lat,
            lon=lon,
            texture_class="clay loam",
            ph=6.4,
            organic_carbon_pct=0.7,
        )

    monkeypatch.setattr(
        "app.backend.routers.plots.build_soil_profile",
        fake_build,
    )


async def test_create_and_list_plot_with_soil(auth_client):
    client, headers, _ = auth_client

    r = await client.post(
        "/api/plots",
        headers=headers,
        json={
            "name": "North field",
            "lat": 22.31,
            "lon": 73.18,
            "area_ha": 1.5,
        },
    )

    assert r.status_code == 201, r.text
    plot = r.json()
    assert plot["name"] == "North field"
    assert plot["soil_status"] == "pending"
    assert plot["soil_snapshot"] is None

    # Wait for background task to complete and poll the status endpoint
    import asyncio

    await asyncio.sleep(0.1)

    status_r = await client.get(
        f"/api/plots/{plot['id']}/soil-status",
        headers=headers,
    )

    assert status_r.status_code == 200
    status_data = status_r.json()
    assert status_data["soil_status"] == "ready"
    assert status_data["soil_snapshot"]["texture_class"] == "clay loam"
    assert status_data["soil_fetched_at"] is not None

    lst = await client.get("/api/plots", headers=headers)
    assert lst.status_code == 200 and len(lst.json()) == 1


async def test_timeline_merges_activity(auth_client):
    client, headers, _ = auth_client

    plot_id = (
        await client.post(
            "/api/plots",
            headers=headers,
            json={"name": "P", "lat": 1.0, "lon": 2.0},
        )
    ).json()["id"]

    assert (
        await client.post(
            "/api/irrigation",
            headers=headers,
            json={
                "plot_id": plot_id,
                "amount_mm": 20,
                "note": "furrow",
            },
        )
    ).status_code == 201

    assert (
        await client.post(
            "/api/actions",
            headers=headers,
            json={
                "plot_id": plot_id,
                "action_type": "spray",
                "details": "neem",
            },
        )
    ).status_code == 201

    tl = await client.get(
        f"/api/plots/{plot_id}/timeline",
        headers=headers,
    )

    assert tl.status_code == 200
    kinds = {e["kind"] for e in tl.json()["entries"]}
    assert kinds == {"irrigation", "action"}


async def test_farmers_cannot_see_each_others_plots(client):
    async def mk():
        n = uuid.uuid4().int
        phone = str(6 + n % 4) + str(n % 1_000_000_000).zfill(9)

        req = (
            await client.post(
                "/api/auth/otp/request",
                json={"phone": phone, "mode": "signup"},
            )
        ).json()

        b = (
            await client.post(
                "/api/auth/otp/verify",
                json={
                    "phone": phone,
                    "otp": req["demo_otp"],
                },
            )
        ).json()

        return {"Authorization": f"Bearer {b['access_token']}"}

    a, b = await mk(), await mk()

    a_plot = (
        await client.post(
            "/api/plots",
            headers=a,
            json={"name": "A field", "lat": 1, "lon": 1},
        )
    ).json()["id"]

    assert (await client.get("/api/plots", headers=b)).json() == []
    assert (
        await client.get(
            f"/api/plots/{a_plot}",
            headers=b,
        )
    ).status_code == 404

    assert (
        await client.delete(
            f"/api/plots/{a_plot}",
            headers=b,
        )
    ).status_code == 404

    assert (
        await client.get(
            f"/api/plots/{a_plot}",
            headers=a,
        )
    ).status_code == 200