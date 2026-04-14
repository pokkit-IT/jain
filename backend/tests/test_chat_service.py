import json
from pathlib import Path

import pytest

from app.engine.base import ChatMessage, LLMResponse, ToolCall
from app.engine.mock import MockProvider
from app.engine.tool_executor import ToolExecutor
from app.plugins.core.registry import PluginRegistry
from app.services.chat_service import ChatService

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


@pytest.fixture
def registry():
    r = PluginRegistry(plugins_dir=FIXTURES)
    r.load_all()
    return r


async def test_chat_service_text_reply(registry):
    provider = MockProvider(
        responses=[LLMResponse(text="Hello human", tool_calls=[])]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
    )

    reply = await service.send(
        conversation=[ChatMessage(role="user", content="hi")],
        user=None,
    )
    assert reply.text == "Hello human"
    assert reply.data is None
    assert reply.display_hint is None
    assert reply.tool_events == []


async def test_chat_service_executes_tool_and_continues(registry, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": [{"id": 1, "title": "Garage sale"}]},
    )

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="find_yard_sales",
                        arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
                    )
                ],
            ),
            LLMResponse(text="Found 1 sale nearby", tool_calls=[]),
        ]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
    )

    reply = await service.send(
        conversation=[ChatMessage(role="user", content="find sales")],
        user=None,
    )
    assert reply.text == "Found 1 sale nearby"
    assert reply.data is not None
    assert reply.data["sales"][0]["title"] == "Garage sale"
    assert reply.display_hint == "map"
    assert len(reply.tool_events) == 1
    assert reply.tool_events[0]["name"] == "find_yard_sales"

    # Provider should have been called twice (initial + continuation).
    assert len(provider.calls) == 2


async def test_chat_service_respects_max_tool_rounds(registry, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": []},
        is_reusable=True,
    )

    # Infinite tool-call loop
    tool_call = ToolCall(
        id="tc1",
        name="find_yard_sales",
        arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
    )
    provider = MockProvider(
        responses=[LLMResponse(text="", tool_calls=[tool_call]) for _ in range(10)]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
        max_tool_rounds=3,
    )

    reply = await service.send(
        conversation=[ChatMessage(role="user", content="find sales")],
        user=None,
    )
    assert "max tool rounds" in reply.text.lower() or reply.text == ""
    assert len(provider.calls) <= 4  # initial + max_tool_rounds


async def test_chat_service_tool_error_does_not_set_data(registry, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        status_code=500,
        json={"detail": "upstream boom"},
    )

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="find_yard_sales",
                        arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
                    )
                ],
            ),
            LLMResponse(text="Something went wrong searching", tool_calls=[]),
        ]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
    )

    reply = await service.send(
        conversation=[ChatMessage(role="user", content="find sales")],
        user=None,
    )
    assert reply.text == "Something went wrong searching"
    assert reply.data is None
    assert reply.display_hint is None
    assert len(reply.tool_events) == 1
    assert reply.tool_events[0]["name"] == "find_yard_sales"


async def test_chat_service_passes_user_to_tool_executor(registry, httpx_mock):
    """When a User is passed to send(), the tool executor receives it."""
    from uuid import uuid4

    from app.models.user import User

    plugin = registry.get_plugin("yardsailing")
    plugin.service_key = "test-key-for-chat-service"  # type: ignore[attr-defined]

    try:
        httpx_mock.add_response(
            method="GET",
            url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
            json={"sales": []},
        )

        provider = MockProvider(
            responses=[
                LLMResponse(
                    text="",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="find_yard_sales",
                            arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
                        )
                    ],
                ),
                LLMResponse(text="found nothing", tool_calls=[]),
            ]
        )
        service = ChatService(
            registry=registry,
            provider=provider,
            tool_executor=ToolExecutor(registry=registry),
        )

        user = User(
            id=uuid4(),
            email="jim@example.com",
            name="Jim",
            email_verified=True,
            google_sub="g-jim-chat",
        )
        await service.send(
            conversation=[ChatMessage(role="user", content="find sales")],
            user=user,
        )

        sent = httpx_mock.get_requests()[0]
        assert sent.headers["x-jain-user-email"] == "jim@example.com"
    finally:
        plugin.service_key = None  # type: ignore[attr-defined]


async def test_chat_service_short_circuits_on_auth_required(registry):
    """When a tool returns auth_required error, chat service returns a
    ChatReply with display_hint='auth_required' and does NOT feed the
    error back to the LLM for a continuation."""
    # Mark the find_yard_sales tool as auth_required for this test
    _, tool = registry.find_tool("find_yard_sales")
    tool.auth_required = True

    try:
        provider = MockProvider(
            responses=[
                LLMResponse(
                    text="Let me search",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="find_yard_sales",
                            arguments={"lat": 1.0, "lng": 2.0},
                        )
                    ],
                ),
                # This second response must NOT be consumed — the service
                # should short-circuit after the auth_required error.
                LLMResponse(text="THIS SHOULD NOT BE USED", tool_calls=[]),
            ]
        )
        service = ChatService(
            registry=registry,
            provider=provider,
            tool_executor=ToolExecutor(registry=registry),
        )

        reply = await service.send(
            conversation=[ChatMessage(role="user", content="find sales")],
            user=None,
        )

        assert reply.display_hint == "auth_required"
        assert reply.data is not None
        assert reply.data["plugin"] == "yardsailing"
        assert "sign in" in reply.text.lower()
        # Only the first LLM call happened
        assert len(provider.calls) == 1
        # The tool call was logged
        assert len(reply.tool_events) == 1
        assert reply.tool_events[0]["name"] == "find_yard_sales"
    finally:
        tool.auth_required = False


