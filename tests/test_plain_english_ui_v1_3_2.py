from __future__ import annotations

from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import game_card_html, likely_result_text, signal_readout, team_profile_pair_html


def test_game_card_hides_public_jargon(board_df):
    board, _ = normalize_board(board_df)
    html = game_card_html(board.iloc[0])
    for banned in ["P10", "P90", "SOS gap", "AdjO", "AdjD", "AdjNet", "Margin SD", "D-I SOS"]:
        assert banned not in html
    for friendly in ["Likely result range", "Data confidence", "Model-implied odds", "Why this pick?"]:
        assert friendly in html


def test_cross_zero_range_is_written_as_normal_language(board_df):
    board, _ = normalize_board(board_df)
    text = likely_result_text(board.iloc[0])
    assert "Lose by" in text and "win by" in text
    _, risks = signal_readout(board.iloc[0])
    joined = " ".join(risks)
    assert "realistic outcomes where either team wins" in joined
    assert "P10" not in joined and "P90" not in joined


def test_team_profile_uses_friendly_metric_names(board_df):
    board, _ = normalize_board(board_df)
    html = team_profile_pair_html(board.iloc[0])
    assert "Offense rating" in html
    assert "Defense rating" in html
    assert "Overall rating" in html
    assert "Schedule strength" in html
    assert "AdjO" not in html
    assert "AdjD" not in html
    assert "AdjNet" not in html
