from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.plugins.core.schema import ToolDef


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    tool_call_id: str
    content: str  # JSON-encoded string or plain text


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "tool"
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[ChatMessage],
        tools: list[ToolDef],
    ) -> LLMResponse:
        ...
