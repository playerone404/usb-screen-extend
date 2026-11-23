#!/usr/bin/env bash
# USB Second Screen — Interactive Launcher for Linux
# Starts the server either in this terminal or as a background service.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
server_script="$here/core/second_screen_server.py"

if [[ ! -f "$server_script" ]]; then
    server_script="$HOME/.local/share/usb-second-screen/second_screen_server.py"
fi

if [[ ! -f "$server_script" ]]; then
    echo "ERROR: Server script not found. Please run ./1_install.sh first." >&2
    exit 1
fi

start_as_service=0
for arg in "$@"; do
    if [[ "$arg" == "--service" ]]; then
        start_as_service=1
    fi
done

# If arguments were passed directly (other than --service), run immediately in terminal
if [[ $# -gt 0 && $start_as_service -eq 0 ]]; then
    echo "==> Starting in terminal with arguments: $*"
    exec python3 "$server_script" "$@"
fi

# ── Check if background service is already active ────────────────────────
if systemctl --user is-active --quiet usb-second-screen 2>/dev/null; then
    echo "==================================================================="
    echo " usb-second-screen is ALREADY RUNNING in the background!"
    echo "==================================================================="
    echo "  [1] Leave it running in the background and exit (Default)"
    echo "  [2] View background service live logs (journalctl)"
    echo "  [3] Stop background service and run in this terminal instead"
    echo "==================================================================="
    read -r -p "Choose an option [1/2/3] (default: 1): " choice
    case "${choice:-1}" in
        2)
            echo "==> Showing live service logs (Press Ctrl+C to exit)..."
            exec journalctl --user -u usb-second-screen -f
            ;;
        3)
            echo "==> Stopping background service..."
            systemctl --user stop usb-second-screen
            echo "==> Starting in this terminal..."
            exec python3 "$server_script" "$@"
            ;;
        *)
            echo "Leaving background service running. Plug in your phone and stream!"
            exit 0
            ;;
    esac
fi

# ── Ask user how to start ────────────────────────────────────────────────
if [[ -t 0 && $start_as_service -eq 0 ]]; then
    echo "==================================================================="
    echo " How would you like to start USB Second Screen?"
    echo "==================================================================="
    echo "  [1] In this terminal (Default)"
    echo "      Runs here; stops cleanly when you close this window (Ctrl+C)."
    echo ""
    echo "  [2] As a background service"
    echo "      Runs quietly in the background and starts automatically on login."
    echo "==================================================================="
    read -r -p "Choose an option [1/2] (default: 1): " choice
    if [[ "${choice:-1}" == "2" ]]; then
        start_as_service=1
    fi
fi

if [[ $start_as_service -eq 1 ]]; then
    echo "==> Enabling and starting background service..."
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable --now usb-second-screen
    echo ""
    echo "==================================================================="
    echo " [OK] usb-second-screen is now running in the background!"
    echo "==================================================================="
    echo "  - Check status:    systemctl --user status usb-second-screen"
    echo "  - View live logs:  journalctl --user -u usb-second-screen -f"
    echo "  - Stop service:    systemctl --user stop usb-second-screen"
    echo "  - Disable service: systemctl --user disable usb-second-screen"
    echo ""
    exit 0
else
    echo "==> Starting in terminal mode (Press Ctrl+C to stop)..."
    exec python3 "$server_script" "$@"
fi
