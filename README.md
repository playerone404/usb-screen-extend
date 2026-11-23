# USB Second Screen (SideScreen)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Windows & Linux](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-green.svg)](#)
[![Android: 8.0+](https://img.shields.io/badge/Android-8.0%2B-brightgreen.svg)](#)
[![Latency: < 20ms](https://img.shields.io/badge/Latency-%3C%2020ms-orange.svg)](#)

> Turn an Android phone or tablet into an ultra-low-latency **second monitor** for your **Windows** or **Linux** PC over a USB cable.  
> **No Wi-Fi required. No root needed. Hardware-accelerated. Real multi-touch support.**

```
┌──────────────┐          USB Cable          ┌──────────────────────────────────────────────────┐
│  Android App │◄───────────────────────────►│                 Host PC Server                   │
│              │       adb reverse           │                                                  │
│  ┌────────┐  │         TCP 7878            │  ┌───────────┐   ┌──────────────┐   ┌─────────┐  │
│  │MediaCo-│  │◄────────────────────────────│  │ H.264     │◄──│ FFmpeg (Win) │◄──│ Virtual │  │
│  │dec     │  │     H.264 video stream      │  │ Framer    │   │ GStreamer/wf │   │ Display │  │
│  └────────┘  │     (< 20ms latency)        │  └───────────┘   └──────────────┘   └─────────┘  │
│              │                             │                                                  │
│  Touch ──────│────────────────────────────►│  ───► Win32 mouse / Linux uinput                │
│  Events      │     touch data packets      │                                                  │
│└──────────────┘                             └──────────────────────────────────────────────────┘
```

When you plug in your phone, the server creates a **true extended desktop monitor** (or mirrors your existing screen), encodes the display in real-time with your GPU, and streams it over USB. Touch inputs on your phone are instantly sent back to control your PC cursor.

---

## ⚠️ Important Note About This Project & AI Development

> **Disclaimer:** None of the code in this repository was written by me by hand. **I am not a developer — I am just a guy working as a system administrator who got an idea and wanted to make it a reality.**
>
> - **Initial Prototype:** Initially created and prototyped using **Claude (Free Plan)**.
> - **Refactor & Hardening:** Later rewritten, restructured, hardened, and unit-tested using **Google Antigravity (Gemini 3.8 Flash)**.
>
> Because this is an AI-assisted project driven by a system admin, issues, code reviews, and community pull requests are very welcome!

---

## 📖 Backstory

<!-- 
======================================================================
The idea for this project came to me when I had a spare Android phone lying around collecting dust. I thought, why not put it to good use by turning it into a second display for my Fedora laptop?

I searched through several applications, but couldn't find anything for Linux that worked quite the way I wanted. So, I turned to Claude (the free version, of course :)) and asked whether it was possible to build an application that could turn an Android phone into a second monitor for a Linux machine.

That led to the first version of the project, which initially supported only Fedora running KDE Plasma with the Wayland compositor.

However, I soon ran into the limitations of Claude's free tier and found it difficult to make further changes and improvements. That's when I got access to a free Google Gemini Pro subscription through a Jio recharge offer (an Indian telecom provider).

That's when the real development and improvements began. I added support for X11-based desktop environments and eventually extended compatibility to Windows as well.

Since I had little to no experience with Android app development or coding in general, I relied heavily on Gemini to handle most of the development, while I enjoyed my coffee and guided the process along. :)

Once the application reached a stage I was happy with, I asked Gemini to perform a comprehensive set of unit tests to check its reliability and identify potential security vulnerabilities. The test cases and their results are included in the repository for anyone interested in reviewing them.

I was initially a little hesitant about making the project public on GitHub, but eventually decided to share it. My hope is that someone else who has faced the same problem might find it useful.

If you're a developer who happens to come across this project, I'd really appreciate any feedback, suggestions, or bug reports. Every bit of input that could help improve the project is welcome!

Thanks for checking it out!
======================================================================
-->


---

## ⚡ Quick Links & Guides

- 🪟 **[Windows Setup & User Guide](windows_screen_extend/README.md)**
- 🐧 **[Linux Setup & User Guide](linux_screen_mirror/README.md)**
- 📱 **[Prebuilt APK Download](usb-second-screen.apk)** *(or see [Building the APK](BUILD_APK.md))*
- 🔒 **[Notes, Security & Usage Guide](NOTES_AND_SECURITY.md)**

---

## ✨ Key Features

- **🚀 Near-Zero Latency (< 20 ms)** — Pure USB 2.0 / 3.0 streaming via `adb reverse`. No Wi-Fi jitter, network drops, or router congestion.
- **🖥️ True Desktop Extension** — Creates a genuine second monitor in Windows and Linux Display Settings (drag windows, games, and browser tabs onto it).
- **👆 Interactive Touch & Mouse Control** — Tap and drag on your phone screen to control the Windows cursor or Linux `/dev/uinput` touchscreen.
- **⚡ Hardware GPU Encoding** — Supports NVIDIA NVENC (`h264_nvenc`), Intel QuickSync (`h264_qsv`), AMD AMF (`h264_amf`), and Linux VA-API for < 2% CPU usage.
- **🪟 Windows 10 & 11 Ready** — Portable system tray app with zero flashing command prompt windows, 60/30 FPS switcher, display selectors, and 1-click tool downloader.
- **🐧 Universal Linux Support** — Compatible with Wayland (**KDE Plasma**, **GNOME**, **Hyprland**, **Sway**) and **X11** sessions.
- **📱 Zero Root Required** — Works on any standard Android 8.0+ device with standard USB Debugging enabled.

---

## 🚀 Quick Start

### 1. Install the Android App
Install [`usb-second-screen.apk`](usb-second-screen.apk) on your Android phone or tablet:
- Copy the APK to your phone and tap to install it, OR
- Run `adb install usb-second-screen.apk` from your terminal.

---

### 2A. Running on Windows

1. **Download Tools (One-Time):**  
   Double-click **`windows_screen_extend/bin/download_tools.bat`** (downloads portable FFmpeg and ADB directly into `bin/`, or the app will prompt you on first launch).
2. **Enable Virtual Display (To Extend Desktop):**  
   Double-click **`windows_screen_extend/1_Setup_Virtual_Display.bat`** (type `1` and press Enter).
3. **Start Streaming:**  
   Double-click **`windows_screen_extend/2_Start_Second_Screen.vbs`**.  
   *(Starts silently in your taskbar tray without any flashing command prompt window).*
4. **Plug in your phone** via USB (with USB Debugging ON) and open the **Second Screen** app.

👉 *See the full [Windows User Manual](windows_screen_extend/README.md) for tray controls and options.*

---

### 2B. Running on Linux

1. **Install Dependencies:**
   ```bash
   cd linux_screen_mirror
   ./1_install.sh            # or ./1_install.sh --with-touch for touch support
   ```
2. **Start Streaming:**
   ```bash
   ./2_start_second_screen.sh
   # (or type `usb-second-screen` from any terminal)
   ```
3. **Plug in your phone** via USB and open the app.

👉 *See the full [Linux User Manual](linux_screen_mirror/README.md) for Wayland/X11 instructions and systemd service setup.*

---

## 🗂️ Repository Structure

```
usb-second-screen/
│
├── android/               ◄── Android client app source code (Kotlin + MediaCodec)
├── windows_screen_extend/ ◄── Windows edition (Tray app, FFmpeg, Amyuni IDD driver)
│   ├── 1_Setup_Virtual_Display.bat
│   ├── 2_Start_Second_Screen.vbs
│   ├── Start_Debug_Console.bat
│   ├── bin/               (download_tools.bat & download_tools.py)
│   ├── core/              (server.py & tray_app.py)
│   └── driver/            (usbmmidd_v2 driver)
│
├── linux_screen_mirror/   ◄── Linux edition (Wayland & X11 capture server)
│   ├── 1_install.sh
│   ├── 2_start_second_screen.sh
│   ├── setup_touch.sh
│   ├── core/              (second_screen_server.py)
│   └── service/           (systemd user unit)
│
├── tests/                 ◄── Automated unit tests (protocol, AUParser, security)
├── usb-second-screen.apk  ◄── Prebuilt ready-to-use Android APK
├── BUILD_APK.md           ◄── Guide for building Android APK from source
├── NOTES_AND_SECURITY.md  ◄── Security considerations, FAQ, and technical notes
└── README.md              ◄── Master repository documentation
```

---

## 🖥️ Supported Platforms

| Platform | Compositor / Display Server | Capture Method | Virtual Display Driver |
|---|---|---|---|
| **Windows 10 / 11** | Desktop Window Manager (DWM) | FFmpeg GDI / Desktop Duplication | Amyuni `usbmmidd` Indirect Display Driver (IDD) |
| **Linux (KDE / GNOME)** | Wayland | `xdg-desktop-portal` + PipeWire + GStreamer | Virtual monitor portal API |
| **Linux (Hyprland / Sway)**| Wayland | `wf-recorder` (wlr-screencopy) | Headless output IPC (`hyprctl` / `swaymsg`) |
| **Linux (X11)** | Xorg (XFCE, i3, Cinnamon, MATE) | GStreamer `ximagesrc` | `xrandr` virtual outputs |

---

## 🔒 Security & Privacy

- **Localhost Only:** All servers bind strictly to `127.0.0.1` and communicate solely over the physical USB cable via ADB. The stream is **never** broadcasted to your local Wi-Fi or LAN.
- **Minimal Permissions:** The Android app only requests standard `INTERNET` permission to connect to the localhost tunnel. No camera, microphone, storage, contacts, or location access.
- **Input Clamping:** Touch coordinates from the phone are normalized and strictly clamped to prevent accidental clicks outside the target display.
- 👉 Read **[`NOTES_AND_SECURITY.md`](NOTES_AND_SECURITY.md)** for full security details and tips.

---

## 🧪 Testing

The repository includes a comprehensive unit test suite covering the wire protocol, H.264 Annex-B parser, coordinate scaling, and static security checks:

```bash
python -m unittest discover -s tests -v
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.
1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/awesome-feature`).
3. Commit your changes (`git commit -m 'Add awesome feature'`).
4. Run the unit test suite (`python -m unittest discover -s tests -v`).
5. Push to the branch (`git push origin feature/awesome-feature`).
6. Open a Pull Request.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).  
Third-party utilities (`ffmpeg`, Amyuni `usbmmidd`, `adb`) are subject to their respective licenses.
