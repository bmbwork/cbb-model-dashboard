#!/usr/bin/env bash
set -euo pipefail

LABEL="com.statfactory.cbb-auto-grade"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_WEB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$HOME/.config/stat_factory"
CONFIG_PATH="$CONFIG_DIR/cbb_automation.json"
LOG_DIR="$HOME/Library/Logs/StatFactory/CBB"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
MANAGED_BASE="$HOME/Library/Application Support/StatFactory/CBB"
EXPECTED_WEB_ROOT="$MANAGED_BASE/dashboard_runtime"
RUNTIME_DIR="$MANAGED_BASE/venv"
RUNTIME_PY="$RUNTIME_DIR/bin/python"
STAGER="$SOURCE_WEB_ROOT/scripts/stage_cbb_background_runtime.sh"

say() { printf '\n[CBB auto-grade] %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  say "Removed $LABEL. Prediction scheduling was left unchanged."
  exit 0
fi

[ -f "$SOURCE_WEB_ROOT/scripts/run_cbb_auto_grade.py" ] || fail "Automatic grading runner is missing. Pull GitHub main first."
[ -f "$STAGER" ] || fail "Background runtime staging helper is missing. Pull GitHub main first."
[ -f "$CONFIG_PATH" ] || fail "CBB automation config is missing. Run install_cbb_model_refresh_launchd.sh once first."

readarray -t CONFIG_VALUES < <(python3 - "$CONFIG_PATH" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
print(data.get("web_root", ""))
print(data.get("model_root", ""))
print(data.get("runtime_policy", ""))
PY
)
WEB_ROOT="${CONFIG_VALUES[0]:-}"
MODEL_ROOT="${CONFIG_VALUES[1]:-}"
RUNTIME_POLICY="${CONFIG_VALUES[2]:-}"
[ "$WEB_ROOT" = "$EXPECTED_WEB_ROOT" ] || fail "CBB config still points at a legacy/Desktop dashboard runtime. Run scripts/install_cbb_model_refresh_launchd.sh first."
[ "$RUNTIME_POLICY" = "managed_app_support_v1" ] || fail "CBB config has not been migrated to the managed background runtime. Run the model-refresh installer first."
[ -n "$MODEL_ROOT" ] || fail "model_root is missing from $CONFIG_PATH"

say "Refreshing managed dashboard automation code"
bash "$STAGER" --web-only "$SOURCE_WEB_ROOT" >/dev/null
[ -f "$WEB_ROOT/scripts/run_cbb_auto_grade.py" ] || fail "Managed dashboard runtime was not staged correctly."
RUNTIME_LOCK="$WEB_ROOT/requirements-automation.lock"
[ -f "$RUNTIME_LOCK" ] || fail "Pinned automation requirements are missing: $RUNTIME_LOCK"

BASE_PY="$(command -v python3.12 2>/dev/null || true)"
if [ -z "$BASE_PY" ] && [ -x "$RUNTIME_PY" ]; then
  BASE_PY="$RUNTIME_PY"
fi
[ -n "$BASE_PY" ] || fail "Python 3.12 was not found for the website automation runtime."
mkdir -p "$MANAGED_BASE" "$LOG_DIR" "$HOME/Library/LaunchAgents"
chmod 700 "$MANAGED_BASE"

if [ ! -x "$RUNTIME_PY" ]; then
  say "Creating isolated CBB website automation runtime"
  "$BASE_PY" -m venv "$RUNTIME_DIR"
fi
say "Synchronizing pinned CBB website automation dependencies"
"$RUNTIME_PY" -m pip install --disable-pip-version-check -q -r "$RUNTIME_LOCK"
"$RUNTIME_PY" - <<'PY'
import sys
import numpy
import pandas
import supabase
if sys.version_info[:2] != (3, 12):
    raise SystemExit("CBB automation runtime must use Python 3.12")
print("CBB website automation runtime verified")
PY
PY="$RUNTIME_PY"

[ -f "$MODEL_ROOT/grade_cbb_champion.sh" ] || fail "Frozen champion grader wrapper not found: $MODEL_ROOT/grade_cbb_champion.sh"
[ -f "$MODEL_ROOT/ACTIVE_CBB_Grade_Slate_V1_1_3B_CHAMPION.py" ] || fail "Frozen V1.1.3B grader not found in $MODEL_ROOT"
[ -x "$MODEL_ROOT/.venv/bin/python3" ] || fail "Managed frozen champion Python runtime is missing: $MODEL_ROOT/.venv/bin/python3"

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
  "Automation Python: $PY" \
  "Dashboard runtime: $WEB_ROOT" \
  "Champion runtime:  $MODEL_ROOT" \
  "Poll cadence: every 30 minutes" \
  "Starts checking a slate 90 minutes after its earliest scheduled tip" \
  "Publishes only when finals/cancellations/final-score corrections change grading state" \
  "Logs: $LOG_DIR/auto_grader.log" \
  "State: $LOG_DIR/last_grading.json" \
  "Uninstall grader only: bash $SOURCE_WEB_ROOT/scripts/install_cbb_auto_grade_launchd.sh --uninstall"
