from uuid import uuid4

import pytest
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
        user = User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g")
        s.add(user)
        await s.flush()
        yield s, user
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_list_delete_child(session_and_user):
    from app.plugins.custody.services import (
        create_child,
        delete_child,
        list_children,
        update_child,
    )

    s, user = session_and_user
    c = await create_child(s, user, name="Mason", dob="2020-08-12")
    assert c.name == "Mason"
    assert c.owner_id == user.id

    all_c = await list_children(s, user)
    assert [x.name for x in all_c] == ["Mason"]

    updated = await update_child(s, c, name="Mason R", dob=None)
    assert updated.name == "Mason R"

    await delete_child(s, c)
    assert await list_children(s, user) == []


@pytest.mark.asyncio
async def test_resolve_child_by_name_case_insensitive(session_and_user):
    from app.plugins.custody.services import create_child, resolve_child

    s, user = session_and_user
    c = await create_child(s, user, name="Mason")
    found = await resolve_child(s, user, name="mason")
    assert found is not None and found.id == c.id

    missing = await resolve_child(s, user, name="Lily")
    assert missing is None


@pytest.mark.asyncio
async def test_resolve_child_default_when_single(session_and_user):
    from app.plugins.custody.services import create_child, resolve_child

    s, user = session_and_user
    c = await create_child(s, user, name="Mason")
    found = await resolve_child(s, user, name=None)
    assert found is not None and found.id == c.id


@pytest.mark.asyncio
async def test_resolve_child_none_when_multiple_and_no_name(session_and_user):
    from app.plugins.custody.services import create_child, resolve_child

    s, user = session_and_user
    await create_child(s, user, name="Mason")
    await create_child(s, user, name="Lily")
    assert await resolve_child(s, user, name=None) is None
