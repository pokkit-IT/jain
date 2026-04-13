import asyncio
import logging
from typing import Any

from anthropic import APIStatusError, AsyncAnthropic

from app.plugins.core.schema import ToolDef

from .base import ChatMessage, LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 529, 503, 502, 504}
_MAX_ATTEMPTS = 4
_BASE_DELAY = 1.0


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

        response = await self._create_with_retry(kwargs)

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

    async def _create_with_retry(self, kwargs: dict[str, Any]) -> Any:
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await self._client.messages.create(**kwargs)
            except APIStatusError as exc:
                if exc.status_code not in _RETRYABLE_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Anthropic %s; retrying in %.1fs (attempt %d/%d)",
                    exc.status_code, delay, attempt + 1, _MAX_ATTEMPTS,
                )
                last_exc = exc
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

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
