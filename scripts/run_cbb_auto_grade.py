#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Reuse the v1.6.1 production-automation configuration/credential contract.
from run_cbb_model_refresh import (
    CONFIG_PATH,
    STATE_DIR,
    load_config,
    resolve_publish_credentials,
    resolve_root,
)

LOCK_PATH = Path.home() / ".config" / "stat_factory" / "cbb_grade.lock"
DEFAULT_ACTOR = "cbb-auto-grader"
DEFAULT_LOOKBACK_DAYS = 2
DEFAULT_MINUTES_AFTER_FIRST_TIP = 90
SLATE_TIMEZONE = "America/Chicago"
TERMINAL_NON_GRADED = {"canceled", "cancelled"}


@contextmanager
def grade_lock(path: Path = LOCK_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another CBB automatic grading run is already active.") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def validate_roots(model_root: Path, web_root: Path) -> None:
    required = [
        model_root / "grade_cbb_champion.sh",
        model_root / "ACTIVE_CBB_Grade_Slate_V1_1_3B_CHAMPION.py",
        web_root / "cbb_dashboard" / "data.py",
        web_root / "cbb_dashboard" / "storage.py",
    ]
    for path in required:
        if not path.exists():
            raise RuntimeError(f"Required automatic-grading file not found: {path}")


def parse_dates(values: Iterable[str]) -> list[date]:
    out: list[date] = []
    seen: set[date] = set()
    for raw in values:
        item = date.fromisoformat(str(raw))
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    values = frame[column]
    if values.dtype == bool:
        return values.fillna(False).astype(bool)
    return values.map(lambda v: str(v).strip().lower() in {"true", "1", "yes", "y"}).fillna(False).astype(bool)


def final_count(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    return int(_bool_series(frame, "Grade Eligible").sum())


def grading_is_settled(frame: pd.DataFrame, expected_rows: int) -> bool:
    if frame is None or frame.empty or expected_rows <= 0 or len(frame) != expected_rows:
        return False
    eligible = _bool_series(frame, "Grade Eligible")
    if int(eligible.sum()) == expected_rows:
        return True
    status = frame.get("Status", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().str.lower()
    terminal = eligible | status.isin(TERMINAL_NON_GRADED)
    return bool(terminal.all())


def grading_fingerprint(frame: pd.DataFrame) -> str:
    """Hash only final/terminal grading state, not transient in-game statuses."""
    if frame is None or frame.empty:
        return ""
    work = pd.DataFrame(index=frame.index)
    work["Game ID"] = frame.get("Game ID", pd.Series("", index=frame.index)).astype(str)
    eligible = _bool_series(frame, "Grade Eligible")
    status = frame.get("Status", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip().str.lower()
    terminal_cancel = status.isin(TERMINAL_NON_GRADED)
    work["Grade Eligible"] = eligible.astype(int)
    work["Terminal Cancel"] = terminal_cancel.astype(int)
    for column in ["Final Away Score", "Final Home Score"]:
        values = pd.to_numeric(frame.get(column, pd.Series(index=frame.index, dtype=float)), errors="coerce")
        work[column] = values.where(eligible)
    # Ignore ordinary scheduled/in-progress status churn. Preserve terminal cancels.
    work["Terminal Status"] = status.where(terminal_cancel, "")
    work = work.sort_values("Game ID", kind="stable").reset_index(drop=True)
    payload = work.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def earliest_tip_utc(board: pd.DataFrame) -> pd.Timestamp | None:
    if board is None or board.empty or "Start Time UTC" not in board.columns:
        return None
    starts = pd.to_datetime(board["Start Time UTC"], utc=True, errors="coerce").dropna()
    if starts.empty:
        return None
    return starts.min()


def is_due_for_poll(
    board: pd.DataFrame,
    now_utc: datetime,
    *,
    minutes_after_first_tip: int = DEFAULT_MINUTES_AFTER_FIRST_TIP,
    force: bool = False,
) -> bool:
    if force:
        return True
    first_tip = earliest_tip_utc(board)
    if first_tip is None:
        # A published board without tip timestamps is rare; allow the grader to
        # use the canonical slate date rather than silently skipping it forever.
        return True
    threshold = first_tip + pd.Timedelta(minutes=int(minutes_after_first_tip))
    return pd.Timestamp(now_utc) >= threshold


def candidate_records(records: list[dict[str, Any]], anchor: date, lookback_days: int) -> list[dict[str, Any]]:
    earliest = anchor - timedelta(days=max(0, int(lookback_days)))
    selected: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("model_version") or "").upper() != "1.1.3B":
            continue
        raw = str(record.get("slate_date") or "")
        try:
            slate = date.fromisoformat(raw)
        except ValueError:
            continue
        if earliest <= slate <= anchor:
            selected.append(record)
    return sorted(selected, key=lambda r: str(r.get("slate_date") or ""))


def make_store(web_root: Path):
    url, secret = resolve_publish_credentials(web_root)
    if str(web_root) not in sys.path:
        sys.path.insert(0, str(web_root))
    from cbb_dashboard.storage import StoreConfig, SupabaseSlateStore

    return SupabaseSlateStore(StoreConfig(url, secret, secret))


def run_champion_grader(model_root: Path, slate_date: str, board: pd.DataFrame) -> Path:
    with tempfile.TemporaryDirectory(prefix=f"cbb_grade_{slate_date}_") as tmp:
        board_path = Path(tmp) / f"published_board_{slate_date}.csv"
        board.to_csv(board_path, index=False)
        command = [
            "bash",
            str(model_root / "grade_cbb_champion.sh"),
            "--date",
            slate_date,
            "--board",
            str(board_path),
        ]
        print(f"[grade] {slate_date} -> frozen V1.1.3B grader", flush=True)
        result = subprocess.run(command, cwd=model_root, text=True, capture_output=True)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-2500:]
            raise RuntimeError(f"Champion grader failed for {slate_date} with exit code {result.returncode}: {detail}")

    output = (
        model_root
        / "outputs"
        / slate_date
        / "grading_champion_v1_1_3B"
        / "latest"
        / f"cbb_graded_board_{slate_date}.csv"
    )
    if not output.exists():
        raise RuntimeError(f"Champion grader completed but output was not found: {output}")
    return output


def validate_graded_board(web_root: Path, path: Path):
    if str(web_root) not in sys.path:
        sys.path.insert(0, str(web_root))
    from cbb_dashboard.data import normalize_graded_board

    raw = pd.read_csv(path)
    return normalize_graded_board(raw)


def grade_record(
    store: Any,
    model_root: Path,
    web_root: Path,
    record: dict[str, Any],
    actor: str,
    now_utc: datetime,
    *,
    force: bool = False,
    minutes_after_first_tip: int = DEFAULT_MINUTES_AFTER_FIRST_TIP,
) -> dict[str, Any]:
    slate_date = str(record.get("slate_date") or "")
    board = pd.DataFrame(record.get("board_json") or [])
    existing = pd.DataFrame(record.get("grading_json") or [])
    result: dict[str, Any] = {
        "date": slate_date,
        "board_rows": int(len(board)),
        "previous_finals": final_count(existing),
    }
    if board.empty:
        result["status"] = "skipped_no_board"
        return result
    if grading_is_settled(existing, len(board)) and not force:
        result["status"] = "skipped_settled"
        return result
    if not is_due_for_poll(board, now_utc, minutes_after_first_tip=minutes_after_first_tip, force=force):
        result["status"] = "skipped_too_early"
        return result

    output = run_champion_grader(model_root, slate_date, board)
    graded, report = validate_graded_board(web_root, output)
    current_finals = final_count(graded)
    result["current_finals"] = current_finals
    result["settled"] = grading_is_settled(graded, len(board))

    # Do not publish an empty live-status snapshot, and do not rewrite Supabase
    # just because a non-final game moved from scheduled -> in progress.
    old_fp = grading_fingerprint(existing)
    new_fp = grading_fingerprint(graded)
    if current_finals == 0 and not result["settled"]:
        result["status"] = "polled_no_finals"
        return result
    if old_fp and old_fp == new_fp:
        result["status"] = "polled_no_change"
        return result

    saved = store.publish_grading(graded, report, output.name, actor)
    result["status"] = "published"
    result["graded_at"] = saved.get("graded_at")
    print(
        f"[publish-grade] {slate_date}: {current_finals}/{len(board)} final; "
        f"{'settled' if result['settled'] else 'partial'} grading published.",
        flush=True,
    )
    return result


def write_state(payload: dict[str, Any]) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / "last_grading.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Poll recent published CBB slates for final scores, run the frozen V1.1.3B grader, and publish changed grading to Supabase."
    )
    parser.add_argument("--model-root", default="")
    parser.add_argument("--web-root", default="")
    parser.add_argument("--anchor-date", default="", help="YYYY-MM-DD; defaults to the Mac's local date.")
    parser.add_argument("--date", action="append", default=[], help="Explicit slate date; repeatable.")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--minutes-after-first-tip", type=int, default=DEFAULT_MINUTES_AFTER_FIRST_TIP)
    parser.add_argument("--actor", default=DEFAULT_ACTOR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    web_root = resolve_root(args.web_root, config, "web_root", Path.home() / "Desktop" / "cbb-model-dashboard")
    model_root = resolve_root(args.model_root, config, "model_root")
    validate_roots(model_root, web_root)
    resolve_publish_credentials(web_root)

    anchor = date.fromisoformat(args.anchor_date) if args.anchor_date else datetime.now(ZoneInfo(SLATE_TIMEZONE)).date()
    explicit_dates = parse_dates(args.date)
    print("CBB automatic grading", flush=True)
    print(f"Model root: {model_root}", flush=True)
    print(f"Web root:   {web_root}", flush=True)
    print("Grader:     frozen V1.1.3B; final scores come from the champion's CBBD client", flush=True)

    if args.dry_run:
        print("Dry run complete. No CBBD or Supabase calls were made.", flush=True)
        return 0

    store = make_store(web_root)
    if explicit_dates:
        dates_to_check = explicit_dates
    else:
        lookback = max(0, int(args.lookback_days))
        dates_to_check = [anchor - timedelta(days=offset) for offset in range(lookback, -1, -1)]

    # Keep the background poll deliberately narrow: at the default lookback this
    # is at most three keyed Supabase reads, never a historical table scan.
    records: list[dict[str, Any]] = []
    for target in dates_to_check:
        record = store.get(target.isoformat(), admin=True)
        if record and str(record.get("model_version") or "").upper() == "1.1.3B":
            records.append(record)

    now_utc = datetime.now(timezone.utc)
    started = datetime.now().astimezone().isoformat()
    results: list[dict[str, Any]] = []
    failures = 0
    with grade_lock():
        for record in records:
            try:
                results.append(
                    grade_record(
                        store,
                        model_root,
                        web_root,
                        record,
                        args.actor,
                        now_utc,
                        force=args.force,
                        minutes_after_first_tip=args.minutes_after_first_tip,
                    )
                )
            except Exception as exc:
                failures += 1
                slate_date = str(record.get("slate_date") or "")
                print(f"[error] {slate_date}: {exc}", file=sys.stderr, flush=True)
                results.append({"date": slate_date, "status": "failed", "error": str(exc)})

    state = {
        "started_at": started,
        "finished_at": datetime.now().astimezone().isoformat(),
        "anchor_date": anchor.isoformat(),
        "results": results,
        "failures": failures,
    }
    state_path = write_state(state)
    print(f"Run state: {state_path}", flush=True)
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
