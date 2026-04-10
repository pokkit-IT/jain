from app.engine.base import ChatMessage, LLMResponse, ToolCall, ToolResult
from app.engine.mock import MockProvider


async def test_mock_provider_text_response():
    provider = MockProvider(responses=[LLMResponse(text="hello there", tool_calls=[])])
    result = await provider.complete(
        system="You are Jain",
        messages=[ChatMessage(role="user", content="hi")],
        tools=[],
    )
    assert result.text == "hello there"
    assert result.tool_calls == []


async def test_mock_provider_tool_call_response():
    tc = ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0})
    provider = MockProvider(responses=[LLMResponse(text="", tool_calls=[tc])])
    result = await provider.complete(system="x", messages=[], tools=[])
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "find_yard_sales"


async def test_mock_provider_continuation_after_tool_result():
    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                tool_calls=[
                    ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0})
                ],
            ),
            LLMResponse(text="Found 3 sales nearby", tool_calls=[]),
        ]
    )

    first = await provider.complete(system="x", messages=[], tools=[])
    assert first.tool_calls

    second = await provider.complete(
        system="x",
        messages=[
            ChatMessage(role="user", content="find sales"),
            ChatMessage(role="assistant", content="", tool_calls=first.tool_calls),
            ChatMessage(
                role="tool",
                content="",
                tool_results=[ToolResult(tool_call_id="tc1", content="3 sales found")],
            ),
        ],
        tools=[],
    )
    assert "Found 3 sales" in second.text
