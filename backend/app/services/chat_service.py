import json
from dataclasses import dataclass, field
from typing import Any

from app.engine.base import ChatMessage, LLMProvider, ToolResult
from app.engine.tool_executor import ToolExecutor
from app.models.user import User
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

    async def send(
        self,
        conversation: list[ChatMessage],
        user: User | None = None,
    ) -> ChatReply:
        """Run the LLM + tool loop and return the final assistant reply.

        The loop runs up to `max_tool_rounds + 1` LLM calls total. The extra
        round is intended to give the LLM a final turn to generate a text
        reply after its last tool execution. If the LLM returns tool_calls
        on that final round, those tools run but their results are discarded
        (the reply text becomes "(max tool rounds reached)"). This is a
        safety bound against pathological tool-use loops.

        Phase 2B: if any tool execution returns a synthetic auth_required
        error, the loop short-circuits immediately and returns a ChatReply
        with display_hint="auth_required" so the mobile app can render an
        inline login prompt.

        Args:
            conversation: Full chat history so far, ending with the user's
                          latest message.
            user: The authenticated User if the caller provided a valid
                  JAIN JWT, or None for anonymous requests.

        Returns:
            ChatReply containing the final text, most recent tool data (if
            any), a display hint, and a log of tool events.
        """
        system = build_system_prompt(self.registry, user=user)
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
                result = await self.tool_executor.execute(call, user=user)
                results.append(result)

                event = {"name": call.name, "arguments": call.arguments}
                tool_events.append(event)

                # Try to parse result content as JSON
                try:
                    parsed = json.loads(result.content)
                except (json.JSONDecodeError, TypeError):
                    parsed = None

                # Phase 2B: short-circuit on auth_required synthetic error.
                # The LLM's in-progress response is discarded; the user sees
                # only a short "sign in first" message + inline login prompt.
                if (
                    isinstance(parsed, dict)
                    and parsed.get("error") == "auth_required"
                ):
                    return ChatReply(
                        text="I'd love to help with that — you'll need to sign in first.",
                        data={"plugin": parsed.get("plugin", "")},
                        display_hint="auth_required",
                        tool_events=tool_events,
                    )

                is_error = isinstance(parsed, dict) and parsed.get("error")
                if parsed is not None and not is_error:
                    plugin, _ = self.registry.find_tool(call.name)
                    plugin_name = plugin.manifest.name if plugin else ""
                    # Update data and hint atomically so a stale "map" hint
                    # never outlives its original sales-shaped data.
                    last_data = parsed
                    last_display_hint = _infer_display_hint(plugin_name, call.name, parsed)

            history.append(ChatMessage(role="tool", content="", tool_results=results))

        return ChatReply(
            text="(max tool rounds reached)",
            data=last_data,
            display_hint=last_display_hint,
            tool_events=tool_events,
        )
