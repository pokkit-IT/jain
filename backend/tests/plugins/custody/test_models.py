import uuid
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(id=uuid4(), email="x@y.com", name="X", email_verified=True, google_sub="g1")
        s.add(user)
        await s.flush()
        yield s, user
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_child_and_event(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason", dob="2020-08-12")
    session.add(child)
    await session.flush()

    evt = CustodyEvent(
        owner_id=user.id,
        child_id=child.id,
        type="pickup",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        notes="school pickup",
        location="Elm Elementary",
        overnight=True,
    )
    session.add(evt)
    await session.commit()

    res = await session.execute(select(CustodyEvent).where(CustodyEvent.child_id == child.id))
    loaded = res.scalar_one()
    assert loaded.type == "pickup"
    assert loaded.overnight is True
    assert loaded.location == "Elm Elementary"


@pytest.mark.asyncio
async def test_expense_fields(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason")
    session.add(child)
    await session.flush()

    evt = CustodyEvent(
        owner_id=user.id, child_id=child.id,
        type="expense",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        amount_cents=4250, category="activity",
        notes="bowling",
    )
    session.add(evt)
    await session.commit()

    res = await session.execute(select(CustodyEvent).where(CustodyEvent.type == "expense"))
    loaded = res.scalar_one()
    assert loaded.amount_cents == 4250
    assert loaded.category == "activity"


@pytest.mark.asyncio
async def test_delete_child_cascades_events(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason")
    session.add(child)
    await session.flush()
    session.add(CustodyEvent(
        owner_id=user.id, child_id=child.id,
        type="note",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        notes="hi",
    ))
    await session.commit()

    await session.delete(child)
    await session.commit()

    res = await session.execute(select(CustodyEvent))
    assert res.scalars().all() == []


@pytest.mark.asyncio
async def test_event_photo_cascades_on_event_delete(session_and_user):
    from app.plugins.custody.models import Child, CustodyEvent, EventPhoto

    session, user = session_and_user
    child = Child(owner_id=user.id, name="Mason")
    session.add(child)
    await session.flush()
    evt = CustodyEvent(
        owner_id=user.id, child_id=child.id,
        type="expense",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        amount_cents=100, category="food",
    )
    session.add(evt)
    await session.flush()
    session.add(EventPhoto(
        id=str(uuid.uuid4()), event_id=evt.id, position=0,
        original_path="p", thumb_path="t", content_type="image/jpeg",
    ))
    await session.commit()

    await session.delete(evt)
    await session.commit()

    res = await session.execute(select(EventPhoto))
    assert res.scalars().all() == []
