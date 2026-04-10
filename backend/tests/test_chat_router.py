from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_chat_service, get_registry
from app.engine.base import LLMResponse, ToolCall
from app.engine.mock import MockProvider
from app.engine.tool_executor import ToolExecutor
from app.main import create_app
from app.plugins.registry import PluginRegistry
from app.services.chat_service import ChatService

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def _build_app(mock_provider: MockProvider):
    app = create_app()
    registry = PluginRegistry(plugins_dir=FIXTURES)
    registry.load_all()
    executor = ToolExecutor(registry=registry)
    service = ChatService(registry=registry, provider=mock_provider, tool_executor=executor)

    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chat_service] = lambda: service
    return app


@pytest.fixture
async def chat_client_text():
    app = _build_app(MockProvider([LLMResponse(text="hello!", tool_calls=[])]))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_chat_endpoint_text_reply(chat_client_text):
    response = await chat_client_text.post(
        "/api/chat",
        json={"message": "hi"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "hello!"
    assert body["data"] is None
    assert body["display_hint"] is None


async def test_plugins_endpoint_lists_loaded():
    app = _build_app(MockProvider([LLMResponse(text="x", tool_calls=[])]))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/plugins")
        assert response.status_code == 200
        body = response.json()
        names = [p["name"] for p in body["plugins"]]
        assert "yardsailing" in names
        assert "small-talk" in names


async def test_plugin_bundle_endpoint_returns_404_for_missing():
    app = _build_app(MockProvider([LLMResponse(text="x", tool_calls=[])]))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/plugins/nonexistent/bundle")
        assert response.status_code == 404


async def test_plugin_bundle_endpoint_returns_404_when_no_components():
    """small-talk has no components declared, so its bundle endpoint 404s."""
    app = _build_app(MockProvider([LLMResponse(text="x", tool_calls=[])]))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/plugins/small-talk/bundle")
        assert response.status_code == 404


async def test_chat_endpoint_resolves_user_from_bearer_token():
    """Chat with a valid Authorization header resolves the user and passes
    it to the chat service."""
    from unittest.mock import AsyncMock, MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.auth.jwt import sign_access_token
    from app.database import get_db
    from app.dependencies import get_chat_service, get_registry
    from app.engine.base import LLMResponse
    from app.engine.mock import MockProvider
    from app.engine.tool_executor import ToolExecutor
    from app.main import create_app
    from app.models.base import Base
    from app.models.user import User
    from app.plugins.registry import PluginRegistry
    from app.services.chat_service import ChatService

    # Set up in-memory DB with a user row
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            email="jim@example.com",
            email_verified=True,
            google_sub="g-jim",
            name="Jim",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = sign_access_token(user)

    # Build app with mocked service
    app = create_app()
    registry = PluginRegistry(plugins_dir=FIXTURES)
    registry.load_all()

    spy = AsyncMock(
        return_value=MagicMock(
            text="hello jim",
            data=None,
            display_hint=None,
            tool_events=[],
        )
    )
    service = ChatService(
        registry=registry,
        provider=MockProvider([LLMResponse(text="x", tool_calls=[])]),
        tool_executor=ToolExecutor(registry=registry),
    )
    service.send = spy

    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chat_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.post(
            "/api/chat",
            json={"message": "hi"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    # The chat service received a User (not None)
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs["user"] is not None
    assert call_kwargs["user"].email == "jim@example.com"

    await engine.dispose()


async def test_chat_endpoint_bad_token_treats_as_anonymous():
    """Chat with a malformed Bearer token should NOT 401 — it should proceed
    anonymously (user=None)."""
    from unittest.mock import AsyncMock, MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.database import get_db
    from app.dependencies import get_chat_service, get_registry
    from app.engine.base import LLMResponse
    from app.engine.mock import MockProvider
    from app.engine.tool_executor import ToolExecutor
    from app.main import create_app
    from app.models.base import Base
    from app.plugins.registry import PluginRegistry
    from app.services.chat_service import ChatService

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    app = create_app()
    registry = PluginRegistry(plugins_dir=FIXTURES)
    registry.load_all()

    spy = AsyncMock(
        return_value=MagicMock(
            text="anon reply",
            data=None,
            display_hint=None,
            tool_events=[],
        )
    )
    service = ChatService(
        registry=registry,
        provider=MockProvider([LLMResponse(text="x", tool_calls=[])]),
        tool_executor=ToolExecutor(registry=registry),
    )
    service.send = spy

    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chat_service] = lambda: service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.post(
            "/api/chat",
            json={"message": "hi"},
            headers={"Authorization": "Bearer garbage-token"},
        )

    assert response.status_code == 200
    # The chat service should have received user=None, not 401
    assert spy.call_args.kwargs["user"] is None

    await engine.dispose()
