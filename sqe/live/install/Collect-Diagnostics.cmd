@echo off
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Collect-Diagnostics.ps1" %*
pause
