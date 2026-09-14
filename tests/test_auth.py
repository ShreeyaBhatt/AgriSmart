"""Phone + OTP login, guest access, profile completion, and protected-route behaviour."""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _rand_phone() -> str:
    return str(1000000000 + int(uuid.uuid4().int % 900000000))


async def test_otp_request_returns_a_random_debug_code(client):
    r = await client.post("/api/auth/otp/request", json={"phone": _rand_phone()})
    assert r.status_code == 200
    code = r.json()["demo_otp"]
    # AGRISMART_OTP_SHOW_CODE is on in tests (as it is by default — see
    # config.py), but the code itself must be a
    # freshly generated 6-digit value, not a fixed shared one — that's the
    # whole point of the fix (a leaked/guessed static code used to log in
    # as anyone).
    assert code is not None and len(code) == 6 and code.isdigit()


async def test_otp_request_is_not_a_fixed_code(client):
    r1 = (await client.post("/api/auth/otp/request", json={"phone": _rand_phone()})).json()
    r2 = (await client.post("/api/auth/otp/request", json={"phone": _rand_phone()})).json()
    # Not a hard guarantee (a 1-in-a-million collision is possible), but
    # confirms request_otp() isn't just returning settings.otp_demo_code.
    assert r1["demo_otp"] != r2["demo_otp"]


async def test_otp_verify_wrong_code_rejected(client, otp_login):
    r = await otp_login(client, _rand_phone(), otp="000000")
    assert r.status_code == 401


async def test_otp_verify_without_request_rejected(client):
    r = await client.post("/api/auth/otp/verify", json={"phone": _rand_phone(), "otp": "123456"})
    assert r.status_code == 401


async def test_otp_verify_is_one_shot(client, otp_login):
    """A correct code can't be replayed a second time."""
    phone = _rand_phone()
    req = await client.post("/api/auth/otp/request", json={"phone": phone})
    code = req.json()["demo_otp"]

    first = await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": code})
    assert first.status_code == 200

    second = await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": code})
    assert second.status_code == 401


async def test_otp_verify_creates_user_and_marks_new(client, otp_login):
    phone = _rand_phone()
    r = await otp_login(client, phone)
    assert r.status_code == 200
    body = r.json()
    assert body["is_new"] is True
    assert body["user"]["phone"] == phone
    assert body["user"]["onboarding_complete"] is False
    assert body["user"]["is_guest"] is False


async def test_otp_verify_normalizes_phone_across_formats(client, otp_login):
    """+91 98765 43210 / 09876543210 / 9876543210 must resolve to one account."""
    bare = _rand_phone()
    r1 = await otp_login(client, bare)
    assert r1.status_code == 200
    user_id = r1.json()["user"]["id"]

    prefixed = f"+91 {bare[:5]} {bare[5:]}"
    r2 = await otp_login(client, prefixed)
    assert r2.status_code == 200
    assert r2.json()["user"]["id"] == user_id
    assert r2.json()["user"]["phone"] == bare  # stored in the normalized bare form

    trunk = f"0{bare}"
    r3 = await otp_login(client, trunk)
    assert r3.status_code == 200
    assert r3.json()["user"]["id"] == user_id


async def test_otp_verify_still_new_until_profile_completed(client, otp_login):
    phone = _rand_phone()
    await otp_login(client, phone)
    r = await otp_login(client, phone)
    assert r.status_code == 200
    assert r.json()["is_new"] is True  # onboarding still incomplete

    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    await client.post("/api/auth/complete-profile", headers=headers, json={
        "name": "Asha", "location_label": "Nashik", "primary_crop": "Wheat",
    })
    r2 = await otp_login(client, phone)
    assert r2.json()["is_new"] is False


async def test_guest_login_is_immediate_and_onboarded(client):
    r = await client.post("/api/auth/guest")
    assert r.status_code == 201
    body = r.json()
    assert body["is_new"] is False
    assert body["user"]["is_guest"] is True
    assert body["user"]["name"] == "Guest"
    assert body["user"]["phone"] is None


async def test_complete_profile_and_me(client, otp_login):
    phone = _rand_phone()
    verify = await otp_login(client, phone)
    headers = {"Authorization": f"Bearer {verify.json()['access_token']}"}

    r = await client.post("/api/auth/complete-profile", headers=headers, json={
        "name": "Bhavesh", "location_label": "Anand, Gujarat", "primary_crop": "Cotton",
    })
    assert r.status_code == 200
    assert r.json()["onboarding_complete"] is True

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["name"] == "Bhavesh"


async def test_complete_profile_trims_whitespace(client, otp_login):
    """A name typed with a stray leading/trailing space must not survive
    into storage — otherwise `name.split(" ")[0]` in the UI renders empty
    and the name looks like it "disappeared" after onboarding."""
    phone = _rand_phone()
    verify = await otp_login(client, phone)
    headers = {"Authorization": f"Bearer {verify.json()['access_token']}"}

    r = await client.post("/api/auth/complete-profile", headers=headers, json={
        "name": "  Ramesh Patel  ", "location_label": " Surat ", "primary_crop": "Cotton",
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Ramesh Patel"
    assert r.json()["location_label"] == "Surat"


async def test_protected_route_requires_auth(client):
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/plots")).status_code == 401
    assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401
