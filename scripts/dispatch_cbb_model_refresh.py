#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_cbb_model_refresh import (
    CONFIG_PATH,
    load_config,
    resolve_publish_credentials,
    resolve_root,
    validate_roots,
)

SLATE_TIMEZONE = "America/Chicago"
TZ = ZoneInfo(SLATE_TIMEZONE)
STATE_PATH = Path.home() / ".config" / "stat_factory" / "cbb_dispatch_state.json"
EARLY_LOCAL = time(18, 15)
MID_FALLBACK_LOCAL = time(8, 15)
MID_EARLIEST_LOCAL = time(6, 15)
MID_NO_BOARD_CUTOFF_LOCAL = time(10, 0)
MID_LEAD = timedelta(hours=10)
LATE_LEAD = timedelta(hours=3)
RETRY_BASE = timedelta(minutes=30)
RETRY_CAP = timedelta(hours=3)


def _local_dt(day: date, value: time) -> datetime:
    return datetime.combine(day, value, tzinfo=TZ)


def parse_utc(value: object) -> datetime | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def first_tip_from_record(record: dict[str, Any] | None) -> datetime | None:
    if not record:
        return None
    board = pd.DataFrame(record.get("board_json") or [])
    if board.empty or "Start Time UTC" not in board.columns:
        return None
    starts = pd.to_datetime(board["Start Time UTC"], errors="coerce", utc=True).dropna()
    if starts.empty:
        return None
    return starts.min().to_pydatetime()


def mid_due_time(target: date, first_tip_utc: datetime | None) -> datetime:
    if first_tip_utc is None:
        return _local_dt(target, MID_FALLBACK_LOCAL)
    candidate = first_tip_utc.astimezone(TZ) - MID_LEAD
    floor = _local_dt(target, MID_EARLIEST_LOCAL)
    return max(candidate, floor)


