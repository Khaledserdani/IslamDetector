@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_remote_bridge_windows.ps1" %*
if errorlevel 1 (
  echo.
  echo ISLAM FREE AGENT could not start. See the message above.
  pause
)
endlocal
