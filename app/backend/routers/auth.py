"""Phone + OTP login, guest access, and first-login profile completion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import create_access_token, get_current_user
from ..models.auth import (
    CompleteProfileRequest,
    OtpRequest,
    OtpRequestOut,
    OtpVerifyRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)
from ..models.user import User
from ..services import otp as otp_service
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
    if body.mode == "signup":
        existing_user = await users_repo.get_by_phone(body.phone)
        if existing_user is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "User already exists",
            )
    elif body.mode == "login":
        existing_user = await users_repo.get_by_phone(body.phone)
        if existing_user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "No account found with this mobile number. Please sign up first.",
            )

    try:
        code = otp_service.request_otp(body.phone)
    except otp_service.OtpCooldownError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Please wait {int(exc.retry_after_s) + 1}s before requesting another code",
        ) from exc

    return OtpRequestOut(phone=body.phone, demo_otp=code)

@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp(body: OtpVerifyRequest) -> TokenResponse:
    if not otp_service.verify_otp(body.phone, body.otp):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired OTP")
    user = await users_repo.get_by_phone(body.phone)
    if user is None:
        if body.mode == "login":
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "No account found with this mobile number. Please sign up first.",
            )
        try:
            user = await users_repo.create_from_phone(body.phone)
        except users_repo.DuplicatePhoneError:
            # Lost a race with a concurrent verify for the same number —
            # the other request's account is the real one, use it.
            user = await users_repo.get_by_phone(body.phone)
            if user is None:
                raise
    return _token_response(user, is_new=not user.onboarding_complete)


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def continue_as_guest() -> TokenResponse:
    user = await users_repo.create_guest()
    return _token_response(user, is_new=False)


@router.post("/link-phone", response_model=UserOut)
async def link_phone(body: OtpVerifyRequest, user: User = Depends(get_current_user)) -> UserOut:
    """Attaches a phone to the caller's own (guest) row. Routing this through
    /otp/verify instead would look up-or-create a *different* user and
    orphan everything the guest already saved."""
    if not user.is_guest:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This account already has a phone number")
    if not otp_service.verify_otp(body.phone, body.otp):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired OTP")
    if await users_repo.get_by_phone(body.phone) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This phone number is already registered — log in with it instead")
    try:
        updated = await users_repo.link_phone(user.id, body.phone)
    except users_repo.DuplicatePhoneError:
        # TOCTOU: someone else registered/linked this exact number between
        # the get_by_phone check above and this write.
        raise HTTPException(status.HTTP_409_CONFLICT, "This phone number is already registered — log in with it instead")
    return UserOut.model_validate(updated, from_attributes=True)


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


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    body: UpdateProfileRequest, user: User = Depends(get_current_user)
) -> UserOut:
    """Edit profile fields after signup — complete-profile is one-shot at
    onboarding, this is the only way to change them afterward, and the only
    way a guest (who skips onboarding entirely) ever gets a primary_crop."""
    updated = await users_repo.update_profile(
        user.id,
        name=body.name,
        location_label=body.location_label,
        primary_crop=body.primary_crop,
    )
    return UserOut.model_validate(updated, from_attributes=True)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)
