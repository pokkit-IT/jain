from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.conversation import Conversation, Message
from app.models.installed_plugin import InstalledPlugin
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


async def test_create_conversation_with_messages(session):
    conv = Conversation(title="Test")
    conv.messages.append(Message(role="user", content="hello"))
    conv.messages.append(Message(role="assistant", content="hi there"))
    session.add(conv)
    await session.commit()

    result = await session.execute(select(Conversation))
    fetched = result.scalar_one()
    assert fetched.title == "Test"
    assert len(fetched.messages) == 2
    assert fetched.messages[0].role == "user"


async def test_installed_plugin(session):
    user = User(
        id=uuid4(),
        email="installer@example.com",
        name="Installer",
        email_verified=True,
        google_sub="g-installer",
    )
    session.add(user)
    await session.flush()

    p = InstalledPlugin(
        name="yardsailing",
        manifest_url="https://example.com/manifest.json",
        manifest_json='{"name":"yardsailing"}',
        service_key="sk-test",
        bundle_path=None,
        installed_at=datetime.now(UTC),
        installed_by=user.id,
    )
    session.add(p)
    await session.commit()

    result = await session.execute(select(InstalledPlugin))
    fetched = result.scalar_one()
    assert fetched.name == "yardsailing"
    assert fetched.manifest_url == "https://example.com/manifest.json"
    assert fetched.service_key == "sk-test"
    assert fetched.installed_by == user.id
