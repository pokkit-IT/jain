import json

import httpx

from app.plugins.registry import PluginRegistry

from .base import ToolCall, ToolResult


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

    async def execute(self, call: ToolCall) -> ToolResult:
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

        base_url = plugin.manifest.api.base_url.rstrip("/")
        endpoint = tool.endpoint or f"/{tool.name}"
        url = base_url + endpoint

        client = await self._get_http()
        try:
            # Default to GET with query params. Tools can override via their endpoint.
            response = await client.get(url, params=call.arguments)
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
