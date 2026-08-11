from pathlib import Path

import numpy as np
import pandas as pd

from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import market_pulse_html
from cbb_dashboard.market import attach_market_to_board, market_records, normalize_market_import
from cbb_dashboard.odds_api_provider import OddsApiConfig, OddsApiMarketProvider

ROOT = Path(__file__).resolve().parents[1]


def _event():
    return {
        "id": "evt-1",
        "sport_key": "basketball_ncaab",
        "commence_time": "2026-01-10T20:00:00Z",
        "home_team": "Home Tech",
        "away_team": "Away State",
        "bookmakers": [
            {
                "key": "draftkings", "title": "DraftKings", "last_update": "2026-01-10T19:10:00Z",
                "markets": [
                    {"key": "spreads", "outcomes": [
                        {"name": "Home Tech", "price": -110, "point": -4.5},
                        {"name": "Away State", "price": -110, "point": 4.5},
                    ]},
                    {"key": "h2h", "outcomes": [
                        {"name": "Home Tech", "price": -190},
                        {"name": "Away State", "price": 165},
                    ]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "price": -105, "point": 145.5},
                        {"name": "Under", "price": -115, "point": 145.5},
                    ]},
                ],
            },
            {
                "key": "fanduel", "title": "FanDuel", "last_update": "2026-01-10T19:11:00Z",
                "markets": [{"key": "spreads", "outcomes": [
                    {"name": "Home Tech", "price": -108, "point": -5.0},
                    {"name": "Away State", "price": -112, "point": 5.0},
                ]}],
            },
            {
                "key": "betmgm", "title": "BetMGM", "last_update": "2026-01-10T19:09:00Z",
                "markets": [{"key": "spreads", "outcomes": [
                    {"name": "Home Tech", "price": -110, "point": -3.5},
                    {"name": "Away State", "price": -110, "point": 3.5},
                ]}],
            },
        ],
    }


def test_odds_api_current_request_uses_ncaab_featured_markets():
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="secret"))
    seen = {}
    def fake(path, params):
        seen["path"] = path
        seen["params"] = dict(params)
        return []
    provider._request = fake  # type: ignore[method-assign]
    provider.current_odds("2026-11-14")
    assert seen["path"] == "v4/sports/basketball_ncaab/odds"
    assert seen["params"]["markets"] == "h2h,spreads,totals"
    assert seen["params"]["regions"] == "us"
    assert seen["params"]["oddsFormat"] == "american"
    assert seen["params"]["apiKey"] == "secret"


def test_named_bookmakers_take_precedence_over_region():
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x", regions="us", bookmakers="draftkings,fanduel"))
    params = provider._base_params()
    assert params["bookmakers"] == "draftkings,fanduel"
    assert "regions" not in params


def test_parser_uses_reference_book_and_cross_book_spread_range(board_df):
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x", reference_bookmaker="draftkings"))
    parsed, fallback = provider.parse_event(_event(), board_df.iloc[0])
    assert fallback is False
    assert set(parsed["Market Type"]) == {"spread", "moneyline", "total"}
    spread = parsed[parsed["Market Type"].eq("spread")].iloc[0]
    ml = parsed[parsed["Market Type"].eq("moneyline")].iloc[0]
    total = parsed[parsed["Market Type"].eq("total")].iloc[0]
    assert spread["Provider"] == "the_odds_api"
    assert spread["Source Label"] == "The Odds API · DraftKings"
    assert float(spread["Home Line"]) == -4.5
    assert float(spread["Away Line"]) == 4.5
    assert int(spread["Book Count"]) == 3
    assert float(spread["Home Spread Min"]) == -5.0
    assert float(spread["Home Spread Max"]) == -3.5
    assert float(spread["Book Spread Range"]) == 1.5
    assert spread["Book Agreement"] == "mixed"
    assert float(ml["Home Price"]) == -190
    assert float(total["Total Line"]) == 145.5


def test_odds_api_does_not_fabricate_betting_splits(board_df):
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x"))
    parsed, _ = provider.parse_event(_event(), board_df.iloc[0])
    normalized = normalize_market_import(parsed)
    assert normalized["Home Ticket %"].isna().all()
    assert normalized["Home Money %"].isna().all()
    raw = board_df.iloc[[0]].copy()
    raw["Model Run At UTC"] = "2026-01-10T19:05:00Z"
    board, _ = normalize_board(raw)
    out = attach_market_to_board(board, normalized)
    html = market_pulse_html(out.iloc[0])
    assert "Not provided" not in html
    assert "SPORTSBOOK LINE" in html
    assert "LINE MOVEMENT" in html
    assert "BOOK CONSENSUS" in html
    assert "The Odds API" in html


