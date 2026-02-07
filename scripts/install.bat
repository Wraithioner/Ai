@echo off
REM ============================================
REM Atlas - Local AI Voice Agent (Windows)
REM ============================================
REM Installs everything needed to run Atlas.
REM No API keys. No cloud. No Ollama. Just Python.
REM ============================================

echo.
echo ============================================
echo   Atlas - Local AI Voice Agent (Windows)
echo ============================================
echo.
echo This will install:
echo   1. Python virtual environment
echo   2. AI model + packages (auto-downloaded)
echo.
echo No Ollama or external servers needed!
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

echo [+] Installing Python packages (this may take a few minutes)...
pip install --upgrade pip -q
pip install -q transformers accelerate huggingface-hub torch numpy pyyaml

echo [+] Core packages installed.
echo [+] Voice packages will be installed if you use voice mode.

REM ---- Done ----
echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo Atlas is ready to go!
echo The AI model will auto-download on first run (~3GB).
echo.
echo   To start (text mode):
echo     cd %PROJECT_DIR%
echo     .venv\Scripts\activate
echo     python -m atlas.main --text-mode
echo.
echo   Configuration: %PROJECT_DIR%\config\settings.yaml
echo.
echo No API keys. No cloud. No Ollama. 100%% local!
echo.
pause
