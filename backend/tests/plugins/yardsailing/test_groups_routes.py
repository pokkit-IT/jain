from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import sign_access_token
from app.database import async_session, engine
from app.main import create_app
from app.models.base import Base
from app.models.user import User


@pytest.fixture
async def client_two_users():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        a = User(id=uuid4(), email="a@b.com", name="A", email_verified=True, google_sub="ga")
        b = User(id=uuid4(), email="b@b.com", name="B", email_verified=True, google_sub="gb")
        s.add_all([a, b])
        await s.commit()
        token_a = sign_access_token(a)
        token_b = sign_access_token(b)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token_a, token_b


async def _create_sale(client, token, *, start="2026-05-02", end="2026-05-03"):
    resp = await client.post(
        "/api/plugins/yardsailing/sales",
        json={
            "title": "s", "address": "1 Main",
            "start_date": start, "end_date": end,
            "start_time": "08:00", "end_time": "17:00",
            "description": None,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_group(client, token, **body):
    resp = await client.post(
        "/api/plugins/yardsailing/groups",
        json={"name": body.pop("name"), **body},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


async def test_create_group_requires_auth(client_two_users):
    c, _, _ = client_two_users
    resp = await c.post("/api/plugins/yardsailing/groups", json={"name": "X"})
    assert resp.status_code == 401


async def test_create_and_get_group(client_two_users):
    c, token_a, _ = client_two_users
    resp = await _create_group(c, token_a, name="100 Mile",
                                start_date="2026-05-01", end_date="2026-05-03")
    assert resp.status_code == 201, resp.text
    gid = resp.json()["id"]
    assert resp.json()["slug"] == "100-mile"
    assert resp.json()["sales_count"] == 0

    detail = await c.get(f"/api/plugins/yardsailing/groups/{gid}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "100 Mile"


async def test_create_group_duplicate_name_conflict(client_two_users):
    c, token_a, _ = client_two_users
    r1 = await _create_group(c, token_a, name="Neighborhood")
    assert r1.status_code == 201
    r2 = await _create_group(c, token_a, name="neighborhood")
    assert r2.status_code == 409


async def test_create_group_bad_dates_422(client_two_users):
    c, token_a, _ = client_two_users
    resp = await _create_group(
        c, token_a, name="Bad", start_date="2026-05-05", end_date="2026-05-01",
    )
    assert resp.status_code == 422


async def test_list_groups_prefix_search(client_two_users):
    c, token_a, _ = client_two_users
    await _create_group(c, token_a, name="100 Mile")
    await _create_group(c, token_a, name="Maple Street")

    resp = await c.get("/api/plugins/yardsailing/groups?q=map")
    assert resp.status_code == 200
    assert [g["name"] for g in resp.json()] == ["Maple Street"]


async def test_set_sale_groups_happy_path(client_two_users):
    c, token_a, _ = client_two_users
    sale_id = await _create_sale(c, token_a)
    gr = await _create_group(c, token_a, name="Fits",
                              start_date="2026-05-01", end_date="2026-05-03")
    gid = gr.json()["id"]

    resp = await c.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/groups",
        json={"group_ids": [gid]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200, resp.text
    assert [g["id"] for g in resp.json()] == [gid]

    # Sale serialization now includes the group
    me = await c.get(
        "/api/plugins/yardsailing/sales",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert me.json()[0]["groups"][0]["id"] == gid


async def test_set_sale_groups_date_mismatch_422(client_two_users):
    c, token_a, _ = client_two_users
    sale_id = await _create_sale(c, token_a, start="2026-06-01", end="2026-06-02")
    gr = await _create_group(c, token_a, name="May Only",
                              start_date="2026-05-01", end_date="2026-05-03")
    gid = gr.json()["id"]

    resp = await c.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/groups",
        json={"group_ids": [gid]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "group_date_mismatch"
    assert resp.json()["detail"]["group_id"] == gid


async def test_set_sale_groups_cross_user_403(client_two_users):
    c, token_a, token_b = client_two_users
    sale_id = await _create_sale(c, token_a)
    gr = await _create_group(c, token_a, name="G")
    gid = gr.json()["id"]

    resp = await c.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/groups",
        json={"group_ids": [gid]},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


async def test_list_sales_recent_group_filter(client_two_users):
    c, token_a, _ = client_two_users
    sale_in = await _create_sale(c, token_a)
    await _create_sale(c, token_a)  # not in group
    gr = await _create_group(c, token_a, name="Only")
    gid = gr.json()["id"]
    await c.post(
        f"/api/plugins/yardsailing/sales/{sale_in}/groups",
        json={"group_ids": [gid]},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp = await c.get(f"/api/plugins/yardsailing/sales/recent?group_id={gid}")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert ids == [sale_in]


async def test_list_group_sales_endpoint(client_two_users):
    c, token_a, _ = client_two_users
    sale_id = await _create_sale(c, token_a)
    gr = await _create_group(c, token_a, name="G")
    gid = gr.json()["id"]
    await c.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/groups",
        json={"group_ids": [gid]},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp = await c.get(f"/api/plugins/yardsailing/groups/{gid}/sales")
    assert resp.status_code == 200
    assert [s["id"] for s in resp.json()] == [sale_id]


async def test_set_sale_groups_replace_and_clear(client_two_users):
    c, token_a, _ = client_two_users
    sale_id = await _create_sale(c, token_a)
    g1 = (await _create_group(c, token_a, name="A")).json()["id"]
    g2 = (await _create_group(c, token_a, name="B")).json()["id"]

    r = await c.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/groups",
        json={"group_ids": [g1, g2]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert {g["id"] for g in r.json()} == {g1, g2}

    r = await c.post(
        f"/api/plugins/yardsailing/sales/{sale_id}/groups",
        json={"group_ids": []},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.json() == []
