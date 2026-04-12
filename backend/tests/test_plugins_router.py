from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import sign_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def app_and_token_for_yardsailing():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = sign_access_token(user)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token


async def test_plugin_call_dispatches_internal_with_auth(app_and_token_for_yardsailing):
    client, token = app_and_token_for_yardsailing
    resp = await client.post(
        "/api/plugins/yardsailing/call",
        json={
            "method": "POST", "path": "/api/plugins/yardsailing/sales",
            "body": {
                "title": "Via Proxy", "address": "1 A",
                "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
                "description": None, "end_date": None,
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["title"] == "Via Proxy"
