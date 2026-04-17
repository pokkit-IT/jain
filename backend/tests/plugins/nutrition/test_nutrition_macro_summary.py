from datetime import date

from app.plugins.nutrition import services as nutrition_services
from app.plugins.nutrition.models import DaySummary
from app.plugins.nutrition.schemas import FoodMacros
from app.plugins.nutrition.services import log_meal_for_user
from app.plugins.nutrition.tools import TOOLS, get_macro_summary_handler


def test_get_macro_summary_tool_is_auth_required():
    t = next(t for t in TOOLS if t.name == "get_macro_summary")
    assert t.auth_required is True
    assert t.handler is get_macro_summary_handler


async def test_summary_rejects_missing_user(session_and_user):
    session, _ = session_and_user
    result = await get_macro_summary_handler({}, user=None, db=session)
    assert result["status"] == "error"
    assert "auth" in result["message"].lower()


async def test_summary_today_empty(session_and_user):
    session, user = session_and_user
    result = await get_macro_summary_handler({}, user=user, db=session)
    assert result["status"] == "ok"
    data = result["data"]
    assert data["period"] == "today"
    assert data["date"] == date.today().isoformat()
    assert data["totals"]["calories"] == 0
    assert data["targets"]["calories"] == 2000
    assert data["remaining"]["calories"] == 2000


async def test_summary_today_after_logging(session_and_user, monkeypatch):
    session, user = session_and_user
    async def _fake(name, _db):
        return FoodMacros(
            name=name, calories_per_100g=200, protein_per_100g=20,
            carbs_per_100g=10, fiber_per_100g=2, fat_per_100g=5,
        )
    monkeypatch.setattr(nutrition_services, "resolve_food", _fake)
    await log_meal_for_user(session, user, "100g x")

    result = await get_macro_summary_handler({"period": "today"}, user=user, db=session)
    assert result["data"]["totals"]["calories"] == 200.0
    assert result["data"]["pct_complete"]["calories"] == 10


async def test_summary_yesterday_explicit_date(session_and_user):
    session, user = session_and_user
    session.add(DaySummary(
        user_id=user.id, day_date="2026-04-10",
        total_calories=1500, total_protein_g=120, meal_count=3,
    ))
    await session.commit()
    result = await get_macro_summary_handler(
        {"date": "2026-04-10"}, user=user, db=session,
    )
    assert result["data"]["date"] == "2026-04-10"
    assert result["data"]["totals"]["calories"] == 1500
