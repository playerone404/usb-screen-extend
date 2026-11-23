#!/usr/bin/env bash
# Uninstalls usb-second-screen: removes the server files, wrapper script,
# systemd user unit, and udev / modules-load configuration that install.sh set up.
#
# Usage:  ./uninstall.sh           remove everything this project installed
#         ./uninstall.sh --keep-packages   skip the system-package removal step
set -euo pipefail

prefix="${PREFIX:-$HOME/.local}"
keep_packages=0
[[ "${1:-}" == "--keep-packages" ]] && keep_packages=1

echo "==> Stopping the systemd user service (if running)"
systemctl --user stop usb-second-screen.service 2>/dev/null || true
systemctl --user disable usb-second-screen.service 2>/dev/null || true

echo "==> Removing server files"
rm -f  "$prefix/bin/usb-second-screen"
rm -rf "$prefix/share/usb-second-screen"

echo "==> Removing systemd user unit"
rm -f "$HOME/.config/systemd/user/usb-second-screen.service"
systemctl --user daemon-reload 2>/dev/null || true

echo "==> Removing udev rule and modules-load config (sudo may be needed)"
if [[ -f /etc/udev/rules.d/99-usb-second-screen-uinput.rules ]]; then
    sudo rm -f /etc/udev/rules.d/99-usb-second-screen-uinput.rules
    sudo udevadm control --reload 2>/dev/null || true
fi
if [[ -f /etc/modules-load.d/uinput.conf ]]; then
    sudo rm -f /etc/modules-load.d/uinput.conf
fi

echo "==> Removing config directory"
rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/usb-second-screen"

if [[ $keep_packages -eq 0 ]]; then
    echo "==> NOTE: Packages installed by install.sh were NOT removed."
    echo "    They may be shared with other software. Remove them manually if desired."
fi

echo ""
echo "Done. usb-second-screen has been uninstalled."
echo "If install.sh added your user to the 'input' group, you can remove yourself with:"
echo "    sudo gpasswd -d \$USER input"
