from uuid import uuid4

import pytest

from app.auth.jwt import sign_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def app_and_two_tokens():
    """Two independent users against a fresh DB. Yields (app, token_a, token_b)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        user_a = User(id=uuid4(), email="a@two.com", name="A", email_verified=True, google_sub="ga")
        user_b = User(id=uuid4(), email="b@two.com", name="B", email_verified=True, google_sub="gb")
        s.add_all([user_a, user_b])
        await s.commit()
        token_a = sign_access_token(user_a)
        token_b = sign_access_token(user_b)

    app = create_app()
    yield app, token_a, token_b


@pytest.fixture(autouse=True)
def _stub_geocode(monkeypatch):
    """Prevent tests from hitting the real Nominatim endpoint.

    Individual tests can override by monkeypatching again.
    """
    async def _fake(_address: str):
        return (40.0, -74.0)

    monkeypatch.setattr(
        "app.plugins.yardsailing.services.geocode", _fake,
    )


@pytest.fixture
async def seed_two_sales(app_and_token):
    """Create two sales via the API and return their IDs as strings."""
    client, token = app_and_token
    ids = []
    for i in range(2):
        resp = await client.post(
            "/api/plugins/yardsailing/sales",
            json={
                "title": f"Sale {i}",
                "address": f"Address {i}",
                "start_date": "2026-04-18",
                "start_time": "08:00",
                "end_time": "14:00",
                "description": None,
                "end_date": None,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])
    return ids
