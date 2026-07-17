@echo off
rem Launch MARK XLVIII (JARVIS) on Windows.
rem Pulls the latest from GitHub first, then starts. Pass --no-update to skip.
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\pythonw.exe" (
  echo.
  echo !! No virtualenv found. Run this once first:
  echo      powershell -ExecutionPolicy Bypass -File install.ps1
  echo.
  pause
  exit /b 1
)

if not exist "config\api_keys.json" (
  echo.
  echo !! config\api_keys.json is missing.
  echo    copy config\api_keys.example.json config\api_keys.json
  echo    then paste your Gemini key from https://aistudio.google.com/apikey
  echo.
  pause
  exit /b 1
)

if /i "%~1"=="--no-update" goto run
if exist "update.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "update.ps1" -Quiet
)

:run
start "" ".venv\Scripts\pythonw.exe" main.py
