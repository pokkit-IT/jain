from sqlalchemy import select

from app.plugins.nutrition import services as nutrition_services
from app.plugins.nutrition.models import Meal, MealItem
from app.plugins.nutrition.schemas import FoodMacros
from app.plugins.nutrition.tools import TOOLS, log_meal_handler


def test_tools_list_exposes_log_meal():
    names = {t.name for t in TOOLS}
    assert "log_meal" in names


def test_log_meal_tool_is_auth_required():
    t = next(t for t in TOOLS if t.name == "log_meal")
    assert t.auth_required is True
    assert t.handler is log_meal_handler


async def test_log_meal_handler_rejects_missing_user(session_and_user):
    session, _ = session_and_user
    result = await log_meal_handler({"raw_input": "eggs"}, user=None, db=session)
    assert result["status"] == "error"
    assert result["data"] == {}
    assert "auth" in result["message"].lower()
    assert result["next_action"] == "none"


async def test_log_meal_handler_persists_meal_and_returns_envelope(
    session_and_user, monkeypatch,
):
    session, user = session_and_user

    async def _fake_resolve(name, _db):
        return FoodMacros(
            name=name, calories_per_100g=200, protein_per_100g=20,
            carbs_per_100g=10, fiber_per_100g=2, fat_per_100g=5,
        )
    monkeypatch.setattr(nutrition_services, "resolve_food", _fake_resolve)

    result = await log_meal_handler(
        {"raw_input": "100g chicken"}, user=user, db=session,
    )
    assert result["status"] == "ok"
    assert result["next_action"] == "none"
    data = result["data"]
    assert "meal_id" in data
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["name"] == "chicken"
    assert item["calories"] == 200.0

    assert data["meal_totals"]["calories"] == 200.0
    assert data["day_totals"]["calories"] == 200.0
    assert data["day_targets"]["calories"] == 2000

    meals = (await session.execute(select(Meal))).scalars().all()
    assert len(meals) == 1
    items = (await session.execute(select(MealItem))).scalars().all()
    assert len(items) == 1


async def test_log_meal_handler_handles_unknown_food_as_estimate(
    session_and_user, monkeypatch,
):
    session, user = session_and_user

    async def _no_usda(_name):
        return None
    monkeypatch.setattr("app.plugins.nutrition.services.fetch_usda_food", _no_usda)

    result = await log_meal_handler(
        {"raw_input": "mysteryfood"}, user=user, db=session,
    )
    assert result["status"] == "ok"
    item = result["data"]["items"][0]
    assert item["calories"] == 0.0
    assert item["food_source"] == "estimate"
