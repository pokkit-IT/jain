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


async def test_post_sales_requires_auth(app_and_token):
    client, _ = app_and_token
    resp = await client.post("/api/plugins/yardsailing/sales", json={
        "title": "s", "address": "a",
        "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
    })
    assert resp.status_code == 401


async def test_post_sales_creates_row(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Big Sale", "address": "123 Main",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Big Sale"
    assert "id" in body


async def test_post_sales_returns_geocoded_coords(app_and_token):
    client, token = app_and_token
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Pinned", "address": "123 Main",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    # The conftest autouse stub returns (40.0, -74.0).
    assert body["lat"] == 40.0
    assert body["lng"] == -74.0


async def test_recent_sales_is_public_and_returns_pins(app_and_token):
    client, token = app_and_token
    await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Public Pin", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/plugins/yardsailing/sales/recent")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["lat"] == 40.0
    assert rows[0]["lng"] == -74.0


async def test_delete_sale_removes_row(app_and_token):
    client, token = app_and_token
    created = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Gone", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    sale_id = created.json()["id"]

    resp = await client.delete(
        f"/api/plugins/yardsailing/sales/{sale_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    missing = await client.get(f"/api/plugins/yardsailing/sales/{sale_id}")
    assert missing.status_code == 404


async def test_update_sale_changes_fields_and_regeocodes(app_and_token):
    client, token = app_and_token
    created = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "Old Title", "address": "old addr",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    sale_id = created.json()["id"]

    resp = await client.put(
        f"/api/plugins/yardsailing/sales/{sale_id}",
        json={
            "title": "New Title", "address": "new addr",
            "start_date": "2026-04-19", "start_time": "09:00", "end_time": "15:00",
            "description": "updated", "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "New Title"
    assert body["address"] == "new addr"
    # Stubbed geocode returns (40.0, -74.0)
    assert body["lat"] == 40.0
    assert body["lng"] == -74.0


async def test_get_my_sales_lists_own_rows(app_and_token):
    client, token = app_and_token
    await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "One", "address": "a",
            "start_date": "2026-04-18", "start_time": "08:00", "end_time": "14:00",
            "description": None, "end_date": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        "/api/plugins/yardsailing/sales",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["title"] == "One"
