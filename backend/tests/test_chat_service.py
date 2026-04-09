import json
from pathlib import Path

import pytest

from app.engine.base import ChatMessage, LLMResponse, ToolCall
from app.engine.mock import MockProvider
from app.engine.tool_executor import ToolExecutor
from app.plugins.registry import PluginRegistry
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
    )
    assert "max tool rounds" in reply.text.lower() or reply.text == ""
    assert len(provider.calls) <= 4  # initial + max_tool_rounds
