@echo off
chcp 65001 >nul
setlocal
title Campus Sports Meet
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local.ps1" %*
set "launch_result=%errorlevel%"
if not "%launch_result%"=="0" (
  echo.
  echo Startup failed. Please check the error above.
  if /I not "%~1"=="-Check" pause
)
exit /b %launch_result%
