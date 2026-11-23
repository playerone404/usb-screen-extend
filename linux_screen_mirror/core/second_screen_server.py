#!/usr/bin/env python3
"""
usb-second-screen server (Linux, Wayland and X11)

Back-ends:
  portal    KDE Plasma / GNOME (Wayland): virtual monitor + capture via xdg-desktop-portal and PipeWire
  hyprland  Hyprland: headless output + wf-recorder (wlr-screencopy)
  sway      Sway: headless output + wf-recorder (wlr-screencopy)
  x11       X11 sessions (XFCE, i3, Cinnamon, MATE, X11 KDE/GNOME): xrandr virtual output + GStreamer ximagesrc

Flow:
  phone app --(adb reverse, USB)--> this server
    1. phone sends its screen size
    2. server creates a virtual monitor (portal: size chosen by the desktop; Hyprland/sway: phone's size)
    3. the monitor is captured as low-latency H.264 (GStreamer or wf-recorder)
    4. server splits the stream into access units and sends them to the phone
    5. touch events from the phone are injected through uinput (optional)
  When the phone disconnects, the virtual monitor is removed again.

Wire format
  phone -> PC : 8-byte messages  [type u8][action u8][slot u8][pad u8][x u16][y u16]
                type 0 = hello (x, y = phone surface width, height)
                type 1 = touch (action 0 down / 1 move / 2 up; x, y = 0..65535 normalised)
  PC -> phone : after hello: [width u16][height u16] of the stream (0, 0 = unknown),
                then repeated  [length u32][one H.264 access unit, Annex-B]
All integers are big-endian.
"""

# -- Platform guard --------------------------------------------------------
import sys
if sys.platform != "linux":
    print("ERROR: usb-second-screen server requires Linux (Wayland). "
          "It cannot run on", sys.platform, file=sys.stderr)
    sys.exit(1)

import argparse
import json
import logging
import os
import select
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import threading

VERSION = "0.1.0"

MSG = struct.Struct(">BBBBHH")
MSG_HELLO, MSG_TOUCH = 0, 1
TOUCH_DOWN, TOUCH_MOVE, TOUCH_UP = 0, 1, 2
MAX_SLOTS = 10
QUIET_GAP = 0.002  # seconds without capture data => the frame in progress is complete
TOUCH_NAME = "usb-second-screen-touch"
APP_ACTIVITY = "com.example.secondscreen/.MainActivity"

# Module-level logger; configured in main() after parsing args.
_logger = logging.getLogger("second-screen")


def log(*a):
    _logger.info(" ".join(str(x) for x in a))


def run(cmd, check=True):
    return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout


def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise EOFError("connection closed")
        data += chunk
    return bytes(data)


# --------------------------------------------------------------------------
# H.264 Annex-B -> access units
# --------------------------------------------------------------------------
class AUParser:
    """Splits a raw H.264 byte stream into access units (one video frame each).

    A new access unit starts at an SPS/PPS/SEI/AUD NAL, or at a slice whose
    first_mb_in_slice == 0, once the current unit already holds a slice.
    The last unit of a burst has no "next frame" to mark its end, so flush()
    is called when the encoder goes quiet, which avoids waiting a frame.
    """

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
# Compositor back-ends: create / remove a virtual monitor
# --------------------------------------------------------------------------
class Hyprland:
    name = "hyprland"

    def _names(self):
        return {m["name"] for m in json.loads(run(["hyprctl", "-j", "monitors", "all"]))}

    def create(self, w, h, fps, scale, position):
        before = self._names()
        run(["hyprctl", "output", "create", "headless"])
        new = self._names() - before
        if not new:
            raise RuntimeError("Hyprland did not report a new headless output")
        out = sorted(new)[0]
        run(["hyprctl", "keyword", "monitor", f"{out},{w}x{h}@{fps},{position},{scale}"])
        return out

    def remove(self, out):
        run(["hyprctl", "output", "remove", out], check=False)

    def bind_touch(self, out):
        r = run(["hyprctl", "keyword", f"device[{TOUCH_NAME}]:output", out], check=False)
        log(f"touch -> {out}: hyprctl said {r.strip() or 'nothing'}")


