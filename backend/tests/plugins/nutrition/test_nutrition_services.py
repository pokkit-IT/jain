from app.plugins.nutrition.schemas import ParsedItem
from app.plugins.nutrition.services import parse_meal_text


def test_parse_quantity_and_plural_noun():
    items = parse_meal_text("2 eggs")
    assert items == [ParsedItem(name="egg", quantity=2.0, unit="piece")]


def test_parse_cup_unit():
    items = parse_meal_text("1 cup oatmeal")
    assert items == [ParsedItem(name="oatmeal", quantity=1.0, unit="cup")]


def test_parse_gram_unit_no_space():
    items = parse_meal_text("100g chicken breast")
    assert items == [ParsedItem(name="chicken breast", quantity=100.0, unit="g")]


def test_parse_gram_unit_with_space():
    items = parse_meal_text("150 g salmon")
    assert items == [ParsedItem(name="salmon", quantity=150.0, unit="g")]


def test_parse_ounce_unit():
    items = parse_meal_text("4 oz steak")
    assert items == [ParsedItem(name="steak", quantity=4.0, unit="oz")]


def test_parse_article_a_or_an():
    items = parse_meal_text("a banana")
    assert items == [ParsedItem(name="banana", quantity=1.0, unit="piece")]
    items2 = parse_meal_text("an apple")
    assert items2 == [ParsedItem(name="apple", quantity=1.0, unit="piece")]


def test_parse_multiple_items_comma_separated():
    items = parse_meal_text("2 eggs, toast, peanut butter")
    names = [i.name for i in items]
    assert names == ["egg", "toast", "peanut butter"]
    assert items[0].quantity == 2.0
    assert items[1].quantity == 1.0
    assert items[2].quantity == 1.0


def test_parse_with_meal_label_prefix():
    items = parse_meal_text("Breakfast: 2 eggs and toast")
    assert [i.name for i in items] == ["egg", "toast"]


def test_parse_and_conjunction():
    items = parse_meal_text("toast with peanut butter")
    assert [i.name for i in items] == ["toast", "peanut butter"]


def test_parse_empty_returns_empty():
    assert parse_meal_text("") == []
    assert parse_meal_text("   ") == []


from app.plugins.nutrition.schemas import FoodMacros
from app.plugins.nutrition.services import calculate_macros


def _food(name="chicken", **overrides):
    defaults = dict(
        name=name,
        calories_per_100g=165.0,
        protein_per_100g=31.0,
        carbs_per_100g=0.0,
        fiber_per_100g=0.0,
        fat_per_100g=3.6,
    )
    defaults.update(overrides)
    return FoodMacros(**defaults)


def test_grams_scale_linearly():
    m = calculate_macros(_food(), quantity=200, unit="g")
    assert m.calories == 330.0
    assert m.protein_g == 62.0
    assert m.fiber_g == 0.0
    assert m.net_carbs_g == 0.0


def test_ounces_convert_to_grams():
    m = calculate_macros(_food(), quantity=4, unit="oz")
    assert round(m.calories, 2) == 187.11
    assert round(m.protein_g, 2) == 35.15


def test_cup_uses_240g():
    m = calculate_macros(
        _food(name="oatmeal", calories_per_100g=68, protein_per_100g=2.4,
              carbs_per_100g=12.0, fiber_per_100g=1.7, fat_per_100g=1.4),
        quantity=1, unit="cup",
    )
    assert round(m.calories, 2) == 163.2


def test_piece_falls_back_to_100g_when_no_serving_size():
    m = calculate_macros(_food(), quantity=2, unit="piece")
    assert m.calories == 330.0


def test_piece_uses_serving_size_g_when_set():
    food = _food(name="egg", calories_per_100g=143, protein_per_100g=12.6,
                 carbs_per_100g=0.7, fiber_per_100g=0.0, fat_per_100g=9.5)
    food.serving_size_g = 50.0
    m = calculate_macros(food, quantity=2, unit="piece")
    assert m.calories == 143.0
    assert round(m.protein_g, 2) == 12.6


