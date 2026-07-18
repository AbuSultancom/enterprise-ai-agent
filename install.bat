@echo off
REM ============================================================
REM  Enterprise AI Agent — Windows Installer (One-Click)
REM  Supports: Windows 10/11, Python >= 3.11
REM ============================================================
setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║   Enterprise AI Agent — One-Click Installer (Windows)   ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

REM --- 1. Check Python >= 3.11 ---
echo [1/4] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   X Python not found! Please install Python 3.11+ from https://python.org
    echo     Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   √ Python %PYVER% found

REM Check version >= 3.11
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo   X Python 3.11+ required! You have %PYVER%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 (
    echo   X Python 3.11+ required! You have %PYVER%
    pause
    exit /b 1
)
echo   √ Python version OK

REM --- 2. Create/activate venv ---
echo.
echo [2/4] Setting up virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo   Creating venv...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo   X Failed to create virtual environment
        pause
        exit /b 1
    )
    echo   √ venv created
) else (
    echo   √ venv already exists
)

REM Activate venv
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo   X Failed to activate venv
    pause
    exit /b 1
)
echo   √ venv activated

REM --- 3. Install requirements ---
echo.
echo [3/4] Installing dependencies...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo   X Failed to install dependencies
    pause
    exit /b 1
)
echo   √ Dependencies installed

REM --- 4. Run setup.py ---
echo.
echo [4/4] Running setup wizard...
python setup.py
if %errorlevel% neq 0 (
    echo   ! Setup wizard exited with an error (code: %errorlevel%)
    echo     You can run it again manually: python setup.py
)

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                    INSTALL COMPLETE!                     ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo   Start the platform:
echo     venv\Scripts\activate
echo     python start.py
echo.
echo   Dashboard:  http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo.
pause
