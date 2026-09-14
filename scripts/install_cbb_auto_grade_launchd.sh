#!/usr/bin/env bash
set -euo pipefail

LABEL="com.statfactory.cbb-auto-grade"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$HOME/.config/stat_factory"
CONFIG_PATH="$CONFIG_DIR/cbb_automation.json"
LOG_DIR="$HOME/Library/Logs/StatFactory/CBB"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUNTIME_DIR="$HOME/Library/Application Support/StatFactory/CBB/venv"
RUNTIME_PY="$RUNTIME_DIR/bin/python"
RUNTIME_LOCK="$WEB_ROOT/requirements-automation.lock"

say() { printf '\n[CBB auto-grade] %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  say "Removed $LABEL. Prediction scheduling was left unchanged."
  exit 0
fi

[ -f "$WEB_ROOT/scripts/run_cbb_auto_grade.py" ] || fail "Automatic grading runner is missing. Pull GitHub main first."
[ -f "$CONFIG_PATH" ] || fail "CBB automation config is missing. Run install_cbb_model_refresh_launchd.sh once first."
[ -f "$RUNTIME_LOCK" ] || fail "Pinned automation requirements are missing: $RUNTIME_LOCK"

BASE_PY="$(command -v python3.12 2>/dev/null || true)"
if [ -z "$BASE_PY" ] && [ -x "$RUNTIME_PY" ]; then
  BASE_PY="$RUNTIME_PY"
fi
[ -n "$BASE_PY" ] || fail "Python 3.12 was not found for the website automation runtime."
mkdir -p "$(dirname "$RUNTIME_DIR")" "$LOG_DIR" "$HOME/Library/LaunchAgents"

if [ ! -x "$RUNTIME_PY" ]; then
  say "Creating isolated CBB automation runtime"
  "$BASE_PY" -m venv "$RUNTIME_DIR"
fi
say "Synchronizing pinned CBB automation dependencies"
"$RUNTIME_PY" -m pip install --disable-pip-version-check -q -r "$RUNTIME_LOCK"
"$RUNTIME_PY" - <<'PY'
import sys
import numpy
import pandas
import supabase
if sys.version_info[:2] != (3, 12):
    raise SystemExit("CBB automation runtime must use Python 3.12")
print("CBB automation runtime verified")
PY
PY="$RUNTIME_PY"

MODEL_ROOT="$("$PY" - "$CONFIG_PATH" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
print(data.get("model_root", ""))
PY
)"
[ -n "$MODEL_ROOT" ] || fail "model_root is missing from $CONFIG_PATH"
[ -f "$MODEL_ROOT/grade_cbb_champion.sh" ] || fail "Frozen champion grader wrapper not found: $MODEL_ROOT/grade_cbb_champion.sh"
[ -f "$MODEL_ROOT/ACTIVE_CBB_Grade_Slate_V1_1_3B_CHAMPION.py" ] || fail "Frozen V1.1.3B grader not found in $MODEL_ROOT"

say "Validating automatic grader without calling CBBD or Supabase"
STAT_FACTORY_HEADLESS_AUTOMATION=1 "$PY" "$WEB_ROOT/scripts/run_cbb_auto_grade.py" --dry-run

"$PY" - "$PLIST" "$PY" "$WEB_ROOT" "$LOG_DIR" "$LABEL" <<'PY'
import pathlib, plistlib, sys
path = pathlib.Path(sys.argv[1])
python = sys.argv[2]
web_root = pathlib.Path(sys.argv[3])
log_dir = pathlib.Path(sys.argv[4])
label = sys.argv[5]
payload = {
    "Label": label,
    "ProgramArguments": [python, str(web_root / "scripts" / "run_cbb_auto_grade.py")],
    "WorkingDirectory": str(web_root),
    "StartInterval": 1800,
    "RunAtLoad": True,
    "ProcessType": "Background",
    "ThrottleInterval": 60,
    "StandardOutPath": str(log_dir / "auto_grader.log"),
    "StandardErrorPath": str(log_dir / "auto_grader_error.log"),
    "EnvironmentVariables": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONNOUSERSITE": "1",
        "STAT_FACTORY_HEADLESS_AUTOMATION": "1",
    },
}
with path.open("wb") as handle:
    plistlib.dump(payload, handle, sort_keys=False)
PY
chmod 600 "$PLIST"
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl enable "gui/$UID/$LABEL" >/dev/null 2>&1 || true

say "Installed successfully"
printf '%s\n' \
  "Runtime: $PY" \
  "Poll cadence: every 30 minutes" \
  "Starts checking a slate 90 minutes after its earliest scheduled tip" \
  "Publishes only when finals/cancellations/final-score corrections change grading state" \
  "Logs: $LOG_DIR/auto_grader.log" \
  "State: $LOG_DIR/last_grading.json" \
  "Uninstall grader only: bash $WEB_ROOT/scripts/install_cbb_auto_grade_launchd.sh --uninstall"
