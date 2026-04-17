"""Recurrence + missed-visit detection for the custody plugin.

Split into a pure function (`expected_pickups`) that the tests
exhaustively pin down, and a DB-touching `refresh_missed` that
glues expected pickups to actual events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol


@dataclass
class ExpectedPickup:
    schedule_id: str
    expected_date: date
    expected_pickup_at: datetime
    expected_dropoff_at: datetime


class _SchedLike(Protocol):
    id: str
    start_date: str
    interval_weeks: int
    weekdays: str
    pickup_time: str
    dropoff_time: str


class _ExceptionLike(Protocol):
    date: str
    kind: str
    override_pickup_at: datetime | None
    override_dropoff_at: datetime | None


def _parse_hhmm(s: str) -> time:
    return time.fromisoformat(s if len(s) >= 5 else f"{s}:00")


def _parse_weekdays(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip() != ""]


def expected_pickups(
    sched: _SchedLike,
    exceptions: list[_ExceptionLike],
    from_date: date,
    to_date: date,
) -> list[ExpectedPickup]:
    """Generate expected pickups for `sched` in [from_date, to_date] inclusive.

    Pure function — no DB access, deterministic from inputs.
    """
    try:
        anchor = date.fromisoformat(sched.start_date)
    except ValueError:
        return []
    if to_date < anchor:
        return []

    weekdays = set(_parse_weekdays(sched.weekdays))
    pickup_t = _parse_hhmm(sched.pickup_time)
    dropoff_t = _parse_hhmm(sched.dropoff_time)

    ex_by_date: dict[str, _ExceptionLike] = {e.date: e for e in exceptions}

    out: list[ExpectedPickup] = []
    cursor = max(anchor, from_date)
    while cursor <= to_date:
        if cursor.weekday() in weekdays:
            delta_weeks = (cursor - anchor).days // 7
            if delta_weeks % sched.interval_weeks == 0:
                iso = cursor.isoformat()
                ex = ex_by_date.get(iso)
                if ex is not None and ex.kind == "skip":
                    cursor += timedelta(days=1)
                    continue
                if ex is not None and ex.kind == "override":
                    pickup_dt = ex.override_pickup_at or datetime.combine(cursor, pickup_t)
                    dropoff_dt = ex.override_dropoff_at or datetime.combine(cursor, dropoff_t)
                else:
                    pickup_dt = datetime.combine(cursor, pickup_t)
                    dropoff_dt = datetime.combine(cursor, dropoff_t)
                out.append(ExpectedPickup(
                    schedule_id=sched.id,
                    expected_date=cursor,
                    expected_pickup_at=pickup_dt,
                    expected_dropoff_at=dropoff_dt,
                ))
        cursor += timedelta(days=1)
    return out


# ---------- DB-backed missed-visit detection ----------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

PICKUP_GRACE_HOURS = 2
MISSED_DEDUPE_HOURS = 4


async def refresh_missed(
    db: AsyncSession, user: User, child_id: str, *, up_to: datetime,
) -> int:
    """Scan active schedules for `child_id` and insert `missed_visit` events
    for any expected pickup that has no pickup in the ±grace window and no
    existing missed_visit in the ±dedupe window. Returns new rows inserted.
    """
    from .models import CustodyEvent, Schedule

    res = await db.execute(
        select(Schedule).where(
            Schedule.owner_id == user.id,
            Schedule.child_id == child_id,
            Schedule.active.is_(True),
        )
    )
    schedules = list(res.scalars().all())
    if not schedules:
        return 0

    new_count = 0
    for sched in schedules:
        exceptions = sched.exceptions  # selectin-loaded
        start = date.fromisoformat(sched.start_date)
        expected = expected_pickups(sched, exceptions, start, up_to.date())
        for ep in expected:
            pickup_lo = ep.expected_pickup_at - timedelta(hours=PICKUP_GRACE_HOURS)
            pickup_hi = ep.expected_pickup_at + timedelta(hours=PICKUP_GRACE_HOURS)
            match = await db.execute(
                select(CustodyEvent.id).where(
                    CustodyEvent.owner_id == user.id,
                    CustodyEvent.child_id == child_id,
                    CustodyEvent.type == "pickup",
                    CustodyEvent.occurred_at >= pickup_lo,
                    CustodyEvent.occurred_at <= pickup_hi,
                )
            )
            if match.first() is not None:
                continue

            dedupe_lo = ep.expected_pickup_at - timedelta(hours=MISSED_DEDUPE_HOURS)
            dedupe_hi = ep.expected_pickup_at + timedelta(hours=MISSED_DEDUPE_HOURS)
            existing = await db.execute(
                select(CustodyEvent.id).where(
                    CustodyEvent.owner_id == user.id,
                    CustodyEvent.child_id == child_id,
                    CustodyEvent.type == "missed_visit",
                    CustodyEvent.occurred_at >= dedupe_lo,
                    CustodyEvent.occurred_at <= dedupe_hi,
                )
            )
            if existing.first() is not None:
                continue

            db.add(CustodyEvent(
                owner_id=user.id,
                child_id=child_id,
                type="missed_visit",
                occurred_at=ep.expected_pickup_at,
                missed_source="auto",
                schedule_id=sched.id,
                notes=(
                    f"Auto-flagged: no pickup within {PICKUP_GRACE_HOURS}h "
                    f"of scheduled {sched.pickup_time}"
                ),
            ))
            new_count += 1

    if new_count:
        await db.commit()
    return new_count


# ---------- Home-screen support (status + summary) ----------

async def compute_status(
    db: AsyncSession, user: User, child_id: str, *, now: datetime,
) -> dict:
    from .models import CustodyEvent, Schedule

    res = await db.execute(
        select(CustodyEvent)
        .where(
            CustodyEvent.owner_id == user.id,
            CustodyEvent.child_id == child_id,
            CustodyEvent.type.in_(["pickup", "dropoff"]),
        )
        .order_by(CustodyEvent.occurred_at.desc())
    )
    transitions = list(res.scalars().all())

    last_pickup = next((e for e in transitions if e.type == "pickup"), None)
    last_dropoff = next((e for e in transitions if e.type == "dropoff"), None)

    state = "no_schedule"
    if last_pickup is not None and (last_dropoff is None or last_dropoff.occurred_at < last_pickup.occurred_at):
        state = "with_you"
    else:
        has_sched = await db.execute(
            select(Schedule.id).where(
                Schedule.owner_id == user.id,
                Schedule.child_id == child_id,
                Schedule.active.is_(True),
            )
        )
        if has_sched.first() is not None:
            state = "away"

    out: dict = {"state": state}
    if state == "with_you" and last_pickup is not None:
        out["since"] = last_pickup.occurred_at
        out["in_care_duration_seconds"] = int((now - last_pickup.occurred_at).total_seconds())
    if state == "away" and last_dropoff is not None:
        out["last_dropoff_at"] = last_dropoff.occurred_at
    if state == "away":
        sched_res = await db.execute(
            select(Schedule).where(
                Schedule.owner_id == user.id,
                Schedule.child_id == child_id,
                Schedule.active.is_(True),
            )
        )
        next_pickup: datetime | None = None
        for sched in sched_res.scalars().all():
            window_end = (now + timedelta(days=60)).date()
            eps = expected_pickups(sched, sched.exceptions, now.date(), window_end)
            for ep in eps:
                if ep.expected_pickup_at > now and (next_pickup is None or ep.expected_pickup_at < next_pickup):
                    next_pickup = ep.expected_pickup_at
        if next_pickup is not None:
            out["next_pickup_at"] = next_pickup
    return out


async def compute_summary(
    db: AsyncSession, user: User, child_id: str, *, year: int, month: int,
) -> dict:
    from calendar import monthrange
    from .models import CustodyEvent

    first = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    last = datetime(year, month, last_day, 23, 59, 59)

    res = await db.execute(
        select(CustodyEvent).where(
            CustodyEvent.owner_id == user.id,
            CustodyEvent.child_id == child_id,
            CustodyEvent.occurred_at >= first,
            CustodyEvent.occurred_at <= last,
        )
    )
    rows = list(res.scalars().all())

    visits = sum(1 for e in rows if e.type == "pickup")
    missed = sum(1 for e in rows if e.type == "missed_visit")
    total_cents = sum(e.amount_cents or 0 for e in rows if e.type == "expense")
    by_category: dict[str, int] = {}
    for e in rows:
        if e.type != "expense" or e.amount_cents is None:
            continue
        key = e.category or "other"
        by_category[key] = by_category.get(key, 0) + e.amount_cents

    return {
        "visits_count": visits,
        "missed_visits_count": missed,
        "total_expense_cents": total_cents,
        "by_category": by_category,
    }
