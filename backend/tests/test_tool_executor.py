import json
from pathlib import Path

import httpx
import pytest

from app.engine.base import ToolCall
from app.engine.tool_executor import ToolExecutor
from app.plugins.registry import PluginRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


@pytest.fixture
def registry():
    r = PluginRegistry(plugins_dir=FIXTURES)
    r.load_all()
    return r


async def test_execute_calls_plugin_api(registry, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": [{"id": 1, "title": "Garage sale"}]},
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10})
    )
    assert result.tool_call_id == "tc1"
    payload = json.loads(result.content)
    assert payload["sales"][0]["title"] == "Garage sale"


async def test_execute_unknown_tool(registry):
    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="nonexistent", arguments={})
    )
    assert result.tool_call_id == "tc1"
    assert "not found" in result.content.lower()


async def test_execute_http_error(registry, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        status_code=500,
        json={"detail": "boom"},
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10})
    )
    assert "error" in result.content.lower()
