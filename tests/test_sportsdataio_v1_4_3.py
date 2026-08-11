from __future__ import annotations

import pandas as pd

from cbb_dashboard.data import normalize_board
from cbb_dashboard.market import attach_market_to_board, market_records, normalize_market_import
from cbb_dashboard.sportsdataio_provider import SportsDataIOConfig, SportsDataIOSplitsProvider
from cbb_dashboard.intelligence import market_interpretation_text, market_pulse_html


def test_sportsdataio_uses_header_auth_and_documented_paths(monkeypatch):
    cfg = SportsDataIOConfig(api_key="SECRET", splits_mode="trial")
    provider = SportsDataIOSplitsProvider(cfg)
    assert provider.session.headers["Ocp-Apim-Subscription-Key"] == "SECRET"
    assert "SECRET" not in provider.BASE_URL


def test_sportsdataio_maps_game_and_parses_spread_split_history(board_df):
    raw = board_df.iloc[[0]].copy()
    board, _ = normalize_board(raw)
    provider = SportsDataIOSplitsProvider(SportsDataIOConfig(api_key="SECRET", splits_mode="production"))
    provider._metadata_cache = {"bet": {}, "period": {}, "outcome": {}, "market": {}}
    events = [{
        "GameID": 777,
        "HomeTeamName": "Home Tech",
        "AwayTeamName": "Away State",
        "DateTime": "2026-01-10T20:00:00Z",
    }]
    mapped = provider.map_board_games(board, events)
    assert len(mapped) == 1
    assert mapped[0]["provider_game_id"] == "777"

    payload = {
        "GameID": 777,
        "BettingMarketSplits": [{
            "BettingMarketID": 999,
            "BettingBetType": "Point Spread",
            "BettingPeriodType": "Full Game",
            "BettingSplits": [
                {"BettingOutcomeType": "Home", "BetPercentage": 37, "MoneyPercentage": 64, "LastSeen": "2026-01-10T19:15:00Z"},
                {"BettingOutcomeType": "Away", "BetPercentage": 63, "MoneyPercentage": 36, "LastSeen": "2026-01-10T19:15:00Z"},
                {"BettingOutcomeType": "Home", "BetPercentage": 41, "MoneyPercentage": 66, "LastSeen": "2026-01-10T19:30:00Z"},
                {"BettingOutcomeType": "Away", "BetPercentage": 59, "MoneyPercentage": 34, "LastSeen": "2026-01-10T19:30:00Z"},
            ],
        }],
    }
    frame = provider.parse_game_splits(payload, board.iloc[0], "777")
    assert len(frame) == 2
    latest = frame.iloc[-1]
    assert latest["Home Ticket %"] == 41
    assert latest["Away Ticket %"] == 59
    assert latest["Home Money %"] == 66
    assert latest["Away Money %"] == 34
    assert latest["Snapshot Role"] == "observed"
    assert latest["Provider"] == "sportsdataio"


def test_line_and_split_providers_merge_without_overwriting_each_other(board_df):
    raw = board_df.iloc[[0]].copy()
    board, _ = normalize_board(raw)
    snapshots = normalize_market_import(pd.DataFrame([
        {
            "Slate Date": "2026-01-10", "Game ID": "101", "Snapshot Time UTC": "2026-01-10T19:20:00Z",
            "Market Type": "spread", "Provider": "the_odds_api", "Source Label": "The Odds API · DraftKings",
            "Home Line": -4.5, "Book Count": 8, "Book Spread Range": .5, "Book Agreement": "tight", "Snapshot Role": "observed",
        },
        {
            "Slate Date": "2026-01-10", "Game ID": "101", "Snapshot Time UTC": "2026-01-10T19:30:00Z",
            "Market Type": "spread", "Provider": "sportsdataio", "Source Label": "SportsDataIO betting splits",
            "Home Ticket %": 41, "Away Ticket %": 59, "Home Money %": 66, "Away Money %": 34, "Snapshot Role": "observed",
        },
    ]))
    out = attach_market_to_board(board, snapshots)
    row = out.iloc[0]
    assert row["_market_current_home_spread"] == -4.5
    assert row["_market_home_ticket_pct"] == 41
    assert row["_market_home_money_pct"] == 66
    assert row["_market_source_label"] == "The Odds API · DraftKings"
    assert row["_market_split_source_label"] == "SportsDataIO betting splits"
    html = market_pulse_html(row)
    assert "PUBLIC BETS" not in html
    assert "PUBLIC MONEY" not in html
    assert "Lines: The Odds API" in html
    assert "Splits: SportsDataIO" not in html


def test_plain_english_market_read_explains_money_ticket_disagreement(board_df):
    raw = board_df.iloc[[0]].copy()
    board, _ = normalize_board(raw)
    snapshots = normalize_market_import(pd.DataFrame([
        {
            "Slate Date": "2026-01-10", "Game ID": "101", "Snapshot Time UTC": "2026-01-10T19:00:00Z",
            "Market Type": "spread", "Provider": "the_odds_api", "Source Label": "The Odds API · DraftKings",
            "Home Line": -3.0, "Snapshot Role": "open",
        },
        {
            "Slate Date": "2026-01-10", "Game ID": "101", "Snapshot Time UTC": "2026-01-10T19:25:00Z",
            "Market Type": "spread", "Provider": "the_odds_api", "Source Label": "The Odds API · DraftKings",
            "Home Line": -4.5, "Snapshot Role": "observed",
        },
        {
            "Slate Date": "2026-01-10", "Game ID": "101", "Snapshot Time UTC": "2026-01-10T19:30:00Z",
            "Market Type": "spread", "Provider": "sportsdataio", "Source Label": "SportsDataIO betting splits",
            "Home Ticket %": 37, "Away Ticket %": 63, "Home Money %": 64, "Away Money %": 36, "Snapshot Role": "observed",
        },
    ]))
    row = attach_market_to_board(board, snapshots).iloc[0]
    text = market_interpretation_text(row)
    assert "Most bets are on Away State (63%)" in text
    assert "most of the money is on Home Tech (64%)" in text
    assert "Fewer bets are backing Home Tech" in text
    assert "model agrees with the money side" in text.lower()


def test_sportsdataio_rows_keep_api_key_out_of_persisted_records(board_df):
    raw = board_df.iloc[[0]].copy()
    board, _ = normalize_board(raw)
    provider = SportsDataIOSplitsProvider(SportsDataIOConfig(api_key="SUPERSECRET", splits_mode="production"))
    provider._metadata_cache = {"bet": {}, "period": {}, "outcome": {}, "market": {}}
    payload = {"BettingMarketSplits": [{"BettingBetType": "Moneyline", "BettingPeriodType": "Full Game", "BettingSplits": [
        {"BettingOutcomeType": "Home", "BetPercentage": .55, "MoneyPercentage": .62, "LastSeen": "2026-01-10T19:00:00Z"},
        {"BettingOutcomeType": "Away", "BetPercentage": .45, "MoneyPercentage": .38, "LastSeen": "2026-01-10T19:00:00Z"},
    ]}]}
    frame = provider.parse_game_splits(payload, board.iloc[0], "777")
    records = market_records(frame, "tester")
    assert records
    assert "SUPERSECRET" not in str(records)
