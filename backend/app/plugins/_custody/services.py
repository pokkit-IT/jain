"""Business logic for the custody plugin. Pure DB functions — callers
(HTTP routes, LLM tool handlers) compose these and own presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from .models import Child, CustodyEvent, EventPhoto, Schedule, ScheduleException


# ---------- Children ----------


async def create_child(
    db: AsyncSession, user: User, *, name: str, dob: str | None = None,
) -> Child:
    child = Child(owner_id=user.id, name=name.strip(), dob=dob)
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return child


async def list_children(db: AsyncSession, user: User) -> list[Child]:
    res = await db.execute(
        select(Child).where(Child.owner_id == user.id).order_by(Child.created_at.asc())
    )
    return list(res.scalars().all())


async def get_child(db: AsyncSession, user: User, child_id: str) -> Child | None:
    res = await db.execute(
        select(Child).where(Child.id == child_id, Child.owner_id == user.id)
    )
    return res.scalar_one_or_none()


async def update_child(
    db: AsyncSession, child: Child, *, name: str | None = None, dob: str | None = None,
) -> Child:
    if name is not None:
        child.name = name.strip()
    child.dob = dob
    await db.commit()
    await db.refresh(child)
    return child


async def delete_child(db: AsyncSession, child: Child) -> None:
    await db.delete(child)
    await db.commit()


async def resolve_child(
    db: AsyncSession, user: User, *, name: str | None,
) -> Child | None:
    """Resolve a child for an LLM tool call.

    When `name` is given, case-insensitive match. When `name` is None,
    default to the user's only child; if they have 0 or 2+, return None.
    """
    if name is not None and name.strip():
        res = await db.execute(
            select(Child).where(
                Child.owner_id == user.id,
                func.lower(Child.name) == name.strip().lower(),
            )
        )
        return res.scalar_one_or_none()

    res = await db.execute(select(Child).where(Child.owner_id == user.id))
    rows = list(res.scalars().all())
    return rows[0] if len(rows) == 1 else None


# ---------- Events ----------


EVENT_TYPES = {
    "pickup", "dropoff", "activity", "expense", "text_screenshot",
    "medical", "school", "missed_visit", "phone_call", "note",
}
EXPENSE_CATEGORIES = {"food", "activity", "clothing", "school", "medical", "other"}
MISSED_SOURCES = {"auto", "manual"}


class InvalidEventData(ValueError):
    """Raised when event input fails type-specific validation."""


@dataclass
class CreateEventInput:
    child_id: str
    type: str
    occurred_at: datetime
    notes: str | None = None
    location: str | None = None
    overnight: bool = False
    amount_cents: int | None = None
    category: str | None = None
    call_connected: bool | None = None
    missed_source: str | None = None
    schedule_id: str | None = None


def _validate_event(data: CreateEventInput) -> None:
    if data.type not in EVENT_TYPES:
        raise InvalidEventData(f"unknown_event_type: {data.type}")
    if data.type == "expense":
        if data.amount_cents is None or data.amount_cents < 0:
            raise InvalidEventData("expense_requires_amount_cents")
        if data.category is not None and data.category not in EXPENSE_CATEGORIES:
            raise InvalidEventData(f"unknown_category: {data.category}")
    if data.type == "missed_visit":
        src = data.missed_source or "manual"
        if src not in MISSED_SOURCES:
            raise InvalidEventData(f"unknown_missed_source: {src}")


async def create_event(
    db: AsyncSession, user: User, data: CreateEventInput,
) -> CustodyEvent:
    _validate_event(data)
    child = await get_child(db, user, data.child_id)
    if child is None:
        raise InvalidEventData("child_not_found")
    evt = CustodyEvent(
        owner_id=user.id,
        child_id=data.child_id,
        type=data.type,
        occurred_at=data.occurred_at,
        notes=data.notes,
        location=data.location,
        overnight=bool(data.overnight) if data.type == "pickup" else False,
        amount_cents=data.amount_cents if data.type == "expense" else None,
        category=data.category if data.type == "expense" else None,
        call_connected=data.call_connected if data.type == "phone_call" else None,
        missed_source=(data.missed_source or "manual") if data.type == "missed_visit" else None,
        schedule_id=data.schedule_id if data.type == "missed_visit" else None,
    )
    db.add(evt)
    await db.commit()
    await db.refresh(evt)
    return evt


async def list_events(
    db: AsyncSession, user: User, *,
    child_id: str | None = None,
    type: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CustodyEvent]:
    stmt = (
        select(CustodyEvent)
        .options(selectinload(CustodyEvent.photos))
        .where(CustodyEvent.owner_id == user.id)
    )
    if child_id is not None:
        stmt = stmt.where(CustodyEvent.child_id == child_id)
    if type is not None:
        stmt = stmt.where(CustodyEvent.type == type)
    if from_dt is not None:
        stmt = stmt.where(CustodyEvent.occurred_at >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(CustodyEvent.occurred_at <= to_dt)
    stmt = stmt.order_by(CustodyEvent.occurred_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    return list(res.scalars().unique().all())


async def get_event(
    db: AsyncSession, user: User, event_id: str,
) -> CustodyEvent | None:
    res = await db.execute(
        select(CustodyEvent)
        .options(selectinload(CustodyEvent.photos))
        .where(CustodyEvent.id == event_id, CustodyEvent.owner_id == user.id)
    )
    return res.scalar_one_or_none()


async def update_event(
    db: AsyncSession, evt: CustodyEvent, **patch,
) -> CustodyEvent:
    allowed = {
        "occurred_at", "notes", "location", "overnight",
        "amount_cents", "category", "call_connected",
        "missed_source",
    }
    for k, v in patch.items():
        if k in allowed:
            setattr(evt, k, v)
    await db.commit()
    await db.refresh(evt)
    return evt


async def delete_event(db: AsyncSession, evt: CustodyEvent) -> None:
    await db.delete(evt)
    await db.commit()


# ---------- Schedules ----------


class InvalidScheduleData(ValueError):
    pass


@dataclass
class CreateScheduleInput:
    child_id: str
    name: str
    start_date: str  # YYYY-MM-DD
    interval_weeks: int
    weekdays: str  # "4,5,6"
    pickup_time: str  # HH:MM
    dropoff_time: str  # HH:MM
    pickup_location: str | None = None
    active: bool = True


def _validate_schedule(data: CreateScheduleInput) -> None:
    if data.interval_weeks < 1:
        raise InvalidScheduleData("interval_weeks_must_be_positive")
    try:
        wds = [int(x) for x in data.weekdays.split(",") if x.strip() != ""]
    except ValueError:
        raise InvalidScheduleData("weekdays_must_be_ints") from None
    if not wds or any(w < 0 or w > 6 for w in wds):
        raise InvalidScheduleData("weekdays_out_of_range")
    for label, t in (("pickup_time", data.pickup_time), ("dropoff_time", data.dropoff_time)):
        if len(t) != 5 or t[2] != ":":
            raise InvalidScheduleData(f"{label}_must_be_HH:MM")


async def create_schedule(
    db: AsyncSession, user: User, data: CreateScheduleInput,
) -> Schedule:
    _validate_schedule(data)
    child = await get_child(db, user, data.child_id)
    if child is None:
        raise InvalidScheduleData("child_not_found")
    sched = Schedule(
        owner_id=user.id,
        child_id=data.child_id,
        name=data.name,
        active=data.active,
        start_date=data.start_date,
        interval_weeks=data.interval_weeks,
        weekdays=data.weekdays,
        pickup_time=data.pickup_time,
        dropoff_time=data.dropoff_time,
        pickup_location=data.pickup_location,
    )
    db.add(sched)
    await db.commit()
    await db.refresh(sched)
    return sched


async def list_schedules(
    db: AsyncSession, user: User, *, child_id: str | None = None,
) -> list[Schedule]:
    stmt = select(Schedule).where(Schedule.owner_id == user.id)
    if child_id is not None:
        stmt = stmt.where(Schedule.child_id == child_id)
    stmt = stmt.order_by(Schedule.created_at.asc())
    res = await db.execute(stmt)
    return list(res.scalars().unique().all())


async def get_schedule(
    db: AsyncSession, user: User, schedule_id: str,
) -> Schedule | None:
    res = await db.execute(
        select(Schedule).where(
            Schedule.id == schedule_id, Schedule.owner_id == user.id,
        )
    )
    return res.scalar_one_or_none()


async def update_schedule(db: AsyncSession, sched: Schedule, **patch) -> Schedule:
    allowed = {
        "name", "active", "start_date", "interval_weeks", "weekdays",
        "pickup_time", "dropoff_time", "pickup_location",
    }
    for k, v in patch.items():
        if k in allowed:
            setattr(sched, k, v)
    await db.commit()
    await db.refresh(sched)
    return sched


async def delete_schedule(db: AsyncSession, sched: Schedule) -> None:
    await db.delete(sched)
    await db.commit()


async def add_schedule_exception(
    db: AsyncSession, sched: Schedule, *,
    date: str, kind: str,
    override_pickup_at: datetime | None = None,
    override_dropoff_at: datetime | None = None,
) -> ScheduleException:
    if kind not in ("skip", "override"):
        raise InvalidScheduleData(f"unknown_exception_kind: {kind}")
    ex = ScheduleException(
        schedule_id=sched.id,
        date=date,
        kind=kind,
        override_pickup_at=override_pickup_at,
        override_dropoff_at=override_dropoff_at,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    return ex


async def get_schedule_exceptions(
    db: AsyncSession, sched: Schedule,
) -> list[ScheduleException]:
    res = await db.execute(
        select(ScheduleException)
        .where(ScheduleException.schedule_id == sched.id)
        .order_by(ScheduleException.date.asc())
    )
    return list(res.scalars().all())


async def delete_schedule_exception(
    db: AsyncSession, ex: ScheduleException,
) -> None:
    await db.delete(ex)
    await db.commit()
