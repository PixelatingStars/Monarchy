@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "monarchy.py"
) else (
  pyw -3 "monarchy.py"
)

