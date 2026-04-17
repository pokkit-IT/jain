import io

import pytest
from PIL import Image

from tests.plugins.yardsailing.conftest import app_and_two_tokens


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (10, 10, 200)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
async def client_token_child(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token, _ = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token}"},
        )
        yield c, token, r.json()["id"]


@pytest.mark.asyncio
async def test_event_crud(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "pickup",
            "occurred_at": "2026-01-02T17:00:00",
            "notes": "school", "overnight": True,
        },
        headers=h,
    )
    assert r.status_code == 201
    eid = r.json()["id"]
    assert r.json()["overnight"] is True

    r_bad = await client.post(
        "/api/plugins/custody/events",
        json={"child_id": cid, "type": "expense"},
        headers=h,
    )
    assert r_bad.status_code == 400

    r_patch = await client.patch(
        f"/api/plugins/custody/events/{eid}",
        json={"notes": "school bus"}, headers=h,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["notes"] == "school bus"

    r_list = await client.get(
        f"/api/plugins/custody/events?child_id={cid}&type=pickup", headers=h,
    )
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    r_del = await client.delete(f"/api/plugins/custody/events/{eid}", headers=h)
    assert r_del.status_code == 204


@pytest.mark.asyncio
async def test_event_photo_upload_and_delete(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "expense",
            "occurred_at": "2026-01-02T12:00:00",
            "amount_cents": 4250, "category": "activity", "notes": "bowling",
        },
        headers=h,
    )
    eid = r.json()["id"]

    r_up = await client.post(
        f"/api/plugins/custody/events/{eid}/photos",
        files={"file": ("receipt.jpg", _jpeg(), "image/jpeg")},
        headers=h,
    )
    assert r_up.status_code == 200
    pid = r_up.json()["id"]

    r_del = await client.delete(
        f"/api/plugins/custody/events/{eid}/photos/{pid}", headers=h,
    )
    assert r_del.status_code == 204


@pytest.mark.asyncio
async def test_events_owner_scope(app_and_two_tokens):
    from httpx import ASGITransport, AsyncClient
    app, token_a, token_b = app_and_two_tokens
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/plugins/custody/children", json={"name": "Mason"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        cid = r.json()["id"]
        re = await client.post(
            "/api/plugins/custody/events",
            json={
                "child_id": cid, "type": "note",
                "occurred_at": "2026-01-02T12:00:00", "notes": "private",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        eid = re.json()["id"]

        r_get = await client.get(
            f"/api/plugins/custody/events?child_id={cid}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r_get.json() == []
        r_patch = await client.patch(
            f"/api/plugins/custody/events/{eid}", json={"notes": "hacked"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r_patch.status_code == 404
