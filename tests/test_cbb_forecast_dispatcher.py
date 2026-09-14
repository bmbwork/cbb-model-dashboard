from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scripts import dispatch_cbb_model_refresh as dispatcher


CT = ZoneInfo("America/Chicago")


def local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=CT)


def action_pairs(actions):
    return [(stage, target) for stage, target, _ in actions]


def test_missed_early_stage_catches_up_after_sleep_before_mid_window():
    now = local(2026, 11, 10, 7, 0)
    actions = dispatcher.due_actions(now, {"stages": {}}, None)

    assert action_pairs(actions) == [("early", date(2026, 11, 10))]
    assert actions[0][2] == local(2026, 11, 9, 18, 15)


def test_missed_early_is_not_backfilled_once_mid_is_due_without_a_board():
    now = local(2026, 11, 10, 8, 30)
    actions = dispatcher.due_actions(now, {"stages": {}}, None)

    assert action_pairs(actions) == [("mid", date(2026, 11, 10))]
    assert actions[0][2] == local(2026, 11, 10, 8, 15)


def test_first_tip_drives_mid_and_late_stages():
    first_tip = local(2026, 11, 10, 19, 0).astimezone(timezone.utc)

    mid = dispatcher.due_actions(local(2026, 11, 10, 9, 0), {"stages": {}}, first_tip)
    assert action_pairs(mid) == [("mid", date(2026, 11, 10))]
    assert mid[0][2] == local(2026, 11, 10, 9, 0)

    late = dispatcher.due_actions(local(2026, 11, 10, 16, 0), {"stages": {}}, first_tip)
    assert action_pairs(late) == [("late", date(2026, 11, 10))]
    assert late[0][2] == local(2026, 11, 10, 16, 0)


def test_completed_or_superseded_stages_do_not_duplicate():
    target = date(2026, 11, 10)
    state = {
        "stages": {
            dispatcher.stage_key(target, "early"): {"status": "completed"},
            dispatcher.stage_key(target, "mid"): {"status": "superseded"},
        }
    }
    first_tip = local(2026, 11, 10, 19, 0).astimezone(timezone.utc)

    actions = dispatcher.due_actions(local(2026, 11, 10, 10, 0), state, first_tip)
    assert actions == []


def test_failed_stage_obeys_retry_backoff():
    target = date(2026, 11, 10)
    now = local(2026, 11, 10, 7, 0)
    state = {
        "stages": {
            dispatcher.stage_key(target, "early"): {
                "status": "failed",
                "attempts": 1,
                "attempted_at_utc": (now - timedelta(minutes=10)).astimezone(timezone.utc).isoformat(),
            }
        }
    }
    assert dispatcher.due_actions(now, state, None) == []

    retry_now = now + timedelta(minutes=21)
    actions = dispatcher.due_actions(retry_now, state, None)
    assert action_pairs(actions) == [("early", target)]


def test_later_success_supersedes_older_unfinished_stage_without_overwriting_completed():
    target = date(2026, 11, 10)
    now = local(2026, 11, 10, 16, 0)
    state = {
        "stages": {
            dispatcher.stage_key(target, "early"): {"status": "completed", "attempts": 1},
            dispatcher.stage_key(target, "mid"): {"status": "failed", "attempts": 2},
        }
    }

    dispatcher.mark_superseded(state, target, "early", now)
    dispatcher.mark_superseded(state, target, "mid", now)

    assert state["stages"][dispatcher.stage_key(target, "early")]["status"] == "completed"
    assert state["stages"][dispatcher.stage_key(target, "mid")]["status"] == "superseded"


def test_mid_due_time_respects_chicago_dst_transition():
    target = date(2027, 3, 14)
    first_tip = local(2027, 3, 14, 17, 0).astimezone(timezone.utc)

    due = dispatcher.mid_due_time(target, first_tip)

    assert due == local(2027, 3, 14, 7, 0)
    assert due.utcoffset() == timedelta(hours=-5)
