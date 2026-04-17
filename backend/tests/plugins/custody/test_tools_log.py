import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def db_and_user():
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
        yield s, user
    await engine.dispose()


@pytest.fixture
async def db_user_child(db_and_user):
    db, user = db_and_user
    from app.plugins.custody.services import create_child
    child = await create_child(db, user, name="Mason")
    return db, user, child


@pytest.mark.asyncio
async def test_log_event_default_now_and_default_child(db_user_child):
    db, user, child = db_user_child
    from app.plugins.custody.tools import log_custody_event_handler
    result = await log_custody_event_handler({"type": "pickup"}, user=user, db=db)
    assert result["ok"] is True
    assert "Mason" in result["summary"]


@pytest.mark.asyncio
async def test_log_event_requires_auth(db_user_child):
    db, user, child = db_user_child
    from app.plugins.custody.tools import log_custody_event_handler
    result = await log_custody_event_handler({"type": "pickup"}, user=None, db=db)
    assert result["error"] == "auth_required"


@pytest.mark.asyncio
async def test_log_event_child_not_found_lists_known(db_user_child):
    db, user, child = db_user_child
    from app.plugins.custody.tools import log_custody_event_handler
    result = await log_custody_event_handler(
        {"type": "pickup", "child_name": "Unknown"},
        user=user, db=db,
    )
    assert result["error"] == "child_not_found"
    assert "Mason" in result["known_children"]


@pytest.mark.asyncio
async def test_log_expense_converts_usd_to_cents(db_user_child):
    db, user, child = db_user_child
    from app.plugins.custody.tools import log_expense_handler
    result = await log_expense_handler(
        {"amount_usd": 42.50, "description": "bowling", "category": "activity"},
        user=user, db=db,
    )
    assert result["ok"] is True
    assert "$42.50" in result["summary"]

    from app.plugins.custody.services import list_events
    rows = await list_events(db, user, child_id=child.id, type="expense", limit=1)
    assert rows[0].amount_cents == 4250


@pytest.mark.asyncio
async def test_log_missed_visit_sets_source_manual(db_user_child):
    db, user, child = db_user_child
    from app.plugins.custody.tools import log_missed_visit_handler
    result = await log_missed_visit_handler(
        {"expected_pickup_at": "2026-01-10T17:00:00", "notes": "no show"},
        user=user, db=db,
    )
    assert result["ok"] is True

    from app.plugins.custody.services import list_events
    rows = await list_events(db, user, child_id=child.id, type="missed_visit", limit=1)
    assert rows[0].missed_source == "manual"
