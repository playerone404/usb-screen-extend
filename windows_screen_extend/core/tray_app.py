#!/usr/bin/env python3
"""
USB Second Screen — Windows System Tray Application
===================================================

Runs the second-screen server in the background and places a monitor icon in the
system notification area (next to the clock).

Provides a right-click menu to:
- Monitor streaming status
- Switch active monitors (Display 1, Display 2, Virtual Display)
- Change frame rates (60 FPS / 30 FPS)
- Enable / disable virtual displays
- Restart server or exit cleanly

Runs without requiring a visible console window (via pythonw.exe).
Requires ZERO external pip packages (uses standard library and ctypes).
"""

import ctypes
from ctypes import wintypes
import os
import shutil
import subprocess
import sys
import threading
import time

# Win32 API constants
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
WM_CONTEXTMENU = 0x007B

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_CHECKED = 0x00000008
MF_UNCHECKED = 0x00000000
MF_GRAYED = 0x00000001
MF_DISABLED = 0x00000002
MF_POPUP = 0x00000010

TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_int64
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


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


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", wintypes.DWORD),
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


class ServerManager:
    """Manages the background server.py process."""

    def __init__(self):
        self.proc = None
        self.monitor_idx = 0  # 0 = auto
        self.fps = 60
        self.bitrate = 20
        self.lock = threading.Lock()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

    def start(self):
        with self.lock:
            self.stop_locked()
            python_bin = sys.executable
            # Prefer pythonw if available to avoid opening console
            pythonw = os.path.join(os.path.dirname(python_bin), "pythonw.exe")
            exe = pythonw if os.path.exists(pythonw) else python_bin

            server_script = os.path.join(self.base_dir, "server.py")
            if not os.path.exists(server_script):
                server_script = os.path.join(self.base_dir, "core", "server.py")
            cmd = [exe, server_script, "--fps", str(self.fps), "--bitrate-mbps", str(self.bitrate)]
            if self.monitor_idx > 0:
                cmd += ["--monitor", str(self.monitor_idx)]

            # Creation flags to ensure no console window pops up
            creationflags = 0x08000000  # CREATE_NO_WINDOW
            try:
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=self.base_dir,
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                print(f"[Tray] Failed to start server: {e}", file=sys.stderr)

    def stop_locked(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def stop(self):
        with self.lock:
            self.stop_locked()

    def restart(self):
        self.start()

    def is_running(self):
        with self.lock:
            return self.proc is not None and self.proc.poll() is None


class SystemTrayApp:
    def __init__(self):
        self.server_mgr = ServerManager()
        self.hwnd = None
        self.h_icon = None
        self.nid = None
        self.class_name = "USBSecondScreenTrayClass"
        self.wnd_proc_ref = WNDPROC(self.wnd_proc)

    def run(self):
        # Load monitor icon from shell32.dll (icon index 15 is standard display)
        self.h_icon = shell32.ExtractIconW(0, "shell32.dll", 15)
        if not self.h_icon:
            self.h_icon = user32.LoadIconW(0, 32512)  # IDI_APPLICATION fallback

        h_instance = kernel32.GetModuleHandleW(None)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self.wnd_proc_ref
        wc.hInstance = h_instance
        wc.lpszClassName = self.class_name
        wc.hIcon = self.h_icon
        wc.hIconSm = self.h_icon
        user32.RegisterClassExW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(
            0, self.class_name, "USB Second Screen Tray",
            0, 0, 0, 0, 0, None, None, h_instance, None
        )

        # Add Tray Icon
        self.nid = NOTIFYICONDATAW()
        self.nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self.nid.hWnd = self.hwnd
        self.nid.uID = 1001
        self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_INFO
        self.nid.uCallbackMessage = WM_TRAYICON
        self.nid.hIcon = self.h_icon
        self.nid.szTip = "USB Second Screen — Running"
        self.nid.szInfoTitle = "USB Second Screen"
        self.nid.szInfo = "Server is running in the system tray. Plug in your phone over USB!"
        self.nid.dwInfoFlags = NIIF_INFO

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self.nid))

        # Check required tools and prompt if missing
        bin_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin"))
        ffmpeg_bin = os.path.join(bin_dir, "ffmpeg.exe")
        if not shutil.which("ffmpeg") and not os.path.exists(ffmpeg_bin):
            dl_bat = os.path.join(bin_dir, "download_tools.bat")
            if os.path.exists(dl_bat):
                MB_YESNO = 0x00000004
                MB_ICONQUESTION = 0x00000020
                res = user32.MessageBoxW(
                    0,
                    "FFmpeg was not found.\n\n"
                    "Would you like to download portable FFmpeg & ADB now?",
                    "USB Second Screen",
                    MB_YESNO | MB_ICONQUESTION,
                )
                if res == 6:  # IDYES
                    subprocess.run(["cmd.exe", "/c", "start", "/wait", dl_bat], shell=False)

        # Start the background server
        self.server_mgr.start()

        # Message loop
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        self.server_mgr.stop()
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
        user32.DestroyWindow(self.hwnd)
        user32.UnregisterClassW(self.class_name, h_instance)

    def show_menu(self):
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))

        h_menu = user32.CreatePopupMenu()
        h_monitor_sub = user32.CreatePopupMenu()
        h_fps_sub = user32.CreatePopupMenu()

        status_str = "● Server Running (Port 7878)" if self.server_mgr.is_running() else "○ Server Stopped"
        user32.AppendMenuW(h_menu, MF_STRING | MF_GRAYED, 1, status_str)
        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, None)

        # Monitor submenu
        monitors = get_monitors()
        cmd_base_mon = 100
        # Auto option
        flags = MF_STRING | (MF_CHECKED if self.server_mgr.monitor_idx == 0 else MF_UNCHECKED)
        user32.AppendMenuW(h_monitor_sub, flags, cmd_base_mon, "Auto-detect (Virtual or Secondary)")

        for i, m in enumerate(monitors):
            prim = " [Primary]" if m["is_primary"] else ""
            label = f"Display {i + 1}: {m['width']}x{m['height']}{prim}"
            flags = MF_STRING | (MF_CHECKED if self.server_mgr.monitor_idx == (i + 1) else MF_UNCHECKED)
            user32.AppendMenuW(h_monitor_sub, flags, cmd_base_mon + i + 1, label)

        user32.AppendMenuW(h_menu, MF_POPUP, h_monitor_sub, "📺 Select Display")

        # FPS submenu
        cmd_fps_30 = 201
        cmd_fps_60 = 202
        f30 = MF_STRING | (MF_CHECKED if self.server_mgr.fps == 30 else MF_UNCHECKED)
        f60 = MF_STRING | (MF_CHECKED if self.server_mgr.fps == 60 else MF_UNCHECKED)
        user32.AppendMenuW(h_fps_sub, f60, cmd_fps_60, "60 FPS (Smooth)")
        user32.AppendMenuW(h_fps_sub, f30, cmd_fps_30, "30 FPS (Battery Saver)")
        user32.AppendMenuW(h_menu, MF_POPUP, h_fps_sub, "⚡ Frame Rate")

        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, None)

        # Virtual display actions
        user32.AppendMenuW(h_menu, MF_STRING, 301, "➕ Enable Virtual Monitor")
        user32.AppendMenuW(h_menu, MF_STRING, 302, "➖ Disable Virtual Monitor")

        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(h_menu, MF_STRING, 401, "🔄 Restart Server")
        user32.AppendMenuW(h_menu, MF_STRING, 402, "❌ Exit")

        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenuEx(
            h_menu, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_NONOTIFY,
            pt.x, pt.y, self.hwnd, None
        )
        user32.DestroyMenu(h_menu)

        self.handle_command(cmd, len(monitors))

    def handle_command(self, cmd, num_monitors):
        if cmd == 0:
            return
        if cmd == 402:  # Exit
            user32.PostQuitMessage(0)
        elif cmd == 401:  # Restart Server
            self.server_mgr.restart()
        elif cmd == 201:  # 30 FPS
            self.server_mgr.fps = 30
            self.server_mgr.restart()
        elif cmd == 202:  # 60 FPS
            self.server_mgr.fps = 60
            self.server_mgr.restart()
        elif cmd == 100:  # Monitor Auto
            self.server_mgr.monitor_idx = 0
            self.server_mgr.restart()
        elif 101 <= cmd <= 100 + num_monitors:
            self.server_mgr.monitor_idx = cmd - 100
            self.server_mgr.restart()
        elif cmd == 301:  # Enable Virtual Monitor
            base = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.join(base, "driver", "usbmmidd_v2", "deviceinstaller64.exe"),
                os.path.join(base, "..", "driver", "usbmmidd_v2", "deviceinstaller64.exe"),
                os.path.join(base, "usbmmidd_v2", "deviceinstaller64.exe"),
            ]
            installer = next((c for c in candidates if os.path.exists(c)), None)
            if installer:
                shell32.ShellExecuteW(None, "runas", installer, "enableidd 1", None, 0)
                time.sleep(1)
                self.server_mgr.restart()
            else:
                setup_bat = os.path.join(base, "..", "1_Setup_Virtual_Display.bat")
                if not os.path.exists(setup_bat):
                    setup_bat = os.path.join(base, "1_Setup_Virtual_Display.bat")
                subprocess.Popen(["cmd.exe", "/c", setup_bat])
        elif cmd == 302:  # Disable Virtual Monitor
            base = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.join(base, "driver", "usbmmidd_v2", "deviceinstaller64.exe"),
                os.path.join(base, "..", "driver", "usbmmidd_v2", "deviceinstaller64.exe"),
                os.path.join(base, "usbmmidd_v2", "deviceinstaller64.exe"),
            ]
            installer = next((c for c in candidates if os.path.exists(c)), None)
            if installer:
                shell32.ShellExecuteW(None, "runas", installer, "enableidd 0", None, 0)
                time.sleep(1)
                self.server_mgr.restart()

    def wnd_proc(self, hwnd, msg, wp, lp):
        if msg == WM_TRAYICON:
            if lp in (WM_RBUTTONUP, WM_LBUTTONUP, WM_CONTEXTMENU):
                self.show_menu()
                return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)


def main():
    app = SystemTrayApp()
    app.run()


if __name__ == "__main__":
    main()
