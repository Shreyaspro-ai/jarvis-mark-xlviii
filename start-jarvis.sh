#!/usr/bin/env bash
# Launch JARVIS on Linux. Pulls the latest version first, then starts.
#   ./start-jarvis.sh              normal (auto-update, then run)
#   ./start-jarvis.sh --no-update  skip the update check
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

if [ ! -x "$PY" ]; then
  echo "!! No virtualenv found. Run ./install.sh first."
  exit 1
fi

if [ ! -f config/api_keys.json ]; then
  echo "!! config/api_keys.json is missing."
  echo "   cp config/api_keys.example.json config/api_keys.json"
  echo "   then paste your own Gemini key from https://aistudio.google.com/apikey"
  exit 1
fi

if [ "${1:-}" != "--no-update" ]; then
  ./update.sh || true
fi

# UTF-8 so the emoji in the logs can't crash the app when output is redirected.
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo ":: Starting JARVIS..."
exec "$PY" main.py
