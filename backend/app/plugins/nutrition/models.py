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
