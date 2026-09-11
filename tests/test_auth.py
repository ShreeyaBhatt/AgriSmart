"""Phone + OTP login, guest access, profile completion, and protected-route behaviour."""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _rand_phone() -> str:
    return str(1000000000 + int(uuid.uuid4().int % 900000000))


async def test_otp_request_returns_demo_code(client):
    r = await client.post("/api/auth/otp/request", json={"phone": _rand_phone()})
    assert r.status_code == 200
    assert r.json()["demo_otp"] == "123456"


async def test_otp_verify_wrong_code_rejected(client):
    r = await client.post("/api/auth/otp/verify", json={"phone": _rand_phone(), "otp": "000000"})
    assert r.status_code == 401


async def test_otp_verify_creates_user_and_marks_new(client):
    phone = _rand_phone()
    r = await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": "123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_new"] is True
    assert body["user"]["phone"] == phone
    assert body["user"]["onboarding_complete"] is False
    assert body["user"]["is_guest"] is False


async def test_otp_verify_still_new_until_profile_completed(client):
    phone = _rand_phone()
    await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": "123456"})
    r = await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": "123456"})
    assert r.status_code == 200
    assert r.json()["is_new"] is True  # onboarding still incomplete

    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    await client.post("/api/auth/complete-profile", headers=headers, json={
        "name": "Asha", "location_label": "Nashik", "primary_crop": "Wheat",
    })
    r2 = await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": "123456"})
    assert r2.json()["is_new"] is False


async def test_guest_login_is_immediate_and_onboarded(client):
    r = await client.post("/api/auth/guest")
    assert r.status_code == 201
    body = r.json()
    assert body["is_new"] is False
    assert body["user"]["is_guest"] is True
    assert body["user"]["name"] == "Guest"
    assert body["user"]["phone"] is None


async def test_complete_profile_and_me(client):
    phone = _rand_phone()
    verify = await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": "123456"})
    headers = {"Authorization": f"Bearer {verify.json()['access_token']}"}

    r = await client.post("/api/auth/complete-profile", headers=headers, json={
        "name": "Bhavesh", "location_label": "Anand, Gujarat", "primary_crop": "Cotton",
    })
    assert r.status_code == 200
    assert r.json()["onboarding_complete"] is True

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["name"] == "Bhavesh"


async def test_protected_route_requires_auth(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/plots")).status_code == 401
    assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401
