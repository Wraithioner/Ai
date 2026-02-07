#!/usr/bin/env bash
# ============================================
# Local AI Voice Agent - Installation Script
# ============================================
# This script installs everything needed to run
# your personal AI voice agent 100% locally.
# No API keys. No cloud. Just your PC.
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect the project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

print_header "Local AI Voice Agent - Installer"

echo "This will install:"
echo "  1. System dependencies (audio libraries)"
echo "  2. Ollama (local LLM runtime)"
echo "  3. Python packages (Whisper, Piper, etc.)"
echo "  4. A default AI model (llama3.1:8b)"
echo ""
read -p "Continue? [Y/n] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ---- Step 1: System dependencies ----
print_header "Step 1/5: System Dependencies"

if command -v apt-get &> /dev/null; then
    print_step "Detected Debian/Ubuntu. Installing with apt..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-pip python3-venv \
        portaudio19-dev \
        alsa-utils \
        ffmpeg \
        curl \
        git
elif command -v dnf &> /dev/null; then
    print_step "Detected Fedora/RHEL. Installing with dnf..."
    sudo dnf install -y \
        python3 python3-pip \
        portaudio-devel \
        alsa-utils \
        ffmpeg \
        curl \
        git
elif command -v pacman &> /dev/null; then
    print_step "Detected Arch Linux. Installing with pacman..."
    sudo pacman -Sy --noconfirm \
        python python-pip \
        portaudio \
        alsa-utils \
        ffmpeg \
        curl \
        git
else
    print_warn "Unknown package manager. Please manually install:"
    print_warn "  python3, pip, portaudio, alsa-utils, ffmpeg"
fi

# ---- Step 2: Ollama ----
print_header "Step 2/5: Ollama (Local LLM Runtime)"

if command -v ollama &> /dev/null; then
    print_step "Ollama is already installed."
else
    print_step "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    print_step "Ollama installed."
fi

# Start Ollama in background if not running
if ! pgrep -x "ollama" > /dev/null; then
    print_step "Starting Ollama server..."
    ollama serve &>/dev/null &
    sleep 3
fi

# ---- Step 3: Pull AI Model ----
print_header "Step 3/5: Downloading AI Model"

MODEL="llama3.1:8b"
print_step "Pulling model: $MODEL (this may take a while on first run)..."
ollama pull "$MODEL"
print_step "Model ready!"

# ---- Step 4: Python environment ----
print_header "Step 4/5: Python Environment"

VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    print_step "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

print_step "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

print_step "Installing Python packages..."
pip install --upgrade pip -q

pip install -q \
    openai-whisper \
    piper-tts \
    torch \
    torchaudio \
    numpy \
    PyAudio \
    requests \
    pyyaml

print_step "Python packages installed."

# ---- Step 5: Systemd service ----
print_header "Step 5/5: Auto-Start Service (Optional)"

echo "Would you like the AI agent to start automatically when your PC boots?"
read -p "Install systemd service? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/ai-agent.service"
    CURRENT_USER=$(whoami)

    sudo tee "$SERVICE_FILE" > /dev/null << SERVICEEOF
[Unit]
Description=Local AI Voice Agent
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStartPre=/bin/bash -c 'until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do sleep 2; done'
ExecStart=$VENV_DIR/bin/python -m agent.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

    sudo systemctl daemon-reload
    sudo systemctl enable ai-agent.service
    print_step "Service installed and enabled!"
    print_step "It will start automatically on next boot."
    echo ""
    echo "  Manual controls:"
    echo "    sudo systemctl start ai-agent    # Start now"
    echo "    sudo systemctl stop ai-agent     # Stop"
    echo "    sudo systemctl status ai-agent   # Check status"
    echo "    journalctl -u ai-agent -f        # View logs"
else
    print_step "Skipped. You can run manually with:"
    echo "    cd $PROJECT_DIR"
    echo "    source .venv/bin/activate"
    echo "    python -m agent.main"
fi

# ---- Done ----
print_header "Installation Complete!"

echo "Your local AI voice agent is ready to go!"
echo ""
echo "  To start it:"
echo "    cd $PROJECT_DIR"
echo "    source .venv/bin/activate"
echo "    python -m agent.main"
echo ""
echo "  To test in text mode (no microphone needed):"
echo "    python -m agent.main --text-mode"
echo ""
echo "  Configuration: $PROJECT_DIR/config/settings.yaml"
echo ""
echo -e "${GREEN}No API keys. No cloud. 100% local. Enjoy!${NC}"
