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
async def test_pdf_export_returns_nonempty_pdf_bytes(session_user_child):
    from app.plugins.custody.export import export_pdf
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

    data = await export_pdf(
        s, user, child_id=child.id,
        from_dt=datetime(2026, 1, 1), to_dt=datetime(2026, 1, 31, 23, 59),
    )
    assert data[:5] == b"%PDF-"
    assert len(data) > 500
