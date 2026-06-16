@echo off
title Building The AI Counsel Launcher
echo ============================================
echo  Building The AI Counsel Launcher
echo ============================================
echo.

echo Step 1: Installing PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo Failed to install PyInstaller. Make sure pip is available.
    pause
    exit /b 1
)
echo.

echo Step 2: Installing launcher dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)
echo.

echo Step 3: Building standalone EXE...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "The-AI-Counsel-Launcher" ^
    --add-data "requirements.txt;." ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL._tkinter_finder ^
    launcher.py
if %errorlevel% neq 0 (
    echo Build failed. See PyInstaller output above.
    pause
    exit /b 1
)
echo.

echo ============================================
echo  Build complete!
echo ============================================
echo.
echo Your EXE is at:
echo   dist\The-AI-Counsel-Launcher.exe
echo.
echo You can move this file anywhere and double-click it
echo to run the launcher without Python installed.
echo.
pause
