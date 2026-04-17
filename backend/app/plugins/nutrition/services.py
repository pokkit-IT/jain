"""Business logic for the nutrition plugin.

Pure async functions that take an AsyncSession and return domain
objects or dicts. No auth checks (tool handlers do that). No HTTP calls
live here — USDA lookup is in `usda.py` so tests can monkeypatch it.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import FoodMacros, ItemMacros, ParsedItem

_SPLIT_PATTERN = re.compile(r"\s*(?:,|\band\b|\bwith\b|\bplus\b|\+)\s*", re.IGNORECASE)
_LABEL_PATTERN = re.compile(
    r"^\s*(?:breakfast|lunch|dinner|snack|meal)\s*[:\-]\s*", re.IGNORECASE,
)
_QTY_UNIT_PATTERN = re.compile(
    r"^(?P<qty>\d+(?:\.\d+)?|\d+/\d+)"
    r"\s*(?P<unit>g|grams?|oz|ounces?|cup|cups|tbsp|tablespoons?|"
    r"tsp|teaspoons?|lb|lbs|pounds?|ml|pieces?)?"
    r"\s+(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
_ARTICLE_PATTERN = re.compile(r"^\s*(?:a|an)\s+(?P<name>.+?)\s*$", re.IGNORECASE)


def _singularize(noun: str) -> str:
    noun = noun.strip()
    if noun.lower().endswith("ies") and len(noun) > 3:
        return noun[:-3] + "y"
    if noun.lower().endswith("es") and len(noun) > 2:
        return noun[:-2] if not noun.lower().endswith("ses") else noun[:-1]
    if noun.lower().endswith("s") and len(noun) > 1 and not noun.lower().endswith("ss"):
        return noun[:-1]
    return noun


def _normalize_unit(raw_unit: str | None) -> str:
    if not raw_unit:
        return "piece"
    u = raw_unit.lower().strip()
    if u in ("g", "gram", "grams"):
        return "g"
    if u in ("oz", "ounce", "ounces"):
        return "oz"
    if u in ("cup", "cups"):
        return "cup"
    if u in ("tbsp", "tablespoon", "tablespoons"):
        return "tbsp"
    if u in ("tsp", "teaspoon", "teaspoons"):
        return "tsp"
    if u in ("lb", "lbs", "pound", "pounds"):
        return "lb"
    if u == "ml":
        return "ml"
    if u in ("piece", "pieces"):
        return "piece"
    return u


def _parse_quantity(raw: str) -> float:
    if "/" in raw:
        num, denom = raw.split("/", 1)
        return float(num) / float(denom)
    return float(raw)


def _parse_phrase(phrase: str) -> ParsedItem | None:
    phrase = phrase.strip()
    if not phrase:
        return None

    m = _QTY_UNIT_PATTERN.match(phrase)
    if m:
        qty = _parse_quantity(m.group("qty"))
        raw_unit = m.group("unit")
        unit = _normalize_unit(raw_unit)
        name = m.group("name").strip().lower()
        if raw_unit is None:
            name = _singularize(name)
        return ParsedItem(name=name, quantity=qty, unit=unit)

    m = _ARTICLE_PATTERN.match(phrase)
    if m:
        name = _singularize(m.group("name").strip().lower())
        return ParsedItem(name=name, quantity=1.0, unit="piece")

    return ParsedItem(
        name=_singularize(phrase.lower()),
        quantity=1.0,
        unit="piece",
    )


def parse_meal_text(raw_input: str) -> list[ParsedItem]:
    """Split a meal description into ParsedItem instances.

    Deterministic regex + rules — never calls an LLM. Phase 1 scope; upgrade
    to LLM parsing later if accuracy becomes a bottleneck.
    """
    if not raw_input or not raw_input.strip():
        return []
    text = _LABEL_PATTERN.sub("", raw_input.strip())
    chunks = _SPLIT_PATTERN.split(text)
    out: list[ParsedItem] = []
    for chunk in chunks:
        item = _parse_phrase(chunk)
        if item is not None:
            out.append(item)
    return out


_UNIT_TO_GRAMS: dict[str, float] = {
    "g": 1.0,
    "oz": 28.35,
    "lb": 453.59,
    "cup": 240.0,
    "tbsp": 15.0,
    "tsp": 5.0,
    "ml": 1.0,
}
_FALLBACK_GRAMS_PER_UNIT = 100.0


def _grams_per_unit(unit: str, food: FoodMacros) -> float:
    if unit in _UNIT_TO_GRAMS:
        return _UNIT_TO_GRAMS[unit]
    if unit in ("piece", "unit"):
        return food.serving_size_g or _FALLBACK_GRAMS_PER_UNIT
    return _FALLBACK_GRAMS_PER_UNIT


def calculate_macros(food: FoodMacros, quantity: float, unit: str) -> ItemMacros:
    """Scale a per-100g FoodMacros to `quantity` of `unit`.

    Net carbs = carbs - fiber, floored at 0.
    """
    grams = quantity * _grams_per_unit(unit, food)
    factor = grams / 100.0

    calories = food.calories_per_100g * factor
    protein_g = food.protein_per_100g * factor
    carbs_g = food.carbs_per_100g * factor
    fiber_g = food.fiber_per_100g * factor
    fat_g = food.fat_per_100g * factor
    net_carbs_g = max(0.0, carbs_g - fiber_g)

    return ItemMacros(
        name=food.name,
        quantity=quantity,
        unit=unit,
        calories=round(calories, 4),
        protein_g=round(protein_g, 4),
        carbs_g=round(carbs_g, 4),
        net_carbs_g=round(net_carbs_g, 4),
        fat_g=round(fat_g, 4),
        fiber_g=round(fiber_g, 4),
        food_source=food.source,
    )
