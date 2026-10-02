@echo off
rem The release builder places this entry point beside scripts/ in the ZIP root.
start "" /b "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0scripts\local_setup.ps1"
exit /b
