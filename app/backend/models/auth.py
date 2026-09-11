"""Pydantic schemas for authentication (phone + OTP + guest)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_PHONE_RE = re.compile(r"^\d{10,15}$")
Language = Literal["en", "hi", "gu"]


def _normalize_phone(v: str) -> str:
    digits = re.sub(r"[\s\-()]", "", v).removeprefix("+")
    if not _PHONE_RE.match(digits):
        raise ValueError("Enter a valid mobile number (10-15 digits)")
    return digits


class OtpRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return _normalize_phone(v)


class OtpRequestOut(BaseModel):
    phone: str
    demo_otp: str  # prototype only: no SMS provider, this code is echoed back for the UI to show


class OtpVerifyRequest(BaseModel):
    phone: str
    otp: str = Field(min_length=4, max_length=8)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return _normalize_phone(v)


class CompleteProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location_label: str = Field(min_length=1, max_length=200)
    primary_crop: str = Field(min_length=1, max_length=80)


class UserOut(BaseModel):
    id: str
    phone: str | None
    email: str | None
    name: str
    is_guest: bool
    location_label: str | None
    primary_crop: str | None
    default_language: Language
    onboarding_complete: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new: bool  # true when the frontend should route to profile completion
    user: UserOut
