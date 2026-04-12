from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.jwt import sign_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale


@pytest.fixture
async def client_and_token():
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
        user_id = user.id

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token, user_id


async def test_form_submission_creates_sale_row(client_and_token):
    """Simulates mobile SaleForm flow:
    PluginBridge.callPluginApi → /api/plugins/yardsailing/call →
    internal ASGI sub-request → yardsailing /sales route →
    Sale row persisted."""
    client, token, user_id = client_and_token

    resp = await client.post(
        "/api/plugins/yardsailing/call",
        json={
            "method": "POST",
            "path": "/api/plugins/yardsailing/sales",
            "body": {
                "title": "Garage Cleanout", "address": "500 Elm",
                "description": "Tools and furniture",
                "start_date": "2026-05-02", "end_date": "2026-05-02",
                "start_time": "07:00", "end_time": "13:00",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text

    async with async_session() as s:
        rows = (await s.execute(select(Sale))).scalars().all()
        assert len(rows) == 1
        assert rows[0].title == "Garage Cleanout"
        assert rows[0].owner_id == user_id


async def test_bundle_endpoint_serves_yardsailing_js(client_and_token):
    """The /api/plugins/yardsailing/bundle endpoint should serve the
    compiled UI bundle built in Task 22."""
    client, token, _ = client_and_token
    resp = await client.get("/api/plugins/yardsailing/bundle")
    assert resp.status_code == 200
    # The bundle was built by Task 22, so it should contain the compiled
    # SaleForm export identifier.
    assert "SaleForm" in resp.text
