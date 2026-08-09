from __future__ import annotations

from cbb_dashboard.storage import sha256_frame


def test_frame_hash_is_deterministic(board_df):
    assert sha256_frame(board_df) == sha256_frame(board_df.copy())
    changed = board_df.copy()
    changed.loc[0, "Win Probability"] = .73
    assert sha256_frame(changed) != sha256_frame(board_df)