def test_net_carbs_subtracts_fiber():
    food = _food(name="broccoli", calories_per_100g=34, protein_per_100g=2.8,
                 carbs_per_100g=7.0, fiber_per_100g=2.6, fat_per_100g=0.4)
    m = calculate_macros(food, quantity=100, unit="g")
    assert m.carbs_g == 7.0
    assert round(m.net_carbs_g, 2) == 4.4
    assert m.fiber_g == 2.6


def test_unknown_unit_falls_back_to_100g():
    m = calculate_macros(_food(), quantity=1, unit="zzz")
    assert m.calories == 165.0


from sqlalchemy import select

from app.plugins.nutrition import services as nutrition_services
from app.plugins.nutrition.models import Food
from app.plugins.nutrition.services import resolve_food


async def test_resolve_food_hits_cache_first(session_and_user, monkeypatch):
    session, _ = session_and_user
    session.add(Food(
        name="oatmeal", calories_per_100g=68, protein_per_100g=2.4,
        carbs_per_100g=12.0, fiber_per_100g=1.7, fat_per_100g=1.4,
    ))
    await session.commit()

    called = {"count": 0}
    async def _should_not_call(_name):
        called["count"] += 1
        return None
    monkeypatch.setattr(nutrition_services, "fetch_usda_food", _should_not_call)

    fm = await resolve_food("oatmeal", session)
    assert fm.name == "oatmeal"
    assert fm.calories_per_100g == 68
    assert called["count"] == 0


async def test_resolve_food_case_insensitive_cache(session_and_user, monkeypatch):
    session, _ = session_and_user
    session.add(Food(
        name="Chicken Breast", calories_per_100g=165, protein_per_100g=31,
        carbs_per_100g=0.0, fiber_per_100g=0.0, fat_per_100g=3.6,
    ))
    await session.commit()

    async def _no_usda(_name):
        return None
    monkeypatch.setattr(nutrition_services, "fetch_usda_food", _no_usda)

    fm = await resolve_food("chicken breast", session)
    assert fm.name == "Chicken Breast"


async def test_resolve_food_alias_match(session_and_user, monkeypatch):
    session, _ = session_and_user
    session.add(Food(
        name="peanut butter", aliases="pb, pnut butter",
        calories_per_100g=588, protein_per_100g=25, carbs_per_100g=20,
        fiber_per_100g=6, fat_per_100g=50,
    ))
    await session.commit()

    async def _no_usda(_name):
        raise AssertionError("should not be called")
    monkeypatch.setattr(nutrition_services, "fetch_usda_food", _no_usda)

    fm = await resolve_food("pb", session)
    assert fm.name == "peanut butter"


async def test_resolve_food_falls_through_to_usda_and_caches(session_and_user, monkeypatch):
    session, _ = session_and_user

    async def _fake_usda(name):
        assert name == "salmon"
        return FoodMacros(
            name="Fish, salmon, Atlantic",
            calories_per_100g=208, protein_per_100g=20,
            carbs_per_100g=0.0, fiber_per_100g=0.0, fat_per_100g=13,
            source="usda", usda_fdc_id="175167",
        )
    monkeypatch.setattr(nutrition_services, "fetch_usda_food", _fake_usda)

    fm = await resolve_food("salmon", session)
    assert fm.name == "Fish, salmon, Atlantic"

    rows = (await session.execute(select(Food))).scalars().all()
    assert any(r.usda_fdc_id == "175167" for r in rows)


async def test_resolve_food_estimate_fallback_when_usda_empty(session_and_user, monkeypatch):
    session, _ = session_and_user
    async def _none(_):
        return None
    monkeypatch.setattr(nutrition_services, "fetch_usda_food", _none)

    fm = await resolve_food("mysteryfood", session)
    assert fm.source == "estimate"
    assert fm.calories_per_100g == 0.0