class Sway:
    name = "sway"

    def _outputs(self):
        return json.loads(run(["swaymsg", "-t", "get_outputs", "-r"]))

    def create(self, w, h, fps, scale, position):
        before = {o["name"] for o in self._outputs()}
        run(["swaymsg", "create_output"])
        after = self._outputs()
        new = [o for o in after if o["name"] not in before]
        if not new:
            raise RuntimeError("sway did not report a new headless output")
        out = new[0]["name"]
        x = max((o["rect"]["x"] + o["rect"]["width"] for o in after if o["name"] != out), default=0)
        run(["swaymsg", "output", out, "mode", f"{w}x{h}@{fps}Hz", "position", str(x), "0", "scale", str(scale)])
        return out

    def remove(self, out):
        run(["swaymsg", "output", out, "unplug"], check=False)

    def bind_touch(self, out):
        run(["swaymsg", "input", f"{TOUCH_NAME}", "map_to_output", out], check=False)


class Existing:
    """Capture a monitor that already exists; nothing is created or removed."""

    name = "existing"

    def __init__(self, output):
        self.output = output
        self.rect = None
        # On X11, look up monitor rect from xrandr if available
        if not os.environ.get("WAYLAND_DISPLAY") and shutil.which("xrandr"):
            try:
                raw = run(["xrandr", "-q"], check=False)
                for line in raw.splitlines():
                    if line.startswith(self.output) and "connected" in line:
                        for part in line.split():
                            if "+" in part and "x" in part:
                                dims, xs, ys = part.split("+", 2)
                                w, h = dims.split("x")
                                self.rect = (int(xs), int(ys), int(w), int(h))
                                break
            except Exception:
                pass

    def create(self, w, h, fps, scale, position):
        return self.output

    def remove(self, out):
        pass

    def bind_touch(self, out):
        if shutil.which("xinput"):
            run(["xinput", "map-to-output", TOUCH_NAME, out], check=False)

    def reply_size(self, w, h):
        if self.rect:
            return self.rect[2], self.rect[3]
        return 0, 0  # size unknown; the phone falls back to its own

    def capture_cmd(self, args, node):
        if args.capture_cmd:
            return shlex.split(args.capture_cmd.format(
                output=node, fps=args.fps, bits=args.bitrate_mbps * 1_000_000))
        # If on X11 with known geometry, use ximagesrc
        if self.rect:
            x, y, w, h = self.rect
            endx, endy = x + w - 1, y + h - 1
            encoder = args.gst_encoder or gst_default_encoder(args)
            return shlex.split(
                f"gst-launch-1.0 -q ximagesrc startx={x} starty={y} endx={endx} endy={endy} "
                f"use-damage=false do-timestamp=true "
                f"! videoconvert ! video/x-raw,format=I420 ! {encoder} "
                "! h264parse config-interval=-1 "
                "! video/x-h264,stream-format=byte-stream,alignment=au "
                "! fdsink fd=1 sync=false")
        # Otherwise fallback to Wayland wf-recorder
        return build_capture_cmd(args, node)


