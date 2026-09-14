from __future__ import annotations

from datetime import date, datetime, timezone
import importlib.util
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_cbb_model_refresh.py"
DISPATCHER = ROOT / "scripts" / "dispatch_cbb_model_refresh.py"
INSTALLER = ROOT / "scripts" / "install_cbb_model_refresh_launchd.sh"
TZ = ZoneInfo("America/Chicago")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manual_runner_defaults_to_anchor_date_only():
    module = load_module(RUNNER, "cbb_model_refresh")
    assert module.scheduled_target_dates(date(2026, 11, 9)) == [date(2026, 11, 9)]
    assert module.scheduled_target_dates(date(2026, 11, 14)) == [date(2026, 11, 14)]


def test_dispatcher_early_stage_targets_tomorrow_after_1815():
    module = load_module(DISPATCHER, "cbb_dispatch_early")
    state = {"stages": {}}
    before = datetime(2026, 11, 9, 18, 0, tzinfo=TZ)
    after = datetime(2026, 11, 9, 18, 20, tzinfo=TZ)
    assert not [a for a in module.due_actions(before, state, None) if a[0] == "early"]
    actions = module.due_actions(after, state, None)
    assert ("early", date(2026, 11, 10)) == (actions[0][0], actions[0][1])


def test_dispatcher_mid_is_game_relative_with_morning_floor():
    module = load_module(DISPATCHER, "cbb_dispatch_mid")
    target = date(2026, 11, 10)
    evening_tip = datetime(2026, 11, 11, 0, 0, tzinfo=timezone.utc)  # 18:00 CT
    assert module.mid_due_time(target, evening_tip) == datetime(2026, 11, 10, 8, 0, tzinfo=TZ)

    noon_tip = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)  # 12:00 CT
    assert module.mid_due_time(target, noon_tip) == datetime(2026, 11, 10, 6, 15, tzinfo=TZ)
    assert module.mid_due_time(target, None) == datetime(2026, 11, 10, 8, 15, tzinfo=TZ)


def test_dispatcher_late_is_three_hours_before_first_tip_and_supersedes_mid_when_both_due():
    module = load_module(DISPATCHER, "cbb_dispatch_late")
    first_tip = datetime(2026, 11, 11, 0, 0, tzinfo=timezone.utc)  # 18:00 CT
    assert module.late_due_time(first_tip) == datetime(2026, 11, 10, 15, 0, tzinfo=TZ)

    now = datetime(2026, 11, 10, 15, 20, tzinfo=TZ)
    actions = module.due_actions(now, {"stages": {}}, first_tip)
    today = [a for a in actions if a[1] == date(2026, 11, 10)]
    assert [a[0] for a in today] == ["late"]


def test_dispatcher_fail_closed_without_board_after_morning_cutoff():
    module = load_module(DISPATCHER, "cbb_dispatch_noboard_cutoff")
    now = datetime(2026, 11, 10, 12, 30, tzinfo=TZ)
    actions = module.due_actions(now, {"stages": {}}, None)
    assert not [a for a in actions if a[1] == date(2026, 11, 10) and a[0] == "mid"]


def test_dispatcher_never_runs_mid_or_late_after_first_tip():
    module = load_module(DISPATCHER, "cbb_dispatch_posttip")
    first_tip = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)  # 12:00 CT
    now = datetime(2026, 11, 10, 12, 30, tzinfo=TZ)
    actions = module.due_actions(now, {"stages": {}}, first_tip)
    assert not [a for a in actions if a[1] == date(2026, 11, 10) and a[0] in {"mid", "late"}]


def test_launchd_installer_uses_dispatcher_and_background_safe_runtime():
    text = INSTALLER.read_text(encoding="utf-8")
    assert 'SAFE_VENV="$HOME/Library/Application Support/StatFactory/CBB/venv/bin/python"' in text
    assert '"StartInterval": 1800' in text
    assert '"RunAtLoad": True' in text
    assert "dispatch_cbb_model_refresh.py" in text
    assert "Mon/Wed/Sat 05:15" not in text
    assert "run_cbb_champion.sh" in text
    assert "ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py" in text


def test_runner_and_dispatcher_preserve_model_market_firewall():
    runner = RUNNER.read_text(encoding="utf-8")
    dispatcher = DISPATCHER.read_text(encoding="utf-8")
    assert 'model_root / "run_cbb_champion.sh"' in runner
    assert '"--refresh-data"' in runner
    assert "SupabaseSlateStore" in runner
    assert "store.publish_board" in runner
    assert "OWLS_INSIGHT_API_KEY" not in runner + dispatcher
    assert "market_current" not in runner + dispatcher
