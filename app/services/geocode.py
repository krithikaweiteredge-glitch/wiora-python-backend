"""Geocoding — turn a place name/address into coordinates.

Uses OpenStreetMap Nominatim (free, no API key; be polite: send a User-Agent and
don't hammer it). Returns None on any failure so callers degrade gracefully."""
from __future__ import annotations

import httpx

_UA = "WioraAssistant/1.0 (personal assistant)"


def geocode(place: str) -> tuple[float, float] | None:
    """(latitude, longitude) for a place/address, or None if not found."""
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1},
            headers={"User-Agent": _UA},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:  # noqa: BLE001
        return None
