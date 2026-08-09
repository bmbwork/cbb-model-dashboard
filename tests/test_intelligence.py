from __future__ import annotations

from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import game_card_html, signal_readout


def test_card_contains_cbb_core_fields(board_df):
    board, _ = normalize_board(board_df)
    html = game_card_html(board.iloc[0])
    assert "Home Tech" in html
    assert "Model win probability" in html
    assert "Frozen V1.0.1" in html
    assert "Projected total" in html


def test_signal_readout_marks_ambiguous_and_pick_change(board_df):
    board, _ = normalize_board(board_df)
    positives, risks = signal_readout(board.iloc[1])
    joined = " ".join(risks).lower()
    assert "ambiguity" in joined
    assert "changes the winner" in joined
