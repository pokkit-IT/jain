"""USDA FoodData Central HTTP client.

Single async function `fetch_usda_food(name)` returning a `FoodMacros` or
None. Separate module so tests can monkeypatch `_build_client` without
poking at httpx globals.
"""

from __future__ import annotations

import logging

import httpx

from .schemas import FoodMacros

_log = logging.getLogger("jain.plugins.nutrition.usda")

USDA_BASE = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_API_KEY = "DEMO_KEY"
_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


_NUTRIENT_MAP = {
    "Energy": "calories_per_100g",
    "Protein": "protein_per_100g",
    "Carbohydrate, by difference": "carbs_per_100g",
    "Total lipid (fat)": "fat_per_100g",
    "Fiber, total dietary": "fiber_per_100g",
}


def _build_client() -> httpx.AsyncClient:
    """Indirection point so tests can inject a MockTransport."""
    return httpx.AsyncClient(timeout=_TIMEOUT)


async def fetch_usda_food(name: str) -> FoodMacros | None:
    """Query USDA FDC for `name` and return its per-100g macros.

    Returns None on empty result, HTTP error, or network failure — callers
    should fall back to an estimate.
    """
    if not name or not name.strip():
        return None

    params = {
        "query": name.strip(),
        "pageSize": 1,
        "api_key": USDA_API_KEY,
    }

    try:
        async with _build_client() as client:
            resp = await client.get(USDA_BASE, params=params)
    except httpx.HTTPError as e:
        _log.info("USDA fetch failed for %r: %s: %s", name, type(e).__name__, e)
        return None

    if resp.status_code != 200:
        _log.info("USDA non-200 for %r: %s", name, resp.status_code)
        return None

    try:
        payload = resp.json()
    except ValueError:
        return None

    foods = payload.get("foods") or []
    if not foods:
        return None

    hit = foods[0]
    macros = {
        "calories_per_100g": 0.0,
        "protein_per_100g": 0.0,
        "carbs_per_100g": 0.0,
        "fat_per_100g": 0.0,
        "fiber_per_100g": 0.0,
    }
    for nutrient in hit.get("foodNutrients") or []:
        key = _NUTRIENT_MAP.get(nutrient.get("nutrientName"))
        if key is None:
            continue
        val = nutrient.get("value")
        if val is None:
            continue
        try:
            macros[key] = float(val)
        except (TypeError, ValueError):
            continue

    serving_size = hit.get("servingSize")
    try:
        serving_size_g = float(serving_size) if serving_size is not None else None
    except (TypeError, ValueError):
        serving_size_g = None

    return FoodMacros(
        name=hit.get("description") or name,
        calories_per_100g=macros["calories_per_100g"],
        protein_per_100g=macros["protein_per_100g"],
        carbs_per_100g=macros["carbs_per_100g"],
        fiber_per_100g=macros["fiber_per_100g"],
        fat_per_100g=macros["fat_per_100g"],
        source="usda",
        usda_fdc_id=str(hit["fdcId"]) if "fdcId" in hit else None,
        serving_size_g=serving_size_g,
    )