class X11:
    """Virtual monitor + capture for X11 sessions via xrandr and GStreamer ximagesrc.

    Uses xrandr to attach a virtual mode (generated with cvt) to an unused display output
    (e.g. VIRTUAL1, None-1, disconnected HDMI/DP), and captures the virtual desktop area
    using GStreamer ximagesrc.
    """

    name = "x11"

    def __init__(self):
        if not shutil.which("xrandr"):
            raise RuntimeError("xrandr not found; install x11-xserver-utils or xorg-xrandr")
        self.port = None
        self.mode = None
        self.rect = None  # (x, y, w, h)

    def _get_outputs(self):
        raw = run(["xrandr", "-q"])
        connected = []
        disconnected = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                port, status = parts[0], parts[1]
                if status == "connected":
                    geom = None
                    for p in parts[2:]:
                        if "+" in p and "x" in p:
                            geom = p
                            break
                    connected.append((port, geom))
                elif status == "disconnected":
                    disconnected.append(port)
        return connected, disconnected

    def create(self, w, h, fps, scale, position):
        connected, disconnected = self._get_outputs()
        if not disconnected:
            raise RuntimeError(
                "No disconnected display ports (like VIRTUAL1, HDMI-2) found in xrandr.\n"
                "To use a virtual monitor on X11, ensure a virtual/disconnected port is available,\n"
                "or pass --output <NAME> to capture an existing monitor."
            )
        # Prefer VIRTUAL or NONE ports first, otherwise take first disconnected port
        candidates = sorted(disconnected, key=lambda p: (not ("VIRTUAL" in p.upper() or "NONE" in p.upper()), p))
        self.port = candidates[0]

        mode_name = f"ss_{w}x{h}_{fps}"
        self.mode = mode_name

        cvt_bin = shutil.which("cvt")
        if cvt_bin:
            cvt_out = run(["cvt", str(w), str(h), str(fps)], check=False)
            modeline = ""
            for line in cvt_out.splitlines():
                if "Modeline" in line:
                    modeline = line.split("Modeline", 1)[1].strip()
                    break
            if modeline:
                parts = shlex.split(modeline)
                tokens = [f'"{mode_name}"'] + parts[1:]
                run(["xrandr", "--newmode"] + tokens, check=False)
        else:
            log("warning: 'cvt' utility not found; mode creation may require cvt from x11-xserver-utils")

        run(["xrandr", "--addmode", self.port, mode_name], check=False)

        # Place output
        primary = connected[0][0] if connected else None
        pos_arg = ["--right-of", primary] if primary else ["--auto"]
        if position == "auto-left" and primary:
            pos_arg = ["--left-of", primary]

        run(["xrandr", "--output", self.port, "--mode", mode_name] + pos_arg)

        # Query updated geometry
        new_connected, _ = self._get_outputs()
        geom = None
        for p, g in new_connected:
            if p == self.port:
                geom = g
                break

        x, y = 0, 0
        if geom and "+" in geom:
            try:
                _, xs, ys = geom.split("+", 2)
                x, y = int(xs), int(ys)
            except ValueError:
                pass

        self.rect = (x, y, w, h)
        log(f"x11 output {self.port} created at +{x}+{y} ({w}x{h})")
        return self.port

    def remove(self, out):
        if self.port:
            run(["xrandr", "--output", self.port, "--off"], check=False)
            if self.mode:
                run(["xrandr", "--delmode", self.port, self.mode], check=False)
                run(["xrandr", "--rmmode", self.mode], check=False)
            self.port = None
            self.mode = None
            self.rect = None

    def bind_touch(self, out):
        if shutil.which("xinput"):
            run(["xinput", "map-to-output", TOUCH_NAME, out], check=False)
            log(f"touch -> {out}: mapped via xinput")
        else:
            log("touch: install xinput to automatically map touch device to the display")

    def reply_size(self, w, h):
        if self.rect:
            return self.rect[2], self.rect[3]
        return w, h

    def capture_cmd(self, args, node):
        if args.capture_cmd:
            return shlex.split(args.capture_cmd.format(
                output=node, fps=args.fps, bits=args.bitrate_mbps * 1_000_000))
        x, y, w, h = self.rect if self.rect else (0, 0, 1920, 1080)
        endx, endy = x + w - 1, y + h - 1
        encoder = args.gst_encoder or gst_default_encoder(args)
        return shlex.split(
            f"gst-launch-1.0 -q ximagesrc startx={x} starty={y} endx={endx} endy={endy} "
            f"use-damage=false do-timestamp=true "
            f"! videoconvert ! video/x-raw,format=I420 ! {encoder} "
            "! h264parse config-interval=-1 "
            "! video/x-h264,stream-format=byte-stream,alignment=au "
            "! fdsink fd=1 sync=false")


