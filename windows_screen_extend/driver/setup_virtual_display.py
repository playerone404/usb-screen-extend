#!/usr/bin/env python3
"""
Downloads, installs, and controls the Amyuni Virtual Display Driver for Windows.
"""

import ctypes
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

DRIVER_URL = "https://www.amyuni.com/downloads/usbmmidd_v2.zip"
shell32 = ctypes.windll.shell32


def run_as_admin(cmd, params, wait=True):
    """Launches a process with UAC elevation (Administrator)."""
    ret = shell32.ShellExecuteW(None, "runas", cmd, params, None, 1)
    if ret <= 32:
        print(f"[ERROR] Administrator elevation was canceled or failed (code {ret}).")
        return False
    return True


def ensure_driver_downloaded(base_dir):
    candidates = [
        os.path.join(base_dir, "usbmmidd_v2"),
        os.path.join(base_dir, "driver", "usbmmidd_v2"),
        os.path.join(base_dir, "..", "driver", "usbmmidd_v2"),
    ]
    for d in candidates:
        installer = os.path.join(d, "deviceinstaller64.exe")
        if os.path.exists(installer):
            return d, installer

    driver_dir = os.path.join(base_dir, "usbmmidd_v2")
    installer = os.path.join(driver_dir, "deviceinstaller64.exe")

    print("==> Downloading Amyuni Virtual Display Driver (usbmmidd v2)...")
    os.makedirs(base_dir, exist_ok=True)
    temp_zip = os.path.join(tempfile.gettempdir(), "usbmmidd_v2.zip")

    try:
        req = urllib.request.Request(DRIVER_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp, open(temp_zip, "wb") as f:
            f.write(resp.read())

        print("==> Extracting driver package...")
        with zipfile.ZipFile(temp_zip, "r") as zf:
            zf.extractall(os.path.join(base_dir, "driver"))

        if os.path.exists(installer):
            print(f"[OK] Driver extracted to: {driver_dir}")
            return driver_dir, installer
        else:
            print("[ERROR] deviceinstaller64.exe not found after extraction.")
            return None, None
    except Exception as e:
        print(f"[ERROR] Failed to download driver: {e}")
        return None, None
    finally:
        if os.path.exists(temp_zip):
            try:
                os.remove(temp_zip)
            except OSError:
                pass


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print("========================================================")
    print("  Windows Virtual Display Driver Setup (usbmmidd v2)")
    print("========================================================")
    print()
    print("This utility manages the free Amyuni Virtual Display Driver,")
    print("which creates a genuine second monitor in Windows Display Settings.")
    print()
    print("Options:")
    print("  [1] Install Driver & Enable Virtual Monitor")
    print("  [2] Enable Virtual Monitor (Add a screen)")
    print("  [3] Disable Virtual Monitor (Remove virtual screen)")
    print("  [4] Uninstall Virtual Display Driver")
    print("  [5] Exit")
    print()

    choice = input("Select an option (1-5): ").strip()
    if choice == "5":
        return 0

    driver_dir, installer = ensure_driver_downloaded(base_dir)
    if not installer:
        return 1

    if choice == "1":
        print("\n==> Requesting Administrator permission to install driver...")
        # deviceinstaller64.exe install usbmmidd.inf usbmmidd && enableidd 1
        cmd = "cmd.exe"
        params = f'/c cd /d "{driver_dir}" && deviceinstaller64.exe install usbmmidd.inf usbmmidd && deviceinstaller64.exe enableidd 1'
        run_as_admin(cmd, params)
        print("\nDriver installed! Check Windows Settings > System > Display for your new screen.")

    elif choice == "2":
        print("\n==> Enabling virtual monitor...")
        run_as_admin(installer, "enableidd 1")
        print("Done.")

    elif choice == "3":
        print("\n==> Disabling virtual monitor...")
        run_as_admin(installer, "enableidd 0")
        print("Done.")

    elif choice == "4":
        print("\n==> Uninstalling driver...")
        cmd = "cmd.exe"
        params = f'/c cd /d "{driver_dir}" && deviceinstaller64.exe stop usbmmidd && deviceinstaller64.exe remove usbmmidd'
        run_as_admin(cmd, params)
        print("Driver uninstalled.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
