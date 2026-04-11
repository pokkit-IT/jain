from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_sale_model_persist_and_load(session):
    user = User(
        id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
    )
    session.add(user)
    await session.flush()

    sale = Sale(
        owner_id=user.id,
        title="Big Saturday",
        address="123 Main",
        description="stuff",
        start_date="2026-04-18",
        end_date="2026-04-18",
        start_time="08:00",
        end_time="14:00",
    )
    session.add(sale)
    await session.commit()

    got = await session.get(Sale, sale.id)
    assert got is not None
    assert got.title == "Big Saturday"
    assert got.owner_id == user.id
    assert isinstance(got.created_at, datetime)
