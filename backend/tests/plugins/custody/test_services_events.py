from datetime import datetime, timedelta, timezone
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


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_create_event_pickup_with_overnight(session_user_child):
    from app.plugins.custody.services import CreateEventInput, create_event

    s, user, child = session_user_child
    evt = await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=_now(), notes="from school", location="Elm",
        overnight=True,
    ))
    assert evt.type == "pickup"
    assert evt.overnight is True
    assert evt.location == "Elm"


@pytest.mark.asyncio
async def test_create_event_expense_requires_amount(session_user_child):
    from app.plugins.custody.services import CreateEventInput, InvalidEventData, create_event

    s, user, child = session_user_child
    with pytest.raises(InvalidEventData):
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="expense", occurred_at=_now(),
            amount_cents=None, category="food",
        ))


@pytest.mark.asyncio
async def test_create_event_rejects_unknown_type(session_user_child):
    from app.plugins.custody.services import CreateEventInput, InvalidEventData, create_event

    s, user, child = session_user_child
    with pytest.raises(InvalidEventData):
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="laundry", occurred_at=_now(),
        ))


@pytest.mark.asyncio
async def test_list_events_filters_and_pagination(session_user_child):
    from app.plugins.custody.services import (
        CreateEventInput,
        create_event,
        list_events,
    )

    s, user, child = session_user_child
    base = _now()
    for i in range(5):
        await create_event(s, user, CreateEventInput(
            child_id=child.id, type="note", occurred_at=base - timedelta(hours=i),
            notes=f"n{i}",
        ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense", occurred_at=base,
        amount_cents=100, category="food", notes="snack",
    ))

    all_notes = await list_events(s, user, child_id=child.id, type="note")
    assert len(all_notes) == 5
    assert [e.notes for e in all_notes] == ["n0", "n1", "n2", "n3", "n4"]  # newest first

    paged = await list_events(s, user, child_id=child.id, type="note", limit=2, offset=2)
    assert [e.notes for e in paged] == ["n2", "n3"]


@pytest.mark.asyncio
async def test_owner_scope_prevents_cross_user_read(session_user_child):
    from app.plugins.custody.services import (
        CreateEventInput,
        create_child,
        create_event,
        list_events,
    )

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note", occurred_at=_now(), notes="mine",
    ))

    other = User(id=uuid4(), email="o@x.com", name="O", email_verified=True, google_sub="g2")
    s.add(other)
    await s.flush()
    other_child = await create_child(s, other, name="Lily")
    assert await list_events(s, other, child_id=other_child.id) == []
    assert await list_events(s, other, child_id=child.id) == []


@pytest.mark.asyncio
async def test_update_and_delete_event(session_user_child):
    from app.plugins.custody.services import (
        CreateEventInput,
        create_event,
        delete_event,
        get_event,
        update_event,
    )

    s, user, child = session_user_child
    evt = await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note", occurred_at=_now(), notes="before",
    ))
    updated = await update_event(s, evt, notes="after", location="park")
    assert updated.notes == "after"
    assert updated.location == "park"

    await delete_event(s, evt)
    assert await get_event(s, user, evt.id) is None
