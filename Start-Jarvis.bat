@echo off
rem Launch MARK XLVIII (Jarvis) with its venv, UTF-8 output, from the right folder
cd /d "%~dp0"
set PYTHONUTF8=1
start "" ".venv\Scripts\pythonw.exe" main.py
