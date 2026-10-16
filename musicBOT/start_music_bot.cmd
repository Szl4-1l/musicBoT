@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PATH=%~dp0.tools\mpv;%~dp0.tools\deno;%PATH%"
set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Python virtual environment was not found: "%PYTHON%"
    pause
    exit /b 1
)
if not exist "%~dp0music_bot_2_GPT6.py" (
    echo Music bot script was not found: "%~dp0music_bot_2_GPT6.py"
    pause
    exit /b 1
)

"%PYTHON%" "%~dp0music_bot_2_GPT6.py" %*
set "BOT_EXIT=%ERRORLEVEL%"
echo.
echo Music bot stopped. Exit code: %BOT_EXIT%
pause
exit /b %BOT_EXIT%
