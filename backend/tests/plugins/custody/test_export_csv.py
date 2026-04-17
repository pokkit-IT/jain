import csv
import io
from datetime import datetime
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
async def test_csv_export_has_header_and_rows(session_user_child):
    from app.plugins.custody.export import export_csv
    from app.plugins.custody.services import CreateEventInput, create_event

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="pickup",
        occurred_at=datetime(2026, 1, 2, 17, 0), notes="school",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="expense",
        occurred_at=datetime(2026, 1, 2, 18, 0),
        amount_cents=4250, category="activity", notes="bowling",
    ))

    data = await export_csv(
        s, user, child_id=child.id,
        from_dt=datetime(2026, 1, 1), to_dt=datetime(2026, 1, 31, 23, 59),
    )
    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    rows = list(reader)
    assert rows[0] == [
        "occurred_at", "type", "child", "notes", "location",
        "amount_usd", "category", "photo_count", "photo_urls",
    ]
    assert len(rows) == 3
    expense_row = next(r for r in rows[1:] if r[1] == "expense")
    assert expense_row[2] == "Mason"
    assert expense_row[5] == "42.50"
    assert expense_row[6] == "activity"


@pytest.mark.asyncio
async def test_csv_export_respects_date_range(session_user_child):
    from app.plugins.custody.export import export_csv
    from app.plugins.custody.services import CreateEventInput, create_event

    s, user, child = session_user_child
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note",
        occurred_at=datetime(2025, 12, 30, 10, 0), notes="before",
    ))
    await create_event(s, user, CreateEventInput(
        child_id=child.id, type="note",
        occurred_at=datetime(2026, 1, 5, 10, 0), notes="in range",
    ))

    data = await export_csv(
        s, user, child_id=child.id,
        from_dt=datetime(2026, 1, 1), to_dt=datetime(2026, 1, 31, 23, 59),
    )
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    note_rows = [r for r in rows[1:]]
    assert len(note_rows) == 1
    assert note_rows[0][3] == "in range"
