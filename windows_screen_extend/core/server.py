#!/usr/bin/env python3
"""
USB Second Screen Server for Windows
====================================

Connects to the Android receiver app over USB via adb reverse.
Captures an existing or virtual monitor using FFmpeg (hardware NVENC/QSV/AMF or CPU libx264)
and streams low-latency H.264 access units to the phone. Touch events from the phone
are translated into Windows cursor and click actions.

Compatible with the standard USB Second Screen Android app.
"""

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time

# Wire protocol constants (matching Android app)
MSG = struct.Struct(">BBBBHH")
MSG_HELLO, MSG_TOUCH = 0, 1
TOUCH_DOWN, TOUCH_MOVE, TOUCH_UP = 0, 1, 2
APP_ACTIVITY = "com.example.secondscreen/.MainActivity"

# Mouse event flags for ctypes.windll.user32.mouse_event
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000

NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

user32 = ctypes.windll.user32


def log(*args):
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] [second-screen-win]", *args, flush=True)


# --------------------------------------------------------------------------
# Monitor enumeration via Windows API
# --------------------------------------------------------------------------
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", ctypes.c_wchar * 32),
    ]


def get_monitors():
    monitors = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(MONITORINFOEX)
        if user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
            r = info.rcMonitor
            monitors.append({
                "device": info.szDevice,
                "left": r.left,
                "top": r.top,
                "right": r.right,
                "bottom": r.bottom,
                "width": r.right - r.left,
                "height": r.bottom - r.top,
                "is_primary": bool(info.dwFlags & 1),
            })
        return True

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
    )
    user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
    return monitors


# --------------------------------------------------------------------------
# H.264 Annex-B parser into discrete access units
# --------------------------------------------------------------------------
class AUParser:
    """Splits raw H.264 byte stream into single video access units."""

    START = b"\x00\x00\x01"

    def __init__(self):
        self.buf = bytearray()
        self.cur = []
        self.has_vcl = False

    @property
    def pending(self):
        return bool(self.buf) or self.has_vcl

    def _add(self, nal, out):
        if not nal:
            return
        t = nal[0] & 0x1F
        vcl = t in (1, 5)
        first_slice = vcl and len(nal) > 1 and bool(nal[1] & 0x80)
        if self.has_vcl and (t in (6, 7, 8, 9) or first_slice):
            out.append(self._emit())
        self.cur.append(nal)
        if vcl:
            self.has_vcl = True

    def _emit(self):
        au = b"".join(b"\x00\x00\x00\x01" + n for n in self.cur)
        self.cur = []
        self.has_vcl = False
        return au

    def _starts(self):
        pos, i = [], 0
        while True:
            i = self.buf.find(self.START, i)
            if i < 0:
                return pos
            pos.append(i)
            i += 3

    def feed(self, data, out):
        self.buf += data
        starts = self._starts()
        for a, b in zip(starts, starts[1:]):
            self._add(bytes(self.buf[a + 3:b]).rstrip(b"\x00"), out)
        if starts:
            del self.buf[:starts[-1]]
        elif len(self.buf) > 3:
            del self.buf[:-3]

    def flush(self, out):
        if self.buf.startswith(self.START):
            self._add(bytes(self.buf[3:]).rstrip(b"\x00"), out)
        self.buf.clear()
        if self.has_vcl:
            out.append(self._emit())


# --------------------------------------------------------------------------
# Touch injection via Windows ctypes
# --------------------------------------------------------------------------
class WindowsTouchInjector:
    def __init__(self, monitor_rect):
        self.rect = monitor_rect
        self.is_down = False
        self.lock = threading.Lock()

    def handle(self, action, x_norm, y_norm):
        with self.lock:
            # Map 0..65535 normalized coordinates to monitor pixel bounds
            left, top = self.rect["left"], self.rect["top"]
            w, h = self.rect["width"], self.rect["height"]

            px = int(left + (x_norm / 65535.0) * w)
            py = int(top + (y_norm / 65535.0) * h)
            # Clamp to monitor bounds
            px = max(left, min(px, left + w - 1))
            py = max(top, min(py, top + h - 1))

            user32.SetCursorPos(px, py)

            if action == TOUCH_DOWN:
                if not self.is_down:
                    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    self.is_down = True
            elif action == TOUCH_UP:
                if self.is_down:
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    self.is_down = False
            elif action == TOUCH_MOVE:
                pass  # Cursor already moved via SetCursorPos

    def release_all(self):
        with self.lock:
            if self.is_down:
                user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_down = False


