"""Async MongoDB client for the account store.

ML/farm data (plots, plantings, diagnoses, irrigation, actions) stays in
SQLite — see ``db.py``. Only user accounts live here, matching the original
build plan's choice of MongoDB, without pulling SQLAlchemy's async engine
into a second database. A ``mongomock://`` URL swaps in an in-memory fake
(``mongomock-motor``) so tests need no real MongoDB server.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from .config import get_settings

_settings = get_settings()

if _settings.mongo_url.startswith("mongomock://"):
    from mongomock_motor import AsyncMongoMockClient

    _client = AsyncMongoMockClient()
else:
    _client = AsyncIOMotorClient(_settings.mongo_url)

_db = _client[_settings.mongo_db_name]
users_collection: AsyncIOMotorCollection = _db["users"]


async def init_mongo_indexes() -> None:
    """Create indexes. Called on FastAPI startup, alongside ``init_db()``.

    Both indexes are ``sparse`` — guests have no ``phone`` and (for now)
    every account has no ``email`` — a non-sparse unique index would reject
    the second document with a null value.
    """
    await users_collection.create_index("phone", unique=True, sparse=True)
    await users_collection.create_index("email", unique=True, sparse=True)
