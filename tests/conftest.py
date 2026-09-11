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
os.environ["AGRISMART_JWT_SECRET"] = "test-secret"
os.environ["AGRISMART_GEMINI_API_KEY"] = ""  # force the offline assistant path
os.environ["AGRISMART_MONGO_URL"] = "mongomock://localhost"  # in-memory fake, no real server


@pytest_asyncio.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    from app.backend.db import Base, engine
    from app.backend.main import app
    from app.backend.mongo import users_collection

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await users_collection.delete_many({})  # the mock Mongo client is a module-level singleton

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(client):
    """(client, headers, user) for an authenticated, onboarded farmer."""
    from app.backend.config import get_settings

    phone = str(1000000000 + int(uuid.uuid4().int % 900000000))
    otp = get_settings().otp_demo_code

    await client.post("/api/auth/otp/request", json={"phone": phone})
    resp = await client.post("/api/auth/otp/verify", json={"phone": phone, "otp": otp})
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    profile = await client.post("/api/auth/complete-profile", headers=headers, json={
        "name": "Test Farmer", "location_label": "Vadodara, Gujarat", "primary_crop": "Cotton",
    })
    assert profile.status_code == 200, profile.text
    return client, headers, profile.json()
