#!/usr/bin/env python3
"""
Downloads portable standalone FFmpeg and Android platform-tools (ADB) for Windows.
"""

import os
import sys
import tempfile
import urllib.request
import zipfile

FFMPEG_URL = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"
ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"


def download_with_progress(url, dest_path, desc):
    print(f"==> Downloading {desc}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        block_size = 64 * 1024
        downloaded = 0
        while True:
            chunk = resp.read(block_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = min(int(downloaded * 100 / total), 100)
                mb_down = downloaded / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                sys.stdout.write(f"\r    {pct}% ({mb_down:.1f} MB / {mb_tot:.1f} MB)")
            else:
                sys.stdout.write(f"\r    {downloaded / (1024 * 1024):.1f} MB")
            sys.stdout.flush()
    print()


def setup_ffmpeg(bin_dir):
    target = os.path.join(bin_dir, "ffmpeg.exe")
    if os.path.exists(target):
        print(f"[OK] ffmpeg.exe already exists in {bin_dir}")
        return True

    temp_zip = os.path.join(tempfile.gettempdir(), "ffmpeg_dl.zip")
    try:
        download_with_progress(FFMPEG_URL, temp_zip, "FFmpeg 7.1 Essentials")
        print("==> Extracting ffmpeg.exe...")
        with zipfile.ZipFile(temp_zip, "r") as zf:
            for member in zf.namelist():
                if member.endswith("bin/ffmpeg.exe") or member.endswith("ffmpeg.exe"):
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    print(f"[OK] Extracted ffmpeg.exe to {target}")
                    return True
        print("[ERROR] Could not find ffmpeg.exe in archive.")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to download FFmpeg: {e}")
        return False
    finally:
        if os.path.exists(temp_zip):
            try: os.remove(temp_zip)
            except OSError: pass


def setup_adb(bin_dir):
    target = os.path.join(bin_dir, "adb.exe")
    if os.path.exists(target):
        print(f"[OK] adb.exe already exists in {bin_dir}")
        return True

    temp_zip = os.path.join(tempfile.gettempdir(), "adb_dl.zip")
    try:
        download_with_progress(ADB_URL, temp_zip, "Google Android Platform-Tools (ADB)")
        print("==> Extracting adb.exe and required libraries...")
        needed = {"adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"}
        found = set()
        with zipfile.ZipFile(temp_zip, "r") as zf:
            for member in zf.namelist():
                fname = os.path.basename(member)
                if fname in needed:
                    with zf.open(member) as src, open(os.path.join(bin_dir, fname), "wb") as dst:
                        dst.write(src.read())
                    found.add(fname)
        if needed.issubset(found):
            print(f"[OK] Extracted ADB tools to {bin_dir}")
            return True
        print(f"[WARN] Extracted: {found}, missing: {needed - found}")
        return len(found) > 0
    except Exception as e:
        print(f"[ERROR] Failed to download ADB: {e}")
        return False
    finally:
        if os.path.exists(temp_zip):
            try: os.remove(temp_zip)
            except OSError: pass


def main():
    bin_dir = os.path.dirname(os.path.abspath(__file__))
    print("=======================================================")
    print("  USB Second Screen — Tool Downloader (Windows)")
    print("=======================================================")
    print()

    ff_ok = setup_ffmpeg(bin_dir)
    print()
    adb_ok = setup_adb(bin_dir)

    print()
    print("=======================================================")
    if ff_ok and adb_ok:
        print("  All tools are ready! You can now start the server.")
    else:
        print("  Some tools could not be downloaded automatically.")
    print("=======================================================")
    return 0 if (ff_ok and adb_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
