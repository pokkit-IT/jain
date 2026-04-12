"""End-to-end integration test: install → call → uninstall an external plugin.

Uses in-process httpx mocking so no real network calls are made.
"""
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import sign_access_token
from app.config import settings
from app.database import async_session, engine
from app.dependencies import reset_registry_for_tests
from app.main import create_app
from app.models.base import Base
from app.models.installed_plugin import InstalledPlugin
from app.models.user import User
from tests.fixtures.fake_external_plugin import FAKE_MANIFEST


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, *, content_type: str = "application/json"):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")
        self.headers = {"content-type": content_type}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err", request=httpx.Request("GET", "http://x"), response=self,
            )


@pytest.fixture
async def admin_client():
    reset_registry_for_tests()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as s:
        user = User(
            id=uuid4(), email="admin@example.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = sign_access_token(user)

    orig = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com"
    app = create_app()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, token
    finally:
        settings.JAIN_ADMIN_EMAILS = orig
        reset_registry_for_tests()


async def test_install_call_uninstall_e2e(admin_client):
    client, token = admin_client
    auth = {"Authorization": f"Bearer {token}"}

    # Step 1: Install fake_weather via POST /api/plugins/install
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as MockAdmin:
        instance = MockAdmin.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_FakeResponse(200, FAKE_MANIFEST))
        resp = await client.post(
            "/api/plugins/install",
            json={
                "manifest_url": "https://fake-weather.test/plugin.json",
                "service_key": "sk-fake",
            },
            headers=auth,
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "fake_weather"
    assert "get_weather" in body["tools"]

    # Step 2: Verify it appears in GET /api/plugins
    resp = await client.get("/api/plugins")
    assert resp.status_code == 200
    plugin_names = [p["name"] for p in resp.json()["plugins"]]
    assert "fake_weather" in plugin_names

    # Step 3: Call it via POST /api/plugins/fake_weather/call
    with patch("app.routers.plugins.httpx.AsyncClient") as MockProxy:
        proxy_instance = MockProxy.return_value.__aenter__.return_value
        proxy_resp = _FakeResponse(200, {"temp_c": 22})
        proxy_instance.get = AsyncMock(return_value=proxy_resp)
        proxy_instance.request = AsyncMock(return_value=proxy_resp)
        resp = await client.post(
            "/api/plugins/fake_weather/call",
            json={"method": "GET", "path": "/weather", "body": None},
            headers=auth,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["temp_c"] == 22

    # Step 4: Uninstall via DELETE /api/plugins/fake_weather
    resp = await client.delete(
        "/api/plugins/fake_weather",
        headers=auth,
    )
    assert resp.status_code == 204

    # Verify removed from DB
    async with async_session() as s:
        row = await s.get(InstalledPlugin, "fake_weather")
        assert row is None

    # Step 5: Verify it no longer appears in GET /api/plugins
    resp = await client.get("/api/plugins")
    assert resp.status_code == 200
    plugin_names = [p["name"] for p in resp.json()["plugins"]]
    assert "fake_weather" not in plugin_names
