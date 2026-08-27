#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

SERVICE_NAME="cmfit.service"

echo "Restarting service: ${SERVICE_NAME}..."

# Restart the systemd service
sudo systemctl restart "${SERVICE_NAME}"

# Verify the service status
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "Success: ${SERVICE_NAME} is active and running."
else
    echo "Error: ${SERVICE_NAME} failed to start properly."
    sudo systemctl status "${SERVICE_NAME}" --no-pager
    exit 1
fi