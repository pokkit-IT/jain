import pytest

from app.plugins.yardsailing.geocoding import geocode


@pytest.fixture(autouse=True)
def _unstub(monkeypatch):
    # Override the autouse stub from conftest — these tests exercise the real helper.
    monkeypatch.setattr(
        "app.plugins.yardsailing.services.geocode",
        __import__("app.plugins.yardsailing.geocoding", fromlist=["geocode"]).geocode,
    )


async def test_geocode_returns_coords_when_found(httpx_mock):
    httpx_mock.add_response(
        url="https://nominatim.openstreetmap.org/search?q=1+Infinite+Loop&format=json&limit=1",
        json=[{"lat": "37.33182", "lon": "-122.03118"}],
    )
    result = await geocode("1 Infinite Loop")
    assert result == (37.33182, -122.03118)


async def test_geocode_returns_none_on_no_match(httpx_mock):
    httpx_mock.add_response(
        url="https://nominatim.openstreetmap.org/search?q=zzzz&format=json&limit=1",
        json=[],
    )
    assert await geocode("zzzz") is None


async def test_geocode_returns_none_on_http_error(httpx_mock):
    httpx_mock.add_response(
        url="https://nominatim.openstreetmap.org/search?q=x&format=json&limit=1",
        status_code=500,
    )
    assert await geocode("x") is None


async def test_geocode_returns_none_for_empty_address():
    assert await geocode("") is None
    assert await geocode("   ") is None
