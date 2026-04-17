from app.plugins.nutrition.schemas import (
    FoodMacros,
    ItemMacros,
    ParsedItem,
    envelope,
)


def test_parsed_item_defaults():
    item = ParsedItem(name="egg", quantity=2, unit="piece")
    assert item.name == "egg"
    assert item.quantity == 2
    assert item.unit == "piece"


def test_food_macros_construct():
    m = FoodMacros(
        name="egg", calories_per_100g=143, protein_per_100g=12.6,
        carbs_per_100g=0.7, fiber_per_100g=0.0, fat_per_100g=9.5,
        source="usda", usda_fdc_id="123",
    )
    assert m.name == "egg"
    assert m.source == "usda"


def test_item_macros_construct():
    im = ItemMacros(
        name="egg", quantity=2, unit="piece",
        calories=140, protein_g=12, carbs_g=1, net_carbs_g=1,
        fat_g=10, fiber_g=0, food_source="usda",
    )
    assert im.calories == 140


def test_envelope_ok():
    e = envelope(status="ok", data={"x": 1}, message="done")
    assert e == {"status": "ok", "data": {"x": 1}, "message": "done", "next_action": "none"}


def test_envelope_error():
    e = envelope(status="error", message="nope")
    assert e["status"] == "error"
    assert e["data"] == {}
    assert e["next_action"] == "none"
