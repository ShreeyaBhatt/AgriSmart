"""Shared fixtures: one SQLite-backed app + an in-memory Mongo fake, reset per test."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest_asyncio

# Configure the app BEFORE it is imported anywhere.
_TMP = Path(__file__).resolve().parent / "_tmp"
_TMP.mkdir(exist_ok=True)
_DB = _TMP / "test.db"
os.environ["AGRISMART_DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB.as_posix()}"
os.environ["AGRISMART_UPLOADS_DIR"] = str(_TMP / "uploads")
os.environ["AGRISMART_JWT_SECRET"] = "test-secret-at-least-32-chars-long-for-hmac-sha256"
os.environ["AGRISMART_GEMINI_API_KEY"] = ""  # force the offline assistant path
os.environ["AGRISMART_LLM_PROVIDER"] = "cards"  # zero-download circuit breaker for fast tests
os.environ["AGRISMART_MONGO_URL"] = "mongomock://localhost"  # in-memory fake, no real server
# otp_show_code defaults to true anyway (see config.py) but pin it
# explicitly so tests don't depend on that default. The resend cooldown is
# keyed by normalized phone, which would otherwise 429 a test that
# deliberately re-requests for the same underlying number in different
# formats (e.g. proving phone normalization) back-to-back.
os.environ["AGRISMART_OTP_SHOW_CODE"] = "true"
os.environ["AGRISMART_OTP_RESEND_COOLDOWN_S"] = "0"


@pytest_asyncio.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    from app.backend.db import Base, engine
    from app.backend.main import app
    from app.backend.mongo import users_collection
    from app.backend.services import otp as otp_service

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await users_collection.delete_many({})  # the mock Mongo client is a module-level singleton
    otp_service.reset_store()  # otp._store is a module-level dict too

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _request_and_verify(client, phone: str, otp: str | None = None):
    """Runs the real /otp/request + /otp/verify flow. Since AGRISMART_OTP_
    SHOW_CODE is on in tests, /otp/request's response carries the actual
    generated code — pass a wrong `otp` explicitly to test rejection."""
    req = await client.post("/api/auth/otp/request", json={"phone": phone})
    assert req.status_code == 200, req.text
    code = otp if otp is not None else req.json()["demo_otp"]
    assert code, "AGRISMART_OTP_SHOW_CODE should be on in tests"
    return await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": code})


@pytest_asyncio.fixture
def otp_login():
    """(client, phone[, otp]) -> the /otp/verify response — see _request_and_verify."""
    return _request_and_verify


@pytest_asyncio.fixture
async def auth_client(client):
    """(client, headers, user) for an authenticated, onboarded farmer."""
    phone = str(1000000000 + int(uuid.uuid4().int % 900000000))
    resp = await _request_and_verify(client, phone)
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    profile = await client.post("/api/auth/complete-profile", headers=headers, json={
        "name": "Test Farmer", "location_label": "Vadodara, Gujarat", "primary_crop": "Cotton",
    })
    assert profile.status_code == 200, profile.text
    return client, headers, profile.json()
