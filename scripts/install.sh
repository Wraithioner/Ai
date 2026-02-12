#!/usr/bin/env bash
# ============================================
# Atlas - Local AI Voice Agent - Installation
# ============================================
# Installs everything needed to run Atlas
# 100% locally. No API keys. No cloud.
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

print_header "Atlas - Local AI Voice Agent - Installer"

echo "This will install:"
echo "  1. System dependencies (audio libraries, ffmpeg)"
echo "  2. Python virtual environment"
echo "  3. All Python packages from requirements.txt"
echo ""
echo "No external servers needed — everything runs locally."
echo ""
read -p "Continue? [Y/n] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ---- Step 1: System dependencies ----
print_header "Step 1/3: System Dependencies"

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

# ---- Step 2: Python environment ----
print_header "Step 2/3: Python Environment"

VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    print_step "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

print_step "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

print_step "Upgrading pip..."
pip install --upgrade pip -q

print_step "Installing Python packages from requirements.txt..."
pip install -r "$PROJECT_DIR/requirements.txt" -q

print_step "Python packages installed."

# ---- Step 3: Systemd service (optional) ----
print_header "Step 3/3: Auto-Start Service (Optional)"

echo "Would you like Atlas to start automatically when your PC boots?"
read -p "Install systemd service? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/atlas-agent.service"
    CURRENT_USER=$(whoami)

    sudo tee "$SERVICE_FILE" > /dev/null << SERVICEEOF
[Unit]
Description=Atlas - Local AI Voice Agent
After=network.target sound.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV_DIR/bin/python -m atlas.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

    sudo systemctl daemon-reload
    sudo systemctl enable atlas-agent.service
    print_step "Service installed and enabled!"
    print_step "It will start automatically on next boot."
    echo ""
    echo "  Manual controls:"
    echo "    sudo systemctl start atlas-agent    # Start now"
    echo "    sudo systemctl stop atlas-agent     # Stop"
    echo "    sudo systemctl status atlas-agent   # Check status"
    echo "    journalctl -u atlas-agent -f        # View logs"
else
    print_step "Skipped. You can run manually with:"
    echo "    cd $PROJECT_DIR"
    echo "    source .venv/bin/activate"
    echo "    python -m atlas.main"
fi

# ---- Done ----
print_header "Installation Complete!"

echo "Atlas is ready to go!"
echo ""
echo "  To start (voice mode):"
echo "    cd $PROJECT_DIR"
echo "    source .venv/bin/activate"
echo "    python -m atlas.main"
echo ""
echo "  To start (text mode - no microphone needed):"
echo "    python -m atlas.main --text-mode"
echo ""
echo "  To train Atlas's brain:"
echo "    python -m atlas.main --train"
echo ""
echo "  Configuration: $PROJECT_DIR/config/settings.yaml"
echo ""
echo -e "${GREEN}No API keys. No cloud. 100% local. Enjoy!${NC}"
