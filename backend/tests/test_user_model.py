from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


async def test_create_user_with_defaults(session):
    u = User(
        email="jim@example.com",
        name="Jim Shelly",
        email_verified=True,
        google_sub="google-sub-123",
    )
    session.add(u)
    await session.commit()

    result = await session.execute(select(User))
    fetched = result.scalar_one()
    assert isinstance(fetched.id, UUID)
    assert fetched.email == "jim@example.com"
    assert fetched.email_verified is True
    assert fetched.google_sub == "google-sub-123"
    assert fetched.name == "Jim Shelly"
    assert fetched.picture_url is None
    assert fetched.last_login_at is not None


async def test_email_is_unique(session):
    u1 = User(email="dup@example.com", name="One", email_verified=True, google_sub="sub-1")
    u2 = User(email="dup@example.com", name="Two", email_verified=True, google_sub="sub-2")
    session.add(u1)
    await session.commit()
    session.add(u2)
    with pytest.raises(Exception):  # IntegrityError from sqlite
        await session.commit()


async def test_google_sub_is_unique(session):
    u1 = User(email="a@example.com", name="A", email_verified=True, google_sub="same-sub")
    u2 = User(email="b@example.com", name="B", email_verified=True, google_sub="same-sub")
    session.add(u1)
    await session.commit()
    session.add(u2)
    with pytest.raises(Exception):
        await session.commit()


async def test_google_sub_can_be_null(session):
    u = User(email="nosub@example.com", name="No Sub", email_verified=False, google_sub=None)
    session.add(u)
    await session.commit()

    result = await session.execute(select(User))
    fetched = result.scalar_one()
    assert fetched.google_sub is None
