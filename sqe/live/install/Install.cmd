@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-SQE-Live.ps1" %*
if errorlevel 1 echo Installation did not finish. Read the error above.
pause
