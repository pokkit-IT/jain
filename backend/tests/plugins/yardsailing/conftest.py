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