async def test_chat_service_anonymous_user_public_tool_works(registry, httpx_mock):
    """Anonymous user calling a non-auth_required tool works normally."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": [{"id": 1, "title": "Sale"}]},
    )

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="find_yard_sales",
                        arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
                    )
                ],
            ),
            LLMResponse(text="Found 1", tool_calls=[]),
        ]
    )
    service = ChatService(
        registry=registry,
        provider=provider,
        tool_executor=ToolExecutor(registry=registry),
    )

    reply = await service.send(
        conversation=[ChatMessage(role="user", content="find sales")],
        user=None,
    )

    assert reply.text == "Found 1"
    assert reply.display_hint == "map"


async def test_chat_service_does_not_short_circuit_on_plugin_returned_auth_required(registry, httpx_mock):
    """If a plugin's actual HTTP response body is {"error": "auth_required"}
    (no __source sentinel), the chat service should NOT trigger the login
    prompt — it's a plugin-level error, not an executor gate refusal."""
    from uuid import uuid4

    from app.models.user import User

    plugin = registry.get_plugin("yardsailing")
    plugin.service_key = "test-key-short-circuit-negative"  # type: ignore[attr-defined]

    try:
        # Plugin returns an auth_required-shaped body but WITHOUT __source
        httpx_mock.add_response(
            method="GET",
            url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
            json={"error": "auth_required", "plugin": "yardsailing"},
        )

        provider = MockProvider(
            responses=[
                LLMResponse(
                    text="",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="find_yard_sales",
                            arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
                        )
                    ],
                ),
                # This SHOULD be consumed — the plugin error is not a gate refusal
                LLMResponse(text="The plugin had an error", tool_calls=[]),
            ]
        )
        service = ChatService(
            registry=registry,
            provider=provider,
            tool_executor=ToolExecutor(registry=registry),
        )

        user = User(
            id=uuid4(),
            email="jim@example.com",
            name="Jim",
            email_verified=True,
            google_sub="g-neg",
        )
        reply = await service.send(
            conversation=[ChatMessage(role="user", content="find sales")],
            user=user,
        )

        # Did NOT short-circuit — display_hint should not be auth_required
        assert reply.display_hint != "auth_required"
        assert reply.text == "The plugin had an error"
        # Both LLM calls happened
        assert len(provider.calls) == 2
    finally:
        plugin.service_key = None  # type: ignore[attr-defined]


async def test_chat_service_sets_component_hint_for_ui_tool(registry):
    """When a tool is marked ui_component, the chat service translates the
    synthetic __display_component marker into display_hint='component:<name>'
    with the initial_data as the reply data."""
    _, tool = registry.find_tool("find_yard_sales")
    tool.ui_component = "SaleForm"

    try:
        provider = MockProvider(
            responses=[
                LLMResponse(
                    text="Here's a form",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="find_yard_sales",
                            arguments={"title": "My Sale", "address": "123 Oak"},
                        )
                    ],
                ),
                LLMResponse(text="Fill it in", tool_calls=[]),
            ]
        )
        service = ChatService(
            registry=registry,
            provider=provider,
            tool_executor=ToolExecutor(registry=registry),
        )

        reply = await service.send(
            conversation=[ChatMessage(role="user", content="give me a form")],
            user=None,
        )

        assert reply.display_hint == "component:SaleForm"
        assert reply.data == {"title": "My Sale", "address": "123 Oak"}
        assert reply.text == "Fill it in"
    finally:
        tool.ui_component = None


async def test_chat_service_extracts_choices(registry, monkeypatch):
    from unittest.mock import AsyncMock
    from app.engine.base import LLMResponse
    from app.services.chat_service import ChatService

    fake_provider = AsyncMock()
    fake_provider.complete.return_value = LLMResponse(
        text="Pick one:\n[CHOICES]Option A|Option B[/CHOICES]",
        tool_calls=[],
    )

    service = ChatService(
        registry=registry,
        provider=fake_provider,
        tool_executor=AsyncMock(),
    )

    reply = await service.send([{"role": "user", "content": "help"}])
    assert reply.text == "Pick one:"
    assert reply.choices == ["Option A", "Option B"]


def test_infer_display_hint_plan_route_returns_route():
    from app.services.chat_service import _infer_display_hint

    route_data = {
        "route": {
            "stops": [{"sale_id": 1, "eta_minutes": 5.0, "in_window": True}],
            "total_distance_miles": 1.2,
            "total_duration_minutes": 10.0,
        }
    }
    hint = _infer_display_hint("yardsailing", "plan_route", route_data)
    assert hint == "route"


def test_infer_display_hint_plan_route_error_returns_none():
    from app.services.chat_service import _infer_display_hint

    hint = _infer_display_hint("yardsailing", "plan_route", {"error": "no_sales_found"})
    assert hint is None


def test_infer_display_hint_find_yard_sales_returns_map():
    from app.services.chat_service import _infer_display_hint

    sales_data = {"sales": [{"id": 1, "title": "Garage sale"}]}
    hint = _infer_display_hint("yardsailing", "find_yard_sales", sales_data)
    assert hint == "map"
