from __future__ import annotations

import pandas as pd

from cbb_dashboard.data import normalize_board
from cbb_dashboard.market import attach_market_to_board, normalize_market_import


def test_observed_snapshot_is_not_silently_promoted_to_decision_or_close(board_df):
    raw = board_df.iloc[[0]].copy()
    board, _ = normalize_board(raw)
    snapshots = normalize_market_import(pd.DataFrame([{
        "Slate Date":"2026-01-10", "Game ID":"101", "Snapshot Time UTC":"2026-01-10T19:20:00Z",
        "Market Type":"spread", "Provider":"owls_insight_odds", "Source Label":"Owls Insight · DraftKings",
        "Home Line":-4.5, "Snapshot Role":"observed",
    }]))
    out = attach_market_to_board(board, snapshots)
    row = out.iloc[0]
    assert pd.isna(row.get("_market_decision_home_spread"))
    assert pd.isna(row.get("_market_closing_home_spread"))
    assert pd.isna(row.get("_market_home_spread"))
    assert pd.isna(row.get("_closing_home_spread"))


def test_explicit_decision_and_close_roles_remain_separate(board_df):
    raw = board_df.iloc[[0]].copy()
    board, _ = normalize_board(raw)
    snapshots = normalize_market_import(pd.DataFrame([
        {"Slate Date":"2026-01-10", "Game ID":"101", "Snapshot Time UTC":"2026-01-10T19:20:00Z", "Market Type":"spread", "Provider":"owls_insight_odds", "Source Label":"Owls Insight · DraftKings", "Home Line":-4.5, "Snapshot Role":"decision"},
        {"Slate Date":"2026-01-10", "Game ID":"101", "Snapshot Time UTC":"2026-01-10T19:55:00Z", "Market Type":"spread", "Provider":"owls_insight_odds", "Source Label":"Owls Insight · DraftKings", "Home Line":-5.5, "Snapshot Role":"close"},
    ]))
    row = attach_market_to_board(board, snapshots).iloc[0]
    assert row["_market_decision_home_spread"] == -4.5
    assert row["_market_closing_home_spread"] == -5.5
    assert row["_market_home_spread"] == -4.5
    assert row["_closing_home_spread"] == -5.5
