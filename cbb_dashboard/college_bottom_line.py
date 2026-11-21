"""Personal college price comparisons. Forecast audit flags are not betting advice."""
from __future__ import annotations


def _signed(value):
    return f"{value:+.1f}"


def _model(team, fair, chance):
    if fair is not None:
        if fair < 0:
            return f"The model makes {team} a {abs(fair):.1f}-point favorite"
        if fair > 0:
            return f"The model has {team} as a {fair:.1f}-point underdog"
        return f"The model has {team} at pick'em"
    if chance is not None and 0 <= chance <= 1:
        return f"The model gives {team} a {chance * 100:.1f}% chance to win"
    return f"A model line or win probability is not reported for {team}"


def render_bottom_line(team, fair, chance, spread=None, moneyline=None, *, minimum_gap=1.5):
    """Use a named, paired quote; never infer a price or a cover probability."""
    model = _model(team, fair, chance)
    closing = " Check splits and line movement before wagering."
    gap = spread["line"] - fair if spread and fair is not None else None
    if spread:
        current = "currently " if spread.get("fresh") else ""
        comparison = f"{model}, while {spread['book']} {current}quotes {team} {_signed(spread['line'])} ({spread['price']:+.0f})."
    else:
        comparison = model + "."
    ml_edge = None
    if moneyline and chance is not None and 0 <= chance <= 1:
        price = moneyline["price"]
        implied = 100 / (price + 100) if price > 0 else -price / (100 - price)
        ml_edge = chance - implied
    cautious = " This is a close matchup, so I'd keep that lean cautious." if chance is not None and chance < .65 else ""
    if gap is not None and gap >= minimum_gap and spread["price"] >= -120:
        return comparison + f" I lean toward {team} at {_signed(spread['line'])} because the book gives us {gap:.1f} more points than the model line." + cautious + closing
    if ml_edge is not None and ml_edge >= .03:
        prefix = " I don't see enough value from the spread alone, but" if spread else ""
        play = f" I lean toward {team} moneyline at {moneyline['price']:+.0f} ({moneyline['book']}); the model's {chance * 100:.1f}% win chance is above the price's {implied * 100:.1f}% break-even rate."
        if prefix:
            play = prefix + play
        return comparison + play + cautious + closing
    if gap is not None and gap < -.01:
        return comparison + " I don't see an edge from the spread difference alone, so I'd wait for a better number." + closing
    if gap is not None:
        return comparison + " I don't see enough value from the spread difference alone, so I'd proceed cautiously." + closing
    if moneyline:
        return comparison + f" {moneyline['book']} quotes {team} moneyline at {moneyline['price']:+.0f}. I don't see enough value at that price, so I'd wait for a better one." + closing
    if spread:
        return comparison + " I can't compare that spread with a reported model line yet." + closing
    return comparison + " I can't judge the betting value until a sportsbook price is reported." + closing
