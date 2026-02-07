#!/usr/bin/env bash
# Uninstall the AI agent systemd service

set -e

echo "Stopping and removing AI agent service..."

sudo systemctl stop ai-agent.service 2>/dev/null || true
sudo systemctl disable ai-agent.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/ai-agent.service
sudo systemctl daemon-reload

echo "Service removed."
echo ""
echo "To fully clean up, you can also:"
echo "  rm -rf $(dirname "$(dirname "$0")")/.venv"
echo "  ollama rm llama3.1:8b"
