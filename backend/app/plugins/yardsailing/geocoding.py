"""Nominatim (OpenStreetMap) geocoding helper.

Free, no API key. Nominatim's usage policy requires a descriptive User-Agent
and asks for no more than 1 req/sec. For a personal yard-sale app that
geocodes once on create, that's fine. If this app ever grows, swap to a
paid provider (Google, Mapbox) by changing only this file.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "jain-yardsailing/0.1 (https://github.com/pokkit-IT/jain)"
_TIMEOUT = 5.0


async def geocode(address: str) -> tuple[float, float] | None:
    """Return (lat, lng) for `address`, or None if not found / on error.

    Never raises — geocoding failure must not block sale creation.
    """
    if not address or not address.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            results = resp.json()
            if not results:
                logger.info("geocode: no match for %r", address)
                return None
            return float(results[0]["lat"]), float(results[0]["lon"])
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        logger.warning("geocode failed for %r: %s", address, exc)
        return None
