import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def db_user_child():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from app.plugins.custody import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid.uuid4(), email="jim@test.com", name="Jim",
            email_verified=True, google_sub="g1",
        )
        s.add(user)
        await s.flush()
        from app.plugins.custody.services import create_child
        child = await create_child(s, user, name="Mason")
        yield s, user, child
    await engine.dispose()


@pytest.mark.asyncio
async def test_query_returns_summary_by_type_and_category(db_user_child):
    db, user, child = db_user_child
    from app.plugins.custody.services import CreateEventInput, create_event
    from app.plugins.custody.tools import query_custody_events_handler

    await create_event(db, user, CreateEventInput(
        child_id=child.id, type="expense",
        occurred_at=datetime(2026, 1, 5, 12),
        notes="bowling", amount_cents=4250, category="activity",
    ))
    await create_event(db, user, CreateEventInput(
        child_id=child.id, type="expense",
        occurred_at=datetime(2026, 1, 6, 12),
        notes="lunch", amount_cents=1500, category="food",
    ))
    await create_event(db, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 5, 17),
    ))

    result = await query_custody_events_handler(
        {"child_name": "Mason", "from_date": "2026-01-01", "to_date": "2026-01-31"},
        user=user, db=db,
    )

    summary = result["summary"]
    assert summary["total_expense_usd"] == 57.5
    assert summary["by_category_usd"] == {"activity": 42.5, "food": 15.0}
    assert summary["by_type"]["expense"] == 2
    assert summary["by_type"]["pickup"] == 1
