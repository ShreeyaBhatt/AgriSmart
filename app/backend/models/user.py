"""The MongoDB-backed account — a plain Pydantic model, not a SQLAlchemy one.

Kept attribute-compatible with the old ORM ``User`` (``.id``, ``.name``, ...)
so every router that only ever did ``user: User = Depends(get_current_user)``
and read a handful of attributes needs no further change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "hi", "gu", "mr", "ta", "te", "pa"]


class User(BaseModel):
    id: str
    phone: str | None = None
    email: str | None = None
    name: str = "Farmer"
    is_guest: bool = False
    location_label: str | None = None
    primary_crop: str | None = None
    default_language: Language = "en"
    onboarding_complete: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
