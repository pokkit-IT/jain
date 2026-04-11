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
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10}),
        user=None,
    )
    assert result.tool_call_id == "tc1"
    payload = json.loads(result.content)
    assert payload["sales"][0]["title"] == "Garage sale"


async def test_execute_unknown_tool(registry):
    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="nonexistent", arguments={}),
        user=None,
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
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10}),
        user=None,
    )
    assert "error" in result.content.lower()


async def test_execute_auth_required_tool_without_user_returns_synthetic_error(registry):
    """When tool.auth_required is True and user is None, return a synthetic
    auth_required error without making any HTTP call."""
    # Mutate the fixture tool to be auth_required for this test
    _, tool = registry.find_tool("find_yard_sales")
    tool.auth_required = True

    try:
        executor = ToolExecutor(registry=registry)
        result = await executor.execute(
            ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0}),
            user=None,
        )
        assert result.tool_call_id == "tc1"
        payload = json.loads(result.content)
        assert payload["error"] == "auth_required"
        assert payload["plugin"] == "yardsailing"
    finally:
        # Restore so other tests see the original fixture state
        tool.auth_required = False


async def test_execute_public_tool_without_user_still_works(registry, httpx_mock):
    """Public tools (auth_required=False) call anonymously even when user is None."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": []},
    )

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="find_yard_sales", arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10}),
        user=None,
    )
    assert json.loads(result.content) == {"sales": []}


async def test_execute_forwards_service_key_headers_when_user_present(registry, httpx_mock):
    """When user is authenticated, the executor forwards X-Jain-Service-Key +
    X-Jain-User-Email + X-Jain-User-Name headers to the plugin."""
    from uuid import uuid4

    from app.config import settings
    from app.models.user import User

    original_key = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = "test-service-key-1234"

    try:
        httpx_mock.add_response(
            method="GET",
            url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
            json={"sales": []},
        )

        user = User(
            id=uuid4(),
            email="jim@example.com",
            name="Jim Shelly",
            email_verified=True,
            google_sub="g-jim",
        )

        executor = ToolExecutor(registry=registry)
        await executor.execute(
            ToolCall(
                id="tc1",
                name="find_yard_sales",
                arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
            ),
            user=user,
        )

        sent_request = httpx_mock.get_requests()[0]
        assert sent_request.headers["x-jain-service-key"] == "test-service-key-1234"
        assert sent_request.headers["x-jain-user-email"] == "jim@example.com"
        # Name is URL-encoded; spaces become %20
        assert sent_request.headers["x-jain-user-name"] == "Jim%20Shelly"
    finally:
        settings.JAIN_SERVICE_KEY = original_key


async def test_execute_no_service_key_headers_when_user_absent(registry, httpx_mock):
    """When user is None, do NOT send service-key or user identity headers."""
    httpx_mock.add_response(
        method="GET",
        url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
        json={"sales": []},
    )

    executor = ToolExecutor(registry=registry)
    await executor.execute(
        ToolCall(
            id="tc1",
            name="find_yard_sales",
            arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
        ),
        user=None,
    )

    sent_request = httpx_mock.get_requests()[0]
    assert "x-jain-service-key" not in sent_request.headers
    assert "x-jain-user-email" not in sent_request.headers
    assert "x-jain-user-name" not in sent_request.headers


async def test_execute_handles_unicode_user_name(registry, httpx_mock):
    """Authenticated users with non-ASCII names (CJK, accents, emoji) must
    not crash the tool executor. User identity headers are URL-encoded."""
    from urllib.parse import unquote
    from uuid import uuid4

    from app.config import settings
    from app.models.user import User

    original_key = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = "test-service-key-unicode"

    try:
        httpx_mock.add_response(
            method="GET",
            url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
            json={"sales": []},
        )

        user = User(
            id=uuid4(),
            email="jīm@example.com",
            name="Jīm Shëlly 山田",
            email_verified=True,
            google_sub="g-unicode",
        )

        executor = ToolExecutor(registry=registry)
        result = await executor.execute(
            ToolCall(
                id="tc1",
                name="find_yard_sales",
                arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
            ),
            user=user,
        )

        # Did not crash
        assert json.loads(result.content) == {"sales": []}

        # Headers round-trip correctly when URL-decoded
        sent = httpx_mock.get_requests()[0]
        assert unquote(sent.headers["x-jain-user-email"]) == "jīm@example.com"
        assert unquote(sent.headers["x-jain-user-name"]) == "Jīm Shëlly 山田"
    finally:
        settings.JAIN_SERVICE_KEY = original_key


async def test_execute_skips_user_headers_when_service_key_empty(registry, httpx_mock):
    """When JAIN_SERVICE_KEY is empty, the executor does NOT forward user
    identity headers even for authenticated users — fail safe rather than
    send an empty key header."""
    from uuid import uuid4

    from app.config import settings
    from app.models.user import User

    original_key = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = ""

    try:
        httpx_mock.add_response(
            method="GET",
            url="https://api.yardsailing.sale/api/sales?lat=1.0&lng=2.0&radius_miles=10",
            json={"sales": []},
        )

        user = User(
            id=uuid4(),
            email="jim@example.com",
            name="Jim",
            email_verified=True,
            google_sub="g-empty-key",
        )

        executor = ToolExecutor(registry=registry)
        await executor.execute(
            ToolCall(
                id="tc1",
                name="find_yard_sales",
                arguments={"lat": 1.0, "lng": 2.0, "radius_miles": 10},
            ),
            user=user,
        )

        sent = httpx_mock.get_requests()[0]
        assert "x-jain-service-key" not in sent.headers
        assert "x-jain-user-email" not in sent.headers
        assert "x-jain-user-name" not in sent.headers
    finally:
        settings.JAIN_SERVICE_KEY = original_key


async def test_execute_ui_component_tool_returns_synthetic_result(registry):
    """When tool.ui_component is set, the executor returns a synthetic
    __display_component marker without making any HTTP call. Used for
    client-side UI triggers like 'show the sale form'."""
    from uuid import uuid4
    from app.models.user import User

    _, tool = registry.find_tool("find_yard_sales")
    tool.ui_component = "SaleForm"

    try:
        executor = ToolExecutor(registry=registry)
        result = await executor.execute(
            ToolCall(id="tc1", name="find_yard_sales", arguments={"title": "Big Sale", "address": "123 Main"}),
            user=User(id=uuid4(), email="u@x.com", name="U", email_verified=True, google_sub="g"),
        )
        assert result.tool_call_id == "tc1"
        payload = json.loads(result.content)
        assert payload["__display_component"] == "SaleForm"
        assert payload["__source"] == "jain_executor_ui"
        assert payload["plugin"] == "yardsailing"
        assert payload["initial_data"] == {"title": "Big Sale", "address": "123 Main"}
    finally:
        tool.ui_component = None


async def test_execute_ui_component_tool_works_for_anonymous_user(registry):
    """UI component tools work even for anonymous users (they're client-
    side and don't touch plugin HTTP endpoints, so there's nothing to
    gate). Auth gating only applies to real HTTP tools."""
    _, tool = registry.find_tool("find_yard_sales")
    tool.ui_component = "SaleForm"

    try:
        executor = ToolExecutor(registry=registry)
        result = await executor.execute(
            ToolCall(id="tc1", name="find_yard_sales", arguments={}),
            user=None,
        )
        payload = json.loads(result.content)
        assert payload["__display_component"] == "SaleForm"
    finally:
        tool.ui_component = None
