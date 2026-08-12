@echo off
REM ============================================================
REM  Enterprise AI Agent v0.6.0 — Windows Installer (One-Click)
REM  Supports: Windows 10/11, Python >= 3.11
REM ============================================================
setlocal enabledelayedexpansion
title Enterprise AI Agent — Installer

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║   Enterprise AI Agent — One-Click Installer  (Windows)      ║
echo  ║   v0.6.0  -  https://github.com/AbuSultancom/enterprise-ai-agent ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

REM ── STEP 1: Check Python >= 3.11 ──────────────────────────────────────────
echo  [1/6] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python not found!
    echo          Install Python 3.11+ from: https://python.org/downloads/
    echo          Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo         Found: Python %PYVER%

for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 goto :python_old
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 goto :python_old
echo         [OK] Python version is compatible.
goto :check_node

:python_old
echo  [ERROR] Python 3.11+ required! You have %PYVER%
pause
exit /b 1

REM ── STEP 2: Check Node.js (for WhatsApp) ──────────────────────────────────
:check_node
echo.
echo  [2/6] Checking Node.js (required for WhatsApp integration)...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo         [WARNING] Node.js not found.
    echo                   WhatsApp integration will be DISABLED.
    echo                   Install from: https://nodejs.org/ (v18+)
    set NODE_OK=0
) else (
    for /f "tokens=1" %%v in ('node --version 2^>^&1') do set NODEVER=%%v
    echo         [OK] Node.js !NODEVER! found.
    set NODE_OK=1
)

REM ── STEP 3: Create / reuse virtual environment ────────────────────────────
echo.
echo  [3/6] Setting up virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo         Creating new venv...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo         [OK] venv created.
) else (
    echo         [OK] Existing venv found (reusing).
)

call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to activate venv.
    pause
    exit /b 1
)
echo         [OK] venv activated.

REM ── STEP 4: Upgrade pip + install dependencies ────────────────────────────
echo.
echo  [4/6] Installing dependencies...
python -m pip install --upgrade pip --quiet
if exist "pyproject.toml" (
    echo         Installing from pyproject.toml...
    python -m pip install -e ".[dev]" --quiet
) else (
    echo         Installing from requirements.txt...
    python -m pip install -r requirements.txt --quiet
)
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo         [OK] Dependencies installed.

REM ── STEP 5: Pre-flight check ──────────────────────────────────────────────
echo.
echo  [5/6] Running pre-flight diagnostics...
python install_check.py
if %errorlevel% EQU 2 (
    echo.
    echo  [WARNING] Critical issues detected. Please fix them before continuing.
    echo            Press any key to continue with setup anyway, or Ctrl+C to abort.
    pause >nul
)

REM ── STEP 6: Run setup wizard (only if not already configured) ─────────────
echo.
echo  [6/6] Running setup wizard...
if not exist "config\settings.json" (
    python setup.py
    if %errorlevel% neq 0 (
        echo  [WARNING] Setup wizard exited with errors. You can re-run: python setup.py
    )
) else (
    echo         [OK] Settings already configured (config\settings.json found).
    echo              To reconfigure, run: python setup.py
)

REM ── Done ──────────────────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║              ✓  INSTALLATION COMPLETE!                       ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
echo   How to start:
echo     venv\Scripts\activate
echo     python start.py
echo.
echo   Or just double-click: run.bat
echo.
echo   Access Points:
echo     🌐 Dashboard:    http://localhost:8000
echo     📚 API Docs:     http://localhost:8000/docs
echo     🤖 Swagger UI:   http://localhost:8000/redoc
echo.
echo   Run diagnostics anytime: python install_check.py
echo.
pause
