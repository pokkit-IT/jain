from app.plugins.nutrition.schemas import ParsedItem
from app.plugins.nutrition.services import parse_meal_text


def test_parse_quantity_and_plural_noun():
    items = parse_meal_text("2 eggs")
    assert items == [ParsedItem(name="egg", quantity=2.0, unit="piece")]


def test_parse_cup_unit():
    items = parse_meal_text("1 cup oatmeal")
    assert items == [ParsedItem(name="oatmeal", quantity=1.0, unit="cup")]


def test_parse_gram_unit_no_space():
    items = parse_meal_text("100g chicken breast")
    assert items == [ParsedItem(name="chicken breast", quantity=100.0, unit="g")]


def test_parse_gram_unit_with_space():
    items = parse_meal_text("150 g salmon")
    assert items == [ParsedItem(name="salmon", quantity=150.0, unit="g")]


def test_parse_ounce_unit():
    items = parse_meal_text("4 oz steak")
    assert items == [ParsedItem(name="steak", quantity=4.0, unit="oz")]


def test_parse_article_a_or_an():
    items = parse_meal_text("a banana")
    assert items == [ParsedItem(name="banana", quantity=1.0, unit="piece")]
    items2 = parse_meal_text("an apple")
    assert items2 == [ParsedItem(name="apple", quantity=1.0, unit="piece")]


def test_parse_multiple_items_comma_separated():
    items = parse_meal_text("2 eggs, toast, peanut butter")
    names = [i.name for i in items]
    assert names == ["egg", "toast", "peanut butter"]
    assert items[0].quantity == 2.0
    assert items[1].quantity == 1.0
    assert items[2].quantity == 1.0


def test_parse_with_meal_label_prefix():
    items = parse_meal_text("Breakfast: 2 eggs and toast")
    assert [i.name for i in items] == ["egg", "toast"]


def test_parse_and_conjunction():
    items = parse_meal_text("toast with peanut butter")
    assert [i.name for i in items] == ["toast", "peanut butter"]


def test_parse_empty_returns_empty():
    assert parse_meal_text("") == []
    assert parse_meal_text("   ") == []


from app.plugins.nutrition.schemas import FoodMacros
from app.plugins.nutrition.services import calculate_macros


def _food(name="chicken", **overrides):
    defaults = dict(
        name=name,
        calories_per_100g=165.0,
        protein_per_100g=31.0,
        carbs_per_100g=0.0,
        fiber_per_100g=0.0,
        fat_per_100g=3.6,
    )
    defaults.update(overrides)
    return FoodMacros(**defaults)


def test_grams_scale_linearly():
    m = calculate_macros(_food(), quantity=200, unit="g")
    assert m.calories == 330.0
    assert m.protein_g == 62.0
    assert m.fiber_g == 0.0
    assert m.net_carbs_g == 0.0


def test_ounces_convert_to_grams():
    m = calculate_macros(_food(), quantity=4, unit="oz")
    assert round(m.calories, 2) == 187.11
    assert round(m.protein_g, 2) == 35.15


def test_cup_uses_240g():
    m = calculate_macros(
        _food(name="oatmeal", calories_per_100g=68, protein_per_100g=2.4,
              carbs_per_100g=12.0, fiber_per_100g=1.7, fat_per_100g=1.4),
        quantity=1, unit="cup",
    )
    assert round(m.calories, 2) == 163.2


def test_piece_falls_back_to_100g_when_no_serving_size():
    m = calculate_macros(_food(), quantity=2, unit="piece")
    assert m.calories == 330.0


def test_piece_uses_serving_size_g_when_set():
    food = _food(name="egg", calories_per_100g=143, protein_per_100g=12.6,
                 carbs_per_100g=0.7, fiber_per_100g=0.0, fat_per_100g=9.5)
    food.serving_size_g = 50.0
    m = calculate_macros(food, quantity=2, unit="piece")
    assert m.calories == 143.0
    assert round(m.protein_g, 2) == 12.6


def test_net_carbs_subtracts_fiber():
    food = _food(name="broccoli", calories_per_100g=34, protein_per_100g=2.8,
                 carbs_per_100g=7.0, fiber_per_100g=2.6, fat_per_100g=0.4)
    m = calculate_macros(food, quantity=100, unit="g")
    assert m.carbs_g == 7.0
    assert round(m.net_carbs_g, 2) == 4.4
    assert m.fiber_g == 2.6


def test_unknown_unit_falls_back_to_100g():
    m = calculate_macros(_food(), quantity=1, unit="zzz")
    assert m.calories == 165.0
