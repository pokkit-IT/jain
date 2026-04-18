import httpx
import pytest

from app.plugins.nutrition import usda
from app.plugins.nutrition.schemas import FoodMacros


USDA_RESPONSE_OK = {
    "foods": [
        {
            "fdcId": 171287,
            "description": "Egg, whole, raw, fresh",
            "servingSize": 50,
            "servingSizeUnit": "g",
            "foodNutrients": [
                {"nutrientName": "Energy", "unitName": "KCAL", "value": 143.0},
                {"nutrientName": "Protein", "unitName": "G", "value": 12.6},
                {"nutrientName": "Carbohydrate, by difference", "unitName": "G", "value": 0.7},
                {"nutrientName": "Total lipid (fat)", "unitName": "G", "value": 9.5},
                {"nutrientName": "Fiber, total dietary", "unitName": "G", "value": 0.0},
            ],
        }
    ]
}

USDA_RESPONSE_BRANDED = {
    "foods": [
        {
            "fdcId": 2345678,
            "description": "MCDONALD'S, Sausage Biscuit with Egg",
            "dataType": "Branded Food",
            "servingSize": 200,
            "servingSizeUnit": "g",
            "foodNutrients": [
                # Values are per serving (200 g), not per 100 g.
                {"nutrientName": "Energy", "unitName": "KCAL", "value": 500.0},
                {"nutrientName": "Protein", "unitName": "G", "value": 18.0},
                {"nutrientName": "Carbohydrate, by difference", "unitName": "G", "value": 38.0},
                {"nutrientName": "Total lipid (fat)", "unitName": "G", "value": 32.0},
                {"nutrientName": "Fiber, total dietary", "unitName": "G", "value": 2.0},
            ],
        }
    ]
}

USDA_RESPONSE_EMPTY = {"foods": []}


def _mock_transport(payload):
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)
    return httpx.MockTransport(_handler)


async def test_fetch_usda_food_parses_nutrients(monkeypatch):
    monkeypatch.setattr(
        usda, "_build_client",
        lambda: httpx.AsyncClient(transport=_mock_transport(USDA_RESPONSE_OK)),
    )
    result = await usda.fetch_usda_food("egg")
    assert isinstance(result, FoodMacros)
    assert result.name == "Egg, whole, raw, fresh"
    assert result.calories_per_100g == 143.0
    assert result.protein_per_100g == 12.6
    assert result.carbs_per_100g == 0.7
    assert result.fat_per_100g == 9.5
    assert result.fiber_per_100g == 0.0
    assert result.usda_fdc_id == "171287"
    assert result.serving_size_g == 50.0
    assert result.source == "usda"


async def test_fetch_usda_food_normalises_branded_food_to_per_100g(monkeypatch):
    """Branded foods report nutrients per serving; we must divide by servingSize/100."""
    monkeypatch.setattr(
        usda, "_build_client",
        lambda: httpx.AsyncClient(transport=_mock_transport(USDA_RESPONSE_BRANDED)),
    )
    result = await usda.fetch_usda_food("mcdonald's sausage biscuit with egg")
    assert isinstance(result, FoodMacros)
    assert result.serving_size_g == 200.0
    # 500 kcal per 200 g serving → 250 kcal per 100 g
    assert result.calories_per_100g == 250.0
    assert result.protein_per_100g == 9.0
    assert result.carbs_per_100g == 19.0
    assert result.fat_per_100g == 16.0
    assert result.fiber_per_100g == 1.0


@pytest.mark.parametrize("name,expected", [
    ("mcdonald's biscuit", True),
    ("wendy's frosty", True),
    ("arby's roast beef", True),
    ("sausage patty", False),
    ("scrambled eggs", False),
    ("chicken breast", False),
])
def test_looks_branded(name, expected):
    assert usda._looks_branded(name) is expected


async def test_fetch_usda_food_sends_datatype_filter_for_branded(monkeypatch):
    """When the name contains a brand possessive, the USDA request includes dataType=Branded Food."""
    captured: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=USDA_RESPONSE_BRANDED)

    monkeypatch.setattr(
        usda, "_build_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
    )
    await usda.fetch_usda_food("mcdonald's biscuit")
    assert len(captured) == 1
    assert "Branded+Food" in str(captured[0].url) or "Branded Food" in str(captured[0].url)


async def test_fetch_usda_food_no_datatype_filter_for_generic(monkeypatch):
    """Generic food names do not get a dataType filter."""
    captured: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=USDA_RESPONSE_OK)

    monkeypatch.setattr(
        usda, "_build_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
    )
    await usda.fetch_usda_food("sausage patty")
    assert len(captured) == 1
    assert "dataType" not in str(captured[0].url)


async def test_fetch_usda_food_returns_none_on_empty(monkeypatch):
    monkeypatch.setattr(
        usda, "_build_client",
        lambda: httpx.AsyncClient(transport=_mock_transport(USDA_RESPONSE_EMPTY)),
    )
    result = await usda.fetch_usda_food("asdfghjklzxcv")
    assert result is None


async def test_fetch_usda_food_returns_none_on_http_error(monkeypatch):
    def _err_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream boom")
    monkeypatch.setattr(
        usda, "_build_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(_err_handler)),
    )
    result = await usda.fetch_usda_food("egg")
    assert result is None


async def test_fetch_usda_food_returns_none_on_network_error(monkeypatch):
    class _BoomClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k):
            raise httpx.ConnectError("nope")
    monkeypatch.setattr(usda, "_build_client", lambda: _BoomClient())
    result = await usda.fetch_usda_food("egg")
    assert result is None
