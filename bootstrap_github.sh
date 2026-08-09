#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

OWNER="${GITHUB_OWNER:-bmbwork}"
REPO="${1:-cbb-model-dashboard}"
VISIBILITY="${2:-public}"

case "$VISIBILITY" in
  public|private) ;;
  *) echo "Visibility must be public or private." >&2; exit 2 ;;
esac

if [ ! -d .git ]; then
  git init
  git branch -M main
fi

git add .
if ! git diff --cached --quiet; then
  git commit -m "Ship CBB Intelligence Terminal v1.1"
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  if ! git remote get-url origin >/dev/null 2>&1; then
    gh repo create "$OWNER/$REPO" "--$VISIBILITY" --source=. --remote=origin --push
  else
    git push -u origin main
  fi
  echo "GitHub deployment source is ready: $OWNER/$REPO"
else
  echo "GitHub CLI is not installed/authenticated. Repository is committed locally."
  echo "Create $OWNER/$REPO in GitHub, then run:"
  echo "  git remote add origin https://github.com/$OWNER/$REPO.git"
  echo "  git push -u origin main"
fi
