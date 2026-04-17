import httpx

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
