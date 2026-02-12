@echo off
REM ============================================
REM Atlas - Local AI Voice Agent (Windows)
REM ============================================
REM Installs everything needed to run Atlas.
REM No API keys. No cloud. Just Python.
REM ============================================

echo.
echo ============================================
echo   Atlas - Local AI Voice Agent (Windows)
echo ============================================
echo.
echo This will install:
echo   1. Python virtual environment
echo   2. All packages from requirements.txt
echo.
echo The AI model will auto-download on first run (~3GB).
echo.
set /p CONFIRM="Continue? [Y/n] "
if /i "%CONFIRM%"=="n" (
    echo Aborted.
    exit /b 0
)

REM ---- Detect project root ----
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

REM ---- Step 1: Check Python ----
echo.
echo ============================================
echo   Step 1/2: Checking Python
echo ============================================
echo.

python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo [+] Python found.

REM ---- Step 2: Python environment ----
echo.
echo ============================================
echo   Step 2/2: Python Environment
echo ============================================
echo.

set VENV_DIR=%PROJECT_DIR%\.venv

if not exist "%VENV_DIR%" (
    echo [+] Creating Python virtual environment...
    python -m venv "%VENV_DIR%"
)

echo [+] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo [+] Upgrading pip...
pip install --upgrade pip -q

echo [+] Installing Python packages from requirements.txt...
pip install -r "%PROJECT_DIR%\requirements.txt" -q

echo [+] All packages installed.

REM ---- Done ----
echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo Atlas is ready to go!
echo.
echo   To start (text mode):
echo     cd %PROJECT_DIR%
echo     .venv\Scripts\activate
echo     python -m atlas.main --text-mode
echo.
echo   To start (voice mode):
echo     python -m atlas.main
echo.
echo   To train Atlas's brain:
echo     python -m atlas.main --train
echo.
echo   Configuration: %PROJECT_DIR%\config\settings.yaml
echo.
echo No API keys. No cloud. 100%% local!
echo.
pause
