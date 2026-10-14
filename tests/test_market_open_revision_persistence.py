from datetime import datetime, timezone

import pandas as pd

from cbb_dashboard.market import _role_row, normalize_market_import, summarize_game_market
from cbb_dashboard.best_odds_archive import _role_row as archive_role_row


def test_cbb_new_forecast_cannot_replace_first_tracked_open_snapshot():
    snapshots = normalize_market_import(pd.DataFrame([
        {"Slate Date": "2026-11-14", "Game ID": "cbb-2026-1",
         "Snapshot Time UTC": "2026-11-10T16:00:00Z",
         "Market Type": "spread", "Snapshot Role": "open",
         "Provider": "owls", "Home Line": -4.0, "Opening Home Line": -4.0},
        {"Slate Date": "2026-11-14", "Game ID": "cbb-2026-1",
         "Snapshot Time UTC": "2026-11-12T16:00:00Z",
         "Market Type": "spread", "Snapshot Role": "open",
         "Provider": "owls", "Home Line": -6.0, "Opening Home Line": -6.0},
        {"Slate Date": "2026-11-14", "Game ID": "cbb-2026-1",
         "Snapshot Time UTC": "2026-11-12T16:05:00Z",
         "Market Type": "spread", "Snapshot Role": "decision",
         "Provider": "owls", "Home Line": -6.0},
        {"Slate Date": "2026-11-14", "Game ID": "cbb-2026-1",
         "Snapshot Time UTC": "2026-11-12T18:00:00Z",
         "Market Type": "spread", "Snapshot Role": "observed",
         "Provider": "owls", "Home Line": -7.0},
    ]))
    board = pd.Series({
        "Game ID": "cbb-2026-1",
        "Home Team": "Home",
        "Away Team": "Away",
        "Start Time UTC": "2026-11-14T20:00:00Z",
        "Model Run At UTC": "2026-11-12T15:30:00Z",
    })
    state = summarize_game_market(board, snapshots)
    assert state.opening_home_spread == -4.0
    assert state.current_home_spread == -7.0
    assert state.decision_home_spread == -6.0


def test_cbb_only_tracked_pre_tip_open_can_anchor_line():
    frame = pd.DataFrame([
        {"Snapshot Role": "open", "Snapshot Time UTC": pd.Timestamp("2026-11-10T16:00Z"), "Home Line": -4},
        {"Snapshot Role": "open", "Snapshot Time UTC": pd.Timestamp("2026-11-12T16:00Z"), "Home Line": -6},
    ])
    assert _role_row(frame, "open")["Home Line"] == -4
    assert _role_row(frame, "decision") is None


def test_cbb_archive_keeps_first_game_open_among_multiple_revisions():
    frame = pd.DataFrame([
        {"market_type": "spread", "captured_at_utc": "2026-11-10T15:00:00Z", "snapshot_role": "open", "best_home_line": -4},
        {"market_type": "spread", "captured_at_utc": "2026-11-12T15:00:00Z", "snapshot_role": "open", "best_home_line": -6},
    ])
    assert float(archive_role_row(frame, "spread", "open")["best_home_line"]) == -4
