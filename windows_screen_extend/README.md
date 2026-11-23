# USB Second Screen — Windows Edition

Turn your Android phone or tablet into an ultra-low-latency **second monitor** for your Windows PC over a USB cable. Zero Wi-Fi required, hardware-accelerated video streaming, and real-time touch input support.

This server is 100% self-contained and compatible with the [`usb-second-screen.apk`](../usb-second-screen.apk) Android client.

---

## ⚡ Quick Start for New Users (3 Simple Steps)

Everything you need (virtual display drivers, system tray app, and 1-click tool downloander) is **ready in this folder**!

### Prerequisites (One-time check):
1. **Python on your PC**: If you don't have Python, download it from [python.org](https://www.python.org/downloads/).  
   > ⚠️ **Important:** During installation, check the box that says **"Add python.exe to PATH"**.
2. **Download Tools (FFmpeg & ADB)**:
   - Double-click **`bin\download_tools.bat`** (or let the app auto-download on first launch).
3. **USB Debugging on your Phone**:
   - On Android: Go to **Settings > About Phone** and tap **Build Number** 7 times to unlock Developer options.
   - Go to **Settings > System / Developer options** and turn **USB Debugging** ON.
4. **App on your Phone**:
   - Install [`usb-second-screen.apk`](../usb-second-screen.apk) on your Android phone.

---

### Step 1: Install the Virtual Display Driver (To Extend Desktop)
1. Double-click **`1_Setup_Virtual_Display.bat`**.
2. Type **`1`** and press **Enter** (a Windows Administrator prompt will appear; click **Yes**).
3. Open **Windows Settings > System > Display**.
4. You will see a new screen appear (Display 2). Under "Multiple displays", select **"Extend desktop to this display"**.

*(Note: If you only want to mirror your existing screen rather than extend, you can skip Step 1).*

---

### Step 2: Start the Second Screen Server
Double-click **`2_Start_Second_Screen.vbs`**.
- It starts completely invisibly in the background with **zero flashing black console windows**.
- A small monitor icon will appear in your **Windows notification tray** (bottom right, next to the clock — you may need to click the `^` arrow to see it).

*(If you ever want to see live terminal logs for testing, use `Start_Debug_Console.bat` instead).*

---

### Step 3: Connect Your Phone
1. Connect your phone to your PC with a USB cable.
2. If your phone asks **"Allow USB debugging?"**, tap **Allow** (and check "Always allow from this computer").
3. Open the **Second Screen** app on your phone.
4. Your extended Windows screen will stream instantly to your phone with smooth, low-latency video and touch support!

---

## 🗂️ What Are All These Files & Folders?

The folder is organized so you only ever need to interact with the numbered files in the root:

```
windows_screen_extend/
│
├── 1_Setup_Virtual_Display.bat   ◄── [STEP 1] Double-click to install/enable virtual screen
├── 2_Start_Second_Screen.vbs     ◄── [STEP 2] Double-click to start streaming (Silent, in tray)
├── Start_Debug_Console.bat       ◄── (Optional) Launch with visible logs in a CMD window
├── README.md                     ◄── This user manual
│
├── bin/                          ◄── Portable tool helpers
│   ├── download_tools.bat        (1-click downloader for FFmpeg & ADB)
│   └── download_tools.py
│
├── core/                         ◄── The Python server engines
│   ├── server.py                 (Main streaming server & touch injector)
│   ├── tray_app.py               (System tray interface next to the clock)
│   └── requirements.txt
│
└── driver/                       ◄── Virtual screen drivers
    ├── setup_virtual_display.py  (Driver installer logic)
    └── usbmmidd_v2/              (Amyuni virtual display driver files)
```

---

## 🎮 How to Control It (System Tray Menu)

While the server is running, look next to your Windows clock in the bottom-right corner and **right-click the monitor icon**:

```
● Server Running (Port 7878)
----------------------------
📺 Select Display       ► [Auto-detect / Display 1 / Display 2]
⚡ Frame Rate           ► [60 FPS (Smooth) / 30 FPS (Battery Saver)]
----------------------------
➕ Enable Virtual Monitor
➖ Disable Virtual Monitor
----------------------------
🔄 Restart Server
❌ Exit
```

- **How to stop the app**: Right-click the icon and choose **❌ Exit**.
- **Switching Displays**: Choose `📺 Select Display` if you want to switch between your main screen and the virtual extended screen.
- **Adjusting Performance**: Choose `⚡ Frame Rate` to switch between **60 FPS** (maximum smoothness) and **30 FPS** (lowest battery/CPU consumption).

---

## ❓ Frequently Asked Questions (FAQ)

### 1. Do I need to download ADB or FFmpeg on a new computer?
If they are not already on your PC, simply double-click **`bin/download_tools.bat`** once. It will automatically download portable copies of official Google ADB and FFmpeg essentials in a few seconds! Alternatively, if you already have them installed in PATH (or via `winget`), the server will automatically detect and use them.

### 2. My phone is mirroring my main screen instead of extending. Why?
This means the virtual display is either not installed or not active:
1. Double-click `1_Setup_Virtual_Display.bat` and press `1` (or right-click the tray icon and click `➕ Enable Virtual Monitor`).
2. Go to **Windows Settings > System > Display**, click the new display, and change the dropdown from "Duplicate" to **"Extend desktop to this display"**.

### 3. Nothing happens when I double-click `2_Start_Second_Screen.vbs`!
It is working! It runs silently in the background so that no black command prompt window flashes on your screen. Check your system tray (click the `^` arrow near the clock) — you will see the monitor icon there.

### 4. How does touch control work?
- **Tap**: Left mouse click at that position.
- **Drag**: Moves your mouse cursor smoothly across your extended display.
- Coordinates automatically scale to match the resolution of your screen.

### 5. The feed is black or says "Waiting for connection"?
- Check that your USB cable supports data transfer (some cheap cables are charging-only).
- Make sure **USB Debugging** is turned on in your phone's Developer Options.
- Unplug and replug the USB cable, then tap **"Allow"** on your phone if prompted.
