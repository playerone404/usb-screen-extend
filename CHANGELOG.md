# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-01

### Added

- **Linux server** (`server/second_screen_server.py`)
  - Virtual monitor creation and automatic cleanup on disconnect
  - Portal back-end (KDE Plasma, GNOME) via xdg-desktop-portal ScreenCast
  - Hyprland back-end via `hyprctl` and `wf-recorder`
  - Sway back-end via `swaymsg` and `wf-recorder`
  - H.264 Annex-B access unit framing and streaming
  - Support for x264, OpenH264, and VA-API encoders
  - Touch input injection via uinput (optional)
  - Automatic `adb reverse` setup and app launching
  - Configurable FPS, bitrate, resolution, encoder, and more
  - Restore token persistence for portal permissions

- **Android app** (`android/`)
  - Kotlin-based receiver app targeting API 24+ (Android 7.0+)
  - Hardware H.264 decoding via `MediaCodec`
  - Full-screen `SurfaceView` display
  - Multi-touch event capture and transmission to the server
  - Auto-reconnect on connection loss
  - Status display with connection state

- **Installation**
  - `install.sh` for Fedora with automatic desktop detection
  - Touch input setup with udev rules

- **Documentation**
  - README with setup instructions and option reference
  - BUILD_APK.md with three APK build methods
  - MIT License
