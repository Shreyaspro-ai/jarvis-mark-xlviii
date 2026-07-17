#!/usr/bin/env bash
# Pull the latest JARVIS and install anything new. Safe to run anytime.
set -uo pipefail
# Resolve this script's directory portably (macOS has no `readlink -f`).
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
cd "$(cd -P "$(dirname "$SOURCE")" && pwd)"

VENV=".venv"
PY="$VENV/bin/python"
QUIET="${1:-}"

say() { [ "$QUIET" = "--quiet" ] || echo "$@"; }

if [ ! -d .git ]; then
  echo "!! Not a git clone - can't auto-update. Re-clone from GitHub."
  exit 1
fi

# Remember what we had, so we only reinstall when deps actually change.
before_req=$(md5sum requirements.txt 2>/dev/null | cut -d' ' -f1)
before_rev=$(git rev-parse HEAD 2>/dev/null)

say ":: Checking for updates..."
git fetch origin main --quiet 2>/dev/null || { say "!! No network - starting with current version."; exit 0; }

remote_rev=$(git rev-parse origin/main 2>/dev/null)
if [ "$before_rev" = "$remote_rev" ]; then
  say ":: Already up to date."
  exit 0
fi

# Refuse to clobber the user's own edits.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "!! You have local changes to tracked files. Not auto-updating."
  echo "   Run 'git stash' to shelve them, or 'git checkout -- .' to discard, then retry."
  exit 0
fi

if ! git merge --ff-only origin/main --quiet 2>/dev/null; then
  echo "!! Your branch has diverged from GitHub. Fix manually:  git status"
  exit 0
fi

say ":: Updated $(git rev-parse --short "$before_rev") -> $(git rev-parse --short HEAD)"
git --no-pager log --oneline "$before_rev..HEAD" 2>/dev/null | sed 's/^/     /'

# Only reinstall dependencies if requirements.txt actually changed.
after_req=$(md5sum requirements.txt 2>/dev/null | cut -d' ' -f1)
if [ "$before_req" != "$after_req" ] && [ -x "$PY" ]; then
  say ":: Dependencies changed - installing..."
  "$PY" -m pip install -q -r requirements.txt 2>&1 | grep -vi 'already satisfied' || true
  say ":: Dependencies up to date."
fi

exit 0
