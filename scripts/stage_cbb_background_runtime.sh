#!/usr/bin/env bash
set -euo pipefail

MODE="full"
if [ "${1:-}" = "--web-only" ]; then
  MODE="web-only"
  shift
fi

SOURCE_WEB_ROOT="${1:-}"
SOURCE_MODEL_ROOT="${2:-}"
MANAGED_BASE="$HOME/Library/Application Support/StatFactory/CBB"
MANAGED_WEB_ROOT="$MANAGED_BASE/dashboard_runtime"
MANAGED_MODEL_ROOT="$MANAGED_BASE/champion_runtime"
AUTOMATION_VENV="$MANAGED_BASE/venv"

say() { printf '\n[CBB runtime] %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[ -n "$SOURCE_WEB_ROOT" ] || fail "Source dashboard repository path is required."
SOURCE_WEB_ROOT="$(cd "$SOURCE_WEB_ROOT" && pwd)"
[ -f "$SOURCE_WEB_ROOT/scripts/run_cbb_model_refresh.py" ] || fail "CBB dashboard source is incomplete: $SOURCE_WEB_ROOT"
[ -f "$SOURCE_WEB_ROOT/requirements-automation.lock" ] || fail "Pinned dashboard automation requirements are missing."
command -v rsync >/dev/null 2>&1 || fail "rsync is required to stage the CBB background runtime."

mkdir -p "$MANAGED_BASE" "$MANAGED_WEB_ROOT"
chmod 700 "$MANAGED_BASE"

say "Staging dashboard automation code outside Desktop/File Provider paths"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.streamlit/secrets.toml' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  "$SOURCE_WEB_ROOT/" "$MANAGED_WEB_ROOT/"

if [ "$MODE" = "web-only" ]; then
  chmod -R go-rwx "$MANAGED_WEB_ROOT"
  printf '%s\n' "$MANAGED_WEB_ROOT"
  exit 0
fi

[ -n "$SOURCE_MODEL_ROOT" ] || fail "Source frozen CBB champion path is required."
SOURCE_MODEL_ROOT="$(cd "$SOURCE_MODEL_ROOT" && pwd)"
for required in \
  run_cbb_champion.sh \
  grade_cbb_champion.sh \
  ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py \
  ACTIVE_CBB_Grade_Slate_V1_1_3B_CHAMPION.py \
  cbb_v1_1_3b_champion.py \
  requirements.txt
do
  [ -f "$SOURCE_MODEL_ROOT/$required" ] || fail "Frozen champion source is missing $required"
done

if [ ! -f "$SOURCE_MODEL_ROOT/.env" ] || ! grep -Eq '^[[:space:]]*(CBBD_API_KEY|BEARER_TOKEN)[[:space:]]*=' "$SOURCE_MODEL_ROOT/.env"; then
  fail "The frozen champion source .env does not contain CBBD_API_KEY or BEARER_TOKEN."
fi

mkdir -p "$MANAGED_MODEL_ROOT"
if [ "$SOURCE_MODEL_ROOT" != "$MANAGED_MODEL_ROOT" ]; then
  say "Staging private frozen champion outside Desktop/File Provider paths"
  # outputs/ and runtime data are intentionally preserved across repairs. The
  # frozen source files are overlaid without deleting locally produced history.
  rsync -a \
    --exclude '.venv/' \
    --exclude 'outputs/' \
    --exclude '__pycache__/' \
    --exclude '.ipynb_checkpoints/' \
    --exclude '.jupyter/' \
    "$SOURCE_MODEL_ROOT/" "$MANAGED_MODEL_ROOT/"
fi

BASE_PY="$(command -v python3.12 2>/dev/null || true)"
if [ -z "$BASE_PY" ] && [ -x "$AUTOMATION_VENV/bin/python" ]; then
  BASE_PY="$AUTOMATION_VENV/bin/python"
fi
[ -n "$BASE_PY" ] || fail "Python 3.12 is required to stage the frozen CBB champion runtime."

say "Rebuilding the private champion Python environment at its managed path"
rm -rf "$MANAGED_MODEL_ROOT/.venv"
"$BASE_PY" -m venv "$MANAGED_MODEL_ROOT/.venv"
MODEL_PY="$MANAGED_MODEL_ROOT/.venv/bin/python3"
"$MODEL_PY" -m pip install --disable-pip-version-check -q -r "$MANAGED_MODEL_ROOT/requirements.txt"
"$MODEL_PY" - <<'PY'
import sys
import numpy
import pandas
import requests
if sys.version_info[:2] != (3, 12):
    raise SystemExit("CBB champion runtime must use Python 3.12")
print("CBB champion runtime verified")
PY

say "Verifying frozen champion source identity after staging"
"$MODEL_PY" - "$SOURCE_MODEL_ROOT" "$MANAGED_MODEL_ROOT" <<'PY'
from pathlib import Path
import hashlib
import sys
source = Path(sys.argv[1])
target = Path(sys.argv[2])
files = [
    "ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py",
    "ACTIVE_CBB_Grade_Slate_V1_1_3B_CHAMPION.py",
    "cbb_v1_1_3b_champion.py",
    "run_cbb_champion.sh",
    "grade_cbb_champion.sh",
]
for name in files:
    a = hashlib.sha256((source / name).read_bytes()).hexdigest()
    b = hashlib.sha256((target / name).read_bytes()).hexdigest()
    if a != b:
        raise SystemExit(f"Managed champion identity mismatch: {name}")
print("Frozen CBB V1.1.3B source identity verified")
PY

chmod 600 "$MANAGED_MODEL_ROOT/.env"
chmod -R go-rwx "$MANAGED_WEB_ROOT" "$MANAGED_MODEL_ROOT"
printf '%s\n' "$MANAGED_WEB_ROOT" "$MANAGED_MODEL_ROOT"
