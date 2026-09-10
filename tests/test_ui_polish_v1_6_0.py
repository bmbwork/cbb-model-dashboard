from pathlib import Path

import pandas as pd

from cbb_dashboard.board_filters import (
    MARKET_HAS_BOTH,
    MOVE_TOWARD,
    RANK_FILTER_ANY_TOP10,
    RANK_FILTER_ANY_TOP25,
    RANK_FILTER_MATCHUP,
    SORT_ML,
    filter_board,
    model_market_spread_gap,
    model_pick_best_ml,
)
from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import betting_splits_html, game_card_html

ROOT = Path(__file__).resolve().parents[1]


def _market_ready_board(board_df: pd.DataFrame) -> pd.DataFrame:
    board, _ = normalize_board(board_df)
    board = board.copy()
    board["Home Rank"] = [8, 31]
    board["Away Rank"] = [14, 6]

    # Game 1 model pick is home.
    board.loc[0, "_best_current_moneyline_home_price"] = -325
    board.loc[0, "_best_current_spread_home_line"] = -6.0
    board.loc[0, "_best_current_spread_home_price"] = -105
    board.loc[0, "_best_current_spread_home_book_title"] = "FanDuel"
    board.loc[0, "_best_current_moneyline_home_book_title"] = "DraftKings"
    board.loc[0, "_best_open_spread_home_line"] = -4.5
    board.loc[0, "_best_close_spread_home_line"] = -6.5

    # Game 2 model pick is away.
    board.loc[1, "_best_current_moneyline_away_price"] = 475
    board.loc[1, "_best_current_spread_away_line"] = 2.5
    board.loc[1, "_best_current_spread_away_price"] = -110
    board.loc[1, "_best_current_spread_away_book_title"] = "Circa"
    board.loc[1, "_best_current_moneyline_away_book_title"] = "Circa"
    board.loc[1, "_best_open_spread_away_line"] = 3.5

    board.loc[0, "_market_home_money_pct"] = 61
    board.loc[0, "_market_home_ticket_pct"] = 48
    board.loc[0, "_market_ml_home_money_pct"] = 58
    board.loc[0, "_market_ml_home_ticket_pct"] = 52
    board.loc[0, "_market_total_over_money_pct"] = 55
    board.loc[0, "_market_total_over_ticket_pct"] = 49
    board.loc[0, "_market_split_source_label"] = "Owls Insight"
    board.loc[0, "_market_split_latest_snapshot_utc"] = "2026-01-10T19:30:00Z"
    return board


def test_model_pick_moneyline_uses_correct_side_and_range(board_df):
    board = _market_ready_board(board_df)
    assert model_pick_best_ml(board.iloc[0]) == -325
    assert model_pick_best_ml(board.iloc[1]) == 475
    filtered = filter_board(board, ml_range_enabled=True, ml_min=-350, ml_max=500, min_win_probability=.50)
    assert filtered["Game ID"].astype(str).tolist() == ["101", "102"]
    filtered = filter_board(board, ml_range_enabled=True, ml_min=-300, ml_max=500, min_win_probability=.50)
    assert filtered["Game ID"].astype(str).tolist() == ["102"]


def test_ap_rank_filters_cover_top10_top25_and_ranked_matchups(board_df):
    board = _market_ready_board(board_df)
    assert len(filter_board(board, ranking_mode=RANK_FILTER_ANY_TOP25)) == 2
    top10 = filter_board(board, ranking_mode=RANK_FILTER_ANY_TOP10)
    assert set(top10["Game ID"].astype(str)) == {"101", "102"}
    ranked = filter_board(board, ranking_mode=RANK_FILTER_MATCHUP)
    assert ranked["Game ID"].astype(str).tolist() == ["101"]


def test_market_availability_movement_gap_and_sort_are_display_only(board_df):
    board = _market_ready_board(board_df)
    before = board[["Model Pick", "Win Probability", "Fair Spread"]].copy()
    assert model_market_spread_gap(board.iloc[0]) == 3.0
    available = filter_board(board, market_mode=MARKET_HAS_BOTH, min_win_probability=.50)
    assert len(available) == 2
    toward = filter_board(board, movement_mode=MOVE_TOWARD, min_win_probability=.50)
    assert set(toward["Game ID"].astype(str)) == {"101", "102"}
    sorted_board = filter_board(board, sort_by=SORT_ML, min_win_probability=.50)
    assert sorted_board.iloc[0]["Model Pick"] == "Metro"
    pd.testing.assert_frame_equal(before.reset_index(drop=True), board[before.columns].reset_index(drop=True))


def test_polished_card_exposes_market_lifecycle_and_validated_splits(board_df):
    board = _market_ready_board(board_df)
    html = game_card_html(board.iloc[0])
    for token in [
        "ML PICK",
        "MODEL SPREAD",
        "BEST SPREAD NOW",
        "BEST ML NOW",
        "MARKET PULSE",
        "BETTING SPLITS",
        "61% money · 48% tickets",
        "Open -4.5",
        "Current -6.0",
        "Projected combined points",
        "Data confidence",
    ]:
        assert token in html


def test_zero_zero_split_is_not_presented_as_real_market_signal(board_df):
    board, _ = normalize_board(board_df.iloc[[0]])
    board.loc[0, "_market_home_money_pct"] = 0
    board.loc[0, "_market_home_ticket_pct"] = 0
    html = betting_splits_html(board.iloc[0])
    assert "0% money · 0% tickets" not in html
    assert "Not offered" in html




def test_away_moneyline_zero_zero_sentinel_does_not_become_100_100(board_df):
    board, _ = normalize_board(board_df.iloc[[1]])
    board.loc[board.index[0], "_market_ml_home_money_pct"] = 0
    board.loc[board.index[0], "_market_ml_home_ticket_pct"] = 0
    html = betting_splits_html(board.iloc[0])
    assert "100% money · 100% tickets" not in html
    assert "moneyline</span><strong>Not offered" in html


def test_sidebar_is_reduced_and_date_picker_moves_to_slates_product():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    nav = 'public_pages = ["Home", "Today\'s Board", "Slates by Date", "Analyst Picks", "Performance Lab"]'
    assert nav in app
    sidebar_block = app.split("with st.sidebar:", 1)[1].split('if page == "Home":', 1)[0]
    assert "Published slate" not in sidebar_block
    assert 'page == "Slates by Date"' in app
    assert 'st.selectbox("Slate date"' in app
    for retired in ["Market Terminal", "Team Intelligence", "Matchup Explorer", "Model Guide"]:
        assert retired not in nav


def test_version_and_source_of_truth_contract():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.6.0"' in app
    assert "market-blind" in app
    assert "THE_ODDS_API_KEY" not in app


def test_public_card_split_projection_keeps_raw_table_private():
    storage = (ROOT / "cbb_dashboard" / "storage.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    sql = (ROOT / "supabase" / "market_terminal_v1_4_7.sql").read_text(encoding="utf-8")
    method = storage.split("def list_card_split_projection", 1)[1].split("def latest_owner_split_capture_time", 1)[0]
    assert "client = self._admin_client()" in method
    assert 'row["snapshot_role"] = "observed"' in method
    for forbidden in ["home_line", "away_line", "sharp_side", "sharp_signal", "sharp_gap_pts"]:
        assert f'"{forbidden}"' not in method
    assert "cached_card_split_list" in app
    assert "display_snapshots" in app
    assert "revoke all on table public.cbb_owner_betting_splits from anon, authenticated" in sql
    assert "grant select on table public.cbb_owner_betting_splits to anon" not in sql
