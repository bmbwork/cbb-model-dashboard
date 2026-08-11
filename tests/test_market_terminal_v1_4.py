from __future__ import annotations

from pathlib import Path
import pandas as pd

from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import game_card_html, market_pulse_html
from cbb_dashboard.market import (
    attach_market_to_board,
    context_flags,
    market_features,
    market_research_frame,
    normalize_context_import,
    normalize_market_import,
    normalize_team_name,
)
from cbb_dashboard.market_provider import SportradarConfig, SportradarMarketProvider

ROOT = Path(__file__).resolve().parents[1]


def _snapshots():
    return normalize_market_import(pd.DataFrame([
        {
            "Slate Date":"2026-01-10","Game ID":"101","Snapshot Time UTC":"2026-01-10T18:00:00Z",
            "Market Type":"spread","Provider":"test","Snapshot Role":"observed",
            "Home Ticket %":28,"Home Money %":39,"Home Line":-4.0,"Opening Home Line":-3.0,
        },
        {
            "Slate Date":"2026-01-10","Game ID":"101","Snapshot Time UTC":"2026-01-10T19:30:00Z",
            "Market Type":"spread","Provider":"test","Snapshot Role":"decision",
            "Home Ticket %":30,"Home Money %":42,"Home Line":-5.0,"Opening Home Line":-3.0,
        },
        {
            "Slate Date":"2026-01-10","Game ID":"101","Snapshot Time UTC":"2026-01-10T19:55:00Z",
            "Market Type":"spread","Provider":"test","Snapshot Role":"close",
            "Home Ticket %":31,"Home Money %":44,"Home Line":-5.5,"Opening Home Line":-3.0,
        },
    ]))


def test_market_import_fills_percentage_complements():
    snap = _snapshots()
    assert snap.loc[0, "Away Ticket %"] == 72
    assert snap.loc[0, "Away Money %"] == 61


def test_state_is_not_removed_from_team_normalization():
    assert normalize_team_name("Michigan State") != normalize_team_name("Michigan")