# --------------------------------------------------------------------------
# Tool helpers: ADB and FFmpeg discovery
# --------------------------------------------------------------------------
def find_adb():
    adb = shutil.which("adb")
    if adb:
        return adb
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "adb.exe"),
        os.path.join(base, "..", "bin", "adb.exe"),
        os.path.join(base, "..", "bin", "platform-tools", "adb.exe"),
        r"C:\Platform-tool\platform-tools\adb.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        r"C:\Program Files\Android\platform-tools\adb.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"


def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "ffmpeg.exe"),
        os.path.join(base, "bin", "ffmpeg.exe"),
        os.path.join(base, "..", "bin", "ffmpeg.exe"),
        os.path.join(base, "..", "ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\ffmpeg\bin\ffmpeg.exe"),
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def detect_best_encoder(ffmpeg_path):
    """Probes FFmpeg for GPU hardware encoders (NVENC, QSV, AMF) or defaults to libx264."""
    try:
        r = subprocess.run([ffmpeg_path, "-encoders"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
        out = r.stdout
        if "h264_nvenc" in out:
            return "h264_nvenc"
        if "h264_qsv" in out:
            return "h264_qsv"
        if "h264_amf" in out:
            return "h264_amf"
    except Exception:
        pass
    return "libx264"


def ensure_tools():
    """Finds FFmpeg and ADB, automatically invoking download_tools.py if missing."""
    ffmpeg = find_ffmpeg()
    adb = find_adb()
    has_adb = (shutil.which(adb) is not None) or os.path.exists(adb)

    if not ffmpeg or not has_adb:
        base = os.path.dirname(os.path.abspath(__file__))
        dl_script = os.path.normpath(os.path.join(base, "..", "bin", "download_tools.py"))
        if os.path.exists(dl_script):
            print("\n[INFO] Missing required tools (FFmpeg or ADB).")
            print("[INFO] Launching automatic tool downloader (bin/download_tools.py)...")
            try:
                subprocess.run([sys.executable, dl_script])
                ffmpeg = find_ffmpeg()
                adb = find_adb()
            except Exception as e:
                print(f"[WARN] Automatic tool download failed: {e}")

    return ffmpeg, adb


# --------------------------------------------------------------------------
# Background ADB keeper
# --------------------------------------------------------------------------
def adb_keeper(adb_path, port, launch_app, stop_event):
    spec = f"tcp:{port}"
    last_state = None
    while not stop_event.is_set():
        up = False
        try:
            r = subprocess.run([adb_path, "reverse", "--list"], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
            up = r.returncode == 0 and f"{spec} {spec}" in r.stdout
            if not up:
                r = subprocess.run([adb_path, "reverse", spec, spec], capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
                up = r.returncode == 0
                if up and launch_app:
                    subprocess.run([adb_path, "shell", "am", "start", "-n", APP_ACTIVITY],
                                   capture_output=True, timeout=5, creationflags=NO_WINDOW)
        except Exception:
            pass

        if up != last_state:
            log("USB link UP! Phone ready to stream." if up else "Waiting for phone via USB (USB debugging on?)...")
            last_state = up
        stop_event.wait(2.0)


# --------------------------------------------------------------------------
# Client Reader & Session Handling
# --------------------------------------------------------------------------
def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise EOFError("socket closed")
        data += chunk
    return bytes(data)


def client_reader(conn, touch, stop_event):
    try:
        while not stop_event.is_set():
            data = recv_exact(conn, MSG.size)
            mtype, action, slot, _, x, y = MSG.unpack(data)
            if mtype == MSG_TOUCH and touch:
                touch.handle(action, x, y)
    except Exception:
        pass
    finally:
        stop_event.set()
        if touch:
            touch.release_all()


def handle_client(conn, args, monitor, ffmpeg_path, encoder):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    except Exception:
        pass
    conn.settimeout(10.0)
    mtype, _, _, _, pw, ph = MSG.unpack(recv_exact(conn, MSG.size))
    conn.settimeout(None)

    if mtype != MSG_HELLO:
        log("Bad hello packet, dropping client.")
        return

    log(f"Phone connected! Reported resolution: {pw}x{ph}")
    target_w = monitor["width"]
    target_h = monitor["height"]
    log(f"Streaming monitor '{monitor['device']}' ({target_w}x{target_h}) @ {args.fps}fps")

    # Send stream resolution to phone
    conn.sendall(struct.pack(">HH", target_w, target_h))

    # Build FFmpeg command for low-latency desktop capture
    bitrate = f"{args.bitrate_mbps}M"
    cmd = [
        ffmpeg_path,
        "-y",
        "-probesize", "32",
        "-analyzeduration", "0",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-f", "gdigrab",
        "-framerate", str(args.fps),
        "-offset_x", str(monitor["left"]),
        "-offset_y", str(monitor["top"]),
        "-video_size", f"{target_w}x{target_h}",
        "-draw_mouse", "1",
        "-i", "desktop",
        "-c:v", encoder,
    ]

    buf_size = f"{max(1, args.bitrate_mbps // 4)}M"

    if encoder == "libx264":
        cmd += [
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-bf", "0",
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", buf_size,
            "-pix_fmt", "yuv420p",
            "-g", str(args.fps),
        ]
    elif encoder == "h264_nvenc":
        cmd += [
            "-preset", "p1",          # Lowest latency NVENC preset
            "-tune", "ull",           # Ultra low latency
            "-zerolatency", "1",      # Zero latency (no frame reordering)
            "-delay", "0",            # Immediate output
            "-bf", "0",               # No B-frames
            "-surfaces", "1",         # Minimum surface buffer
            "-no-scenecut", "1",      # Avoid lookahead buffer
            "-forced-idr", "1",       # Clean IDR frames
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", buf_size,
            "-pix_fmt", "yuv420p",
            "-g", str(args.fps),
        ]
    elif encoder == "h264_qsv":
        cmd += [
            "-preset", "veryfast",
            "-async_depth", "1",
            "-bf", "0",
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", buf_size,
            "-pix_fmt", "nv12",
            "-g", str(args.fps),
        ]
    elif encoder == "h264_amf":
        cmd += [
            "-usage", "ultralowlatency",
            "-quality", "speed",
            "-bf", "0",
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", buf_size,
            "-pix_fmt", "yuv420p",
            "-g", str(args.fps),
        ]
    else:  # Generic fallback
        cmd += [
            "-b:v", bitrate,
            "-pix_fmt", "yuv420p",
            "-g", str(args.fps),
        ]

    cmd += ["-f", "h264", "pipe:1"]

    stop_event = threading.Event()
    touch = WindowsTouchInjector(monitor) if args.touch else None

    # Start reader thread for touch
    threading.Thread(target=client_reader, args=(conn, touch, stop_event), daemon=True).start()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if not args.verbose else None,
        bufsize=0,
        creationflags=NO_WINDOW
    )

    parser = AUParser()
    sent_frames = 0
    raw_fd = proc.stdout.fileno()
    try:
        while not stop_event.is_set():
            # Read directly from OS pipe descriptor without buffering delay
            chunk = os.read(raw_fd, 8192)
            if not chunk:
                break
            aus = []
            parser.feed(chunk, aus)
            for au in aus:
                conn.sendall(struct.pack(">I", len(au)) + au)
                sent_frames += 1
    except (OSError, EOFError):
        log("Connection closed by phone.")
    finally:
        stop_event.set()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(2)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            proc.stdout.close()
        except Exception:
            pass
        if touch:
            touch.release_all()
        log(f"Session closed. Total frames sent: {sent_frames}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="USB Second Screen Server for Windows")
    parser.add_argument("--port", type=int, default=7878, help="Port to listen on (default: 7878)")
    parser.add_argument("--fps", type=int, default=60, help="Frame rate (default: 60)")
    parser.add_argument("--bitrate-mbps", type=int, default=20, help="Bitrate in Mbps (default: 20)")
    parser.add_argument("--monitor", type=int, default=0,
                        help="Monitor index to stream (0 = auto-select secondary if present, else primary)")
    parser.add_argument("--codec", default="auto", choices=["auto", "libx264", "h264_nvenc", "h264_qsv", "h264_amf"],
                        help="Video encoder (default: auto)")
    parser.add_argument("--touch", action="store_true", default=True, help="Enable touch injection into Windows (default: on)")
    parser.add_argument("--no-touch", dest="touch", action="store_false", help="Disable touch input injection")
    parser.add_argument("--no-adb", action="store_true", help="Do not manage adb reverse automatically")
    parser.add_argument("--no-launch", dest="launch_app", action="store_false",
                        help="Do not auto-open the app on the phone")
    parser.add_argument("--verbose", action="store_true", help="Show FFmpeg verbose output")
    args = parser.parse_args()

    # Discover FFmpeg & ADB
    ffmpeg, adb_path = ensure_tools()
    if not ffmpeg:
        print("\n[ERROR] FFmpeg was not found on your system!")
        print("To fix this, run 'download_tools.bat' in the 'bin' folder, or install via:")
        print("    winget install Gyan.FFmpeg\n")
        sys.exit(1)

    encoder = detect_best_encoder(ffmpeg) if args.codec == "auto" else args.codec
    log(f"Using FFmpeg: {ffmpeg}")
    log(f"Selected H.264 encoder: {encoder}")

    # Enumerate monitors
    monitors = get_monitors()
    if not monitors:
        log("No monitors found via Windows API.")
        sys.exit(1)

    print("\nDetected Displays:")
    for idx, m in enumerate(monitors):
        prim = " [Primary]" if m["is_primary"] else ""
        print(f"  [{idx + 1}] {m['device']} - {m['width']}x{m['height']} at ({m['left']}, {m['top']}){prim}")

    # Select monitor
    if args.monitor > 0 and args.monitor <= len(monitors):
        selected_monitor = monitors[args.monitor - 1]
    else:
        # Auto-pick: pick first non-primary monitor (e.g. Virtual Display) if present, else primary
        secondary = [m for m in monitors if not m["is_primary"]]
        selected_monitor = secondary[0] if secondary else monitors[0]

    log(f"Active monitor for streaming: {selected_monitor['device']} ({selected_monitor['width']}x{selected_monitor['height']})")

    # Start ADB keeper
    stop_event = threading.Event()
    if not args.no_adb:
        log(f"Using ADB: {adb_path}")
        threading.Thread(target=adb_keeper, args=(adb_path, args.port, args.launch_app, stop_event), daemon=True).start()

    # Start TCP Server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", args.port))
    server.listen(1)
    log(f"Listening on 127.0.0.1:{args.port}. Plug in your phone and open the app!")

    try:
        while True:
            conn, addr = server.accept()
            # Refresh monitor layout dynamically on every connection
            monitors = get_monitors()
            if args.monitor > 0 and args.monitor <= len(monitors):
                active_monitor = monitors[args.monitor - 1]
            else:
                secondary = [m for m in monitors if not m["is_primary"]]
                active_monitor = secondary[0] if secondary else monitors[0]

            log(f"Streaming target: '{active_monitor['device']}' ({active_monitor['width']}x{active_monitor['height']}) [Primary: {active_monitor['is_primary']}]")
            try:
                handle_client(conn, args, active_monitor, ffmpeg, encoder)
            except Exception as e:
                log("Error handling client:", e)
            finally:
                conn.close()
    except KeyboardInterrupt:
        log("Server stopping...")
    finally:
        stop_event.set()
        server.close()


if __name__ == "__main__":
    main()
