from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.services import (
    CreateSaleInput,
    create_sale,
    get_sale_by_id,
    list_sales_for_owner,
)


@pytest.fixture
async def session_and_user():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        yield s, user
    await engine.dispose()


async def test_create_sale_persists_row(session_and_user):
    session, user = session_and_user
    data = CreateSaleInput(
        title="Big Sale", address="123 Main", description=None,
        start_date="2026-04-18", end_date=None,
        start_time="08:00", end_time="14:00",
    )
    sale = await create_sale(session, user, data)

    assert sale.id
    assert sale.owner_id == user.id
    assert sale.title == "Big Sale"


async def test_list_sales_for_owner_returns_only_this_users(session_and_user):
    session, user = session_and_user
    other = User(
        id=uuid4(), email="b@b.com", name="B", email_verified=True, google_sub="g2",
    )
    session.add(other)
    await session.commit()

    await create_sale(session, user, CreateSaleInput(
        title="Mine", address="a", description=None,
        start_date="2026-04-18", end_date=None,
        start_time="08:00", end_time="14:00",
    ))
    await create_sale(session, other, CreateSaleInput(
        title="Theirs", address="b", description=None,
        start_date="2026-04-18", end_date=None,
        start_time="08:00", end_time="14:00",
    ))

    rows = await list_sales_for_owner(session, user)
    assert len(rows) == 1
    assert rows[0].title == "Mine"


async def test_get_sale_by_id_returns_none_when_missing(session_and_user):
    session, _ = session_and_user
    assert await get_sale_by_id(session, "does-not-exist") is None
