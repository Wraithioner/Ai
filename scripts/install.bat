@echo off
REM ============================================
REM Local AI Voice Agent - Windows Installer
REM ============================================
REM Installs everything needed to run Atlas,
REM your personal AI voice agent 100%% locally.
REM No API keys. No cloud. Just your PC.
REM ============================================

echo.
echo ============================================
echo   Atlas - Local AI Voice Agent (Windows)
echo ============================================
echo.
echo This will install:
echo   1. Python virtual environment + packages
echo   2. Ollama (local LLM runtime)
echo   3. A default AI model (llama3.1:8b)
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
echo   Step 1/4: Checking Python
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

REM ---- Step 2: Check/Install Ollama ----
echo.
echo ============================================
echo   Step 2/4: Ollama (Local LLM Runtime)
echo ============================================
echo.

ollama --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Ollama not found.
    echo     Please download and install Ollama from: https://ollama.com/download
    echo     Then re-run this script.
    pause
    exit /b 1
)
echo [+] Ollama found.

REM ---- Step 3: Pull AI model ----
echo.
echo ============================================
echo   Step 3/4: Downloading AI Model
echo ============================================
echo.

echo [+] Pulling llama3.1:8b (this may take a while on first run)...
ollama pull llama3.1:8b

REM ---- Step 4: Python environment ----
echo.
echo ============================================
echo   Step 4/4: Python Environment
echo ============================================
echo.

set VENV_DIR=%PROJECT_DIR%\.venv

if not exist "%VENV_DIR%" (
    echo [+] Creating Python virtual environment...
    python -m venv "%VENV_DIR%"
)

echo [+] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo [+] Installing Python packages...
pip install --upgrade pip -q
pip install -q openai-whisper piper-tts torch torchaudio numpy PyAudio requests pyyaml

echo [+] Python packages installed.

REM ---- Done ----
echo.
echo ============================================
echo   Installation Complete!
echo ============================================
echo.
echo Atlas is ready to go!
echo.
echo   To start (voice mode):
echo     cd %PROJECT_DIR%
echo     .venv\Scripts\activate
echo     python -m agent.main
echo.
echo   To test (text mode, no mic needed):
echo     python -m agent.main --text-mode
echo.
echo   Configuration: %PROJECT_DIR%\config\settings.yaml
echo.
echo No API keys. No cloud. 100%% local. Enjoy!
echo.
pause
