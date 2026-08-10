from __future__ import annotations

import pandas as pd

from cbb_dashboard.data import attach_grading, normalize_board, normalize_graded_board
from cbb_dashboard.intelligence import game_card_grid_html, game_card_html


def _champion_board(board_df: pd.DataFrame) -> pd.DataFrame:
    b = board_df.copy()
    b["Model Version"] = "1.1.3B"
    n = len(b)
    b["Champion Margin Calibration Adj"] = ([1.4, -0.8] * n)[:n]
    b["Champion Baseline Home Margin"] = ([5.0, -1.0] * n)[:n]
    b["Champion Calibrated Home Margin"] = ([6.4, -1.8] * n)[:n]
    b["Champion Calibration Status"] = "ACTIVE"
    b["Champion Training Games"] = 900
    b["Champion Training Dates"] = 25
    b["Schedule Translation Margin Adj"] = 0.0
    return b


def test_card_grid_is_compacted_to_prevent_markdown_code_blocks(board_df):
    board, _ = normalize_board(_champion_board(board_df))
    html = game_card_grid_html(board)
    assert html.count('class="game-card ') == 2
    assert "\n" not in html
    assert "Game Intelligence Dossier" in html
    assert "Why we like Home Tech" in html


def test_champion_card_uses_b_calibration_not_old_translation(board_df):
    board, _ = normalize_board(_champion_board(board_df))
    html = game_card_html(board.iloc[0])
    assert "Production champion" in html
    assert "B calibration" in html
    assert "V1.1 translation" not in html
    assert "Frozen V1.0.1 audit" in html


def test_ml_and_market_spread_w_are_displayable(board_df):
    raw = _champion_board(board_df.iloc[[0]].copy())
    raw["Final Away Score"] = 70
    raw["Final Home Score"] = 80
    raw["Status"] = "final"
    raw["Grade Eligible"] = True
    raw["Actual Winner"] = "Home Tech"
    raw["Actual Home Margin"] = 10.0
    raw["Actual Total"] = 150.0
    raw["Model Winner Correct"] = True
    raw["Absolute Margin Error"] = 3.6
    raw["Brier Component"] = 0.08
    raw["Log Loss Component"] = 0.3
    raw["Market Home Spread"] = -6.5
    graded, _ = normalize_graded_board(raw)
    assert bool(graded.loc[0, "_ml_correct"]) is True
    assert bool(graded.loc[0, "_spread_correct"]) is True
    board, _ = normalize_board(_champion_board(board_df.iloc[[0]].copy()))
    merged = attach_grading(board, raw)
    html = game_card_html(merged.iloc[0])
    assert "ML <strong>W</strong>" in html
    assert "SPREAD <strong>W</strong>" in html
    assert "Home line -6.5" in html


def test_fair_spread_is_not_used_as_ats_line(board_df):
    raw = _champion_board(board_df.iloc[[0]].copy())
    raw["Final Away Score"] = 70
    raw["Final Home Score"] = 80
    raw["Status"] = "final"
    raw["Grade Eligible"] = True
    raw["Actual Winner"] = "Home Tech"
    raw["Actual Home Margin"] = 10.0
    raw["Actual Total"] = 150.0
    raw["Model Winner Correct"] = True
    raw["Absolute Margin Error"] = 3.6
    raw["Brier Component"] = 0.08
    raw["Log Loss Component"] = 0.3
    graded, _ = normalize_graded_board(raw)
    assert graded.loc[0, "_spread_source"] == ""
    assert pd.isna(graded.loc[0, "_spread_correct"])