class Portal:
    """Virtual monitor + capture through xdg-desktop-portal ScreenCast (KDE Plasma, GNOME).

    The portal creates a virtual monitor and exposes it as a PipeWire stream, which
    gst-launch reads and encodes. The monitor lives as long as the portal session,
    so remove() just closes the session. The desktop chooses the monitor size
    (KDE before Plasma 6.8 always uses 1920x1080); the phone letterboxes it.
    The first connection may show a dialog on the PC; the choice is remembered.
    """

    name = "portal"
    DEST = "org.freedesktop.portal.Desktop"
    PATH = "/org/freedesktop/portal/desktop"
    VIRTUAL = 4

    def __init__(self):
        import jeepney  # only this back-end needs it (Fedora: python3-jeepney)
        from jeepney.io.blocking import Proxy, open_dbus_connection

        self.j = jeepney
        self.Proxy = Proxy
        self.conn = open_dbus_connection(bus="SESSION", enable_fds=True)
        self.sender = self.conn.unique_name[1:].replace(".", "_")
        self.addr = jeepney.DBusAddress(self.PATH, bus_name=self.DEST,
                                        interface="org.freedesktop.portal.ScreenCast")
        self.token_file = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
            "usb-second-screen", "restore_token")
        self.counter = 0
        self.session = None
        self.fd = None
        self.size = None

    # -- D-Bus helpers ---------------------------------------------------------
    def _request(self, method, signature, make_body, timeout):
        """Call a portal method and wait for its asynchronous Response signal."""
        j = self.j
        self.counter += 1
        token = f"usb_second_screen_{os.getpid()}_{self.counter}"
        path = f"/org/freedesktop/portal/desktop/request/{self.sender}/{token}"
        rule = j.MatchRule(type="signal", interface="org.freedesktop.portal.Request",
                           member="Response", path=path)
        self.Proxy(j.message_bus, self.conn).AddMatch(rule)  # subscribe before calling
        with self.conn.filter(rule) as queue:
            self.conn.send_and_get_reply(
                j.new_method_call(self.addr, method, signature, make_body(token)), timeout=30)
            try:
                msg = self.conn.recv_until_filtered(queue, timeout=timeout)
            except TimeoutError:
                raise RuntimeError(f"portal {method}: no answer (is a dialog waiting on the PC screen?)")
        code, results = msg.body
        if code != 0:
            raise RuntimeError(f"portal {method} was refused or cancelled (code {code})")
        return results

    def _read_token(self):
        try:
            with open(self.token_file) as f:
                return f.read().strip()
        except OSError:
            return ""

    def _save_token(self, token):
        try:
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, "w") as f:
                f.write(token)
        except OSError:
            pass

    # -- back-end interface ------------------------------------------------------
    def create(self, w, h, fps, scale, position):
        try:
            return self._create()
        except Exception:
            self.remove(None)
            raise

    def _create(self):
        j = self.j
        try:
            reply = self.conn.send_and_get_reply(
                j.Properties(self.addr).get("AvailableSourceTypes"), timeout=10)
            if not reply.body[0][1] & self.VIRTUAL:
                raise RuntimeError("this desktop's screencast portal cannot create virtual monitors")
        except TimeoutError:
            raise RuntimeError("the screencast portal did not answer; is xdg-desktop-portal running?")

        res = self._request("CreateSession", "a{sv}", lambda t: (
            {"handle_token": ("s", t), "session_handle_token": ("s", t + "_s")},), 30)
        self.session = res["session_handle"][1]

        opts = {"types": ("u", self.VIRTUAL), "multiple": ("b", False),
                "cursor_mode": ("u", 2), "persist_mode": ("u", 2)}
        token = self._read_token()
        if token:
            opts["restore_token"] = ("s", token)
        self._request("SelectSources", "oa{sv}", lambda t: (
            self.session, dict(opts, handle_token=("s", t))), 30)

        res = self._request("Start", "osa{sv}", lambda t: (
            self.session, "", {"handle_token": ("s", t)}), 180)
        node, props = res["streams"][1][0]
        if "size" in props:
            self.size = tuple(props["size"][1])
        if "restore_token" in res:
            self._save_token(res["restore_token"][1])

        reply = self.conn.send_and_get_reply(
            j.new_method_call(self.addr, "OpenPipeWireRemote", "oa{sv}", (self.session, {})), timeout=10)
        self.fd = reply.body[0].to_raw_fd()
        return str(node)

    def remove(self, out):
        if self.session:
            session, self.session = self.session, None
            try:
                addr = self.j.DBusAddress(session, bus_name=self.DEST,
                                          interface="org.freedesktop.portal.Session")
                self.conn.send_and_get_reply(self.j.new_method_call(addr, "Close"), timeout=5)
            except Exception:
                pass
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)
        self.size = None

    def bind_touch(self, out):
        log("touch: map the 'usb-second-screen-touch' device to the new monitor in "
            "System Settings > Input Devices > Touchscreen")

    def reply_size(self, w, h):
        return self.size or (0, 0)

    def capture_cmd(self, args, node):
        if args.capture_cmd:
            return shlex.split(args.capture_cmd.format(
                output=node, fd=self.fd, fps=args.fps, bits=args.bitrate_mbps * 1_000_000))
        encoder = args.gst_encoder or gst_default_encoder(args)
        return shlex.split(
            f"gst-launch-1.0 -q pipewiresrc fd={self.fd} path={node} do-timestamp=true "
            f"! videoconvert ! video/x-raw,format=I420 ! {encoder} "
            "! h264parse config-interval=-1 "
            "! video/x-h264,stream-format=byte-stream,alignment=au "
            "! fdsink fd=1 sync=false")


