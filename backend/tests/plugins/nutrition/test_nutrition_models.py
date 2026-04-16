from sqlalchemy import select

from app.plugins.nutrition.models import Food, UserProfile


async def test_user_profile_defaults(session_and_user):
    session, user = session_and_user
    profile = UserProfile(user_id=user.id)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    assert profile.id
    assert profile.calorie_target == 2000
    assert profile.protein_g == 150
    assert profile.carbs_g == 200
    assert profile.fat_g == 65
    assert profile.fiber_g == 25
    assert profile.tone_mode == "coach"
    assert profile.goals == "fat-loss"


async def test_food_row_minimal(session_and_user):
    session, _ = session_and_user
    food = Food(
        name="egg, whole, raw",
        calories_per_100g=143.0,
        protein_per_100g=12.6,
        carbs_per_100g=0.7,
        fiber_per_100g=0.0,
        fat_per_100g=9.5,
    )
    session.add(food)
    await session.commit()

    row = (await session.execute(select(Food))).scalar_one()
    assert row.name == "egg, whole, raw"
    assert row.source == "usda"
    assert row.aliases is None
    assert row.usda_fdc_id is None


from app.plugins.nutrition.models import DaySummary, Meal, MealItem


async def test_meal_with_items_cascade_delete(session_and_user):
    session, user = session_and_user
    meal = Meal(
        user_id=user.id,
        raw_input="2 eggs",
        day_date="2026-04-16",
    )
    meal.items.append(MealItem(
        food_name="egg",
        quantity=2.0,
        unit="piece",
        calories=140.0,
        protein_g=12.0,
        carbs_g=1.0,
        net_carbs_g=1.0,
        fat_g=10.0,
        fiber_g=0.0,
    ))
    session.add(meal)
    await session.commit()
    await session.refresh(meal)

    assert meal.id
    assert meal.is_closed is False
    assert len(meal.items) == 1
    assert meal.items[0].food_source == "usda"

    meal_id = meal.id
    await session.delete(meal)
    await session.commit()

    from sqlalchemy import select
    rows = (await session.execute(
        select(MealItem).where(MealItem.meal_id == meal_id)
    )).scalars().all()
    assert rows == []  # cascade delete removed items


async def test_day_summary_unique_per_user_day(session_and_user):
    session, user = session_and_user
    s1 = DaySummary(user_id=user.id, day_date="2026-04-16")
    session.add(s1)
    await session.commit()

    dup = DaySummary(user_id=user.id, day_date="2026-04-16")
    session.add(dup)
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
