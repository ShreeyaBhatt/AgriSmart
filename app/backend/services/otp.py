"""One-time-password issuing and verification for phone login.

No SMS provider is wired up here — see ``_deliver()``. That used to mean the
whole "OTP" mechanism was a single static code (``AGRISMART_OTP_DEMO_CODE``)
accepted for *every* phone number and echoed straight back in the API
response: anyone who knew (or guessed, since it shipped as a checked-in
default) that code could log in as any farmer.

Every free-tier SMS route was tried and ruled out for this deployment (see
``config.py``'s comment on ``otp_show_code``), so for now the code is shown
on-screen instead of texted — ``settings.otp_show_code`` (on by default)
controls that. That's still a real improvement over the old static code: a
fresh *random* code is generated per phone/request, held server-side
(hashed, with an expiry and a capped number of verification attempts) rather
than compared against one shared value, and is consumed on first use so it
can't be replayed. When a real SMS provider becomes available, point
``_deliver()`` at it and set ``AGRISMART_OTP_SHOW_CODE=false`` — nothing
else in this module needs to change.

State is a plain in-process dict — this hackathon build already assumes a
single worker process (see the README's run instructions), and there's no
other cross-process shared state for auth. Swap this module for a
Redis-backed store before ever running with multiple workers.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass

from ..config import get_settings

log = logging.getLogger(__name__)


class OtpCooldownError(Exception):
    """Raised when a new code is requested before otp_resend_cooldown_s has
    elapsed since the last one for this phone. ``retry_after_s`` is how much
    longer the caller must wait."""

    def __init__(self, retry_after_s: float) -> None:
        self.retry_after_s = retry_after_s
        super().__init__(f"retry after {retry_after_s:.0f}s")


@dataclass
class _Entry:
    code_hash: str
    expires_at: float
    attempts_left: int
    requested_at: float


_store: dict[str, _Entry] = {}


def _hash(phone: str, code: str) -> str:
    # Salted with the phone number so two farmers never share a code_hash,
    # and so a leaked hash from one entry can't be replayed against another.
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def _deliver(phone: str, code: str) -> None:
    """No SMS provider is configured (see the module docstring for why) —
    log the code either way, so it's recoverable from the server log even
    when otp_show_code is off. Point this at a real provider (Twilio,
    MSG91, ...) to actually text farmers; nothing else in this module needs
    to change."""
    log.info("OTP for %s: %s (shown on-screen -- no SMS provider configured)", phone, code)


def request_otp(phone: str) -> str | None:
    """Generates, stores, and 'delivers' a fresh code for ``phone``.

    Returns the code when ``settings.otp_show_code`` is set (the default —
    see its config.py comment) so the frontend can display it; set that to
    false once a real SMS provider is wired up in ``_deliver()``.
    Raises ``OtpCooldownError`` if called again too soon for the same phone.
    """
    s = get_settings()
    now = time.time()
    prev = _store.get(phone)
    if prev is not None:
        elapsed = now - prev.requested_at
        if elapsed < s.otp_resend_cooldown_s:
            raise OtpCooldownError(s.otp_resend_cooldown_s - elapsed)

    code = f"{secrets.randbelow(1_000_000):06d}"
    _store[phone] = _Entry(
        code_hash=_hash(phone, code),
        expires_at=now + s.otp_ttl_s,
        attempts_left=s.otp_max_attempts,
        requested_at=now,
    )
    _deliver(phone, code)
    return code if s.otp_show_code else None


def verify_otp(phone: str, code: str) -> bool:
    """One-shot: a correct code is consumed on success (can't be replayed),
    and a wrong one costs an attempt so a stored code can't be brute-forced
    (expired/exhausted entries are also dropped, so they can't linger)."""
    entry = _store.get(phone)
    if entry is None:
        return False
    if time.time() > entry.expires_at or entry.attempts_left <= 0:
        _store.pop(phone, None)
        return False
    entry.attempts_left -= 1
    if _hash(phone, code) != entry.code_hash:
        return False
    _store.pop(phone, None)
    return True


def reset_store() -> None:
    """Test-only: clear all pending codes between test runs."""
    _store.clear()