def late_due_time(first_tip_utc: datetime) -> datetime:
    return first_tip_utc.astimezone(TZ) - LATE_LEAD


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"stages": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"stages": {}}
    stages = raw.get("stages")
    if not isinstance(stages, dict):
        stages = {}
    return {"stages": stages}


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cutoff = (datetime.now(TZ).date() - timedelta(days=21)).isoformat()
    stages = {
        key: value
        for key, value in dict(state.get("stages") or {}).items()
        if key.split(":", 1)[0] >= cutoff
    }
    path.write_text(json.dumps({"stages": stages}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stage_key(target: date, stage: str) -> str:
    return f"{target.isoformat()}:{stage}"


def stage_done(state: dict[str, Any], target: date, stage: str) -> bool:
    row = dict(state.get("stages") or {}).get(stage_key(target, stage), {})
    return str(row.get("status") or "") in {"completed", "superseded"}


def retry_allowed(state: dict[str, Any], target: date, stage: str, now: datetime) -> bool:
    row = dict(state.get("stages") or {}).get(stage_key(target, stage), {})
    if str(row.get("status") or "") != "failed":
        return True
    last = parse_utc(row.get("attempted_at_utc"))
    if last is None:
        return True
    attempts = max(1, int(row.get("attempts") or 1))
    wait = min(RETRY_BASE * (2 ** min(attempts - 1, 4)), RETRY_CAP)
    return now.astimezone(timezone.utc) >= last + wait


def mark_superseded(state: dict[str, Any], target: date, stage: str, now: datetime) -> None:
    if stage_done(state, target, stage):
        return
    state.setdefault("stages", {})[stage_key(target, stage)] = {
        "status": "superseded",
        "attempts": 0,
        "attempted_at_utc": now.astimezone(timezone.utc).isoformat(),
        "returncode": 0,
    }


def due_actions(
    now: datetime,
    state: dict[str, Any],
    today_first_tip_utc: datetime | None,
) -> list[tuple[str, date, datetime]]:
    """Return due model revisions without backfilling a stage after a later stage is due.

    The previous-evening EARLY revision may be caught up after sleep/restart, but only
    until the MID window opens. Once MID or LATE is due, the older stage is obsolete.
    """
    local_now = now.astimezone(TZ)
    today = local_now.date()
    actions: list[tuple[str, date, datetime]] = []

    before_tip = today_first_tip_utc is None or local_now < today_first_tip_utc.astimezone(TZ)
    no_board_window_open = today_first_tip_utc is not None or local_now <= _local_dt(today, MID_NO_BOARD_CUTOFF_LOCAL)
    if before_tip and no_board_window_open:
        middle_due = mid_due_time(today, today_first_tip_utc)
        late_due = late_due_time(today_first_tip_utc) if today_first_tip_utc is not None else None
        missed_early_due = _local_dt(today - timedelta(days=1), EARLY_LOCAL)

        if (
            local_now >= missed_early_due
            and local_now < middle_due
            and not stage_done(state, today, "early")
            and retry_allowed(state, today, "early", local_now)
        ):
            actions.append(("early", today, missed_early_due))
        elif (
            late_due is not None
            and local_now >= late_due
            and not stage_done(state, today, "late")
            and retry_allowed(state, today, "late", local_now)
        ):
            actions.append(("late", today, late_due))
        elif (
            local_now >= middle_due
            and not stage_done(state, today, "mid")
            and retry_allowed(state, today, "mid", local_now)
        ):
            actions.append(("mid", today, middle_due))

    tomorrow = today + timedelta(days=1)
    early_due = _local_dt(today, EARLY_LOCAL)
    if (
        local_now >= early_due
        and not stage_done(state, tomorrow, "early")
        and retry_allowed(state, tomorrow, "early", local_now)
    ):
        actions.append(("early", tomorrow, early_due))

    return actions


def make_store(web_root: Path):
    url, secret = resolve_publish_credentials(web_root)
    if str(web_root) not in sys.path:
        sys.path.insert(0, str(web_root))
    from cbb_dashboard.storage import StoreConfig, SupabaseSlateStore

    return SupabaseSlateStore(StoreConfig(url, secret, secret))


def current_first_tip(store: Any, target: date) -> datetime | None:
    record = store.get(target.isoformat(), admin=True)
    return first_tip_from_record(record)


def record_attempt(
    state: dict[str, Any],
    target: date,
    stage: str,
    status: str,
    now: datetime,
    returncode: int,
) -> None:
    key = stage_key(target, stage)
    stages = state.setdefault("stages", {})
    previous = dict(stages.get(key) or {})
    attempts = int(previous.get("attempts") or 0) + 1
    stages[key] = {
        "status": status,
        "attempts": attempts,
        "attempted_at_utc": now.astimezone(timezone.utc).isoformat(),
        "returncode": int(returncode),
    }


def run_stage(web_root: Path, target: date, stage: str) -> int:
    command = [
        sys.executable,
        str(web_root / "scripts" / "run_cbb_model_refresh.py"),
        "--date",
        target.isoformat(),
        "--actor",
        f"cbb-scheduled-{stage}",
    ]
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=web_root, text=True)
    return int(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch CBB V1.1.3B forecast revisions: next-day early, game-day middle, "
            "and a late revision three hours before the first scheduled tip."
        )
    )
    parser.add_argument("--model-root", default="")
    parser.add_argument("--web-root", default="")
    parser.add_argument("--now", default="", help="Testing override: ISO timestamp. Production uses current time.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    web_root = resolve_root(args.web_root, config, "web_root", Path.home() / "Desktop" / "cbb-model-dashboard")
    model_root = resolve_root(args.model_root, config, "model_root")
    validate_roots(model_root, web_root)
    resolve_publish_credentials(web_root)

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    now = now.astimezone(TZ)

    if args.dry_run:
        print("CBB forecast dispatcher dry run")
        print(f"Local time:  {now.isoformat()}")
        print("Cadence:     early = 18:15 CT for tomorrow, with pre-mid catch-up after sleep/restart")
        print("             mid   = max(06:15 CT, first tip - 10h); fallback 08:15 CT before 10:00 CT if no board exists")
        print("             late  = first tip - 3h")
        print("Poll:        every 30 minutes via launchd")
        print("Model:       frozen V1.1.3B; no sportsbook data enters the model")
        print("Dry run complete. No model, provider, or Supabase read/write calls were made.")
        return 0

    store = make_store(web_root)
    first_tip = current_first_tip(store, now.date())
    state = load_state()
    actions = due_actions(now, state, first_tip)
    if not actions:
        payload = {
            "status": "no_action_due",
            "local_time": now.isoformat(),
            "first_tip_utc": first_tip.isoformat() if first_tip else None,
        }
        print(json.dumps(payload, sort_keys=True), flush=True)
        return 0

    failures = 0
    for stage, target, due_at in actions:
        print(
            json.dumps(
                {
                    "status": "running",
                    "stage": stage,
                    "target_date": target.isoformat(),
                    "due_at_local": due_at.isoformat(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        code = run_stage(web_root, target, stage)
        if code == 0:
            record_attempt(state, target, stage, "completed", now, code)
            if stage == "mid":
                mark_superseded(state, target, "early", now)
            elif stage == "late":
                mark_superseded(state, target, "early", now)
                mark_superseded(state, target, "mid", now)
        else:
            failures += 1
            record_attempt(state, target, stage, "failed", now, code)
        save_state(state)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
