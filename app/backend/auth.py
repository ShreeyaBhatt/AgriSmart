"""Lean JWT auth — bearer tokens (PyJWT) against the Mongo-backed user store.

Deliberately not ``fastapi-users``: a handful of functions is enough here and
keeps the dependency surface small. Accounts live in MongoDB (``mongo.py``,
``services/users.py``); there's no password to check anymore — login is
phone + OTP or guest (see ``routers/auth.py``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .models.user import User
from .services import users as users_repo

_bearer = HTTPBearer(auto_error=False)
_UNAUTH = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                        headers={"WWW-Authenticate": "Bearer"})


def create_access_token(user_id: str) -> str:
    s = get_settings()
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


async def _user_from_credentials(creds: HTTPAuthorizationCredentials | None) -> User | None:
    if creds is None:
        return None
    s = get_settings()
    try:
        payload = jwt.decode(creds.credentials, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    return await users_repo.get_by_id(payload.get("sub"))


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    user = await _user_from_credentials(creds)
    if user is None:
        raise _UNAUTH
    return user


async def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User | None:
    """For endpoints usable logged-in or anonymously (e.g. the soil quick-check)."""
    return await _user_from_credentials(creds)
