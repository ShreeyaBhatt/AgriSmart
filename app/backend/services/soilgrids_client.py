"""Thin async client for the SoilGrids 2.0 REST API (ISRIC).

Two endpoints:
  * ``/properties/query``     -> particle size, pH, SOC, N, CEC, bulk density, coarse fragments
  * ``/classification/query`` -> WRB Reference Soil Group + probabilities

No API key. Unauthenticated use is rate-limited (~5 req/min) so calls are
serialised through a process-wide async throttle and retried on 429 / 5xx with
exponential backoff. Docs: https://www.isric.org/explore/soilgrids/faq-soilgrids
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

# The nine properties the pipeline consumes, and the three shallow depth layers
# that make up the 0-30 cm plough zone.
PROPERTIES = ("phh2o", "soc", "nitrogen", "sand", "silt", "clay", "cec", "bdod", "cfvo")
DEPTHS = ("0-5cm", "5-15cm", "15-30cm")


class SoilGridsError(RuntimeError):
    """Raised when SoilGrids cannot be reached or returns an unusable payload."""


def properties_have_values(payload: dict[str, Any]) -> bool:
    """True if at least one property/depth carries a non-null mean.

    The SoilGrids mosaic service intermittently answers 200 with every ``mean``
    set to ``null`` (tile failed to load server-side, or the point is masked).
    Such a payload is unusable and should be retried / fall back.
    """
    for layer in (payload.get("properties") or {}).get("layers") or []:
        for depth in layer.get("depths") or []:
            if (depth.get("values") or {}).get("mean") is not None:
                return True
    return False


class _Throttle:
    """Serialises callers and enforces a minimum gap between outbound requests."""

    def __init__(self, min_interval_s: float) -> None:
        self._min_interval_s = min_interval_s
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def __aenter__(self) -> None:
        await self._lock.acquire()
        wait = self._min_interval_s - (time.monotonic() - self._last)
        if wait > 0:
            await asyncio.sleep(wait)

    async def __aexit__(self, *exc: object) -> None:
        self._last = time.monotonic()
        self._lock.release()


_throttle: _Throttle | None = None


def _get_throttle() -> _Throttle:
    global _throttle
    if _throttle is None:
        _throttle = _Throttle(get_settings().soilgrids_min_interval_s)
    return _throttle


async def _get(client: httpx.AsyncClient, url: str, params: Any) -> dict[str, Any]:
    settings = get_settings()
    last_exc: Exception | None = None
    for attempt in range(1, settings.soilgrids_max_retries + 1):
        try:
            async with _get_throttle():
                resp = await client.get(url, params=params)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:  # ValueError = bad JSON
            last_exc = exc
            backoff = min(2 ** attempt, 8)
            log.warning("SoilGrids %s failed (attempt %d/%d): %s; retrying in %ss",
                        url, attempt, settings.soilgrids_max_retries, exc, backoff)
            if attempt < settings.soilgrids_max_retries:
                await asyncio.sleep(backoff)
    raise SoilGridsError(f"SoilGrids request failed after retries: {last_exc}") from last_exc


_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=settings.soilgrids_timeout_s,
            headers={"User-Agent": settings.http_user_agent, "Accept": "application/json"},
        )
    return _client

async def fetch_properties(lat: float, lon: float) -> dict[str, Any]:
    """Return the raw ``/properties/query`` GeoJSON Feature for a point.

    Retries when the service answers with an all-null payload; raises
    :class:`SoilGridsError` if every attempt is unusable.
    """
    settings = get_settings()
    params = [("lon", lon), ("lat", lat), ("value", "mean"), ("value", "uncertainty")]
    params += [("property", p) for p in PROPERTIES]
    params += [("depth", d) for d in DEPTHS]
    url = f"{settings.soilgrids_base_url}/properties/query"
    client = _get_client()
    for attempt in range(1, settings.soilgrids_max_retries + 1):
        payload = await _get(client, url, params)
        if properties_have_values(payload):
            return payload
        log.warning("SoilGrids returned an all-null payload for (%s, %s) "
                    "(attempt %d/%d)", lat, lon, attempt, settings.soilgrids_max_retries)
        if attempt < settings.soilgrids_max_retries:
            await asyncio.sleep(1.5 * attempt)
    raise SoilGridsError(f"SoilGrids has no usable data for ({lat}, {lon}) after retries")


async def fetch_classification(lat: float, lon: float, number_classes: int = 3) -> dict[str, Any]:
    """Return the raw ``/classification/query`` payload (WRB soil group) for a point."""
    settings = get_settings()
    params = {"lon": lon, "lat": lat, "number_classes": number_classes}
    client = _get_client()
    return await _get(client, f"{settings.soilgrids_base_url}/classification/query", params)
