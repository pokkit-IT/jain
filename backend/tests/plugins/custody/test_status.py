from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


@pytest.mark.asyncio
async def test_status_no_schedule_no_events(session_user_child):
    from app.plugins.custody.schedules import compute_status

    s, user, child = session_user_child
    st = await compute_status(s, user, child.id, now=datetime(2026, 1, 5, 12, 0))
    assert st["state"] == "no_schedule"


@pytest.mark.asyncio
async def test_status_with_you_after_pickup(session_user_child):
    from app.plugins.custody.schedules import compute_status
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="w", start_date="2026-01-02",
        interval_weeks=1, weekdays="4",
        pickup_time="17:00", dropoff_time="19:00",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 9, 17, 0),
    ))
    st = await compute_status(s, user, child.id, now=datetime(2026, 1, 9, 18, 0))
    assert st["state"] == "with_you"
    assert st["since"] == datetime(2026, 1, 9, 17, 0)
    assert st["in_care_duration_seconds"] == 3600


@pytest.mark.asyncio
async def test_status_away_after_dropoff_shows_next_pickup(session_user_child):
    from app.plugins.custody.schedules import compute_status
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="w", start_date="2026-01-02",
        interval_weeks=1, weekdays="4",
        pickup_time="17:00", dropoff_time="19:00",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 2, 17, 0),
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="dropoff",
        occurred_at=datetime(2026, 1, 4, 19, 0),
    ))
    st = await compute_status(s, user, child.id, now=datetime(2026, 1, 5, 12, 0))
    assert st["state"] == "away"
    assert st["last_dropoff_at"] == datetime(2026, 1, 4, 19, 0)
    assert st["next_pickup_at"] == datetime(2026, 1, 9, 17, 0)


@pytest.mark.asyncio
async def test_summary_aggregates_month(session_user_child):
    from app.plugins.custody.schedules import compute_summary
    from app.plugins.custody.services import (
        CreateEventInput,
        create_event,
    )

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup", occurred_at=datetime(2026, 1, 3, 10, 0),
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=datetime(2026, 1, 3, 12, 0),
        amount_cents=4250, category="activity",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=datetime(2026, 1, 5, 12, 0),
        amount_cents=1500, category="food",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=datetime(2026, 2, 1, 12, 0),
        amount_cents=9999, category="food",
    ))

    summary = await compute_summary(s, user, child.id, year=2026, month=1)
    assert summary["visits_count"] == 1
    assert summary["total_expense_cents"] == 5750
    assert summary["by_category"] == {"activity": 4250, "food": 1500}
    assert summary["missed_visits_count"] == 0
