import pandas as pd

from cbb_dashboard.premium_ui_patch import premium_betting_splits_html


def test_premium_split_panel_uses_money_bar_with_ticket_context():
    row = pd.Series({
        "Away Team": "Michigan",
        "Home Team": "Oklahoma",
        "_market_current_away_spread": 5.5,
        "_market_current_home_spread": -5.5,
        "_market_away_money_pct": 20,
        "_market_home_money_pct": 80,
        "_market_away_ticket_pct": 15,
        "_market_home_ticket_pct": 85,
        "_market_ml_away_money_pct": 25,
        "_market_ml_home_money_pct": 75,
        "_market_ml_away_ticket_pct": 10,
        "_market_ml_home_ticket_pct": 90,
        "_market_total_over_money_pct": 21,
        "_market_total_under_money_pct": 79,
        "_market_total_over_ticket_pct": 66,
        "_market_total_under_ticket_pct": 34,
        "_market_total_line": 43.5,
        "_market_split_source_label": "DraftKings",
    })
    html = premium_betting_splits_html(row)
    assert "SPREAD MONEY" in html
    assert "MONEYLINE MONEY" in html
    assert "TOTAL MONEY" in html
    assert "Tickets:" in html
    assert html.count("cbb-money-bar") == 3
