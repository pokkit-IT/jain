"""Admin/debug HTTP endpoints for the nutrition plugin.

End-user flows run through the LLM tool handlers in `tools.py`; these
routes exist so you can poke at state directly during development. All
endpoints require auth and scope results to the current user.
"""

from datetime import date as _date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

from .models import DaySummary, Meal
from .services import get_profile

router = APIRouter(prefix="/api/plugins/nutrition", tags=["nutrition"])


class ProfileResponse(BaseModel):
    user_id: str
    calorie_target: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int
    tone_mode: str
    goals: str


class MealItemResponse(BaseModel):
    id: str
    food_name: str
    quantity: float
    unit: str
    calories: float
    protein_g: float
    carbs_g: float
    net_carbs_g: float
    fat_g: float
    fiber_g: float
    food_source: str


class MealResponse(BaseModel):
    id: str
    day_date: str
    raw_input: str
    is_closed: bool
    items: list[MealItemResponse]


class DaySummaryResponse(BaseModel):
    id: str
    day_date: str
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_net_carbs_g: float
    total_fat_g: float
    total_fiber_g: float
    meal_count: int
    is_closed: bool


@router.get("/profile", response_model=ProfileResponse)
async def read_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    profile = await get_profile(db, user)
    return ProfileResponse(
        user_id=str(profile.user_id),
        calorie_target=profile.calorie_target,
        protein_g=profile.protein_g,
        carbs_g=profile.carbs_g,
        fat_g=profile.fat_g,
        fiber_g=profile.fiber_g,
        tone_mode=profile.tone_mode,
        goals=profile.goals,
    )


@router.get("/meals/today")
async def list_meals_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today_iso = _date.today().isoformat()
    stmt = (
        select(Meal)
        .where(Meal.user_id == user.id, Meal.day_date == today_iso)
        .order_by(Meal.logged_at.desc())
    )
    meals = list((await db.execute(stmt)).scalars().unique().all())
    return {
        "meals": [
            MealResponse(
                id=m.id, day_date=m.day_date, raw_input=m.raw_input,
                is_closed=m.is_closed,
                items=[
                    MealItemResponse(
                        id=i.id, food_name=i.food_name, quantity=i.quantity,
                        unit=i.unit, calories=i.calories, protein_g=i.protein_g,
                        carbs_g=i.carbs_g, net_carbs_g=i.net_carbs_g,
                        fat_g=i.fat_g, fiber_g=i.fiber_g,
                        food_source=i.food_source,
                    )
                    for i in m.items
                ],
            ).model_dump()
            for m in meals
        ],
    }


@router.get("/day-summaries")
async def list_day_summaries(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = (
        select(DaySummary)
        .where(DaySummary.user_id == user.id)
        .order_by(DaySummary.day_date.desc())
        .limit(30)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return {
        "day_summaries": [
            DaySummaryResponse(
                id=r.id, day_date=r.day_date,
                total_calories=r.total_calories,
                total_protein_g=r.total_protein_g,
                total_carbs_g=r.total_carbs_g,
                total_net_carbs_g=r.total_net_carbs_g,
                total_fat_g=r.total_fat_g,
                total_fiber_g=r.total_fiber_g,
                meal_count=r.meal_count,
                is_closed=r.is_closed,
            ).model_dump()
            for r in rows
        ],
    }