def gst_default_encoder(args):
    def has(element):
        try:
            return subprocess.run(["gst-inspect-1.0", element], capture_output=True).returncode == 0
        except OSError:
            raise RuntimeError("gst-inspect-1.0 not found; install gstreamer1 (see README)")

    kbps, gop = args.bitrate_mbps * 1000, args.fps * 2
    if has("x264enc"):
        return (f"x264enc tune=zerolatency speed-preset=ultrafast bitrate={kbps} "
                f"key-int-max={gop} bframes=0 byte-stream=true")
    if has("openh264enc"):
        return f"openh264enc bitrate={kbps * 1000} gop-size={gop} complexity=low"
    raise RuntimeError("no GStreamer H.264 encoder: install gstreamer1-plugin-openh264, or "
                       "gstreamer1-plugins-ugly from RPM Fusion (x264)")


def pick_compositor(args):
    if args.output:
        return Existing(args.output)
    choice = args.compositor
    if choice == "auto":
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            choice = "hyprland"
        elif os.environ.get("SWAYSOCK"):
            choice = "sway"
        elif session_type == "x11" or (not os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY")):
            choice = "x11"
        elif "KDE" in desktop or "GNOME" in desktop:
            choice = "portal"
        else:
            sys.exit("Could not detect the desktop. Use --compositor portal|hyprland|sway|x11, "
                     "or --output NAME to capture an existing monitor.")
    if choice == "portal":
        try:
            return Portal()
        except Exception as exc:
            sys.exit(f"Cannot use the portal back-end: {exc!r}\n"
                     "Install python3-jeepney and make sure a desktop session bus is running.")
    if choice == "x11":
        return X11()
    return {"hyprland": Hyprland, "sway": Sway}[choice]()


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------
def build_capture_cmd(args, output):
    bits = args.bitrate_mbps * 1_000_000
    if args.capture_cmd:
        return shlex.split(args.capture_cmd.format(output=output, fps=args.fps, bits=bits))
    cmd = ["wf-recorder", "-y", "-o", output, "-c", args.codec, "-m", "h264",
           "-r", str(args.fps), "-f", "pipe:1"]
    rate = ["-p", f"b={bits}", "-p", f"maxrate={bits}", "-p", f"bufsize={bits // args.fps * 2}",
            "-p", f"g={args.fps * 2}"]
    if args.codec == "libx264":
        cmd += ["-p", "preset=ultrafast", "-p", "tune=zerolatency"] + rate
    elif "vaapi" in args.codec:
        cmd += ["-d", args.vaapi_device] + rate
    else:
        cmd += rate
    return cmd


def clamp_size(w, h, max_short):
    short = min(w, h)
    if short > max_short:
        w, h = w * max_short / short, h * max_short / short
    return max(int(w) // 2 * 2, 160), max(int(h) // 2 * 2, 160)


# --------------------------------------------------------------------------
# Touch injection (uinput)
# --------------------------------------------------------------------------
class TouchInjector:
    def __init__(self):
        from evdev import AbsInfo, UInput, ecodes as e

        self.e = e
        rng = AbsInfo(0, 0, 65535, 0, 0, 0)
        caps = {
            e.EV_KEY: [e.BTN_TOUCH],
            e.EV_ABS: [
                (e.ABS_X, rng), (e.ABS_Y, rng),
                (e.ABS_MT_SLOT, AbsInfo(0, 0, MAX_SLOTS - 1, 0, 0, 0)),
                (e.ABS_MT_TRACKING_ID, AbsInfo(0, 0, 65535, 0, 0, 0)),
                (e.ABS_MT_POSITION_X, rng), (e.ABS_MT_POSITION_Y, rng),
            ],
        }
        self.ui = UInput(caps, name=TOUCH_NAME, input_props=[e.INPUT_PROP_DIRECT])
        self.ids = {}
        self.next_id = 1
        self.lock = threading.Lock()

    def handle(self, action, slot, x, y):
        e, ui = self.e, self.ui
        slot %= MAX_SLOTS
        with self.lock:
            ui.write(e.EV_ABS, e.ABS_MT_SLOT, slot)
            if action == TOUCH_UP:
                if slot in self.ids:
                    ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, -1)
                    del self.ids[slot]
                    if not self.ids:
                        ui.write(e.EV_KEY, e.BTN_TOUCH, 0)
            else:
                if slot not in self.ids:
                    self.ids[slot] = self.next_id
                    self.next_id = self.next_id % 65000 + 1
                    ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, self.ids[slot])
                    if len(self.ids) == 1:
                        ui.write(e.EV_KEY, e.BTN_TOUCH, 1)
                ui.write(e.EV_ABS, e.ABS_MT_POSITION_X, x)
                ui.write(e.EV_ABS, e.ABS_MT_POSITION_Y, y)
                ui.write(e.EV_ABS, e.ABS_X, x)
                ui.write(e.EV_ABS, e.ABS_Y, y)
            ui.syn()

    def release_all(self):
        for slot in list(self.ids):
            self.handle(TOUCH_UP, slot, 0, 0)


