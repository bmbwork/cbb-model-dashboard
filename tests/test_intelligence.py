from __future__ import annotations

from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import (
    game_card_html,
    market_context_html,
    model_market_gap,
    signal_readout,
    team_profile_pair_html,
)


def test_card_contains_bettor_first_core_fields_without_old_model_audit(board_df):
    board, _ = normalize_board(board_df)
    html = game_card_html(board.iloc[0])
    assert "Home Tech" in html
    assert "Chance model pick wins" in html
    assert "Model spread" in html
    assert "Projected combined points" in html
    assert "Likely result range" not in html
    assert "Frozen V1.0.1" not in html
    assert "Schedule Translation" not in html


def test_signal_readout_marks_near_coin_flip_and_uncertainty(board_df):
    board, _ = normalize_board(board_df)
    _, risks = signal_readout(board.iloc[1])
    joined = " ".join(risks).lower()
    assert "close game" in joined
    assert "either team wins" not in joined


def test_team_profile_pair_contains_requested_snapshot_metrics(board_df):
    raw = board_df.copy()
    raw["Home PPG"] = [78.4, 73.0]
    raw["Away PPG"] = [71.2, 75.5]
    raw["Home PPG Allowed"] = [66.8, 70.1]
    raw["Away PPG Allowed"] = [72.0, 68.7]
    board, _ = normalize_board(raw)
    html = team_profile_pair_html(board.iloc[0])
    for token in ["Offense rating", "Defense rating", "Overall rating", "Schedule strength", "Points / game", "Points allowed / game", "Matchup edge"]:
        assert token in html
    assert "78.4" in html
    assert "66.8" in html


def test_market_context_is_display_only_and_gap_is_from_pick_perspective(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Market Home Spread"] = -7.0
    board, _ = normalize_board(raw)
    row = board.iloc[0]
    # Model fair is Home Tech -9.0; market -7.0 is two points more favorable.
    assert model_market_gap(row) == 2.0
    html = market_context_html(row)
    assert "Home Tech -7.0" in html
    assert "gives the pick 2.0 more points" in html
    assert "not an automatic bet recommendation" in html
