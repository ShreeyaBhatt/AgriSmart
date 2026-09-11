"""Model layer.

* ``orm``    — SQLAlchemy tables (app database, SQLite)
* ``user``   — the MongoDB-backed account (Pydantic, not SQLAlchemy)
* ``soil``, ``recommend`` — Pydantic request/response schemas
* ``auth``   — Pydantic schemas for phone+OTP login
"""

from .orm import (  # noqa: F401
    Base,
    Diagnosis,
    FarmerAction,
    IrrigationEvent,
    Planting,
    Plot,
)
from .user import User  # noqa: F401
