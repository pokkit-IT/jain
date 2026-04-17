import pytest

from tests.plugins.yardsailing.conftest import app_and_two_tokens  # reuse fixture


@pytest.fixture
async def client_and_token(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token_a, _ = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, token_a


@pytest.mark.asyncio
async def test_child_create_list_update_delete(client_and_token):
    client, token = client_and_token
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/plugins/custody/children",
        json={"name": "Mason", "dob": "2020-08-12"},
        headers=headers,
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    r = await client.get("/api/plugins/custody/children", headers=headers)
    assert r.status_code == 200
    assert [c["name"] for c in r.json()] == ["Mason"]

    r = await client.patch(
        f"/api/plugins/custody/children/{cid}",
        json={"name": "Mason R"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Mason R"

    r = await client.delete(f"/api/plugins/custody/children/{cid}", headers=headers)
    assert r.status_code == 204
    r = await client.get("/api/plugins/custody/children", headers=headers)
    assert r.json() == []


@pytest.mark.asyncio
async def test_children_owner_scope(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token_a, token_b = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ra = await client.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert ra.status_code == 201
        cid = ra.json()["id"]

        rb = await client.get(
            "/api/plugins/custody/children",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert rb.json() == []

        rb_patch = await client.patch(
            f"/api/plugins/custody/children/{cid}", json={"name": "hacked"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert rb_patch.status_code == 404
