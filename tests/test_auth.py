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


# --- Mobile number validation --------------------------------------------
# Backend is the source of truth (app/backend/models/auth.py _normalize_phone);
# the frontend's isValidPhone in Login.jsx mirrors the same rules for instant
# feedback, but must never be the only guard — every case here is exercised
# straight against the API, exactly as a bypassed/hostile client would hit it.
@pytest.mark.parametrize("bad_phone", [
    "98765432109",          # 11 digits — more than 10
    "987654321098765",      # 15 digits — well over 10
    "1111111111",           # repetitive / obviously fake
    "0000000000",           # repetitive / obviously fake
    "-111111111",           # negative number
    "-9876543210",          # negative, would be 10 digits if the sign were stripped
    "98765abcde",           # non-digit characters
    "9876$54#3210",         # non-digit characters
    "987654321",            # 9 digits — fewer than 10
    "",                     # blank
])
async def test_otp_request_rejects_invalid_mobile_numbers(client, bad_phone):
    r = await client.post("/api/auth/otp/request", json={"phone": bad_phone})
    assert r.status_code == 422, f"{bad_phone!r} should have been rejected, got {r.status_code}: {r.text}"


async def test_otp_verify_also_rejects_invalid_mobile_numbers(client):
    # /otp/verify shares the same OtpVerifyRequest.phone validator as
    # /otp/request — this proves both endpoints (i.e. both the login and the
    # sign-up flow, which are the same two calls) enforce it identically.
    r = await client.post("/api/auth/otp/verify", json={"phone": "1111111111", "otp": "123456"})
    assert r.status_code == 422


async def test_otp_request_accepts_a_valid_ten_digit_number(client):
    r = await client.post("/api/auth/otp/request", json={"phone": _rand_phone()})
    assert r.status_code == 200
