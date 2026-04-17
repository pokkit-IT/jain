"""LLM tool definitions for the nutrition internal plugin.

Every handler returns the standard response envelope:
    {"status": ..., "data": ..., "message": ..., "next_action": "none"}
"""

from app.plugins.core.schema import ToolDef, ToolInputSchema

from .schemas import envelope
from .services import (
    get_profile,
    log_meal_for_user,
    summary_for_period,
    upsert_profile,
)


def _item_to_dict(mi) -> dict:
    return {
        "id": mi.id,
        "name": mi.food_name,
        "quantity": mi.quantity,
        "unit": mi.unit,
        "calories": mi.calories,
        "protein_g": mi.protein_g,
        "carbs_g": mi.carbs_g,
        "net_carbs_g": mi.net_carbs_g,
        "fat_g": mi.fat_g,
        "fiber_g": mi.fiber_g,
        "food_source": mi.food_source,
    }


def _meal_totals(items: list[dict]) -> dict:
    keys = ("calories", "protein_g", "carbs_g", "fat_g", "fiber_g")
    return {k: round(sum(i[k] for i in items), 2) for k in keys}


async def log_meal_handler(args, user=None, db=None):
    """Parse, resolve, persist a meal. Returns meal + day totals + targets."""
    if user is None:
        return envelope(status="error", message="Authentication required.")

    raw_input = args.get("raw_input") or ""
    meal, day = await log_meal_for_user(db, user, raw_input)
    profile = await get_profile(db, user)

    items = [_item_to_dict(i) for i in meal.items]
    meal_totals = _meal_totals(items)
    day_totals = {
        "calories": round(day.total_calories, 2),
        "protein_g": round(day.total_protein_g, 2),
        "carbs_g": round(day.total_carbs_g, 2),
        "fat_g": round(day.total_fat_g, 2),
        "fiber_g": round(day.total_fiber_g, 2),
    }
    day_targets = {
        "calories": profile.calorie_target,
        "protein_g": profile.protein_g,
        "carbs_g": profile.carbs_g,
        "fat_g": profile.fat_g,
    }
    remaining_cals = max(0, profile.calorie_target - int(day.total_calories))
    message = (
        f"Logged {len(items)} item{'s' if len(items) != 1 else ''}. "
        f"{remaining_cals} calories remaining today."
    )
    return envelope(
        status="ok",
        data={
            "meal_id": meal.id,
            "items": items,
            "meal_totals": meal_totals,
            "day_totals": day_totals,
            "day_targets": day_targets,
        },
        message=message,
    )


TOOLS: list[ToolDef] = [
    ToolDef(
        name="log_meal",
        description=(
            "Log a meal conversationally. Use when the user describes "
            "eating something or lists food they consumed. Pass raw_input "
            "exactly as the user said it — the backend parses it."
        ),
        input_schema=ToolInputSchema(
            properties={
                "raw_input": {
                    "type": "string",
                    "description": "The user's exact meal description.",
                },
                "meal_time": {
                    "type": "string",
                    "description": "Optional ISO datetime; defaults to now.",
                },
            },
            required=["raw_input"],
        ),
        auth_required=True,
        handler=log_meal_handler,
    ),
]
