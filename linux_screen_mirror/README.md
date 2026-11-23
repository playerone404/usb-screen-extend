# USB Second Screen — Linux Edition

Turn your Android phone or tablet into an ultra-low-latency **second monitor** for your **Linux PC** over a USB cable. Zero Wi-Fi required, hardware-accelerated video streaming, and multi-touch support.

100% compatible with the official Android client ([`usb-second-screen.apk`](../usb-second-screen.apk)) in the repository root.

---

## 🗂️ Folder Structure

The folder is structured to keep all Linux components neatly grouped and easy to run:

```
linux_screen_mirror/
│
├── 1_install.sh              ◄── [STEP 1] Package installer & system setup (Ubuntu, Fedora, Arch)
├── 2_start_second_screen.sh   ◄── [STEP 2] Quick launcher to start streaming
├── setup_touch.sh            ◄── Run anytime to enable phone touch control without reinstalling
├── uninstall.sh              ◄── Clean uninstaller
├── README.md                 ◄── This user manual
│
├── core/                     ◄── Core server scripts
│   ├── second_screen_server.py (Wayland & X11 capture server)
│   └── requirements.txt      (Python packages: jeepney, evdev)
│
└── service/                  ◄── Background service
    └── usb-second-screen.service (Systemd user unit)
```

---

## ⚡ Quick Start (2 Simple Steps)

### Step 1: Install Dependencies
Open a terminal in this folder and run:

```bash
# Standard install (Ubuntu/Debian, Fedora, or Arch Linux)
./1_install.sh

# Or install with touch support (control your PC via phone screen taps)
./1_install.sh --with-touch
```
*What this does:*
- Automatically detects your package manager (`apt`, `dnf`, or `pacman`).
- Automatically detects your session type (**Wayland** or **X11**).
- Installs the exact packages needed (ADB, GStreamer/PipeWire, xrandr/xinput, or wf-recorder).
- Installs the `usb-second-screen` command to `~/.local/bin/` and registers the systemd service.

*(Note: If you passed `--with-touch`, log out and log back in once so your user's new `input` group permissions take effect).*

#### Forgot to enable touch during install?
No problem! You don't need to reinstall everything. Just run:
```bash
./setup_touch.sh
```
Then log out and back in once to apply the new permissions, and launch with `./2_start_second_screen.sh --touch`.

---

### Step 2: Start Streaming
Connect your phone with a USB cable (with **USB Debugging** enabled), open the **Second Screen** app on the phone, and run:

```bash
./2_start_second_screen.sh
```

It will ask you how you want to start:
- **[1] In this terminal (Default)** — Runs right in your terminal window, and cleanly stops as soon as you close it or press `Ctrl+C`.
- **[2] As a background service** — Starts immediately in the background and runs automatically every time you log in to Linux.

*(Tip: You can skip the prompt by passing flags directly, e.g., `./2_start_second_screen.sh --touch` or `./2_start_second_screen.sh --service`).*

You will see:
```text
[second-screen] compositor: portal, listening on 127.0.0.1:7878
[second-screen] waiting for a phone (USB debugging on?)...
[second-screen] USB link UP! Phone ready to stream.
```

Drag any window off the edge of your screen onto your phone!

---

## 🖥️ Supported Linux Desktop Environments

| Desktop / Session | Technology Used | How the Virtual Monitor Works |
|---|---|---|
| **KDE Plasma (Wayland)** | xdg-desktop-portal + PipeWire + GStreamer | Desktop creates a genuine virtual screen in System Settings. |
| **GNOME (Wayland)** | xdg-desktop-portal + PipeWire + GStreamer | Desktop creates a virtual screen automatically. |
| **Hyprland (Wayland)** | `hyprctl output create headless` + `wf-recorder` | Creates headless monitor matching your phone's exact resolution. |
| **Sway (Wayland)** | `swaymsg create_output` + `wf-recorder` | Creates headless monitor matching your phone's exact resolution. |
| **X11 (Any Desktop)** | `xrandr` virtual monitor + `ximagesrc` | Adds a virtual mode to disconnected display output (VGA-1/HDMI-1). |

---

## 🔄 Running as a Background Service (Optional)

If you want the server to start automatically whenever you log in:

```bash
# Enable and start the systemd user service
systemctl --user enable --now usb-second-screen

# Check service status
systemctl --user status usb-second-screen

# Stop the service
systemctl --user stop usb-second-screen
```

---

## 🗑️ How to Uninstall

To remove the installed server files, systemd service, and udev rules:

```bash
./uninstall.sh
```

---

## ⚙️ Command-Line Flags

You can customize the server by passing flags to `2_start_second_screen.sh` or `usb-second-screen`:

```bash
./2_start_second_screen.sh [options]
```

| Flag | Default | Description |
|---|---|---|
| `--fps <NUM>` | `60` | Stream frame rate (e.g. `60` or `30`) |
| `--bitrate <BPS>` | `20000000` | Stream bitrate in bps (default: 20 Mbps) |
| `--touch` | Off | Enable touch input forwarding to `/dev/uinput` |
| `--encoder <NAME>` | `auto` | Video encoder (`x264enc`, `openh264enc`, `vaapih264enc`) |
| `--no-portal` | Off | Skip xdg-desktop-portal and force direct capture |
| `--no-adb` | Off | Do not manage `adb reverse` automatically |
| `-v, --verbose` | Off | Show detailed debug logs |