from datetime import date

from app.plugins.nutrition.models import DaySummary, Meal, MealItem
from app.plugins.nutrition.services import log_meal_for_user


async def test_log_meal_creates_meal_items_and_day_summary(session_and_user, monkeypatch):
    session, user = session_and_user
    async def _fake_resolve(name, _db):
        return FoodMacros(
            name=name, calories_per_100g=100, protein_per_100g=10,
            carbs_per_100g=5, fiber_per_100g=1, fat_per_100g=3,
            source="usda",
        )
    monkeypatch.setattr(nutrition_services, "resolve_food", _fake_resolve)

    meal, day = await log_meal_for_user(session, user, "100g chicken")

    assert meal.user_id == user.id
    assert meal.day_date == date.today().isoformat()
    assert len(meal.items) == 1
    item = meal.items[0]
    assert item.food_name == "chicken"
    assert item.calories == 100.0
    assert item.protein_g == 10.0

    assert day.user_id == user.id
    assert day.day_date == meal.day_date
    assert day.total_calories == 100.0
    assert day.meal_count == 1


async def test_log_meal_increments_existing_day_summary(session_and_user, monkeypatch):
    session, user = session_and_user
    async def _fake_resolve(name, _db):
        return FoodMacros(
            name=name, calories_per_100g=100, protein_per_100g=10,
            carbs_per_100g=5, fiber_per_100g=1, fat_per_100g=3,
        )
    monkeypatch.setattr(nutrition_services, "resolve_food", _fake_resolve)

    _m1, _d1 = await log_meal_for_user(session, user, "100g chicken")
    _m2, d2 = await log_meal_for_user(session, user, "200g chicken")

    assert d2.total_calories == 300.0
    assert d2.meal_count == 2
    assert round(d2.total_protein_g, 2) == 30.0


async def test_log_meal_propagates_brand_context_to_unbranded_items(session_and_user, monkeypatch):
    """Brand from first item (e.g. mcdonald's) is prepended to subsequent unbranded items."""
    session, user = session_and_user
    resolved_names: list[str] = []

    async def _capture_resolve(name, _db):
        resolved_names.append(name)
        return FoodMacros(
            name=name, calories_per_100g=100, protein_per_100g=10,
            carbs_per_100g=5, fiber_per_100g=1, fat_per_100g=3,
            source="usda",
        )
    monkeypatch.setattr(nutrition_services, "resolve_food", _capture_resolve)

    await log_meal_for_user(session, user, "McDonald's biscuit, sausage patty, scrambled eggs")

    assert resolved_names[0] == "mcdonald's biscuit"
    assert resolved_names[1] == "mcdonald's sausage patty"
    assert resolved_names[2] == "mcdonald's scrambled egg"


async def test_log_meal_no_brand_propagation_without_branded_item(session_and_user, monkeypatch):
    """No brand context when no item has a possessive brand name."""
    session, user = session_and_user
    resolved_names: list[str] = []

    async def _capture_resolve(name, _db):
        resolved_names.append(name)
        return FoodMacros(
            name=name, calories_per_100g=100, protein_per_100g=10,
            carbs_per_100g=5, fiber_per_100g=1, fat_per_100g=3,
            source="usda",
        )
    monkeypatch.setattr(nutrition_services, "resolve_food", _capture_resolve)

    await log_meal_for_user(session, user, "sausage patty, scrambled eggs, biscuit")

    assert resolved_names == ["sausage patty", "scrambled egg", "biscuit"]


async def test_log_meal_empty_parse_still_creates_meal(session_and_user, monkeypatch):
    session, user = session_and_user
    async def _no_resolve(*a, **k):
        raise AssertionError("should not be called")
    monkeypatch.setattr(nutrition_services, "resolve_food", _no_resolve)

    meal, day = await log_meal_for_user(session, user, "")
    assert meal.items == []
    assert day.total_calories == 0.0
    assert day.meal_count == 1


