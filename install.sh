#!/usr/bin/env bash
# One-time JARVIS setup on Linux. After this, ./start-jarvis.sh keeps itself updated.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

VENV=".venv"
PY="$VENV/bin/python"

echo "==> JARVIS (MARK XLVIII) - Linux setup"

# ---- 1. System libraries -------------------------------------------------
# PyQt6 needs X11/GL libs, sounddevice needs PortAudio, pyautogui needs scrot/tk.
if command -v apt-get >/dev/null 2>&1; then
  echo "==> Installing system libraries (needs sudo)..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq \
    python3-venv python3-dev python3-tk build-essential git \
    portaudio19-dev libportaudio2 \
    libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 \
    libxcb-icccm4 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 \
    scrot xdotool wmctrl \
    || echo "!! Some system packages failed - JARVIS may still work. Continuing."
elif command -v dnf >/dev/null 2>&1; then
  echo "==> Installing system libraries via dnf (needs sudo)..."
  sudo dnf install -y python3-devel python3-tkinter gcc git portaudio-devel \
    mesa-libGL libxkbcommon-x11 xcb-util-cursor scrot xdotool wmctrl \
    || echo "!! Some system packages failed. Continuing."
else
  echo "!! Unknown package manager. Install manually: portaudio, python3-venv, python3-tk, git."
fi

# ---- 2. Virtualenv ------------------------------------------------------
if [ ! -x "$PY" ]; then
  echo "==> Creating virtualenv..."
  python3 -m venv "$VENV" || { echo "!! venv creation failed"; exit 1; }
fi

echo "==> Installing Python dependencies (this takes a few minutes)..."
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt || { echo "!! pip install failed"; exit 1; }
# Not in requirements.txt upstream, but JARVIS needs both:
"$PY" -m pip install -q PyQt6 truststore || echo "!! PyQt6/truststore install failed"

# ---- 3. API key ---------------------------------------------------------
if [ ! -f config/api_keys.json ]; then
  cp config/api_keys.example.json config/api_keys.json
  echo
  echo "==> ACTION NEEDED: add your own Gemini API key"
  echo "    Get a free key at https://aistudio.google.com/apikey"
  echo "    Then edit:  config/api_keys.json"
  echo "    (This file is git-ignored - it is never uploaded.)"
fi

chmod +x start-jarvis.sh update.sh install.sh 2>/dev/null

echo
echo "==> Setup complete."
echo "    Start JARVIS with:   ./start-jarvis.sh"
echo "    It auto-updates from GitHub on every launch."
