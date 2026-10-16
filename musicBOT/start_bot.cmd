@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
"%~dp0.venv\Scripts\python.exe" "%~dp0bot _GPT6.py" %*
pause
