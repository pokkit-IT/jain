"""SQLAlchemy models for the nutrition plugin.

All tables are prefixed with `nutrition_` per the internal-plugin naming
convention so plugin tables can't collide with JAIN core tables.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


def _uuid() -> str:
    return str(uuid4())


class UserProfile(Base):
    """Per-user macro targets, tone, and goals. One row per user."""

    __tablename__ = "nutrition_user_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_nutrition_user_profiles_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )
    calorie_target: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2000, server_default="2000",
    )
    protein_g: Mapped[int] = mapped_column(
        Integer, nullable=False, default=150, server_default="150",
    )
    carbs_g: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200, server_default="200",
    )
    fat_g: Mapped[int] = mapped_column(
        Integer, nullable=False, default=65, server_default="65",
    )
    fiber_g: Mapped[int] = mapped_column(
        Integer, nullable=False, default=25, server_default="25",
    )
    tone_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="coach", server_default="coach",
    )
    goals: Mapped[str] = mapped_column(
        String(50), nullable=False, default="fat-loss", server_default="fat-loss",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship()


class Food(Base):
    """Macro information for a single food item at 100 g basis.

    Populated from the USDA FoodData Central API on first lookup and cached
    here. `usda_fdc_id` is the upstream identifier so rows can be refreshed
    later. Local / estimated rows set source='estimate' and leave fdc_id null.
    """

    __tablename__ = "nutrition_foods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="usda", server_default="usda",
    )
    usda_fdc_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class Meal(Base):
    """A logged meal. Items hold the per-food macros; totals are derived.

    `raw_input` preserves the user's exact text for later audit or re-parse.
    `day_date` is the YYYY-MM-DD of `logged_at` in the server's local time,
    stamped at insert so the value is stable even if the server TZ changes.
    `is_closed` flips True after day-close (reserved for Phase 2).
    """

    __tablename__ = "nutrition_meals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    day_date: Mapped[str] = mapped_column(String(10), nullable=False)
    is_closed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MealItem(Base):
    """One resolved food line inside a Meal. Macros are in absolute amounts
    (already scaled for quantity + unit — NOT per-100g).
    """

    __tablename__ = "nutrition_meal_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    meal_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("nutrition_meals.id", ondelete="CASCADE"),
        nullable=False,
    )
    food_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    net_carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float] = mapped_column(Float, nullable=False)
    food_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="usda", server_default="usda",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    meal: Mapped[Meal] = relationship(back_populates="items")


class DaySummary(Base):
    """Pre-computed per-day macro totals, incremented on each log.

    Unique on (user_id, day_date). `is_closed` gets flipped after day-close
    (Phase 2) and is advisory only — queries always filter by day_date.
    """

    __tablename__ = "nutrition_day_summaries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "day_date", name="uq_nutrition_day_summaries_user_day",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
    )
    day_date: Mapped[str] = mapped_column(String(10), nullable=False)
    total_calories: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    total_protein_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    total_carbs_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    total_net_carbs_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    total_fat_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    total_fiber_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    meal_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    is_closed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
