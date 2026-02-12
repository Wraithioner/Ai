#!/usr/bin/env bash
# Uninstall the Atlas agent systemd service

set -e

echo "Stopping and removing Atlas agent service..."

sudo systemctl stop atlas-agent.service 2>/dev/null || true
sudo systemctl disable atlas-agent.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/atlas-agent.service
sudo systemctl daemon-reload

echo "Service removed."
echo ""
echo "To fully clean up, you can also:"
echo "  rm -rf $(dirname "$(dirname "$0")")/.venv"
