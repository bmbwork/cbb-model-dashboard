from __future__ import annotations

from cbb_dashboard.storage import sha256_frame


def test_frame_hash_is_deterministic(board_df):
    assert sha256_frame(board_df) == sha256_frame(board_df.copy())
    changed = board_df.copy()
    changed.loc[0, "Win Probability"] = .73
    assert sha256_frame(changed) != sha256_frame(board_df)


def test_records_sort_by_publish_time_not_slate_date():
    from cbb_dashboard.storage import SupabaseSlateStore

    records = [
        {
            "slate_date": "2026-04-04",
            "published_at": "2026-08-09T18:57:00+00:00",
            "revision": 1,
        },
        {
            "slate_date": "2026-03-19",
            "published_at": "2026-08-10T21:40:00+00:00",
            "revision": 1,
        },
    ]

    ordered = SupabaseSlateStore.sort_records_by_publish_recency(records)
    assert ordered[0]["slate_date"] == "2026-03-19"
    assert ordered[1]["slate_date"] == "2026-04-04"


def test_grading_timestamp_does_not_change_default_board_order():
    from cbb_dashboard.storage import SupabaseSlateStore

    records = [
        {
            "slate_date": "2026-03-19",
            "published_at": "2026-08-10T21:40:00+00:00",
            "graded_at": None,
            "updated_at": "2026-08-10T21:40:00+00:00",
        },
        {
            "slate_date": "2026-04-04",
            "published_at": "2026-08-09T18:57:00+00:00",
            "graded_at": "2026-08-10T21:50:00+00:00",
            "updated_at": "2026-08-10T21:50:00+00:00",
        },
    ]

    ordered = SupabaseSlateStore.sort_records_by_publish_recency(records)
    assert ordered[0]["slate_date"] == "2026-03-19"
