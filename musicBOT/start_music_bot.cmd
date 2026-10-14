@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PATH=%~dp0.tools\mpv;%~dp0.tools\deno;%PATH%"
"%~dp0.venv\Scripts\python.exe" "%~dp0music_bot_2_GPT6.py"
pause
