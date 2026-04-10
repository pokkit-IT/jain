import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.conversation import Conversation, Message
from app.models.installed_plugin import InstalledPlugin


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
    p = InstalledPlugin(name="yardsailing", version="1.0.0", enabled=True)
    session.add(p)
    await session.commit()

    result = await session.execute(select(InstalledPlugin))
    fetched = result.scalar_one()
    assert fetched.name == "yardsailing"
    assert fetched.enabled is True
