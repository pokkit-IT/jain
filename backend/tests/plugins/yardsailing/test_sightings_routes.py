from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import sign_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User
from app.plugins.yardsailing.models import Sale


@pytest.fixture
async def app_and_token():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as s:
        user = User(
            id=uuid4(), email="a@b.com", name="A",
            email_verified=True, google_sub="g",
        )
        s.add(user)
        await s.commit()
        token = sign_access_token(user)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token


async def test_drop_sighting_requires_auth(app_and_token):
    c, _ = app_and_token
    resp = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.0, "lng": -74.0, "now_hhmm": "10:00"},
    )
    assert resp.status_code == 401


async def test_drop_sighting_creates_unconfirmed(app_and_token):
    c, token = app_and_token
    resp = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.0, "lng": -74.0, "now_hhmm": "10:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "sighting"
    assert body["confirmations"] == 1
    assert body["title"] == "Unconfirmed sale"


async def test_second_drop_bumps_to_confirmed(app_and_token):
    c, token = app_and_token
    hdr = {"Authorization": f"Bearer {token}"}
    r1 = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.0, "lng": -74.0, "now_hhmm": "10:00"},
        headers=hdr,
    )
    assert r1.status_code == 201
    first_id = r1.json()["id"]

    r2 = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.00027, "lng": -74.0, "now_hhmm": "10:01"},
        headers=hdr,
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == first_id
    assert r2.json()["confirmations"] == 2


async def test_drop_rejected_after_cutoff(app_and_token):
    c, token = app_and_token
    resp = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.0, "lng": -74.0, "now_hhmm": "17:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "drop_window_closed"


async def test_drop_invalid_coords_422(app_and_token):
    c, token = app_and_token
    resp = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 999.0, "lng": -74.0, "now_hhmm": "10:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_expired_unconfirmed_hidden_from_recent(app_and_token):
    c, token = app_and_token
    hdr = {"Authorization": f"Bearer {token}"}
    # Create a sighting via the endpoint.
    r = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.0, "lng": -74.0, "now_hhmm": "10:00"},
        headers=hdr,
    )
    sale_id = r.json()["id"]

    # Reach into the DB and backdate created_at past the TTL.
    async with async_session() as s:
        sale = await s.get(Sale, sale_id)
        assert sale is not None
        sale.created_at = datetime.now() - timedelta(hours=3)
        await s.commit()

    recent = await c.get("/api/plugins/yardsailing/sales/recent")
    assert recent.status_code == 200
    ids = [x["id"] for x in recent.json()]
    assert sale_id not in ids


async def test_confirmed_sighting_still_listed(app_and_token):
    c, token = app_and_token
    hdr = {"Authorization": f"Bearer {token}"}
    r1 = await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.0, "lng": -74.0, "now_hhmm": "10:00"},
        headers=hdr,
    )
    sale_id = r1.json()["id"]
    await c.post(
        "/api/plugins/yardsailing/sightings",
        json={"lat": 40.0, "lng": -74.0, "now_hhmm": "10:01"},
        headers=hdr,
    )

    # Backdate past TTL; confirmed sighting should still appear.
    async with async_session() as s:
        sale = await s.get(Sale, sale_id)
        sale.created_at = datetime.now() - timedelta(hours=3)
        await s.commit()

    recent = await c.get("/api/plugins/yardsailing/sales/recent")
    ids = [x["id"] for x in recent.json()]
    assert sale_id in ids
