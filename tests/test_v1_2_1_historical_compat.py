from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd


def _load_numeric_helper():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_numeric_board_series")
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"pd": pd, "np": np}
    exec(compile(module, str(app_path), "exec"), ns)
    return ns["_numeric_board_series"]


def test_missing_champion_training_columns_return_series_for_historical_board():
    helper = _load_numeric_helper()
    board = pd.DataFrame({"Schedule Translation Training Games": [125, 125], "Data Quality": [70, 68]})
    champion_games = helper(board, "Champion Training Games")
    champion_dates = helper(board, "Champion Training Dates")
    assert isinstance(champion_games, pd.Series)
    assert isinstance(champion_dates, pd.Series)
    assert len(champion_games) == len(board)
    assert champion_games.isna().all()
    assert champion_dates.isna().all()
    assert helper(board, "Schedule Translation Training Games").notna().any()


def test_missing_optional_status_columns_are_safe():
    helper = _load_numeric_helper()
    board = pd.DataFrame(index=range(3))
    assert helper(board, "Data Quality").isna().all()
    assert helper(board, "_display_adj", 0.0).eq(0.0).all()
