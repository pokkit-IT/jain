from app.plugins.core.schema import ToolDef

from .base import ChatMessage, LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """Deterministic LLM for tests. Returns pre-loaded responses in order."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(
        self,
        system: str,
        messages: list[ChatMessage],
        tools: list[ToolDef],
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if not self._responses:
            raise RuntimeError("MockProvider exhausted")
        return self._responses.pop(0)
