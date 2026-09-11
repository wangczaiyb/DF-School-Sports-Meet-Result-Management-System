@echo off
title Campus Sports Meet System - Start
cd /d "%~dp0"
set "SPORTS_MEET_NO_BROWSER=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"
if errorlevel 1 (
    echo.
    echo Startup failed. See the message above or logs in the data folder.
    pause
    exit /b 1
)
if /i "%~1"=="--no-browser" exit /b 0
start "" "http://127.0.0.1:5173"
exit /b 0
