from __future__ import annotations

import pandas as pd

from cbb_dashboard.intelligence import best_odds_html, dossier_html, evidence_html


def _row(**updates) -> pd.Series:
    base = {
        "Home Team": "Home State",
        "Away Team": "Road Tech",
        "Model Pick": "Home State",
        "Win Probability": 0.621,
        "Fair Spread": -4.5,
        "Fair Moneyline": -164,
        "Availability Verified": True,
        "Neutral Site": False,
        "Data Quality": 82,
        "Margin SD": 13.5,
        "_best_open_spread_home_line": -3.5,
        "_best_open_spread_home_book_title": "DraftKings",
        "_best_current_spread_home_line": -4.5,
        "_best_current_spread_home_price": -110,
        "_best_current_spread_home_book_title": "DraftKings",
        "_best_current_moneyline_home_price": -170,
        "_best_current_moneyline_home_book_title": "DraftKings",
        "_best_close_spread_home_line": float("nan"),
        "Betting Sharp Side": "Home State",
        "Betting Sharp Signal": "sharp_consensus",
        "Betting Sharp Confidence": "strong",
    }
    base.update(updates)
    return pd.Series(base)


def test_primary_market_strip_uses_heating_cooling_language() -> None:
    heating = best_odds_html(_row())
    assert "Market heating on Home State" in heating
    assert "Open -3.5" in heating
    assert "Current -4.5" in heating
    assert "BEST ML NOW" in heating
    assert "MODEL-IMPLIED ODDS" in heating

    cooling = best_odds_html(_row(
        _best_open_spread_home_line=-5.5,
        _best_current_spread_home_line=-4.5,
    ))
    assert "Market cooling on Home State" in cooling


def test_dossier_matches_cfb_plain_english_contract() -> None:
    html = dossier_html(_row())
    assert "Game intelligence dossier" in html
    assert "WHY Home State IS THE PICK" in html
    assert "WHAT COULD GO WRONG" in html
    assert "MODEL = what Stat Factory predicted before sportsbook data was added" in html
    assert "Market information never changes the original model pick" in html


def test_evidence_visually_separates_model_and_market_context() -> None:
    html = evidence_html(_row())
    assert 'evidence-tag model' in html
    assert 'evidence-tag market' in html
    assert "sharp-money signal" in html.lower()
