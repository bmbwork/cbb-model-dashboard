#!/usr/bin/env bash
set -euo pipefail

LABEL="com.statfactory.cbb-model-refresh"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WEB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_ROOT="${2:-$DEFAULT_WEB_ROOT}"
MODEL_ROOT="${1:-${CBB_MODEL_ROOT:-}}"
CONFIG_DIR="$HOME/.config/stat_factory"
CONFIG_PATH="$CONFIG_DIR/cbb_automation.json"
ENV_PATH="$CONFIG_DIR/cbb_automation.env"
LOG_DIR="$HOME/Library/Logs/StatFactory/CBB"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUNTIME_DIR="$HOME/Library/Application Support/StatFactory/CBB/venv"
RUNTIME_PY="$RUNTIME_DIR/bin/python"
RUNTIME_LOCK="$WEB_ROOT/requirements-automation.lock"

say() { printf '\n[CBB automation] %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  say "Removed $LABEL from launchd. Configuration/secrets were left in $CONFIG_DIR."
  exit 0
fi

[ -d "$WEB_ROOT/.git" ] || fail "CBB website repository not found: $WEB_ROOT"
[ -f "$WEB_ROOT/scripts/run_cbb_model_refresh.py" ] || fail "Scheduled refresh runner is missing from the website repository."
[ -f "$WEB_ROOT/scripts/dispatch_cbb_model_refresh.py" ] || fail "Forecast dispatcher is missing from the website repository."
[ -f "$RUNTIME_LOCK" ] || fail "Pinned automation requirements are missing: $RUNTIME_LOCK"

if [ -z "$MODEL_ROOT" ] && [ -f "$CONFIG_PATH" ]; then
  MODEL_ROOT="$(python3 - "$CONFIG_PATH" <<'PY' 2>/dev/null || true
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
try:
    print(str(json.loads(p.read_text(encoding="utf-8")).get("model_root") or ""))
except Exception:
    pass
PY
)"
fi

if [ -z "$MODEL_ROOT" ]; then
  matches="$(find "$HOME/Desktop" -maxdepth 4 -type f -name 'run_cbb_champion.sh' -print 2>/dev/null || true)"
  count="$(printf '%s\n' "$matches" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')"
  if [ "$count" = "1" ]; then
    MODEL_ROOT="$(dirname "$matches")"
    say "Auto-detected frozen champion at: $MODEL_ROOT"
  elif [ "$count" = "0" ]; then
    fail "Could not auto-detect run_cbb_champion.sh under ~/Desktop. Re-run with the model folder as the first argument."
  else
    printf '\nMultiple CBB champion runners were found:\n%s\n' "$matches" >&2
    fail "Re-run with the exact frozen V1.1.3B model folder as the first argument."
  fi
fi

MODEL_ROOT="$(cd "$MODEL_ROOT" && pwd)"
[ -f "$MODEL_ROOT/run_cbb_champion.sh" ] || fail "run_cbb_champion.sh not found in: $MODEL_ROOT"
[ -f "$MODEL_ROOT/ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py" ] || fail "Frozen V1.1.3B champion runner not found in: $MODEL_ROOT"
[ -x "$MODEL_ROOT/.venv/bin/python3" ] || fail "Model Python was not found at $MODEL_ROOT/.venv/bin/python3"
if [ ! -f "$MODEL_ROOT/.env" ] || ! grep -Eq '^[[:space:]]*(CBBD_API_KEY|BEARER_TOKEN)[[:space:]]*=' "$MODEL_ROOT/.env"; then
  fail "The frozen model .env does not contain CBBD_API_KEY or BEARER_TOKEN. The scheduled runner would not be able to refresh basketball data."
fi

BASE_PY="$(command -v python3.12 2>/dev/null || true)"
if [ -z "$BASE_PY" ] && [ -x "$RUNTIME_PY" ]; then
  BASE_PY="$RUNTIME_PY"
