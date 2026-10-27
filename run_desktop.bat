@echo off
title SONIQ MAX - Sound Profile Manager
echo =======================================================================
echo   Launching SONIQ MAX Native Desktop Sound Profile Manager...
echo =======================================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app_desktop.py
) else (
    python app_desktop.py
)
pause
