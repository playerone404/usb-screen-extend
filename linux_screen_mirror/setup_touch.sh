#!/usr/bin/env bash
# USB Second Screen — Touch / uinput Setup for Linux
# Enables non-root users to create virtual touchscreens via /dev/uinput.
set -euo pipefail

echo "==> Configuring /dev/uinput touch permissions (sudo required)..."
echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' | \
    sudo tee /etc/udev/rules.d/99-usb-second-screen-uinput.rules >/dev/null

echo uinput | sudo tee /etc/modules-load.d/uinput.conf >/dev/null
sudo usermod -aG input "$USER"
sudo udevadm control --reload
sudo udevadm trigger
sudo modprobe uinput || true

echo ""
echo "==================================================================="
echo " [OK] Touch permissions have been configured successfully!"
echo "==================================================================="
echo ""
echo "IMPORTANT:"
echo "1. Log out and log back in to your Linux session (so your user"
echo "   is recognized as part of the 'input' group)."
echo "2. Start streaming with touch enabled:"
echo "       ./2_start_second_screen.sh --touch"
echo "   (or: usb-second-screen --touch)"
echo ""
