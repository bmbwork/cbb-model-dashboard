#!/usr/bin/env bash
set -euo pipefail

MODEL_ROOT="${1:-}"
CONFIG_JSON="$HOME/.config/stat_factory/cbb_automation.json"
AUTOMATION_ENV="$HOME/.config/stat_factory/cbb_automation.env"
OBJECT_PATH="cbb/production/CBB_V1_1_3B_Champion.zip"
BUCKET="cbb"

fail(){ printf '\nERROR: %s\n' "$*" >&2; exit 1; }
say(){ printf '\n[CBB model archive] %s\n' "$*"; }

if [ -z "$MODEL_ROOT" ] && [ -f "$CONFIG_JSON" ]; then
  MODEL_ROOT="$(python3 - "$CONFIG_JSON" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1])
try:
    d=json.loads(p.read_text())
    print(d.get("source_model_root") or d.get("model_root") or "")
except Exception:
    pass
PY
)"
fi

[ -n "$MODEL_ROOT" ] || fail "Champion root was not resolved. Pass the frozen V1.1.3B folder as argument 1."
MODEL_ROOT="$(cd "$MODEL_ROOT" && pwd)"

required=(
  "run_cbb_champion.sh"
  "grade_cbb_champion.sh"
  "ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py"
  "ACTIVE_CBB_Grade_Slate_V1_1_3B_CHAMPION.py"
  "cbb_v1_1_3b_champion.py"
  "requirements.txt"
)
for f in "${required[@]}"; do
  [ -f "$MODEL_ROOT/$f" ] || fail "Missing frozen champion file: $f"
done

if [ -f "$AUTOMATION_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$AUTOMATION_ENV"
  set +a
fi
SUPABASE_URL="${SUPABASE_URL:-}"
SUPABASE_KEY="${SUPABASE_SECRET_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"
[ -n "$SUPABASE_URL" ] || fail "SUPABASE_URL is not available."
[ -n "$SUPABASE_KEY" ] || fail "SUPABASE_SECRET_KEY/SUPABASE_SERVICE_ROLE_KEY is not available."

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PKG="$WORK/CBB_V1_1_3B_Champion"
mkdir -p "$PKG"

say "Copying frozen champion source without secrets or runtime output"
for f in "${required[@]}"; do
  cp "$MODEL_ROOT/$f" "$PKG/$f"
done

# Include non-secret source/support files if present. Never include hidden env files,
# virtualenvs, outputs, caches, or generated predictions.
for f in README.md MODEL_CARD.md data_dictionary.md release_notes.md; do
  [ -f "$MODEL_ROOT/$f" ] && cp "$MODEL_ROOT/$f" "$PKG/$f"
done

(
  cd "$PKG"
  sha256sum "${required[@]}" > SHA256SUMS.txt
  {
    echo "model_version=CBB_V1_1_3B"
    echo "package_role=frozen_production_champion"
    echo "source_root=$MODEL_ROOT"
    echo "created_at_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "secret_files_included=false"
  } > MODEL_MANIFEST.txt
)

ZIP="$WORK/CBB_V1_1_3B_Champion.zip"
(
  cd "$WORK"
  zip -r "$ZIP" "CBB_V1_1_3B_Champion" >/dev/null
)
sha256sum "$ZIP" | tee "$WORK/CBB_V1_1_3B_Champion.zip.sha256"

say "Uploading to private Supabase bucket: $BUCKET/$OBJECT_PATH"
curl --fail-with-body --silent --show-error \
  -X POST "$SUPABASE_URL/storage/v1/object/$BUCKET/$OBJECT_PATH" \
  -H "Authorization: Bearer $SUPABASE_KEY" \
  -H "apikey: $SUPABASE_KEY" \
  -H "x-upsert: true" \
  -H "Content-Type: application/zip" \
  --data-binary @"$ZIP"

printf '\n'
say "Upload complete"
printf 'Object: %s/%s\n' "$BUCKET" "$OBJECT_PATH"
printf 'Package SHA256: '
sha256sum "$ZIP" | awk '{print $1}'
