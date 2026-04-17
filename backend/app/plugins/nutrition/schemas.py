"""Shared types for the nutrition plugin.

Dataclasses used by services.py, usda.py, tools.py. Pydantic request
bodies live alongside because they stay tiny; add more if routes.py grows.
"""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class ParsedItem:
    """One food phrase extracted from a meal description."""
    name: str
    quantity: float
    unit: str


@dataclass
class FoodMacros:
    """Macro info at a 100 g basis, ready to scale via calculate_macros."""
    name: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fiber_per_100g: float
    fat_per_100g: float
    source: str = "usda"
    usda_fdc_id: str | None = None
    serving_size_g: float | None = None


@dataclass
class ItemMacros:
    """Macros for a specific quantity of food, already scaled."""
    name: str
    quantity: float
    unit: str
    calories: float
    protein_g: float
    carbs_g: float
    net_carbs_g: float
    fat_g: float
    fiber_g: float
    food_source: str = "usda"


EnvelopeStatus = Literal["ok", "error", "partial"]


def envelope(
    status: EnvelopeStatus = "ok",
    data: dict[str, Any] | None = None,
    message: str = "",
    next_action: str = "none",
) -> dict[str, Any]:
    """Build the standard tool-handler response envelope."""
    return {
        "status": status,
        "data": data if data is not None else {},
        "message": message,
        "next_action": next_action,
    }
