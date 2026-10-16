@echo off
setlocal
cd /d "%~dp0"

set "BOT_DIR=%~dp0musicBOT"
set "PYTHON=%BOT_DIR%\.venv\Scripts\python.exe"

where git >nul 2>&1
if errorlevel 1 (
    echo Git was not found. Install Git or add it to PATH.
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    echo Python virtual environment was not found:
    echo %PYTHON%
    pause
    exit /b 1
)

echo Checking GitHub for updates...
for /f %%H in ('git rev-parse HEAD 2^>nul') do set "OLD_HEAD=%%H"
git pull --ff-only origin main
if errorlevel 1 (
    echo.
    echo Update failed. Local files were not overwritten.
    echo Fix the Git error above, then run this file again.
    pause
    exit /b 1
)

for /f %%H in ('git rev-parse HEAD 2^>nul') do set "NEW_HEAD=%%H"
if not "%OLD_HEAD%"=="%NEW_HEAD%" (
    echo Updating Python dependencies...
    "%PYTHON%" -m pip install --disable-pip-version-check -r "%BOT_DIR%\requirements.txt"
    if errorlevel 1 (
        echo Dependency update failed. The bot was not started.
        pause
        exit /b 1
    )
)

call "%BOT_DIR%\start_music_bot.cmd"
set "BOT_EXIT=%ERRORLEVEL%"
echo Music bot launcher finished. Exit code: %BOT_EXIT%
pause
exit /b %BOT_EXIT%
