import pytest

from tests.plugins.yardsailing.conftest import app_and_two_tokens


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
async def test_schedule_crud_and_exception(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/plugins/custody/schedules",
        json={
            "child_id": cid, "name": "EOW Fri-Sun",
            "start_date": "2026-01-02", "interval_weeks": 2,
            "weekdays": "4,5,6",
            "pickup_time": "17:00", "dropoff_time": "19:00",
        },
        headers=h,
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    r = await client.patch(
        f"/api/plugins/custody/schedules/{sid}",
        json={"name": "EOW weekends"}, headers=h,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "EOW weekends"

    r = await client.post(
        f"/api/plugins/custody/schedules/{sid}/exceptions",
        json={"date": "2026-02-20", "kind": "skip"},
        headers=h,
    )
    assert r.status_code == 201
    xid = r.json()["id"]

    r = await client.get("/api/plugins/custody/schedules", headers=h)
    assert len(r.json()) == 1
    assert len(r.json()[0]["exceptions"]) == 1

    r = await client.delete(
        f"/api/plugins/custody/schedules/exceptions/{xid}", headers=h,
    )
    assert r.status_code == 204

    r = await client.delete(f"/api/plugins/custody/schedules/{sid}", headers=h)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_schedule_rejects_bad_weekdays(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/api/plugins/custody/schedules",
        json={
            "child_id": cid, "name": "bad",
            "start_date": "2026-01-02", "interval_weeks": 1,
            "weekdays": "9", "pickup_time": "17:00", "dropoff_time": "19:00",
        },
        headers=h,
    )
    assert r.status_code == 400
