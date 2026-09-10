#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Iterable

import pandas as pd

CONFIG_DIR = Path.home() / ".config" / "stat_factory"
CONFIG_PATH = CONFIG_DIR / "cbb_automation.json"
ENV_PATH = CONFIG_DIR / "cbb_automation.env"
STATE_DIR = Path.home() / "Library" / "Logs" / "StatFactory" / "CBB"
LOCK_PATH = CONFIG_DIR / "cbb_refresh.lock"
DEFAULT_ACTOR = "cbb-scheduled-refresh"


def _clean_secret(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.upper().startswith("YOUR_") or text.upper().startswith("REPLACE_ME"):
        return ""
    return text


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_streamlit_secrets(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(k): str(v) for k, v in raw.items() if not isinstance(v, dict)}


def resolve_publish_credentials(web_root: Path) -> tuple[str, str]:
    file_env = read_env_file(ENV_PATH)
    streamlit = read_streamlit_secrets(web_root / ".streamlit" / "secrets.toml")

    def first(*keys: str) -> str:
        for key in keys:
            for source in (os.environ, file_env, streamlit):
                value = _clean_secret(source.get(key, ""))
                if value:
                    return value
        return ""

    url = first("SUPABASE_URL")
    secret = first("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    if not url or not secret:
        raise RuntimeError(
            "Supabase automation credentials are missing. Run scripts/install_cbb_model_refresh_launchd.sh "
            "once from an interactive terminal to configure them securely."
        )
    return url, secret


def scheduled_target_dates(anchor: date) -> list[date]:
    """Return the forecast window for a scheduled Monday/Wednesday/Saturday run."""
    if anchor.weekday() == 0:  # Monday -> Mon, Tue, Wed
        offsets = (0, 1, 2)
    elif anchor.weekday() == 2:  # Wednesday -> Wed, Thu, Fri
        offsets = (0, 1, 2)
    elif anchor.weekday() == 5:  # Saturday -> Sat, Sun
        offsets = (0, 1)
    else:
        offsets = (0,)
    return [anchor + timedelta(days=offset) for offset in offsets]


def parse_dates(values: Iterable[str]) -> list[date]:
    out: list[date] = []
    seen: set[date] = set()
    for value in values:
        item = date.fromisoformat(str(value))
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def load_config(path: Path = CONFIG_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Could not parse automation config: {path}") from exc
    return {str(k): str(v) for k, v in data.items() if v is not None}


def resolve_root(cli_value: str, config: dict[str, str], key: str, fallback: Path | None = None) -> Path:
    raw = str(cli_value or config.get(key, "") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    if fallback is not None:
        return fallback.expanduser().resolve()
    raise RuntimeError(f"Automation config is missing {key}.")


@contextmanager
def run_lock(path: Path = LOCK_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another CBB scheduled refresh is already running.") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def validate_roots(model_root: Path, web_root: Path) -> None:
    required_model = [
        model_root / "run_cbb_champion.sh",
        model_root / "ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py",
    ]
    for path in required_model:
        if not path.exists():
            raise RuntimeError(f"Required frozen champion file not found: {path}")
    if not (web_root / "cbb_dashboard" / "storage.py").exists():
        raise RuntimeError(f"CBB website repository not found at: {web_root}")


def run_model(model_root: Path, target: date, refresh_data: bool) -> tuple[str, Path | None]:
    command = ["bash", str(model_root / "run_cbb_champion.sh"), "--date", target.isoformat()]
    if refresh_data:
        command.append("--refresh-data")
    print(f"[model] {target.isoformat()} -> {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=model_root, text=True)
    if result.returncode == 3:
        print(f"[model] {target.isoformat()}: no modelable games; publish skipped.", flush=True)
        return "no_games", None
    if result.returncode != 0:
        raise RuntimeError(f"Champion runner failed for {target.isoformat()} with exit code {result.returncode}.")
    board = model_root / "outputs" / target.isoformat() / "latest" / f"cbb_decision_board_{target.isoformat()}.csv"
    if not board.exists():
        raise RuntimeError(f"Champion completed but website board was not found: {board}")
    return "modeled", board


def publish_board(web_root: Path, board_path: Path, actor: str) -> dict[str, object]:
    url, secret = resolve_publish_credentials(web_root)
    if str(web_root) not in sys.path:
        sys.path.insert(0, str(web_root))
    from cbb_dashboard.data import normalize_board
    from cbb_dashboard.storage import StoreConfig, SupabaseSlateStore

    raw = pd.read_csv(board_path)
    board, report = normalize_board(raw)
    # A service-role key is intentionally used only by this local automation.
    # Passing it for the public-client slot avoids requiring a second local key;
    # all writes still go through the admin client inside SupabaseSlateStore.
    store = SupabaseSlateStore(StoreConfig(url, secret, secret))
    saved = store.publish_board(board, report, board_path.name, actor)
    revision = int(saved.get("revision") or 1)
    print(
        f"[publish] {report.slate_date}: revision {revision}, {report.rows} games, "
        f"{report.d1_games} D-I games.",
        flush=True,
    )
    return saved


def write_run_state(payload: dict[str, object]) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / "last_refresh.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run frozen CBB V1.1.3B on the scheduled horizon and publish each slate to Supabase."
    )
    parser.add_argument("--model-root", default="")
    parser.add_argument("--web-root", default="")
    parser.add_argument("--anchor-date", default="", help="YYYY-MM-DD; defaults to the Mac's local date.")
    parser.add_argument("--date", action="append", default=[], help="Explicit target date; repeatable.")
    parser.add_argument("--no-refresh-data", action="store_true")
    parser.add_argument("--actor", default=DEFAULT_ACTOR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config()
    web_root = resolve_root(args.web_root, config, "web_root", Path.home() / "Desktop" / "cbb-model-dashboard")
    model_root = resolve_root(args.model_root, config, "model_root")
    validate_roots(model_root, web_root)

    anchor = date.fromisoformat(args.anchor_date) if args.anchor_date else datetime.now().astimezone().date()
    targets = parse_dates(args.date) if args.date else scheduled_target_dates(anchor)
    if not args.date and len(targets) > 1:
        # Publish future slates first and the anchor/current slate last so the
        # v1.6.0 publication-recency default still resolves to the current day.
        targets = targets[1:] + targets[:1]
    if not targets:
        raise RuntimeError("No target dates were selected.")

    # Validate publishing credentials before spending model/API work.
    resolve_publish_credentials(web_root)

    print("CBB scheduled production refresh", flush=True)
    print(f"Model root: {model_root}", flush=True)
    print(f"Web root:   {web_root}", flush=True)
    print("Targets:    " + ", ".join(d.isoformat() for d in targets), flush=True)
    print("Model:      frozen V1.1.3B; sportsbook data is not passed to the model", flush=True)

    if args.dry_run:
        print("Dry run complete. No model or Supabase calls were made.", flush=True)
        return 0

    started = datetime.now().astimezone().isoformat()
    results: list[dict[str, object]] = []
    failures = 0
    with run_lock():
        for target in targets:
            row: dict[str, object] = {"date": target.isoformat()}
            try:
                status, board_path = run_model(model_root, target, refresh_data=not args.no_refresh_data)
                row["model_status"] = status
                if board_path is not None:
                    saved = publish_board(web_root, board_path, args.actor)
                    row["publish_status"] = "published"
                    row["revision"] = int(saved.get("revision") or 1)
                    row["board"] = str(board_path)
                else:
                    row["publish_status"] = "skipped"
            except Exception as exc:
                failures += 1
                row["status"] = "failed"
                row["error"] = str(exc)
                print(f"[error] {target.isoformat()}: {exc}", file=sys.stderr, flush=True)
            results.append(row)

    state = {
        "started_at": started,
        "finished_at": datetime.now().astimezone().isoformat(),
        "anchor_date": anchor.isoformat(),
        "targets": [d.isoformat() for d in targets],
        "results": results,
        "failures": failures,
    }
    state_path = write_run_state(state)
    print(f"Run state: {state_path}", flush=True)
    if failures:
        print(f"CBB scheduled refresh finished with {failures} failed target(s).", file=sys.stderr, flush=True)
        return 1
    print("CBB scheduled refresh complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