def client_reader(conn, touch, stop):
    try:
        while not stop.is_set():
            mtype, action, slot, _, x, y = MSG.unpack(recv_exact(conn, MSG.size))
            if mtype == MSG_TOUCH and touch:
                touch.handle(action, slot, x, y)
    except (OSError, EOFError):
        pass
    finally:
        stop.set()
        if touch:
            try:
                touch.release_all()
            except OSError:
                pass


# --------------------------------------------------------------------------
# One phone session
# --------------------------------------------------------------------------
def handle_client(conn, args, comp, touch):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn.settimeout(10)
    mtype, _, _, _, pw, ph = MSG.unpack(recv_exact(conn, MSG.size))
    conn.settimeout(None)
    if mtype != MSG_HELLO or not (100 <= pw <= 10000 and 100 <= ph <= 10000):
        log("bad hello, dropping client")
        return
    w, h = clamp_size(pw, ph, args.max_short_side)
    log(f"phone is {pw}x{ph}")

    out = comp.create(w, h, args.fps, args.scale, args.position)
    proc = None
    stop = threading.Event()
    try:
        if touch:
            comp.bind_touch(out)
        if hasattr(comp, "capture_cmd"):
            cmd = comp.capture_cmd(args, out)
        else:
            cmd = build_capture_cmd(args, out)
        extra = {"pass_fds": (comp.fd,)} if getattr(comp, "fd", None) is not None else {}
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=0, **extra)
        reply_w, reply_h = comp.reply_size(w, h) if hasattr(comp, "reply_size") else (w, h)
        log(f"virtual monitor {out}, stream {reply_w}x{reply_h or '?'}")
        conn.sendall(struct.pack(">HH", reply_w, reply_h))
        threading.Thread(target=client_reader, args=(conn, touch, stop), daemon=True).start()

        parser, fd, sent = AUParser(), proc.stdout.fileno(), 0
        while not stop.is_set():
            ready, _, _ = select.select([fd], [], [], QUIET_GAP if parser.pending else 0.25)
            aus, eof = [], False
            if ready:
                chunk = os.read(fd, 1 << 18)
                if chunk:
                    parser.feed(chunk, aus)
                else:
                    parser.flush(aus)
                    eof = True
            else:
                parser.flush(aus)
                eof = proc.poll() is not None
            for au in aus:
                conn.sendall(struct.pack(">I", len(au)) + au)
                sent += 1
            if eof:
                break
        if sent == 0 and not stop.is_set():
            log("capture produced no video. Run the capture command by hand to see why. Portal back-end: "
                "check `gst-inspect-1.0 pipewiresrc x264enc openh264enc`. wf-recorder back-end: on Fedora "
                "x264 needs libavcodec-freeworld (RPM Fusion), or use --codec h264_vaapi")
    except (OSError, EOFError) as exc:
        log("session ended:", exc)
    finally:
        stop.set()
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(2)
            except subprocess.TimeoutExpired:
                proc.kill()
        comp.remove(out)
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()
        log("session closed, virtual monitor removed")


