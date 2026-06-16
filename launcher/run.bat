@echo off
cd /d "%~dp0"

where pythonw >nul 2>&1
if %errorlevel% neq 0 (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Python is not installed or not in your PATH.
        echo.
        echo Please install Python 3.10 or later from:
        echo   https://www.python.org/downloads/
        echo.
        echo IMPORTANT: During installation, check "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
    echo [info] pythonw not found, using python instead...
    python launcher.py 2>launcher-crash.log
) else (
    pythonw launcher.py 2>launcher-crash.log
)

if errorlevel 1 (
    echo.
    echo Something went wrong. Error details:
    echo.
    if exist launcher-crash.log (
        type launcher-crash.log
    ) else (
        echo (no crash log was created)
    )
    echo.
    pause
)
