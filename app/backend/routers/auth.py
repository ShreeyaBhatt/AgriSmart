"""Phone + OTP login, guest access, and first-login profile completion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import create_access_token, get_current_user
from ..config import get_settings
from ..models.auth import (
    CompleteProfileRequest,
    OtpRequest,
    OtpRequestOut,
    OtpVerifyRequest,
    TokenResponse,
    UserOut,
)
from ..models.user import User
from ..services import users as users_repo

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User, *, is_new: bool) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        is_new=is_new,
        user=UserOut.model_validate(user, from_attributes=True),
    )


@router.post("/otp/request", response_model=OtpRequestOut)
async def request_otp(body: OtpRequest) -> OtpRequestOut:
    # Demo mode: no SMS provider is wired up, so there's nothing to send and
    # nothing to store/expire — the fixed demo code from settings *is* the
    # whole mechanism. It's echoed back here so the UI can show it directly.
    return OtpRequestOut(phone=body.phone, demo_otp=get_settings().otp_demo_code)


@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp(body: OtpVerifyRequest) -> TokenResponse:
    if body.otp != get_settings().otp_demo_code:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect OTP")
    user = await users_repo.get_by_phone(body.phone)
    if user is None:
        user = await users_repo.create_from_phone(body.phone)
    return _token_response(user, is_new=not user.onboarding_complete)


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def continue_as_guest() -> TokenResponse:
    user = await users_repo.create_guest()
    return _token_response(user, is_new=False)


@router.post("/complete-profile", response_model=UserOut)
async def complete_profile(
    body: CompleteProfileRequest, user: User = Depends(get_current_user)
) -> UserOut:
    updated = await users_repo.complete_profile(
        user.id,
        name=body.name,
        location_label=body.location_label,
        primary_crop=body.primary_crop,
    )
    return UserOut.model_validate(updated, from_attributes=True)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)
