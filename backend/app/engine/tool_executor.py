import json
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.plugins.registry import PluginRegistry

from .base import ToolCall, ToolResult

if TYPE_CHECKING:
    from app.models.user import User


class ToolExecutor:
    """Executes LLM-initiated tool calls against plugin APIs."""

    def __init__(self, registry: PluginRegistry, http_client: httpx.AsyncClient | None = None):
        self.registry = registry
        self._http = http_client

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def execute(
        self, call: ToolCall, user: "User | None" = None
    ) -> ToolResult:
        plugin, tool = self.registry.find_tool(call.name)
        if plugin is None or tool is None:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": f"tool '{call.name}' not found"}),
            )

        if plugin.manifest.api is None:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": f"plugin '{plugin.manifest.name}' has no api"}),
            )

        # Phase 2B: gate auth-required tools at the executor level.
        # Anonymous callers (user is None) get a synthetic error result
        # without any HTTP call so the chat service can short-circuit to
        # display_hint: "auth_required".
        if tool.auth_required and user is None:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({
                    "error": "auth_required",
                    "plugin": plugin.manifest.name,
                    # Sentinel that distinguishes the executor's synthetic
                    # refusal from a plugin-returned {"error": "auth_required"}
                    # body. Only this exact value triggers the chat service
                    # short-circuit + AuthPrompt UI.
                    "__source": "jain_executor_gate",
                }),
            )

        base_url = plugin.manifest.api.base_url.rstrip("/")
        endpoint = tool.endpoint or f"/{tool.name}"
        url = base_url + endpoint
        method = (tool.method or "GET").upper()

        # Phase 2B: build headers, adding service-key + user identity when
        # the caller is authenticated. Anonymous calls to public tools send
        # no auth headers at all.
        #
        # User identity headers are URL-encoded because httpx encodes header
        # values as Latin-1 by default, and User.name / User.email can contain
        # non-Latin characters from Google OAuth (CJK, accents, emoji).
        # Plugins MUST urllib.parse.unquote() these values on receipt.
        #
        # If JAIN_SERVICE_KEY is empty (misconfigured), we refuse to forward
        # user identity rather than send a foot-gun empty key. The call falls
        # through to anonymous mode and whatever the plugin does with no auth.
        headers = {"X-Requested-With": "XMLHttpRequest"}
        if user is not None and settings.JAIN_SERVICE_KEY:
            from urllib.parse import quote
            headers["X-Jain-Service-Key"] = settings.JAIN_SERVICE_KEY
            headers["X-Jain-User-Email"] = quote(user.email, safe="@")
            headers["X-Jain-User-Name"] = quote(user.name, safe="")

        client = await self._get_http()
        try:
            if method == "GET":
                response = await client.get(url, params=call.arguments, headers=headers)
            else:
                # Mutating methods send arguments as JSON body.
                response = await client.request(
                    method, url, json=call.arguments, headers=headers
                )
            response.raise_for_status()
            return ToolResult(tool_call_id=call.id, content=response.text)
        except httpx.HTTPStatusError as e:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps(
                    {"error": f"upstream error {e.response.status_code}", "detail": e.response.text}
                ),
            )
        except httpx.RequestError as e:
            return ToolResult(
                tool_call_id=call.id,
                content=json.dumps({"error": f"request failed: {type(e).__name__}"}),
            )
