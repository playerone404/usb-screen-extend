# USB Second Screen — Notes, Security & Guidelines

This document outlines key technical notes, security considerations, and best practices to keep in mind when running, developing, or publishing this application.

---

## 🔒 1. Security & Privacy Considerations

### Localhost-Only Socket Binding (`127.0.0.1`)
- Both the Windows and Linux servers bind strictly to **`127.0.0.1`** (loopback address), **never** `0.0.0.0` or public network interfaces.
- The phone communicates with the server through `adb reverse tcp:7878 tcp:7878`, which tunnels TCP packets securely through the physical USB cable.
- **Why this matters:** Anyone on the same Wi-Fi or local area network (LAN) cannot intercept your video stream or send fake touch inputs to your PC.

### Never Run the Server as Root (`sudo`)
- On Linux, touch injection uses `/dev/uinput` via the system `input` group.
- **Do NOT run `second_screen_server.py` as root (`sudo`)!** The installer (`./1_install.sh --with-touch` or `./setup_touch.sh`) grants the required `/dev/uinput` permissions to your normal user account.
- Running desktop capture as root can expose privileged session handles and bypass Wayland/X11 security boundaries.

### Mouse & Touch Injection Guardrails
- Coordinates received from the phone are normalized (`0..65535`) and strictly clamped to the target monitor's pixel boundaries.
- When the phone disconnects or the app closes, the server automatically executes a failsafe `release_all()` to ensure mouse buttons or touch slots are never left stuck in a pressed state.
- **Note:** Because touch events simulate standard mouse clicks, anything visible on the extended screen can be clicked from the phone.

### Screen Privacy & DRM
- The server captures the raw pixel framebuffer of the selected display.
- **Be mindful of privacy:** Any passwords, private messages, or banking details dragged onto the extended screen will be mirrored on the phone's display.
- **DRM Protected Content:** Streaming services that enforce HDCP/DRM (e.g., Netflix, Disney+, Amazon Prime Video) will appear as black rectangles in the video feed. This is expected operating system behavior.

---

## 💻 2. Operating System Notes

### Windows Edition (`windows_screen_extend`)
- **Virtual Display Driver:** The project uses the signed Amyuni USB Mobile Monitor Virtual Display driver (`usbmmidd_v2`). It is a legitimate, digitally signed Indirect Display Driver (IDD).
- **Driver Re-enabling After Reboot:** Depending on your Windows power settings, the virtual screen may go to sleep after a PC reboot. To reactivate it, simply double-click `1_Setup_Virtual_Display.bat` (select `[1]` or `[2]`), or right-click the system tray icon and select **➕ Enable Virtual Monitor**.
- **Display Resolution & Aspect Ratio:**
  - In **Windows Settings > System > Display**, you can adjust the resolution of the virtual display (e.g., `1920x1080` or `1280x720`).
  - For the sharpest picture without black letterbox bars, match the aspect ratio of your Android phone (typically 16:9 or 19.5:9).
- **Silent Background Execution:** `2_Start_Second_Screen.vbs` uses `wscript.exe` with window mode `0` to launch the tray app without triggering a flashing black command prompt box.

### Linux Edition (`linux_screen_mirror`)
- **Compositor Back-ends:**
  - **KDE Plasma & GNOME (Wayland):** Uses `xdg-desktop-portal` and PipeWire to request a virtual display session.
  - **Hyprland & Sway (Wayland):** Creates headless outputs dynamically via `hyprctl` / `swaymsg` and captures them using `wf-recorder` (wlr-screencopy).
  - **X11 Desktops (XFCE, i3, Cinnamon, etc.):** Uses `xrandr` to activate unused display outputs and captures with GStreamer `ximagesrc`.
- **Systemd User Service:** If enabled, `usb-second-screen.service` runs under your user session (`systemctl --user`), not the system-wide daemon.

---

## 📱 3. Android Client Notes

- **USB Debugging Requirement:** The client requires **USB Debugging** enabled in Developer Options. USB debugging is used solely to establish the `adb reverse` TCP tunnel; root access is **not** required.
- **Battery & Charging:** Continuous 60 FPS H.264 video decoding uses the phone's dedicated hardware DSP/GPU (`MediaCodec`). While connected to a PC USB 3.0 or USB-C port, the phone will trickle-charge or stay at a steady battery level.
- **Screen Timeout:** The Android app automatically requests `FLAG_KEEP_SCREEN_ON` while a stream session is active, so the screen will not turn off while in use.
- **Permissions:** The Android app requests only `android.permission.INTERNET` (which Android requires to connect to `127.0.0.1` sockets). It requests zero sensitive permissions (no camera, microphone, storage, or location).

---

## ⚡ 4. Latency & Performance Optimization

| Setting | Recommended Value | When to Use |
|---|---|---|
| **Frame Rate** | `60 FPS` | Default for smooth desktop interaction, cursor movement, and video playback. |
| **Frame Rate** | `30 FPS` | Recommended when running on laptop battery or older CPU hardware. |
| **Bitrate** | `15 - 20 Mbps` | Optimal balance of image quality and latency over USB 2.0 / 3.0. |
| **Encoder** | Hardware (`NVENC` / `QSV` / `AMF` / `VA-API`) | Uses <2% CPU and encodes in ~2-4ms. |
| **Encoder** | Software (`libx264`) | Fallback if no GPU hardware encoder is present. Uses `ultrafast` preset with `zerolatency`. |

---

## 🚀 5. Publishing to GitHub Checklist

Before committing and pushing changes to GitHub:

1. **Verify `.gitignore` is present:** Ensure `.gitignore` is committed in the root directory so local configs, build caches, and keystores are never leaked.
2. **Never commit personal paths or credentials:**
   - `android/local.properties` contains your local Android SDK directory and must stay ignored.
   - Do not commit ADB authorization keys (`adbkey`, `adbkey.pub`).
   - Do not commit device serial numbers or private IP addresses.
3. **Run Unit Tests:**
   Run the included test suite to verify protocol and parser integrity:
   ```bash
   python -m unittest discover -s tests -v
   ```
4. **File Sizes:** GitHub enforces a 100 MB per-file limit. The bundled portable `ffmpeg.exe` is ~87 MB, which is below the limit, but keeping repository size minimal without large binaries lets users run `bin/download_tools.bat` on demand.
