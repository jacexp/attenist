@echo off
cd /d "%~dp0"
title Attenist

rem ─── Auto-setup if venv missing ─────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup...
    call setup.bat
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: Setup failed. Please run setup.bat manually.
        pause
        exit /b 1
    )
)

rem ─── Activate ───────────────────────────────────────────────
call venv\Scripts\activate.bat

rem ─── Launch ─────────────────────────────────────────────────
echo Starting Attenist...
echo.

venv\Scripts\python.exe main.py

rem ─── Handle unexpected exit ─────────────────────────────────
if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   Application exited unexpectedly.
    echo   Error code: %errorlevel%
    echo ============================================
)

pause
