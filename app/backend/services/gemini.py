"""Shared Gemini access for every module that optionally uses it (currently
Module E's assistant and Module D's sustainability sanity-check).

Centralised for two reasons that both showed up as real reliability problems
when each caller configured the SDK itself:

1. Configuring the SDK and building the model object is the expensive part —
   profiled at ~9-15s on a cold process, separate from actual generation
   (~4-6s). ``get_model()`` pays that once per process (ideally at startup
   via ``warm_up()``) instead of on every call, and instead of *every
   caller* paying it independently.
2. A slow/hung Gemini call must never stall a farmer's request indefinitely.
   ``generate()`` bounds every call with ``settings.gemini_timeout_s`` and
   never raises — any failure (missing key, quota, network, timeout, empty
   response) just returns ``None`` so the caller can fall back to its own
   deterministic path.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from ..config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def get_model():
    import google.generativeai as genai

    s = get_settings()
    genai.configure(api_key=s.gemini_api_key)
    return genai.GenerativeModel(s.gemini_model)


def reset_cache() -> None:
    get_model.cache_clear()


async def generate(prompt: str) -> str | None:
    """Runs one prompt against the cached model. Returns the response text,
    or ``None`` on a missing key, timeout, or any other failure — never
    raises, so callers can always fall back to a deterministic answer."""
    s = get_settings()
    if not s.gemini_api_key:
        return None
    try:
        model = get_model()
        resp = await asyncio.wait_for(
            model.generate_content_async(prompt), timeout=s.gemini_timeout_s
        )
        return (resp.text or "").strip() or None
    except asyncio.TimeoutError:
        log.warning("Gemini call timed out after %ss", s.gemini_timeout_s)
        return None
    except Exception as exc:  # missing key, quota, network, SDK change
        log.warning("Gemini call failed: %s", exc)
        return None


async def warm_up() -> None:
    """Pays the one-time SDK/gRPC-channel setup cost at server startup
    instead of on whichever request happens to arrive first. A missing/
    invalid key or a flaky network just means this is skipped — not fatal,
    the first real call simply pays the cost this was meant to avoid."""
    if not get_settings().gemini_api_key:
        return
    if await generate("Reply with one word: ready") is None:
        log.warning("Gemini warm-up did not get a response (assistant/sustainability will still work, just slower on the first call)")
