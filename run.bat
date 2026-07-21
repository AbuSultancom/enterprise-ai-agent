@echo off
title Enterprise AI Agent Launcher
echo ========================================================
echo   Enterprise AI Agent - Launcher
echo ========================================================
echo.

:: Check python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

:: Create virtual environment if missing
if not exist venv (
    echo [INFO] Creating virtual environment (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment and install packages
echo [INFO] Activating virtual environment...
call venv\Scripts\activate

echo [INFO] Checking / Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Run setup if config is missing
if not exist config\settings.json (
    echo [INFO] Running initial setup wizard...
    python setup.py
)

:: Start the application
echo.
echo [SUCCESS] Starting Enterprise AI Agent...
echo ========================================================
python start.py
pause
