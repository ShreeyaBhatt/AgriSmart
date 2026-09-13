"""User account repo — a handful of functions over the ``users`` Mongo
collection (deliberately not an ODM; see ``auth.py``'s docstring for the same
"keep the dependency surface small" reasoning).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..models.user import User
from ..mongo import users_collection


def _uuid() -> str:
    return uuid.uuid4().hex


def _to_user(doc: dict) -> User:
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return User(**doc)


def _omit_none(doc: dict) -> dict:
    # `phone` and `email` carry unique *sparse* indexes — sparse only skips
    # documents where the field is absent, not documents that explicitly
    # store it as null. Every doc got the same explicit null, so the second
    # insert always tripped a duplicate-key error. Omitting the key entirely
    # for unset fields is what actually makes the index treat it as unset.
    return {k: v for k, v in doc.items() if v is not None}


async def get_by_id(user_id: str) -> User | None:
    doc = await users_collection.find_one({"_id": user_id})
    return _to_user(doc) if doc else None


async def get_by_phone(phone: str) -> User | None:
    doc = await users_collection.find_one({"phone": phone})
    return _to_user(doc) if doc else None


async def create_from_phone(phone: str) -> User:
    doc = {
        "_id": _uuid(),
        "phone": phone,
        "email": None,
        "name": "Farmer",
        "is_guest": False,
        "location_label": None,
        "primary_crop": None,
        "default_language": "en",
        "onboarding_complete": False,
        "created_at": datetime.now(timezone.utc),
    }
    await users_collection.insert_one(_omit_none(doc))
    return _to_user(doc)


async def create_guest() -> User:
    doc = {
        "_id": _uuid(),
        "phone": None,
        "email": None,
        "name": "Guest",
        "is_guest": True,
        "location_label": None,
        "primary_crop": None,
        "default_language": "en",
        "onboarding_complete": True,
        "created_at": datetime.now(timezone.utc),
    }
    await users_collection.insert_one(_omit_none(doc))
    return _to_user(doc)


async def link_phone(user_id: str, phone: str) -> User:
    """Attach a phone number to an existing (guest) user in place, rather than
    creating a second account — the guest's id doesn't change, so every plot/
    diagnosis/log already keyed to it stays attached with no data migration."""
    await users_collection.update_one(
        {"_id": user_id},
        {"$set": {"phone": phone, "is_guest": False}},
    )
    user = await get_by_id(user_id)
    assert user is not None  # just written above
    return user


async def complete_profile(user_id: str, *, name: str, location_label: str, primary_crop: str) -> User:
    await users_collection.update_one(
        {"_id": user_id},
        {"$set": {
            "name": name,
            "location_label": location_label,
            "primary_crop": primary_crop,
            "onboarding_complete": True,
        }},
    )
    user = await get_by_id(user_id)
    assert user is not None  # just written above
    return user
