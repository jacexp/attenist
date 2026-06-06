@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Please run setup first or ensure 'venv' folder exists.
    pause
    exit /b 1
)

venv\Scripts\python.exe main.py

pause