def test_reference_fallback_preserves_named_source(board_df):
    event = _event()
    event["bookmakers"] = [b for b in event["bookmakers"] if b["key"] != "draftkings"]
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x", reference_bookmaker="draftkings"))
    parsed, fallback = provider.parse_event(event, board_df.iloc[0])
    assert fallback is True
    assert parsed.iloc[0]["Source Label"] == "The Odds API · FanDuel"


def test_team_alias_mapping_handles_uconn_connecticut(board_df):
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x"))
    board = board_df.iloc[[0]].copy()
    board.loc[:, "Home Team"] = "UConn"
    board.loc[:, "Away Team"] = "Duke"
    event = _event()
    event["id"] = "uconn-duke"
    event["home_team"] = "Connecticut Huskies"
    event["away_team"] = "Duke Blue Devils"
    mapped = provider.map_board_games(board, [event])
    assert len(mapped) == 1
    assert mapped[0]["swapped"] is False


def test_swapped_provider_designation_is_translated_to_board_home(board_df):
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x"))
    event = _event()
    event["home_team"], event["away_team"] = event["away_team"], event["home_team"]
    # Outcomes remain named by the actual teams, so swap the points to provider designation.
    dk = event["bookmakers"][0]
    spread = next(m for m in dk["markets"] if m["key"] == "spreads")
    for o in spread["outcomes"]:
        o["point"] = 4.5 if o["name"] == "Home Tech" else -4.5
    mapped = provider.map_board_games(board_df.iloc[[0]], [event])
    assert mapped[0]["swapped"] is True
    parsed, _ = provider.parse_event(event, board_df.iloc[0], swapped=True)
    spread_row = parsed[parsed["Market Type"].eq("spread")].iloc[0]
    assert float(spread_row["Home Line"]) == 4.5


def test_historical_endpoint_is_explicit_and_role_can_mark_decision(board_df):
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x"))
    provider.historical_odds = lambda stamp: ([_event()], "2026-01-10T19:00:00Z")  # type: ignore[method-assign]
    snapshots, context, health = provider.refresh(board_df.iloc[[0]], historical_at="2026-01-10T19:02:00Z", snapshot_role="decision")
    assert context.empty
    assert health["mode"] == "historical"
    assert snapshots["Snapshot Role"].eq("decision").all()
    assert snapshots["Snapshot Time UTC"].astype(str).str.contains("19:00:00").all()


def test_records_keep_actual_reference_line_for_ats(board_df):
    provider = OddsApiMarketProvider(OddsApiConfig(api_key="x"))
    parsed, _ = provider.parse_event(_event(), board_df.iloc[0], snapshot_role="decision")
    records = market_records(parsed, "tester")
    spread = next(r for r in records if r["market_type"] == "spread")
    assert spread["home_line"] == -4.5
    assert spread["source_label"] == "The Odds API · DraftKings"
    assert spread["home_ticket_pct"] is None


def test_app_and_secrets_use_the_odds_api_as_primary():
    app = (ROOT / "app.py").read_text()
    secrets = (ROOT / "STREAMLIT_SECRETS_TEMPLATE.toml").read_text()
    assert "Refresh The Odds API market lines" in app
    assert "THE_ODDS_API_KEY" in app
    assert "Refresh Action Network market data" not in app
    assert "Refresh Sportradar fallback" not in app
    assert 'THE_ODDS_API_REFERENCE_BOOKMAKER = "draftkings"' in secrets
    assert "ACTION_NETWORK_API_KEY" not in secrets


def test_v142_schema_stays_provider_agnostic_and_rls_protected():
    sql = (ROOT / "supabase" / "market_terminal_v1_4_2.sql").read_text().lower()
    assert "cbb_market_snapshots" in sql
    assert "cbb_game_context" in sql
    assert "ticket_count bigint" in sql  # retained for a future optional split source
    assert "enable row level security" in sql
    assert "grant select" in sql
    assert "for insert" not in sql and "for update" not in sql and "for delete" not in sql
