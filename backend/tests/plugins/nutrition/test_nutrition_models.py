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
