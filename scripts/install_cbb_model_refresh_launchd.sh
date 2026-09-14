#!/usr/bin/env bash
set -euo pipefail

LABEL="com.statfactory.cbb-model-refresh"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_WEB_ROOT="${2:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SOURCE_MODEL_ROOT="${1:-${CBB_MODEL_ROOT:-}}"
CONFIG_DIR="$HOME/.config/stat_factory"
CONFIG_PATH="$CONFIG_DIR/cbb_automation.json"
ENV_PATH="$CONFIG_DIR/cbb_automation.env"
LOG_DIR="$HOME/Library/Logs/StatFactory/CBB"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
MANAGED_BASE="$HOME/Library/Application Support/StatFactory/CBB"
WEB_ROOT="$MANAGED_BASE/dashboard_runtime"
MODEL_ROOT="$MANAGED_BASE/champion_runtime"
RUNTIME_DIR="$MANAGED_BASE/venv"
RUNTIME_PY="$RUNTIME_DIR/bin/python"
STAGER="$SOURCE_WEB_ROOT/scripts/stage_cbb_background_runtime.sh"

say() { printf '\n[CBB automation] %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  say "Removed $LABEL from launchd. Managed runtime/configuration were left intact."
  exit 0
fi

SOURCE_WEB_ROOT="$(cd "$SOURCE_WEB_ROOT" && pwd)"
[ -d "$SOURCE_WEB_ROOT/.git" ] || fail "CBB website repository not found: $SOURCE_WEB_ROOT"
[ -f "$SOURCE_WEB_ROOT/scripts/run_cbb_model_refresh.py" ] || fail "Scheduled refresh runner is missing from the website repository."
[ -f "$SOURCE_WEB_ROOT/scripts/dispatch_cbb_model_refresh.py" ] || fail "Forecast dispatcher is missing from the website repository."
[ -f "$SOURCE_WEB_ROOT/requirements-automation.lock" ] || fail "Pinned automation requirements are missing."
[ -f "$STAGER" ] || fail "Background runtime staging helper is missing. Pull GitHub main first."

if [ -z "$SOURCE_MODEL_ROOT" ] && [ -f "$CONFIG_PATH" ]; then
  SOURCE_MODEL_ROOT="$(python3 - "$CONFIG_PATH" <<'PY' 2>/dev/null || true
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
try:
    data = json.loads(p.read_text(encoding="utf-8"))
    print(str(data.get("source_model_root") or data.get("model_root") or ""))
except Exception:
    pass
PY
)"
fi

if [ -z "$SOURCE_MODEL_ROOT" ]; then
  matches="$(find "$HOME/Desktop" -maxdepth 4 -type f -name 'run_cbb_champion.sh' -print 2>/dev/null || true)"
  count="$(printf '%s\n' "$matches" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')"
  if [ "$count" = "1" ]; then
    SOURCE_MODEL_ROOT="$(dirname "$matches")"
    say "Auto-detected frozen champion source at: $SOURCE_MODEL_ROOT"
  elif [ "$count" = "0" ] && [ -f "$MODEL_ROOT/run_cbb_champion.sh" ]; then
    SOURCE_MODEL_ROOT="$MODEL_ROOT"
    say "Reusing the existing managed frozen champion runtime."
  elif [ "$count" = "0" ]; then
    fail "Could not auto-detect run_cbb_champion.sh under ~/Desktop. Re-run with the exact frozen V1.1.3B folder as the first argument."
  else
    printf '\nMultiple CBB champion runners were found:\n%s\n' "$matches" >&2
    fail "Re-run with the exact frozen V1.1.3B model folder as the first argument."
  fi
fi

SOURCE_MODEL_ROOT="$(cd "$SOURCE_MODEL_ROOT" && pwd)"
[ -f "$SOURCE_MODEL_ROOT/run_cbb_champion.sh" ] || fail "run_cbb_champion.sh not found in: $SOURCE_MODEL_ROOT"
[ -f "$SOURCE_MODEL_ROOT/ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py" ] || fail "Frozen V1.1.3B champion runner not found in: $SOURCE_MODEL_ROOT"
[ -f "$SOURCE_MODEL_ROOT/grade_cbb_champion.sh" ] || fail "Frozen V1.1.3B grader wrapper not found in: $SOURCE_MODEL_ROOT"
if [ ! -f "$SOURCE_MODEL_ROOT/.env" ] || ! grep -Eq '^[[:space:]]*(CBBD_API_KEY|BEARER_TOKEN)[[:space:]]*=' "$SOURCE_MODEL_ROOT/.env"; then
  fail "The frozen model source .env does not contain CBBD_API_KEY or BEARER_TOKEN."
fi

BASE_PY="$(command -v python3.12 2>/dev/null || true)"
if [ -z "$BASE_PY" ] && [ -x "$RUNTIME_PY" ]; then
  BASE_PY="$RUNTIME_PY"
fi
[ -n "$BASE_PY" ] || fail "Python 3.12 was not found for CBB automation."

mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents" "$MANAGED_BASE"
chmod 700 "$CONFIG_DIR" "$MANAGED_BASE"

say "Staging dashboard + private champion into the managed background runtime"
bash "$STAGER" "$SOURCE_WEB_ROOT" "$SOURCE_MODEL_ROOT" >/dev/null
[ -f "$WEB_ROOT/scripts/dispatch_cbb_model_refresh.py" ] || fail "Managed dashboard runtime was not staged correctly."
[ -x "$MODEL_ROOT/.venv/bin/python3" ] || fail "Managed frozen champion Python runtime was not built correctly."
RUNTIME_LOCK="$WEB_ROOT/requirements-automation.lock"

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

say "Migrating protected publish credentials to the headless env file when available"
credential_status=0
if "$PY" - "$SOURCE_WEB_ROOT" "$ENV_PATH" <<'PY'
import os
import pathlib
import shlex
import sys
import tomllib

source_web = pathlib.Path(sys.argv[1])
env_path = pathlib.Path(sys.argv[2])
values = dict(os.environ)
if env_path.exists():
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
secrets = source_web / ".streamlit" / "secrets.toml"
if secrets.exists():
    try:
        data = tomllib.loads(secrets.read_text(encoding="utf-8"))
        for key, value in data.items():
            if not isinstance(value, dict):
                values.setdefault(str(key), str(value))
    except Exception:
        pass

def clean(*keys: str) -> str:
    for key in keys:
        value = str(values.get(key, "") or "").strip()
        if value and not value.upper().startswith("YOUR_") and not value.upper().startswith("REPLACE_ME"):
            return value
    return ""

url = clean("SUPABASE_URL")
secret = clean("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY")
if url and secret:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        f"SUPABASE_URL={shlex.quote(url)}\nSUPABASE_SECRET_KEY={shlex.quote(secret)}\n",
        encoding="utf-8",
    )
    env_path.chmod(0o600)
    raise SystemExit(0)
raise SystemExit(1)
PY
then
  credential_status=0
else
  credential_status=$?
fi

if [ "$credential_status" -ne 0 ]; then
  [ -t 0 ] || fail "Supabase automation credentials are not available locally. Re-run this installer from an interactive terminal."
  printf '\nA server-side Supabase credential is required so the scheduled model can publish new slates.\n'
  printf 'The key is stored only in %s with mode 600 and is never committed to Git.\n\n' "$ENV_PATH"
  read -r -p "SUPABASE_URL: " supabase_url
  read -r -s -p "SUPABASE_SECRET_KEY (hidden): " supabase_secret
  printf '\n'
  [ -n "$supabase_url" ] || fail "SUPABASE_URL cannot be blank."
  [ -n "$supabase_secret" ] || fail "SUPABASE_SECRET_KEY cannot be blank."
  umask 077
  {
    printf 'SUPABASE_URL=%q\n' "$supabase_url"
    printf 'SUPABASE_SECRET_KEY=%q\n' "$supabase_secret"
  } > "$ENV_PATH"
  chmod 600 "$ENV_PATH"
fi

"$PY" - "$CONFIG_PATH" "$MODEL_ROOT" "$WEB_ROOT" "$SOURCE_MODEL_ROOT" "$SOURCE_WEB_ROOT" <<'PY'
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
payload = {
    "model_root": sys.argv[2],
    "web_root": sys.argv[3],
    "source_model_root": sys.argv[4],
    "source_web_root": sys.argv[5],
    "schedule": "30-minute dispatcher: next-day early 18:15 CT; game-day mid; late first-tip minus 3h",
    "model_version": "1.1.3B",
    "runtime_policy": "managed_app_support_v1",
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
chmod 600 "$CONFIG_PATH"

TODAY_CT="$(TZ=America/Chicago date +%F)"
say "Validating managed scheduler configuration without running the model"
STAT_FACTORY_HEADLESS_AUTOMATION=1 "$PY" "$WEB_ROOT/scripts/run_cbb_model_refresh.py" --date "$TODAY_CT" --dry-run
STAT_FACTORY_HEADLESS_AUTOMATION=1 "$PY" "$WEB_ROOT/scripts/dispatch_cbb_model_refresh.py" --dry-run

say "Installing 30-minute game-relative forecast dispatcher"
"$PY" - "$PLIST" "$PY" "$WEB_ROOT" "$LOG_DIR" "$LABEL" <<'PY'
import pathlib
import plistlib
import sys
plist_path = pathlib.Path(sys.argv[1])
python = sys.argv[2]
web_root = sys.argv[3]
log_dir = pathlib.Path(sys.argv[4])
label = sys.argv[5]
payload = {
    "Label": label,
    "ProgramArguments": [python, str(pathlib.Path(web_root) / "scripts" / "dispatch_cbb_model_refresh.py")],
    "WorkingDirectory": web_root,
    "StartInterval": 1800,
    "ProcessType": "Background",
    "ThrottleInterval": 60,
    "StandardOutPath": str(log_dir / "forecast_dispatch.log"),
    "StandardErrorPath": str(log_dir / "forecast_dispatch_error.log"),
    "EnvironmentVariables": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONNOUSERSITE": "1",
        "STAT_FACTORY_HEADLESS_AUTOMATION": "1",
    },
}
with plist_path.open("wb") as handle:
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
  "Dispatcher: every 30 minutes; installation/reload does not execute a forecast." \
  "EARLY:      18:15 CT -> tomorrow's slate, with pre-MID sleep/restart catch-up." \
  "MID:        first tip minus 10h, no earlier than 06:15 CT; 08:15 fallback only before 10:00 CT if no board exists." \
  "LATE:       first tip minus 3h, never after the first tip." \
  "Retries:    failed stages back off automatically; completed/superseded stages do not duplicate." \
  "Logs:       $LOG_DIR/forecast_dispatch.log" \
  "Errors:     $LOG_DIR/forecast_dispatch_error.log" \
  "State:      $CONFIG_DIR/cbb_dispatch_state.json" \
  "Dry run:    STAT_FACTORY_HEADLESS_AUTOMATION=1 $PY $WEB_ROOT/scripts/dispatch_cbb_model_refresh.py --dry-run" \
  "Uninstall:  bash $SOURCE_WEB_ROOT/scripts/install_cbb_model_refresh_launchd.sh --uninstall"