fi
[ -n "$BASE_PY" ] || fail "Python 3.12 was not found for the website automation runtime."

mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents" "$(dirname "$RUNTIME_DIR")"
chmod 700 "$CONFIG_DIR"

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

"$PY" - "$CONFIG_PATH" "$MODEL_ROOT" "$WEB_ROOT" <<'PY'
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
payload = {
    "model_root": sys.argv[2],
    "web_root": sys.argv[3],
    "schedule": "30-minute dispatcher: next-day early 18:15 CT; game-day mid; late first-tip minus 3h",
    "model_version": "1.1.3B",
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
chmod 600 "$CONFIG_PATH"

has_credentials=0
if "$PY" - "$WEB_ROOT" "$ENV_PATH" <<'PY' >/dev/null 2>&1
import os
import pathlib
import sys
import tomllib
web = pathlib.Path(sys.argv[1])
env_path = pathlib.Path(sys.argv[2])
values = dict(os.environ)
if env_path.exists():
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values.setdefault(k.strip(), v.strip().strip('"').strip("'"))
secrets = web / ".streamlit" / "secrets.toml"
if secrets.exists():
    try:
        data = tomllib.loads(secrets.read_text(encoding="utf-8"))
        for k, v in data.items():
            if not isinstance(v, dict):
                values.setdefault(str(k), str(v))
    except Exception:
        pass
def clean(key):
    value = str(values.get(key, "") or "").strip()
    return bool(value and not value.upper().startswith("YOUR_") and not value.upper().startswith("REPLACE_ME"))
raise SystemExit(0 if clean("SUPABASE_URL") and (clean("SUPABASE_SECRET_KEY") or clean("SUPABASE_SERVICE_ROLE_KEY")) else 1)
PY
then
  has_credentials=1
fi

if [ "$has_credentials" -ne 1 ]; then
  [ -t 0 ] || fail "Supabase automation credentials are not available locally. Re-run this installer from an interactive terminal."
  printf '\nA server-side Supabase credential is required so the scheduled model can publish new slates.\n'
  printf 'The key is stored only in %s with mode 600 and is never committed to Git.\n\n' "$ENV_PATH"
  read -r -p "SUPABASE_URL: " supabase_url
  read -r -s -p "SUPABASE_SECRET_KEY (hidden): " supabase_secret
  printf '\n'
  [ -n "$supabase_url" ] || fail "SUPABASE_URL cannot be blank."
  [ -n "$supabase_secret" ] || fail "SUPABASE_SECRET_KEY cannot be blank."
  umask 077
  cat > "$ENV_PATH" <<EOF
SUPABASE_URL=$supabase_url
SUPABASE_SECRET_KEY=$supabase_secret
EOF
  chmod 600 "$ENV_PATH"
fi

TODAY_CT="$(TZ=America/Chicago date +%F)"
say "Validating scheduler configuration without running the model"
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
    "RunAtLoad": True,
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
  "Runtime:    $PY" \
  "Dispatcher: every 30 minutes and once at login." \
  "EARLY:      18:15 CT -> tomorrow's slate." \
  "MID:        first tip minus 10h, no earlier than 06:15 CT; 08:15 fallback only before 10:00 CT if no board exists." \
  "LATE:       first tip minus 3h, never after the first tip." \
  "Retries:    failed stages back off automatically; completed stages do not duplicate." \
  "Each due revision runs frozen V1.1.3B with refreshed basketball data and publishes immutably downstream." \
  "Logs:       $LOG_DIR/forecast_dispatch.log" \
  "Errors:     $LOG_DIR/forecast_dispatch_error.log" \
  "State:      $CONFIG_DIR/cbb_dispatch_state.json" \
  "Dry run:    STAT_FACTORY_HEADLESS_AUTOMATION=1 $PY $WEB_ROOT/scripts/dispatch_cbb_model_refresh.py --dry-run" \
  "Uninstall:  bash $WEB_ROOT/scripts/install_cbb_model_refresh_launchd.sh --uninstall"
