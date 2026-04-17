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
async def test_status_no_schedule(client_token_child):
    client, token, cid = client_token_child
    r = await client.get(
        f"/api/plugins/custody/status?child_id={cid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "no_schedule"


@pytest.mark.asyncio
async def test_summary_empty_month(client_token_child):
    client, token, cid = client_token_child
    r = await client.get(
        f"/api/plugins/custody/summary?child_id={cid}&month=2026-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["visits_count"] == 0
    assert data["total_expense_cents"] == 0


@pytest.mark.asyncio
async def test_refresh_missed_returns_count(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/plugins/custody/schedules",
        json={
            "child_id": cid, "name": "wk",
            "start_date": "2026-01-02", "interval_weeks": 1, "weekdays": "4",
            "pickup_time": "17:00", "dropoff_time": "19:00",
        },
        headers=h,
    )
    r = await client.post(
        f"/api/plugins/custody/schedules/refresh-missed?child_id={cid}&up_to=2026-01-10",
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["new_rows"] == 2


@pytest.mark.asyncio
async def test_export_csv_endpoint(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "note",
            "occurred_at": "2026-01-05T10:00:00", "notes": "hi",
        },
        headers=h,
    )
    r = await client.get(
        f"/api/plugins/custody/export?child_id={cid}"
        f"&from=2026-01-01T00:00:00&to=2026-01-31T23:59:59&format=csv",
        headers=h,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert b"occurred_at" in r.content


@pytest.mark.asyncio
async def test_export_pdf_endpoint(client_token_child):
    client, token, cid = client_token_child
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/plugins/custody/events",
        json={
            "child_id": cid, "type": "note",
            "occurred_at": "2026-01-05T10:00:00", "notes": "hi",
        },
        headers=h,
    )
    r = await client.get(
        f"/api/plugins/custody/export?child_id={cid}"
        f"&from=2026-01-01T00:00:00&to=2026-01-31T23:59:59&format=pdf",
        headers=h,
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
