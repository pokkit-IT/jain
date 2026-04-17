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


from sqlalchemy import func as _sqlfunc, or_, select

from .models import Food
from .usda import fetch_usda_food


async def _find_cached_food(name: str, db: AsyncSession) -> Food | None:
    """Case-insensitive lookup against nutrition_foods by name or alias."""
    needle = name.strip().lower()
    stmt = select(Food).where(
        or_(
            _sqlfunc.lower(Food.name) == needle,
            _sqlfunc.lower(Food.aliases).like(f"%{needle}%"),
        )
    ).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _food_to_macros(f: Food) -> FoodMacros:
    return FoodMacros(
        name=f.name,
        calories_per_100g=f.calories_per_100g,
        protein_per_100g=f.protein_per_100g,
        carbs_per_100g=f.carbs_per_100g,
        fiber_per_100g=f.fiber_per_100g,
        fat_per_100g=f.fat_per_100g,
        source=f.source,
        usda_fdc_id=f.usda_fdc_id,
        serving_size_g=None,
    )


async def _cache_usda_food(fm: FoodMacros, db: AsyncSession) -> None:
    """Persist a USDA-sourced FoodMacros into nutrition_foods."""
    db.add(Food(
        name=fm.name,
        calories_per_100g=fm.calories_per_100g,
        protein_per_100g=fm.protein_per_100g,
        carbs_per_100g=fm.carbs_per_100g,
        fiber_per_100g=fm.fiber_per_100g,
        fat_per_100g=fm.fat_per_100g,
        source=fm.source,
        usda_fdc_id=fm.usda_fdc_id,
    ))
    await db.commit()


async def resolve_food(name: str, db: AsyncSession) -> FoodMacros:
    """Return macros for `name`, preferring cache → USDA → zero estimate.

    Never returns None. Unknown foods yield source='estimate' with zeroed
    macros so meal logging never hard-fails — the user can correct later.
    """
    cached = await _find_cached_food(name, db)
    if cached is not None:
        return _food_to_macros(cached)

    hit = await fetch_usda_food(name)
    if hit is not None:
        await _cache_usda_food(hit, db)
        return hit

    return FoodMacros(
        name=name,
        calories_per_100g=0.0,
        protein_per_100g=0.0,
        carbs_per_100g=0.0,
        fiber_per_100g=0.0,
        fat_per_100g=0.0,
        source="estimate",
    )


from datetime import date as _date, datetime as _datetime, timezone as _timezone

from app.models.user import User

from .models import DaySummary, Meal, MealItem


async def _get_or_create_day_summary(
    db: AsyncSession, user_id, day_date: str,
) -> DaySummary:
    stmt = select(DaySummary).where(
        DaySummary.user_id == user_id,
        DaySummary.day_date == day_date,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row
    row = DaySummary(user_id=user_id, day_date=day_date)
    db.add(row)
    await db.flush()
    return row


def _sum_item_totals(items: list[ItemMacros]) -> dict[str, float]:
    return {
        "calories": sum(i.calories for i in items),
        "protein_g": sum(i.protein_g for i in items),
        "carbs_g": sum(i.carbs_g for i in items),
        "net_carbs_g": sum(i.net_carbs_g for i in items),
        "fat_g": sum(i.fat_g for i in items),
        "fiber_g": sum(i.fiber_g for i in items),
    }


async def log_meal_for_user(
    db: AsyncSession, user: User, raw_input: str,
    logged_at: _datetime | None = None,
) -> tuple[Meal, DaySummary]:
    """Parse, resolve, scale, persist — returns (meal, day_summary).

    Increments (not recomputes) the user's DaySummary row for today.
    Commits on success; caller does NOT need to commit again.
    """
    parsed = parse_meal_text(raw_input)
    resolved: list[ItemMacros] = []
    for p in parsed:
        food = await resolve_food(p.name, db)
        resolved.append(calculate_macros(food, p.quantity, p.unit))

    now = logged_at or _datetime.now(_timezone.utc)
    day = now.date().isoformat() if isinstance(now, _datetime) else _date.today().isoformat()

    meal = Meal(
        user_id=user.id,
        raw_input=raw_input,
        day_date=day,
    )
    for m in resolved:
        meal.items.append(MealItem(
            food_name=m.name,
            quantity=m.quantity,
            unit=m.unit,
            calories=m.calories,
            protein_g=m.protein_g,
            carbs_g=m.carbs_g,
            net_carbs_g=m.net_carbs_g,
            fat_g=m.fat_g,
            fiber_g=m.fiber_g,
            food_source=m.food_source,
        ))
    db.add(meal)
    await db.flush()

    summary = await _get_or_create_day_summary(db, user.id, day)
    totals = _sum_item_totals(resolved)
    summary.total_calories += totals["calories"]
    summary.total_protein_g += totals["protein_g"]
    summary.total_carbs_g += totals["carbs_g"]
    summary.total_net_carbs_g += totals["net_carbs_g"]
    summary.total_fat_g += totals["fat_g"]
    summary.total_fiber_g += totals["fiber_g"]
    summary.meal_count += 1

    await db.commit()
    await db.refresh(meal)
    await db.refresh(summary)
    return meal, summary


from .models import UserProfile

_PROFILE_FIELDS = {
    "calorie_target", "protein_g", "carbs_g", "fat_g",
    "fiber_g", "tone_mode", "goals",
}


async def get_profile(db: AsyncSession, user: User) -> UserProfile:
    """Return the user's profile, creating a defaults row on first call."""
    stmt = select(UserProfile).where(UserProfile.user_id == user.id)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    profile = UserProfile(user_id=user.id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def upsert_profile(
    db: AsyncSession, user: User, updates: dict,
) -> UserProfile:
    """Set any of _PROFILE_FIELDS supplied in `updates`. Ignores unknowns."""
    profile = await get_profile(db, user)
    for key, value in updates.items():
        if key in _PROFILE_FIELDS and value is not None:
            setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile
