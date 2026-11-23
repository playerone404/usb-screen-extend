#!/usr/bin/env bash
# Installs the usb-second-screen server.
# Supports Fedora (dnf), Ubuntu/Debian (apt), and Arch Linux (pacman).
#
#   ./install.sh               server for the current desktop (KDE/GNOME -> portal, Hyprland/sway -> wf-recorder)
#   ./install.sh --with-touch  also set up /dev/uinput access for touch input
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
prefix="${PREFIX:-$HOME/.local}"
with_touch=0
[[ "${1:-}" == "--with-touch" ]] && with_touch=1

# ── Detect package manager ──────────────────────────────────────────────
detect_pm() {
    if command -v dnf &>/dev/null; then echo dnf
    elif command -v apt-get &>/dev/null; then echo apt
    elif command -v pacman &>/dev/null; then echo pacman
    else
        echo "ERROR: Could not detect a supported package manager (dnf, apt, pacman)." >&2
        exit 1
    fi
}
PM="$(detect_pm)"
echo "==> Detected package manager: $PM"

# ── Detect display server session ───────────────────────────────────────
session_type="${XDG_SESSION_TYPE:-}"
if [[ -z "$session_type" ]]; then
    if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        session_type="wayland"
    elif [[ -n "${DISPLAY:-}" ]]; then
        session_type="x11"
    else
        session_type="wayland"
    fi
fi
echo "==> Detected session type: $session_type"

# ── Build package list ──────────────────────────────────────────────────
desktop="${XDG_CURRENT_DESKTOP:-}"

declare -a pkgs=()
case "$PM" in
    dnf)
        pkgs=(android-tools python3-evdev)
        if [[ "${session_type,,}" == "x11" ]]; then
            # X11 session: only install X11 tools + GStreamer with ximagesrc (no Wayland/portal/pipewire)
            pkgs+=(xorg-x11-server-utils xinput
                   gstreamer1-plugins-base gstreamer1-plugins-good
                   gstreamer1-plugins-bad-free gstreamer1-plugin-openh264)
        else
            # Wayland session: only install Wayland tools (no X11/xrandr/xinput)
            case "${desktop^^}" in
                *KDE*|*GNOME*)
                    pkgs+=(python3-jeepney pipewire-gstreamer
                           gstreamer1-plugins-base gstreamer1-plugins-good
                           gstreamer1-plugins-bad-free gstreamer1-plugin-openh264)
                    ;;
                *)
                    pkgs+=(wf-recorder)
                    ;;
            esac
        fi
        ;;
    apt)
        pkgs=(adb python3-evdev)
        if [[ "${session_type,,}" == "x11" ]]; then
            # X11 session: only install X11 tools + GStreamer with ximagesrc (no Wayland/portal/pipewire)
            pkgs+=(x11-xserver-utils xinput
                   gstreamer1.0-plugins-base gstreamer1.0-plugins-good
                   gstreamer1.0-plugins-bad gstreamer1.0-openh264)
        else
            # Wayland session: only install Wayland tools (no X11/xrandr/xinput)
            case "${desktop^^}" in
                *KDE*|*GNOME*)
                    pkgs+=(python3-jeepney pipewire gstreamer1.0-pipewire
                           gstreamer1.0-plugins-base gstreamer1.0-plugins-good
                           gstreamer1.0-plugins-bad gstreamer1.0-openh264)
                    ;;
                *)
                    pkgs+=(wf-recorder)
                    ;;
            esac
        fi
        ;;
    pacman)
        pkgs=(android-tools python-evdev)
        if [[ "${session_type,,}" == "x11" ]]; then
            # X11 session: only install X11 tools + GStreamer with ximagesrc (no Wayland/portal/pipewire)
            pkgs+=(xorg-xrandr xorg-xinput
                   gst-plugins-base gst-plugins-good
                   gst-plugins-bad gstreamer)
        else
            # Wayland session: only install Wayland tools (no X11/xrandr/xinput)
            case "${desktop^^}" in
                *KDE*|*GNOME*)
                    pkgs+=(python-jeepney gst-plugin-pipewire
                           gst-plugins-base gst-plugins-good
                           gst-plugins-bad gstreamer)
                    ;;
                *)
                    pkgs+=(wf-recorder)
                    ;;
            esac
        fi
        ;;
esac

# ── Install packages ────────────────────────────────────────────────────
echo "==> Installing packages (sudo needed): ${pkgs[*]}"
case "$PM" in
    dnf)    sudo dnf install -y "${pkgs[@]}" ;;
    apt)    sudo apt-get update && sudo apt-get install -y "${pkgs[@]}" ;;
    pacman) sudo pacman -S --needed --noconfirm "${pkgs[@]}" ;;
esac

# ── Install server ──────────────────────────────────────────────────────
echo "==> Installing server to $prefix"
server_src="$here/core/second_screen_server.py"
[[ ! -f "$server_src" ]] && server_src="$here/server/second_screen_server.py"
install -Dm755 "$server_src" "$prefix/share/usb-second-screen/second_screen_server.py"
mkdir -p "$prefix/bin"
cat > "$prefix/bin/usb-second-screen" <<EOF
#!/usr/bin/env bash
exec python3 "$prefix/share/usb-second-screen/second_screen_server.py" "\$@"
EOF
chmod +x "$prefix/bin/usb-second-screen"

# ── Install systemd user unit ───────────────────────────────────────────
echo "==> Installing systemd user service"
unit_dir="$HOME/.config/systemd/user"
mkdir -p "$unit_dir"
service_src="$here/service/usb-second-screen.service"
[[ ! -f "$service_src" ]] && service_src="$here/server/usb-second-screen.service"
install -Dm644 "$service_src" "$unit_dir/usb-second-screen.service"
systemctl --user daemon-reload 2>/dev/null || true

# ── Touch / uinput setup ───────────────────────────────────────────────
if [[ $with_touch -eq 1 ]]; then
    if [[ -f "$here/setup_touch.sh" ]]; then
        bash "$here/setup_touch.sh"
    else
        echo "==> Allowing the 'input' group to create virtual touch devices (sudo needed)"
        echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' |
            sudo tee /etc/udev/rules.d/99-usb-second-screen-uinput.rules >/dev/null
        echo uinput | sudo tee /etc/modules-load.d/uinput.conf >/dev/null
        sudo usermod -aG input "$USER"
        sudo udevadm control --reload
        sudo udevadm trigger
        sudo modprobe uinput || true
        echo "    Log out and back in so the new group applies, then start the server with --touch."
    fi
fi

# ── PATH check ──────────────────────────────────────────────────────────
case ":$PATH:" in
    *":$prefix/bin:"*) ;;
    *) echo "NOTE: $prefix/bin is not in your PATH" ;;
esac

cat <<'MSG'

Done. Check the H.264 encoder (KDE/GNOME):
    gst-inspect-1.0 pipewiresrc openh264enc x264enc

  Fedora:  openh264enc is installed above. For better quality x264enc:
           enable RPM Fusion free, then  sudo dnf install gstreamer1-plugins-ugly

  Ubuntu:  sudo apt install gstreamer1.0-plugins-ugly

  Arch:    The x264 encoder is in gst-plugins-ugly (community):
           sudo pacman -S gst-plugins-ugly

Then install the Android app (see README.md) and run:  usb-second-screen
MSG
