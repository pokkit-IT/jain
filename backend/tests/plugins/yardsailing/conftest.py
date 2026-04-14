import pytest


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
