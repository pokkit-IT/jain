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
async def test_create_list_update_delete_schedule(session_user_child):
    from app.plugins.custody.services import (
        CreateScheduleInput,
        create_schedule,
        delete_schedule,
        list_schedules,
        update_schedule,
    )

    s, user, child = session_user_child
    sched = await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="EOW Fri-Sun",
        start_date="2026-01-02", interval_weeks=2,
        weekdays="4,5,6", pickup_time="17:00", dropoff_time="19:00",
    ))
    assert sched.name == "EOW Fri-Sun"
    assert sched.interval_weeks == 2

    all_s = await list_schedules(s, user, child_id=child.id)
    assert len(all_s) == 1

    updated = await update_schedule(s, sched, name="EOW weekends", pickup_location="her house")
    assert updated.name == "EOW weekends"
    assert updated.pickup_location == "her house"

    await delete_schedule(s, sched)
    assert await list_schedules(s, user, child_id=child.id) == []


@pytest.mark.asyncio
async def test_rejects_bad_weekdays(session_user_child):
    from app.plugins.custody.services import (
        CreateScheduleInput,
        InvalidScheduleData,
        create_schedule,
    )

    s, user, child = session_user_child
    with pytest.raises(InvalidScheduleData):
        await create_schedule(s, user, CreateScheduleInput(
            child_id=child.id, name="bad",
            start_date="2026-01-02", interval_weeks=1,
            weekdays="7,9", pickup_time="17:00", dropoff_time="19:00",
        ))


@pytest.mark.asyncio
async def test_schedule_exception_crud(session_user_child):
    from app.plugins.custody.services import (
        CreateScheduleInput,
        add_schedule_exception,
        create_schedule,
        delete_schedule_exception,
        get_schedule_exceptions,
    )

    s, user, child = session_user_child
    sched = await create_schedule(s, user, CreateScheduleInput(
        child_id=child.id, name="weekly",
        start_date="2026-01-02", interval_weeks=1,
        weekdays="4", pickup_time="17:00", dropoff_time="19:00",
    ))
    ex = await add_schedule_exception(
        s, sched, date="2026-02-20", kind="skip",
    )
    rows = await get_schedule_exceptions(s, sched)
    assert [r.id for r in rows] == [ex.id]

    await delete_schedule_exception(s, ex)
    assert await get_schedule_exceptions(s, sched) == []
