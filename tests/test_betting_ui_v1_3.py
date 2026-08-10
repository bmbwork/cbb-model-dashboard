from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from cbb_dashboard.data import board_table, normalize_board, normalize_graded_board
from cbb_dashboard.intelligence import game_card_html, market_context_html


def test_public_board_table_excludes_development_plumbing(board_df):
    board, _ = normalize_board(board_df)
    table = board_table(board)
    assert "V1.0.1 Baseline Pick" not in table.columns
    assert "Champion Margin Calibration Adj" not in table.columns
    assert "Schedule Translation Margin Adj" not in table.columns
    assert "Home AdjO" in table.columns
    assert "Away AdjD" in table.columns


def test_closing_only_cannot_create_ats_grade(board_df):
    raw = board_df.iloc[[0]].copy()
    raw["Final Away Score"] = 70
    raw["Final Home Score"] = 80
    raw["Status"] = "final"
    raw["Grade Eligible"] = True
    raw["Actual Winner"] = "Home Tech"
    raw["Actual Home Margin"] = 10.0
    raw["Actual Total"] = 150.0
    raw["Model Winner Correct"] = True
    raw["Absolute Margin Error"] = 1.0
    raw["Brier Component"] = 0.05
    raw["Log Loss Component"] = 0.2
    raw["Closing Home Spread"] = -7.5
    graded, _ = normalize_graded_board(raw)
    assert pd.isna(graded.loc[0, "_spread_correct"])
    html = game_card_html(graded.iloc[0])
    assert "SPREAD <span" not in html
    assert "SPREAD <strong>W</strong>" not in html
    assert "spread result needs a pregame/taken line" in html


def test_no_market_line_does_not_create_betting_recommendation(board_df):
    board, _ = normalize_board(board_df)
    html = market_context_html(board.iloc[0])
    assert "No pregame sportsbook spread saved" in html
    assert "will not grade the spread" in html


def test_app_version_and_public_page_copy_are_v13():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(app)
    assert 'APP_VERSION = "1.3.4"' in app
    assert "Open <strong>Why this pick?</strong>" in app
