from typing import Any

from anthropic import AsyncAnthropic

from app.plugins.core.schema import ToolDef

from .base import ChatMessage, LLMProvider, LLMResponse, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        client: Any | None = None,
        max_tokens: int = 2048,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self._client = client or AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        system: str,
        messages: list[ChatMessage],
        tools: list[ToolDef],
    ) -> LLMResponse:
        api_messages = self._convert_messages(messages)
        api_tools = [self._convert_tool(t) for t in tools]

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": api_messages,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        response = await self._client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )

        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls)

    def _convert_tool(self, tool: ToolDef) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": tool.input_schema.type,
                "properties": tool.input_schema.properties,
                "required": tool.input_schema.required,
            },
        }

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "user":
                out.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                blocks: list[dict[str, Any]] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                out.append({"role": "assistant", "content": blocks})
            elif msg.role == "tool":
                blocks = [
                    {"type": "tool_result", "tool_use_id": tr.tool_call_id, "content": tr.content}
                    for tr in msg.tool_results
                ]
                out.append({"role": "user", "content": blocks})
        return out
