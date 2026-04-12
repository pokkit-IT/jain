from app.services.choices import extract_choices


def test_extract_choices_basic():
    reply = "How would you like to proceed?\n[CHOICES]Fill out a form|Let AI help[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert clean == "How would you like to proceed?"
    assert choices == ["Fill out a form", "Let AI help"]


def test_extract_choices_three_options():
    reply = "What next?\n[CHOICES]A|B|C[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert clean == "What next?"
    assert choices == ["A", "B", "C"]


def test_extract_choices_strips_whitespace():
    reply = "Pick one:\n[CHOICES] Option A | Option B [/CHOICES]"
    clean, choices = extract_choices(reply)
    assert choices == ["Option A", "Option B"]


def test_extract_choices_none_when_absent():
    reply = "Just a normal reply with no choices."
    clean, choices = extract_choices(reply)
    assert clean == "Just a normal reply with no choices."
    assert choices is None


def test_extract_choices_malformed_no_closing_tag():
    reply = "Broken [CHOICES]A|B but no end tag"
    clean, choices = extract_choices(reply)
    assert clean == reply
    assert choices is None


def test_extract_choices_empty_pipes_ignored():
    reply = "Pick:\n[CHOICES]A||B|[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert choices == ["A", "B"]


def test_extract_choices_single_option():
    reply = "Only one:\n[CHOICES]Do it[/CHOICES]"
    clean, choices = extract_choices(reply)
    assert choices == ["Do it"]


def test_extract_choices_mid_text():
    reply = "Here are options [CHOICES]A|B[/CHOICES] and more text."
    clean, choices = extract_choices(reply)
    assert clean == "Here are options and more text."
    assert choices == ["A", "B"]
