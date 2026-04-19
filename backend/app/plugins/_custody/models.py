from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


def _new_id() -> str:
    return str(uuid4())


class Child(Base):
    __tablename__ = "custody_children"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    dob: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    owner: Mapped[User] = relationship()
    events: Mapped[list["CustodyEvent"]] = relationship(
        "CustodyEvent", back_populates="child",
        cascade="all, delete-orphan", lazy="selectin",
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="child",
        cascade="all, delete-orphan", lazy="selectin",
    )


class Schedule(Base):
    """Recurring custody schedule for a child (e.g. EOW Fri-Sun)."""

    __tablename__ = "custody_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    child_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_children.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1",
    )
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    interval_weeks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1",
    )
    weekdays: Mapped[str] = mapped_column(String(32), nullable=False)  # "4,5,6"
    pickup_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    dropoff_time: Mapped[str] = mapped_column(String(5), nullable=False)
    pickup_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    child: Mapped[Child] = relationship(back_populates="schedules")
    exceptions: Mapped[list["ScheduleException"]] = relationship(
        "ScheduleException", back_populates="schedule",
        cascade="all, delete-orphan", lazy="selectin",
    )


class CustodyEvent(Base):
    """Polymorphic event row. `type` drives which optional columns are meaningful.

    typed columns (nullable, set only when relevant):
      overnight       → pickup
      amount_cents    → expense
      category        → expense
      call_connected  → phone_call
      missed_source   → missed_visit ("auto" or "manual")
      schedule_id     → missed_visit
    """

    __tablename__ = "custody_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True,
    )
    child_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_children.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    overnight: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0",
    )
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    call_connected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    missed_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    schedule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("custody_schedules.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    child: Mapped[Child] = relationship(back_populates="events")
    photos: Mapped[list["EventPhoto"]] = relationship(
        "EventPhoto", back_populates="event",
        cascade="all, delete-orphan", order_by="EventPhoto.position",
        lazy="selectin",
    )


class EventPhoto(Base):
    """Receipt / text-screenshot / misc photo attached to a CustodyEvent."""

    __tablename__ = "custody_event_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_events.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumb_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
    )

    event: Mapped[CustodyEvent] = relationship(back_populates="photos")


class ScheduleException(Base):
    """One-off override or skip for a specific scheduled date."""

    __tablename__ = "custody_schedule_exceptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    schedule_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("custody_schedules.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # skip | override
    override_pickup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    override_dropoff_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    schedule: Mapped[Schedule] = relationship(back_populates="exceptions")
