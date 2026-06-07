@echo off
cd /d "%~dp0"
title Attenist Setup

echo.
echo ============================================
echo        Attenist — Setup
echo ============================================
echo.

rem ─── Step 1: Check Python ───────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python is not installed or not found in PATH.
    echo.
    echo Python 3.11+ is required.
    echo.
    echo Download from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

rem ─── Step 2: Display version ────────────────────────────────
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo %PYVER% detected.
echo.

rem ─── Step 3: Create venv if missing ─────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Done.
    echo.
) else (
    echo Virtual environment found.
    echo.
)

rem ─── Step 4: Activate ───────────────────────────────────────
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

rem ─── Step 5: Upgrade pip ────────────────────────────────────
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
echo Done.
echo.

rem ─── Step 6: Install requirements ───────────────────────────
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install some dependencies.
    echo Check the error messages above.
    pause
    exit /b 1
)
echo Done.
echo.

rem ─── Step 7: Verify critical imports ────────────────────────
echo Verifying installation...
python -c "import PySide6; import openpyxl; import rapidfuzz; import PIL; from google import genai; print('OK')" >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   Installation successful.
    echo   Attenist is ready to use.
    echo   Double-click Start.bat to launch, or it will launch now...
    echo ============================================
    timeout /t 3
    start "" Start.bat
) else (
    echo.
    echo WARNING: Some packages failed to import.
    echo.
    python -c "import PySide6" >nul 2>&1 || echo   FAILED: PySide6
    python -c "import openpyxl" >nul 2>&1 || echo   FAILED: openpyxl
    python -c "import rapidfuzz" >nul 2>&1 || echo   FAILED: rapidfuzz
    python -c "import PIL" >nul 2>&1 || echo   FAILED: pillow
    python -c "from google import genai" >nul 2>&1 || echo   FAILED: google-genai
    echo.
    echo Try running setup.bat again.
)

echo.
pause
