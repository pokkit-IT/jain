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
