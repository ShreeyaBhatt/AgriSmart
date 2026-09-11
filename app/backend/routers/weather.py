"""Module C — Weather Intelligence endpoint."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, status

from ..models.modules import WeatherAdvice, WeatherAdviceRequest
from ..services.weather import build_advice, fetch_forecast

router = APIRouter(prefix="/weather", tags=["weather"])


@router.post("/advice", response_model=WeatherAdvice)
async def weather_advice(req: WeatherAdviceRequest) -> WeatherAdvice:
    try:
        forecast = await fetch_forecast(req.lat, req.lon)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Weather service unavailable: {exc}")
    return build_advice(
        req.lat, req.lon, forecast,
        last_disease=req.last_disease, crop=req.crop, stage=req.stage,
    )
