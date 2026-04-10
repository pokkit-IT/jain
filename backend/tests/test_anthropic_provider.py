from unittest.mock import AsyncMock, MagicMock

from app.engine.anthropic_provider import AnthropicProvider
from app.engine.base import ChatMessage, ToolCall, ToolResult
from app.plugins.schema import ToolDef, ToolInputSchema


def _make_tool() -> ToolDef:
    return ToolDef(
        name="find_yard_sales",
        description="Search sales",
        input_schema=ToolInputSchema(
            type="object",
            properties={"lat": {"type": "number"}},
            required=["lat"],
        ),
    )


async def test_anthropic_provider_text_only():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(type="text", text="Hi there")]
    fake_response.stop_reason = "end_turn"
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    provider = AnthropicProvider(
        api_key="test",
        model="claude-sonnet-4-20250514",
        client=fake_client,
    )
    result = await provider.complete(
        system="You are Jain",
        messages=[ChatMessage(role="user", content="hi")],
        tools=[],
    )
    assert result.text == "Hi there"
    assert result.tool_calls == []

    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"
    assert call_kwargs["system"] == "You are Jain"
    assert call_kwargs["messages"][0]["role"] == "user"


async def test_anthropic_provider_tool_call():
    fake_client = MagicMock()
    block = MagicMock(type="tool_use")
    block.id = "tu_1"
    block.name = "find_yard_sales"
    block.input = {"lat": 1.0, "lng": 2.0}

    fake_response = MagicMock()
    fake_response.content = [block]
    fake_response.stop_reason = "tool_use"
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    provider = AnthropicProvider(api_key="test", model="m", client=fake_client)
    result = await provider.complete(
        system="x",
        messages=[ChatMessage(role="user", content="find sales at 1,2")],
        tools=[_make_tool()],
    )
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "find_yard_sales"
    assert result.tool_calls[0].arguments == {"lat": 1.0, "lng": 2.0}

    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0]["name"] == "find_yard_sales"


async def test_anthropic_provider_includes_tool_results_in_history():
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [MagicMock(type="text", text="done")]
    fake_response.stop_reason = "end_turn"
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    provider = AnthropicProvider(api_key="test", model="m", client=fake_client)
    history = [
        ChatMessage(role="user", content="find sales"),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="tu_1", name="find_yard_sales", arguments={"lat": 1.0})],
        ),
        ChatMessage(
            role="tool",
            content="",
            tool_results=[ToolResult(tool_call_id="tu_1", content='{"sales":[]}')],
        ),
    ]
    await provider.complete(system="x", messages=history, tools=[])

    sent = fake_client.messages.create.call_args.kwargs["messages"]
    # user -> assistant(tool_use) -> user(tool_result)
    assert sent[0]["role"] == "user"
    assert sent[1]["role"] == "assistant"
    assert any(b["type"] == "tool_use" for b in sent[1]["content"])
    assert sent[2]["role"] == "user"
    assert any(b["type"] == "tool_result" for b in sent[2]["content"])
