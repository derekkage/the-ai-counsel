@echo off
cd /d "%~dp0"
pythonw launcher.py 2>launcher-crash.log
if errorlevel 1 (
    echo Something went wrong. Check launcher-crash.log for details.
    pause
)