from app.plugins.nutrition.models import UserProfile
from app.plugins.nutrition.services import get_profile, upsert_profile


async def test_get_profile_creates_default_on_first_call(session_and_user):
    session, user = session_and_user
    profile = await get_profile(session, user)
    assert profile.user_id == user.id
    assert profile.calorie_target == 2000
    assert profile.protein_g == 150


async def test_get_profile_returns_existing(session_and_user):
    session, user = session_and_user
    session.add(UserProfile(user_id=user.id, calorie_target=1800, protein_g=160))
    await session.commit()

    profile = await get_profile(session, user)
    assert profile.calorie_target == 1800
    assert profile.protein_g == 160


async def test_upsert_profile_updates_only_provided_fields(session_and_user):
    session, user = session_and_user
    p1 = await upsert_profile(session, user, {"protein_g": 180, "tone_mode": "ruthless-mentor"})
    assert p1.protein_g == 180
    assert p1.tone_mode == "ruthless-mentor"
    assert p1.calorie_target == 2000

    p2 = await upsert_profile(session, user, {"calorie_target": 1800})
    assert p2.calorie_target == 1800
    assert p2.protein_g == 180
    assert p2.tone_mode == "ruthless-mentor"


async def test_upsert_profile_rejects_unknown_fields(session_and_user):
    session, user = session_and_user
    p = await upsert_profile(session, user, {"calorie_target": 1500, "bogus": "x"})
    assert p.calorie_target == 1500


from app.plugins.nutrition.services import summary_for_period


async def test_summary_today_empty_day(session_and_user):
    session, user = session_and_user
    result = await summary_for_period(session, user, period="today")
    today = date.today().isoformat()
    assert result["period"] == "today"
    assert result["date"] == today
    assert result["totals"]["calories"] == 0
    assert result["targets"]["calories"] == 2000
    assert result["remaining"]["calories"] == 2000
    assert result["pct_complete"]["calories"] == 0


async def test_summary_today_with_meals(session_and_user, monkeypatch):
    session, user = session_and_user
    async def _fake_resolve(name, _db):
        return FoodMacros(
            name=name, calories_per_100g=200, protein_per_100g=20,
            carbs_per_100g=10, fiber_per_100g=2, fat_per_100g=5,
        )
    monkeypatch.setattr(nutrition_services, "resolve_food", _fake_resolve)
    await log_meal_for_user(session, user, "100g chicken")

    result = await summary_for_period(session, user, period="today")
    assert result["totals"]["calories"] == 200.0
    assert result["totals"]["protein_g"] == 20.0
    assert result["remaining"]["calories"] == 1800.0
    assert result["pct_complete"]["calories"] == 10


async def test_summary_specific_date(session_and_user):
    session, user = session_and_user
    session.add(DaySummary(
        user_id=user.id, day_date="2026-04-10",
        total_calories=1500, total_protein_g=120, meal_count=3,
    ))
    await session.commit()

    result = await summary_for_period(session, user, period=None, date="2026-04-10")
    assert result["date"] == "2026-04-10"
    assert result["totals"]["calories"] == 1500
    assert result["totals"]["protein_g"] == 120


async def test_summary_week_aggregates_multiple_days(session_and_user):
    session, user = session_and_user
    today = date.today()
    from datetime import timedelta
    for i in range(3):
        d = today - timedelta(days=i)
        session.add(DaySummary(
            user_id=user.id, day_date=d.isoformat(),
            total_calories=1000, total_protein_g=80, meal_count=2,
        ))
    await session.commit()

    result = await summary_for_period(session, user, period="week")
    assert result["period"] == "week"
    assert result["totals"]["calories"] == 3000
    assert result["totals"]["protein_g"] == 240
    assert result["targets"]["calories"] == 2000 * 7
