from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from cbb_dashboard.intelligence import market_pulse_html, signal_readout
from cbb_dashboard.owlsinsight_provider import OwlsInsightConfig, OwlsInsightSplitsProvider, derive_public_betting_notes
from cbb_dashboard.market import attach_market_to_board, context_frame


ROOT = Path(__file__).resolve().parents[1]


def _board():
    return pd.DataFrame([{
        "Target Date": "2026-03-19",
        "Game ID": "g1",
        "Away Team": "North Carolina",
        "Home Team": "Duke",
        "Model Pick": "Duke",
        "Fair Spread": -6.0,
        "Win Probability": .68,
        "Availability Verified": True,
        "Data Quality": 75,
    }])


def _live_payload():
    return {
        "sport": "ncaab",
        "data": [{
            "event_id": "owls-1",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "splits": [{
                "book": "circa", "title": "Circa Sports",
                "spread": {"away_line": 5.5, "home_line": -5.5, "away_handle_pct": 64, "home_handle_pct": 36, "away_bets_pct": 38, "home_bets_pct": 62},
                "total": {"line": 151.5, "over_handle_pct": 54, "under_handle_pct": 46, "over_bets_pct": 58, "under_bets_pct": 42},
                "moneyline": {"away_price": 190, "home_price": -225, "away_handle_pct": 61, "home_handle_pct": 39, "away_bets_pct": 41, "home_bets_pct": 59},
            }, {
                "book": "dk", "title": "DraftKings",
                "spread": {"away_line": 6.0, "home_line": -6.0, "away_handle_pct": 60, "home_handle_pct": 40, "away_bets_pct": 35, "home_bets_pct": 65},
                "total": {"line": 152.0, "over_handle_pct": 50, "under_handle_pct": 50, "over_bets_pct": 55, "under_bets_pct": 45},
                "moneyline": {"away_price": 200, "home_price": -240, "away_handle_pct": 58, "home_handle_pct": 42, "away_bets_pct": 39, "home_bets_pct": 61},
            }],
        }],
        "meta": {"source": "circa_dk"},
    }


def test_api_key_uses_bearer_header_not_url():
    provider = OwlsInsightSplitsProvider(OwlsInsightConfig(api_key="owlsinsight_test_secret"))
    assert provider.session.headers["Authorization"] == "Bearer owlsinsight_test_secret"
    assert "owlsinsight_test_secret" not in provider.BASE_URL
    assert provider.live_splits.__name__ == "live_splits"


def test_live_ncaab_split_shape_parses_per_book_and_market():
    provider = OwlsInsightSplitsProvider(OwlsInsightConfig(api_key="owlsinsight_test_secret"))
    frame, health = provider.parse(_live_payload(), _board())
    assert health["mapped_games"] == 1
    assert health["split_games"] == 1
    assert len(frame) == 6  # 2 books x spread/ML/total
    assert set(frame["Sportsbook Scope"]) == {"circa", "dk"}
    spread = frame[frame["Market Type"].eq("spread")]
    assert sorted(spread["Home Ticket %"].tolist()) == [62.0, 65.0]
    assert sorted(spread["Away Money %"].tolist()) == [60.0, 64.0]


def test_public_notes_are_qualitative_and_no_percentages_leak():
    provider = OwlsInsightSplitsProvider(OwlsInsightConfig(api_key="owlsinsight_test_secret"))
    frame, _ = provider.parse(_live_payload(), _board())
    notes = derive_public_betting_notes(_board(), frame)
    assert len(notes) == 1
    note = notes[0]
    assert note["betting_signal"] == "money_disagrees"
    assert note["betting_public_side"] == "Duke"
    assert note["betting_money_side"] == "North Carolina"
    assert "%" not in note["betting_note"]
    assert not re.search(r"\b(?:100|[1-9]?\d)\s*percent\b", note["betting_note"], re.I)


def test_public_market_pulse_uses_qualitative_context_not_raw_split_values():
    provider = OwlsInsightSplitsProvider(OwlsInsightConfig(api_key="owlsinsight_test_secret"))
    raw, _ = provider.parse(_live_payload(), _board())
    notes = derive_public_betting_notes(_board(), raw)
    context = context_frame([notes[0]])
    public_board = attach_market_to_board(_board(), pd.DataFrame(), context)
    html = market_pulse_html(public_board.iloc[0])
    assert "BETTING CROWD" in html
    assert ("Bets and money disagree" in html) or ("Sharp-money signal: North Carolina" in html)
    assert "62%" not in html and "65%" not in html and "64%" not in html
    assert "PUBLIC BETS" not in html and "PUBLIC MONEY" not in html


def test_betting_context_enters_reasons_risks_without_numbers():
    row = _board().iloc[0].copy()
    row["Betting Signal"] = "money_disagrees"
    row["Betting Public Side"] = "Duke"
    row["Betting Money Side"] = "North Carolina"
    positives, risks = signal_readout(row)
    joined = " ".join(positives + risks)
    assert "money side favors North Carolina" in joined
    assert "%" not in joined


def test_v144_migration_keeps_raw_splits_private():
    sql = (ROOT / "supabase" / "market_terminal_v1_4_4.sql").read_text().lower()
    assert "create table if not exists public.cbb_owner_betting_splits" in sql
    assert "revoke all on table public.cbb_owner_betting_splits from anon, authenticated" in sql
    assert "grant select on table public.cbb_owner_betting_splits to anon" not in sql
    assert 'create policy "cbb_owner_betting_splits_public_read"' not in sql
    assert "betting_note text" in sql


def test_app_uses_owls_secret_and_keeps_model_firewall():
    app = (ROOT / "app.py").read_text()
    assert 'APP_VERSION = "1.4.8"' in app
    assert 'optional_secret("OWLS_INSIGHT_API_KEY")' in app
    assert "OwlsInsightSplitsProvider" in app
    assert "SportsDataIOSplitsProvider" not in app
    assert "market-blind" in app
