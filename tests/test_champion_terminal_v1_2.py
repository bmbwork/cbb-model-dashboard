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


def _graded(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out["Final Away Score"] = 70
    out["Final Home Score"] = 80
    out["Status"] = "final"
    out["Grade Eligible"] = True
    out["Actual Winner"] = "Home Tech"
    out["Actual Home Margin"] = 10.0
    out["Actual Total"] = 150.0
    out["Model Winner Correct"] = True
    out["Absolute Margin Error"] = 3.6
    out["Brier Component"] = 0.08
    out["Log Loss Component"] = 0.3
    return out


def test_card_grid_is_compacted_to_prevent_markdown_code_blocks(board_df):
    board, _ = normalize_board(_champion_board(board_df))
    html = game_card_grid_html(board)
    assert html.count('class="game-card ') == 2
    assert "\n" not in html
    assert "Why this pick?" in html
    assert "WHY THE MODEL LIKES Home Tech" in html


def test_bettor_facing_champion_card_hides_research_plumbing(board_df):
    board, _ = normalize_board(_champion_board(board_df))
    html = game_card_html(board.iloc[0])
    assert "Production model" in html
    assert "Model spread" in html
    assert "Model-implied odds" in html
    assert "B calibration" not in html
    assert "Frozen V1.0.1" not in html
    assert "V1.1 translation" not in html


def test_ml_and_decision_spread_w_are_displayable(board_df):
    raw = _graded(_champion_board(board_df.iloc[[0]].copy()))
    raw["Bet Home Spread"] = -6.5
    raw["Closing Home Spread"] = -8.0
    graded, _ = normalize_graded_board(raw)
    assert bool(graded.loc[0, "_ml_correct"]) is True
    assert bool(graded.loc[0, "_spread_correct"]) is True
    board, _ = normalize_board(_champion_board(board_df.iloc[[0]].copy()))
    merged = attach_grading(board, raw)
    html = game_card_html(merged.iloc[0])
    assert "ML <strong>W</strong>" in html
    assert "SPREAD <strong>W</strong>" in html
    assert "ML + SPREAD SWEEP" in html
    assert "Saved spread: Home Tech -6.5" in html
    assert "Beat closing line by 1.5 pts" in html


def test_fair_spread_and_closing_spread_are_not_used_as_ats_line(board_df):
    raw = _graded(_champion_board(board_df.iloc[[0]].copy()))
    raw["Closing Home Spread"] = -6.5
    graded, _ = normalize_graded_board(raw)
    assert graded.loc[0, "_spread_source"] == ""
    assert pd.isna(graded.loc[0, "_spread_correct"])
    assert graded.loc[0, "_closing_home_spread"] == -6.5