def test_decision_and_closing_lines_remain_separate(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Model Run At UTC"] = "2026-01-10T19:25:00Z"
    board, _ = normalize_board(raw)
    out = attach_market_to_board(board, _snapshots())
    assert float(out.loc[0, "_market_home_spread"]) == -5.0
    assert float(out.loc[0, "_closing_home_spread"]) == -5.5
    assert "decision-time" in str(out.loc[0, "_spread_source"])


def test_market_features_reverse_line_movement(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Model Run At UTC"] = "2026-01-10T19:25:00Z"
    board, _ = normalize_board(raw)
    out = attach_market_to_board(board, _snapshots())
    features = market_features(out.iloc[0])
    # 70% of tickets are on Away State while spread moves from Home -3 to Home -5.5.
    assert features["ticket_team"] == "Away State"
    assert features["line_move_team"] == "Home Tech"
    assert features["reverse_line_movement"] is True


def test_market_research_includes_model_market_gap(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Model Run At UTC"] = "2026-01-10T19:25:00Z"
    board, _ = normalize_board(raw)
    out = attach_market_to_board(board, _snapshots())
    research = market_research_frame(out)
    # Model likes Home Tech -9 while the decision line is Home Tech -5: +4 pts to model side.
    assert float(research.loc[0, "Decision Line For Model Pick"]) == -5.0
    assert float(research.loc[0, "Model-Market Gap"]) == 4.0


def test_market_spotlight_requires_all_context_flags(board_df):
    board, _ = normalize_board(board_df.iloc[[0]])
    ctx = normalize_context_import(pd.DataFrame([{
        "Slate Date":"2026-01-10","Game ID":"101","Home Rank":8,"Away Rank":14,
        "Conference Game":True,"Saturday":True,"Prime Time":True,"Neutral Site":False,
    }]))
    out = attach_market_to_board(board, pd.DataFrame(), ctx)
    flags = context_flags(out.iloc[0])
    assert flags["spotlight"] is True


def test_market_pulse_and_card_do_not_modify_model_prediction(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Model Run At UTC"] = "2026-01-10T19:25:00Z"
    board, _ = normalize_board(raw)
    before = board[["Model Pick","Win Probability","Fair Spread","Projected Home Score","Projected Away Score"]].copy()
    out = attach_market_to_board(board, _snapshots())
    pd.testing.assert_frame_equal(before.reset_index(drop=True), out[before.columns].reset_index(drop=True))
    assert "MARKET PULSE" in market_pulse_html(out.iloc[0]).upper()
    assert "MARKET PULSE" in game_card_html(out.iloc[0]).upper()


def test_provider_urls_and_config_are_sportradar_ready():
    provider = SportradarMarketProvider(SportradarConfig(api_key="x", ncaamb_api_key="y", odds_api_key="z"))
    seen = []
    provider._get = lambda url, key: seen.append((url,key)) or {}  # type: ignore[method-assign]
    provider.daily_schedule("2026-11-14")
    provider.betting_splits("game-123")
    provider.daily_odds_mappings("2026-11-14")
    assert "/ncaamb/production/v8/en/games/2026/11/14/schedule.json" in seen[0][0]
    assert "/betting-splits/v3/production/ncaamb/en/game/game-123" in seen[1][0]
    assert "/mapping/production/v2/en/sports/sr:sport:2/schedules/2026-11-14/" in seen[2][0]


def test_market_schema_is_public_read_server_write_only():
    sql = (ROOT / "supabase" / "market_terminal_v1_4.sql").read_text().lower()
    assert "cbb_market_snapshots" in sql and "cbb_game_context" in sql
    assert "enable row level security" in sql
    assert "grant select" in sql
    assert "for insert" not in sql and "for update" not in sql and "for delete" not in sql


def test_app_has_market_terminal_and_admin_refresh_but_no_public_secret():
    source = (ROOT / "app.py").read_text()
    assert '"Market Terminal"' in source
    assert "Refresh The Odds API market lines" in source
    assert "THE_ODDS_API_KEY" in source
    assert "st.write(action_key" not in source
    assert "raw bet" not in source.lower()

def test_sportradar_split_parser_accepts_common_market_outcome_shape(board_df):
    provider = SportradarMarketProvider(SportradarConfig(api_key="x"))
    row = board_df.iloc[0].copy()
    payload = {
        "markets": [
            {
                "market": "spread",
                "outcomes": [
                    {"name":"Home Tech", "bet_percentage":0.35, "stake_percentage":0.58, "spread":-4.5},
                    {"name":"Away State", "bet_percentage":0.65, "stake_percentage":0.42, "spread":4.5},
                ],
            },
            {
                "market": "moneyLine",
                "outcomes": [
                    {"name":"Home Tech", "ticket_percentage":45, "money_percentage":60},
                    {"name":"Away State", "ticket_percentage":55, "money_percentage":40},
                ],
            },
        ]
    }
    parsed = provider.parse_betting_splits(payload, row, "gid")
    assert set(parsed["Market Type"]) == {"spread", "moneyline"}
    spread = parsed[parsed["Market Type"].eq("spread")].iloc[0]
    assert spread["Home Ticket %"] == 35
    assert abs(float(spread["Home Money %"]) - 58) < 1e-9
    assert spread["Away Ticket %"] == 65


def test_current_rankings_do_not_leak_into_old_slate():
    payload = {
        "effective_time":"2026-02-01T12:00:00Z",
        "rankings":[{"rank":1,"market":"Home","name":"Tech"}],
    }
    assert SportradarMarketProvider._ranking_map(payload, "2026-01-10") == {}
    assert SportradarMarketProvider._ranking_map(payload, "2026-02-02")

def test_odds_comparison_book_disagreement_summary():
    payload = {
        "markets":[{
            "name":"spread",
            "books":[
                {"name":"Consensus","outcomes":[{"type":"home","spread":-4.0,"open_spread":-3.0},{"type":"away","spread":4.0,"open_spread":3.0}]},
                {"name":"Book A","outcomes":[{"type":"home","spread":-3.5},{"type":"away","spread":3.5}]},
                {"name":"Book B","outcomes":[{"type":"home","spread":-5.5},{"type":"away","spread":5.5}]},
            ],
        }]
    }
    odds = SportradarMarketProvider._consensus_odds(payload)
    assert odds["home_spread"] == -4.0
    assert odds["book_count"] == 3
    assert odds["book_spread_range"] == 2.0
    assert odds["book_agreement"] == "wide"

def test_post_start_market_snapshot_cannot_replace_pregame_state(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Model Run At UTC"] = "2026-01-10T19:25:00Z"
    board, _ = normalize_board(raw)
    snap = _snapshots().copy()
    post = snap.iloc[[0]].copy()
    post["Snapshot Time UTC"] = pd.to_datetime(["2026-01-10T21:00:00Z"], utc=True)
    post["Home Line"] = -20.0
    post["Home Ticket %"] = 99.0
    post["Away Ticket %"] = 1.0
    post["Raw Snapshot Hash"] = "poststart"
    all_snap = pd.concat([snap, post], ignore_index=True)
    out = attach_market_to_board(board, all_snap)
    assert float(out.loc[0, "_market_current_home_spread"]) == -5.5
    assert float(out.loc[0, "_market_home_ticket_pct"]) == 31.0
