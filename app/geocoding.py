from __future__ import annotations

import json
from typing import Any

import httpx

from .config import GEOCODING_URL, GEOCODING_USER_AGENT


def reverse_geocode(latitude: float, longitude: float) -> dict[str, str] | None:
    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 14,
        "accept-language": "ru,en",
    }
    try:
        response = httpx.get(
            GEOCODING_URL,
            params=params,
            headers={"User-Agent": GEOCODING_USER_AGENT, "Accept": "application/json"},
            timeout=5,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        return None

    address = payload.get("address") or {}
    locality = next(
        (address.get(key) for key in ("city", "town", "village", "municipality", "county") if address.get(key)),
        None,
    )
    display_name = payload.get("display_name")
    if not display_name:
        return None
    return {"address": str(display_name), "locality": str(locality or "")}
