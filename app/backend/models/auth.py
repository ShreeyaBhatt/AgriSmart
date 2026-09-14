"""Pydantic schemas for authentication (phone + OTP + guest)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_PHONE_RE = re.compile(r"^\d{10,15}$")
Language = Literal["en", "hi", "gu", "mr", "ta", "te", "pa"]

# AgriSmart's target market (SIH India hackathon) — used only to collapse a
# country-code-prefixed number down to the same bare digits as one entered
# without it.
_INDIA_CC = "91"


def _normalize_phone(v: str) -> str:
    digits = re.sub(r"\D", "", v)
    digits = digits.lstrip("0")

    if len(digits) > 10 and digits.startswith(_INDIA_CC):
        digits = digits[len(_INDIA_CC):]

    # Must be exactly 10 digits
    if len(digits) != 10:
        raise ValueError("Enter a valid mobile number")

    # Indian mobile numbers start with 6, 7, 8, or 9
    if digits[0] not in "6789":
        raise ValueError("Enter a valid mobile number")

    # Reject numbers made entirely of the same digit
    if len(set(digits)) == 1:
        raise ValueError("Enter a valid mobile number")

    return digits


def _strip_required(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("This field can't be blank")
    return v


def _strip_optional(v: str | None) -> str | None:
    return _strip_required(v) if v is not None else v


class OtpRequest(BaseModel):
    phone: str
    mode: Literal["login", "signup"]

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return _normalize_phone(v)


class OtpRequestOut(BaseModel):
    phone: str
    # Set when AGRISMART_OTP_SHOW_CODE=true (the default here, since no free
    # SMS provider was viable for this deployment — see config.py). Set the
    # env var to false once a real SMS provider is wired up in
    # services/otp.py so codes stop being shown on-screen.
    demo_otp: str | None = None


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

    @field_validator("name", "location_label", "primary_crop")
    @classmethod
    def _trim(cls, v: str) -> str:
        return _strip_required(v)


class UpdateProfileRequest(BaseModel):
    """Same fields as CompleteProfileRequest, all optional — for editing
    after signup rather than the one-shot initial fill-in.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    location_label: str | None = Field(default=None, min_length=1, max_length=200)
    primary_crop: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("name", "location_label", "primary_crop")
    @classmethod
    def _trim(cls, v: str | None) -> str | None:
        return _strip_optional(v)


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
    is_new: bool
    user: UserOut