# --------------------------------------------------------------------------
# adb: keep `adb reverse` alive and open the app when the phone is plugged in
# --------------------------------------------------------------------------
def adb_keeper(args, stop):
    adb = shutil.which("adb")
    if not adb:
        log("adb not found; install android-tools or pass --no-adb and run adb reverse yourself")
        return
    base = [adb] + (["-s", args.adb_serial] if args.adb_serial else [])
    spec = f"tcp:{args.port}"
    last = None
    while not stop.is_set():
        up = False
        try:
            r = subprocess.run(base + ["reverse", "--list"], capture_output=True, text=True, timeout=8)
            up = r.returncode == 0 and f"{spec} {spec}" in r.stdout
            if not up:
                r = subprocess.run(base + ["reverse", spec, spec], capture_output=True, text=True, timeout=8)
                up = r.returncode == 0
                if up and args.launch_app:
                    subprocess.run(base + ["shell", "am", "start", "-n", APP_ACTIVITY],
                                   capture_output=True, timeout=8)
        except (subprocess.TimeoutExpired, OSError):
            pass
        if up != last:
            log("USB link up, phone can connect" if up else "waiting for a phone (USB debugging on?)")
            last = up
        stop.wait(2.0)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Use an Android phone as a second monitor over USB.")
    ap.add_argument("--version", action="version", version=f"usb-second-screen {VERSION}")
    ap.add_argument("--port", type=int, default=7878)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--bitrate-mbps", type=int, default=20)
    ap.add_argument("--max-short-side", type=int, default=1080,
                    help="cap the virtual monitor's shorter side (default 1080)")
    ap.add_argument("--scale", type=float, default=1.0, help="compositor scale of the virtual monitor")
    ap.add_argument("--position", default="auto-right", help="Hyprland monitor position")
    ap.add_argument("--codec", default="libx264", help="libx264 (default) or h264_vaapi")
    ap.add_argument("--vaapi-device", default="/dev/dri/renderD128")
    ap.add_argument("--compositor", choices=["auto", "portal", "hyprland", "sway", "x11"], default="auto",
                    help="auto picks portal on KDE/GNOME (Wayland), hyprland, sway, or x11")
    ap.add_argument("--gst-encoder", help="GStreamer encoder element(s) for the portal back-end, e.g. "
                    "'x264enc tune=zerolatency speed-preset=ultrafast bitrate=20000 byte-stream=true'")
    ap.add_argument("--output", help="capture this existing monitor instead of creating one")
    ap.add_argument("--capture-cmd", help="custom capture command printing raw H.264 to stdout; "
                    "may use {output} {fps} {bits}")
    ap.add_argument("--touch", action="store_true", help="inject phone touches via uinput")
    ap.add_argument("--no-adb", action="store_true", help="do not manage adb reverse")
    ap.add_argument("--no-launch", dest="launch_app", action="store_false",
                    help="do not open the app on the phone automatically")
    ap.add_argument("--adb-serial", help="adb device serial when several are connected")
    ap.add_argument("--log-file", metavar="PATH",
                    help="log to this file instead of stderr")
    args = ap.parse_args()

    # -- Configure logging -------------------------------------------------
    handler: logging.Handler
    if args.log_file:
        handler = logging.FileHandler(args.log_file)
    else:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[second-screen] %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)

    comp = pick_compositor(args)
    touch = None
    if args.touch:
        try:
            touch = TouchInjector()
            log(f"touch device '{TOUCH_NAME}' ready")
        except Exception as exc:  # missing python-evdev or no /dev/uinput access
            log(f"touch disabled: {exc}")

    # -- Signal handling ---------------------------------------------------
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    def sighup_handler(*_):
        log("SIGHUP received — reloading configuration is not yet implemented; ignoring")

    signal.signal(signal.SIGHUP, sighup_handler)

    stop = threading.Event()
    if not args.no_adb:
        threading.Thread(target=adb_keeper, args=(args, stop), daemon=True).start()

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(1)
    log(f"compositor: {comp.name}, listening on 127.0.0.1:{args.port}")

    # -- Accept loop with single-client enforcement ------------------------
    client_lock = threading.Lock()
    active_client = [False]  # mutable flag: True while a session is running

    try:
        while True:
            conn, addr = srv.accept()
            with client_lock:
                if active_client[0]:
                    log(f"rejected connection from {addr}: another client is already connected")
                    try:
                        conn.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    conn.close()
                    continue
                active_client[0] = True

            try:
                handle_client(conn, args, comp, touch)
            except Exception as exc:
                log("session error:", repr(exc))
            finally:
                conn.close()
                with client_lock:
                    active_client[0] = False
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        srv.close()


if __name__ == "__main__":
    main()
