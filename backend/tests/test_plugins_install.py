import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import sign_access_token
from app.config import settings
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.installed_plugin import InstalledPlugin
from app.models.user import User


@pytest.fixture
async def admin_client():
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


_VALID_MANIFEST = {
    "name": "weather",
    "version": "1.0.0",
    "type": "external",
    "description": "Weather lookup",
    "skills": [],
    "api": {"base_url": "https://weather.example.com"},
}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                "err", request=httpx.Request("GET", "http://x"), response=self,
            )


async def test_install_requires_admin_auth(admin_client):
    client, _ = admin_client
    resp = await client.post(
        "/api/plugins/install",
        json={"manifest_url": "https://weather.example.com/plugin.json", "service_key": "sk"},
    )
    assert resp.status_code == 401


async def test_install_fetches_validates_persists(admin_client):
    client, token = admin_client
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        instance = Mock.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_FakeResponse(200, _VALID_MANIFEST))
        resp = await client.post(
            "/api/plugins/install",
            json={
                "manifest_url": "https://weather.example.com/plugin.json",
                "service_key": "sk-1234",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "weather"

    async with async_session() as s:
        row = await s.get(InstalledPlugin, "weather")
        assert row is not None
        assert row.service_key == "sk-1234"
        assert json.loads(row.manifest_json)["name"] == "weather"


async def test_install_rejects_internal_type(admin_client):
    client, token = admin_client
    manifest = dict(_VALID_MANIFEST)
    manifest["type"] = "internal"
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(200, manifest),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
    assert "internal" in resp.json()["detail"].lower()


async def test_install_rejects_name_collision_with_internal(admin_client):
    client, token = admin_client
    manifest = dict(_VALID_MANIFEST)
    manifest["name"] = "yardsailing"
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(200, manifest),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 409


async def test_install_handles_manifest_fetch_failure(admin_client):
    client, token = admin_client
    with patch("app.routers.plugins_admin.httpx.AsyncClient") as Mock:
        Mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_FakeResponse(404, {"error": "nope"}),
        )
        resp = await client.post(
            "/api/plugins/install",
            json={"manifest_url": "x", "service_key": "k"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
