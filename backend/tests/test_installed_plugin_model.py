from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.installed_plugin import InstalledPlugin
from app.models.user import User


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_installed_plugin_has_spec_columns(session: AsyncSession):
    user = User(
        id=uuid4(),
        email="a@b.com",
        name="A",
        email_verified=True,
        google_sub="g",
    )
    session.add(user)
    await session.flush()

    plugin = InstalledPlugin(
        name="weather",
        manifest_url="https://example.com/plugin.json",
        manifest_json='{"name":"weather"}',
        service_key="sk-1234",
        bundle_path=None,
        installed_at=datetime.now(UTC),
        installed_by=user.id,
    )
    session.add(plugin)
    await session.commit()

    got = await session.get(InstalledPlugin, "weather")
    assert got is not None
    assert got.manifest_url == "https://example.com/plugin.json"
    assert got.service_key == "sk-1234"
    assert got.bundle_path is None
    assert got.installed_by == user.id
