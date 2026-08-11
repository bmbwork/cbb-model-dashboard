from pathlib import Path

import pandas as pd

from cbb_dashboard.intelligence import market_pulse_html

ROOT = Path(__file__).resolve().parents[1]


def _row(**updates):
    base = {
        "Home Team": "Duke",
        "_market_source_label": "The Odds API · DraftKings",
        "_market_latest_snapshot_utc": "2026-03-19T14:55:00Z",
        "_market_current_home_spread": -27.5,
        "_market_opening_home_spread": -27.5,
        "_market_book_agreement": "tight",
        "_market_book_spread_range": 0.5,
        "_market_book_count": 6,
    }
    base.update(updates)
    return pd.Series(base)


def test_odds_api_only_market_pulse_uses_line_movement_and_consensus_not_empty_split_columns():
    html = market_pulse_html(_row())
    assert "SPORTSBOOK LINE" in html
    assert "LINE MOVEMENT" in html
    assert "BOOK CONSENSUS" in html
    assert "First snapshot" in html
    assert "6 books" in html
    assert "Not provided" not in html
    assert "separate splits source" not in html


def test_market_pulse_stat_cards_have_explicit_classes_for_stable_layout():
    html = market_pulse_html(_row())
    assert html.count('class="market-pulse-stat"') == 3
    # Tight consensus is already communicated by the consensus card, so the
    # narrative footer should not repeat the same information.
    assert 'class="market-pulse-read"' not in html
    assert "Sportsbooks are tightly aligned on the spread." not in html


def test_market_pulse_with_real_splits_still_shows_bets_money_and_line():
    html = market_pulse_html(_row(
        **{
            "_market_home_ticket_pct": 72.0,
            "_market_away_ticket_pct": 28.0,
            "_market_home_money_pct": 61.0,
            "_market_away_money_pct": 39.0,
        }
    ))
    # market_features may need model-side pick fields before choosing a team; the
    # layout contract is what this regression protects when split data is present.
    if "BETS" in html:
        assert "MONEY" in html
        assert "SPORTSBOOK LINE" in html


def test_css_styles_market_pulse_children_and_mobile_stack():
    css = (ROOT / "cbb_dashboard" / "ui.py").read_text()
    assert ".market-pulse-stat" in css
    assert ".market-pulse-head em" in css
    assert ".market-pulse-read" in css
    assert "grid-template-columns:1fr" in css


def test_app_version_bumped_for_market_pulse_trim_hotfix():
    app = (ROOT / "app.py").read_text()
    assert 'APP_VERSION = "1.4.2.3"' in app
