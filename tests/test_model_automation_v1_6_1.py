from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_cbb_model_refresh.py"
INSTALLER = ROOT / "scripts" / "install_cbb_model_refresh_launchd.sh"


def load_runner():
    spec = importlib.util.spec_from_file_location("cbb_model_refresh", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scheduled_windows_cover_full_week_without_gaps():
    module = load_runner()
    assert [d.isoformat() for d in module.scheduled_target_dates(date(2026, 11, 9))] == [
        "2026-11-09", "2026-11-10", "2026-11-11"
    ]
    assert [d.isoformat() for d in module.scheduled_target_dates(date(2026, 11, 11))] == [
        "2026-11-11", "2026-11-12", "2026-11-13"
    ]
    assert [d.isoformat() for d in module.scheduled_target_dates(date(2026, 11, 14))] == [
        "2026-11-14", "2026-11-15"
    ]


def test_non_scheduled_manual_run_defaults_to_one_date():
    module = load_runner()
    assert module.scheduled_target_dates(date(2026, 11, 10)) == [date(2026, 11, 10)]


def test_launchd_schedule_is_mon_wed_sat_early_local_time():
    text = INSTALLER.read_text(encoding="utf-8")
    assert '{"Weekday": 2, "Hour": 5, "Minute": 15}' in text
    assert '{"Weekday": 4, "Hour": 5, "Minute": 15}' in text
    assert '{"Weekday": 7, "Hour": 5, "Minute": 15}' in text
    assert "run_cbb_champion.sh" in text
    assert "ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py" in text


def test_runner_uses_frozen_champion_and_publishes_downstream_only():
    text = RUNNER.read_text(encoding="utf-8")
    assert 'model_root / "run_cbb_champion.sh"' in text
    assert '"--refresh-data"' in text
    assert "SupabaseSlateStore" in text
    assert "store.publish_board" in text
    assert "OWLS_INSIGHT_API_KEY" not in text
    assert "market_current" not in text


def test_scheduled_runner_publishes_anchor_date_last_for_v160_today_board():
    text = RUNNER.read_text(encoding="utf-8")
    assert "targets = targets[1:] + targets[:1]" in text
    assert "publication-recency default still resolves to the current day" in text
