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
