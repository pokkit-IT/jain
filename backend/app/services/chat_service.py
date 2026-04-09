import json
from dataclasses import dataclass, field
from typing import Any

from app.engine.base import ChatMessage, LLMProvider, ToolResult
from app.engine.tool_executor import ToolExecutor
from app.plugins.registry import PluginRegistry

from .context_builder import build_system_prompt


@dataclass
class ChatReply:
    text: str
    data: Any | None = None
    display_hint: str | None = None
    tool_events: list[dict] = field(default_factory=list)


def _infer_display_hint(plugin_name: str, tool_name: str, data: Any) -> str | None:
    """Infer how the frontend should render tool results.

    Phase 1 heuristic:
    - find_* tools returning a dict with list values -> map
    - create_* tools -> None (inline text reply)
    """
    if not isinstance(data, dict):
        return None
    if tool_name.startswith("find_"):
        # Look for a list-valued key (sales, items, etc.)
        for value in data.values():
            if isinstance(value, list) and value:
                return "map"
    return None


class ChatService:
    def __init__(
        self,
        registry: PluginRegistry,
        provider: LLMProvider,
        tool_executor: ToolExecutor,
        max_tool_rounds: int = 5,
    ):
        self.registry = registry
        self.provider = provider
        self.tool_executor = tool_executor
        self.max_tool_rounds = max_tool_rounds

    async def send(self, conversation: list[ChatMessage]) -> ChatReply:
        system = build_system_prompt(self.registry)
        tools = self.registry.all_tools()
        history = list(conversation)

        last_data: Any = None
        last_display_hint: str | None = None
        tool_events: list[dict] = []

        for _round in range(self.max_tool_rounds + 1):
            response = await self.provider.complete(
                system=system, messages=history, tools=tools
            )

            if not response.tool_calls:
                return ChatReply(
                    text=response.text,
                    data=last_data,
                    display_hint=last_display_hint,
                    tool_events=tool_events,
                )

            # Append assistant turn (with tool_use blocks) and execute each tool
            history.append(
                ChatMessage(
                    role="assistant",
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
            )

            results: list[ToolResult] = []
            for call in response.tool_calls:
                result = await self.tool_executor.execute(call)
                results.append(result)

                event = {"name": call.name, "arguments": call.arguments}
                tool_events.append(event)

                # Try to parse result content as JSON for data/display_hint
                try:
                    parsed = json.loads(result.content)
                except (json.JSONDecodeError, TypeError):
                    parsed = None

                if parsed is not None and not (
                    isinstance(parsed, dict) and parsed.get("error")
                ):
                    last_data = parsed
                    plugin, _ = self.registry.find_tool(call.name)
                    plugin_name = plugin.manifest.name if plugin else ""
                    hint = _infer_display_hint(plugin_name, call.name, parsed)
                    if hint:
                        last_display_hint = hint

            history.append(ChatMessage(role="tool", content="", tool_results=results))

        return ChatReply(
            text="(max tool rounds reached)",
            data=last_data,
            display_hint=last_display_hint,
            tool_events=tool_events,
        )
