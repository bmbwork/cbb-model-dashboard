"""Price-first Bottom Line examples; audit metadata is deliberately not an input."""
import pytest
from cbb_dashboard.college_bottom_line import render_bottom_line

def quote(line=-3.5, price=-110):
    return {"line": line, "price": price, "book": "DraftKings", "fresh": True}

@pytest.mark.parametrize("fair,line,expected", [
    (-3, -3.5, "I'd wait for a better number"),
    (-3, -3, "I'd proceed cautiously"),
    (-3, -2.5, "I'd proceed cautiously"),
    (-7, -3.5, "I lean toward Ohio State at -3.5"),
    (3, 6, "I lean toward Ohio State at +6.0"),
    (0, 0, "I'd proceed cautiously"),
])
def test_personal_price_comparison_cases(fair, line, expected):
    text = render_bottom_line("Ohio State", fair, .6, quote(line))
    assert expected in text
    assert "DraftKings currently quotes Ohio State" in text
    assert "Check splits and line movement before wagering." in text
    assert not any(word in text.lower() for word in ("historical", "timing", "unverified", "pass", "deployment"))

def test_requested_ohio_state_example_has_the_actual_model_and_book_numbers():
    text = render_bottom_line("Ohio State", -3, .6, quote())
    assert "a 3.0-point favorite" in text and "Ohio State -3.5 (-110)" in text
    assert "I don't see an edge from the spread difference alone" in text

def test_missing_quote_is_explicit_without_inventing_a_price():
    text = render_bottom_line("Ohio State", -3, .6)
    assert "I can't judge the betting value until a sportsbook price is reported" in text
    assert "DraftKings" not in text

def test_moneyline_lean_uses_real_price_and_win_probability():
    text = render_bottom_line("Ohio State", -3, .6, moneyline=quote(None, 150))
    assert "I lean toward Ohio State moneyline at +150 (DraftKings)" in text
    assert "60.0% win chance" in text and "40.0% break-even" in text

def test_moneyline_can_have_value_without_a_spread_edge():
    text = render_bottom_line("Ohio State", -3, .6, quote(), quote(None, 150))
    assert "spread alone, but I lean toward Ohio State moneyline" in text

def test_old_quote_is_compared_without_being_called_current():
    q = quote(); q["fresh"] = False
    text = render_bottom_line("Ohio State", -3, .6, q)
    assert "DraftKings quotes Ohio State -3.5" in text
    assert "currently" not in text and "wait for a better number" in text
