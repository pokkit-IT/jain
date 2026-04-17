from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
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


def _dt(year, month, day, hour=17, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute)


@pytest.mark.asyncio
async def test_missed_flagged_when_no_pickup_in_window(session_user_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import CreateScheduleInput, create_schedule

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))

    created = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 10))
    assert created == 2  # Jan 2 and Jan 9 both missed

    res = await s.execute(
        select(CustodyEvent).where(CustodyEvent.type == "missed_visit")
        .order_by(CustodyEvent.occurred_at.asc())
    )
    rows = list(res.scalars().all())
    assert len(rows) == 2
    assert rows[0].occurred_at == _dt(2026, 1, 2)
    assert rows[0].missed_source == "auto"


@pytest.mark.asyncio
async def test_pickup_within_2h_suppresses_missed(session_user_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=_dt(2026, 1, 2, 18, 0),
    ))

    created = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 3))
    assert created == 0
    res = await s.execute(
        select(CustodyEvent).where(CustodyEvent.type == "missed_visit")
    )
    assert res.scalars().all() == []


@pytest.mark.asyncio
async def test_idempotent_across_runs(session_user_child):
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import CreateScheduleInput, create_schedule

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    first = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 10))
    second = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 10))
    assert first == 2
    assert second == 0


@pytest.mark.asyncio
async def test_manual_missed_visit_blocks_auto_flag(session_user_child):
    from app.plugins.custody.models import CustodyEvent
    from app.plugins.custody.schedules import refresh_missed
    from app.plugins.custody.services import (
        CreateEventInput,
        CreateScheduleInput,
        create_event,
        create_schedule,
    )

    s, user, child = session_user_child
    await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="wk",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="missed_visit",
        occurred_at=_dt(2026, 1, 2),
        missed_source="manual",
        notes="she texted she wasn't bringing him",
    ))
    created = await refresh_missed(s, user, child.id, up_to=datetime(2026, 1, 3))
    assert created == 0
    res = await s.execute(
        select(CustodyEvent).where(CustodyEvent.type == "missed_visit")
    )
    rows = list(res.scalars().all())
    assert len(rows) == 1
    assert rows[0].missed_source == "manual"
