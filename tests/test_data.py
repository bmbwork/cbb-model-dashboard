from __future__ import annotations

import pandas as pd
import pytest

from cbb_dashboard.data import DataValidationError, dataframe_records, normalize_board


def test_normalize_v11_board(board_df):
    board, report = normalize_board(board_df)
    assert report.slate_date == "2026-01-10"
    assert report.model_version == "1.1.0"
    assert report.d1_games == 2
    assert board["_pick_changed"].tolist() == [False, True]
    assert board["_translation"].tolist() == [4.0, -3.0]


def test_reject_old_baseline_board(board_df):
    bad = board_df.copy()
    bad["Model Version"] = "1.0.1"
    with pytest.raises(DataValidationError):
        normalize_board(bad)


def test_json_records_strip_internal_fields(board_df):
    board, _ = normalize_board(board_df)
    records = dataframe_records(board)
    assert records and "_rank" not in records[0]
    assert records[0]["Game ID"] == 101


def test_probability_guardrail(board_df):
    bad = board_df.copy()
    bad.loc[0, "Win Probability"] = 1.2
    with pytest.raises(DataValidationError):
        normalize_board(bad)
