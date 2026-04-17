from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import sign_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def app_and_token():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as s:
        u = User(
            id=uuid4(), email="r@nut.com", name="R",
            email_verified=True, google_sub="gr",
        )
        s.add(u)
        await s.commit()
        token = sign_access_token(u)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, token


async def test_get_profile_returns_defaults_for_new_user(app_and_token):
    client, token = app_and_token
    r = await client.get(
        "/api/plugins/nutrition/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["calorie_target"] == 2000
    assert body["protein_g"] == 150


async def test_profile_requires_auth(app_and_token):
    client, _ = app_and_token
    r = await client.get("/api/plugins/nutrition/profile")
    assert r.status_code == 401


async def test_list_meals_today_empty_initially(app_and_token):
    client, token = app_and_token
    r = await client.get(
        "/api/plugins/nutrition/meals/today",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"meals": []}


async def test_list_day_summaries_empty_initially(app_and_token):
    client, token = app_and_token
    r = await client.get(
        "/api/plugins/nutrition/day-summaries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"day_summaries": []}
