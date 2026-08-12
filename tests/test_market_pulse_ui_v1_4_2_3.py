import pandas as pd

from cbb_dashboard.intelligence import market_pulse_html


def _row(**updates):
    base = {
        "Home Team": "Duke",
        "_market_source_label": "Owls Insight · DraftKings",
        "_market_latest_snapshot_utc": "2026-03-19T14:55:00Z",
        "_market_current_home_spread": -27.5,
        "_market_opening_home_spread": -27.5,
        "_market_book_agreement": "tight",
        "_market_book_spread_range": 0.5,
        "_market_book_count": 10,
    }
    base.update(updates)
    return pd.Series(base)


def test_tight_consensus_does_not_repeat_narrative_under_consensus_card():
    html = market_pulse_html(_row())
    assert "BOOK CONSENSUS" in html
    assert "Tight" in html
    assert "10 books" in html
    assert "0.5 pt range" in html
    assert "Sportsbooks are tightly aligned on the spread." not in html
    assert 'class="market-pulse-read"' not in html


def test_wide_consensus_keeps_actionable_warning_footer():
    html = market_pulse_html(_row(
        _market_book_agreement="wide",
        _market_book_spread_range=3.0,
    ))
    assert 'class="market-pulse-read"' in html
    assert "Sportsbooks disagree by as much as 3.0 points on the spread." in html


def test_actionable_footer_is_visual_separator_not_large_paragraph():
    from pathlib import Path
    css = (Path(__file__).resolve().parents[1] / "cbb_dashboard" / "ui.py").read_text()
    assert "font-size:.58rem !important" in css
    assert "border-top:1px solid" in css
