"""Touchscreen taps from Linux evdev, stdlib only (no python-evdev dependency).

Reads /dev/input/eventN for the ADS7846 (resistive) or any touchscreen,
reports taps as raw (x, y) plus axis ranges so callers can map to screen
fractions. Read-only local input; nothing here touches the vehicle.
"""

from __future__ import annotations

import fcntl
import os
import queue
import struct
import threading
from dataclasses import dataclass
from pathlib import Path

EV_KEY, EV_ABS = 0x01, 0x03
ABS_X, ABS_Y = 0x00, 0x01
BTN_TOUCH = 0x14A
_EVENT = struct.Struct("llHHi")      # struct input_event (64-bit)
_ABSINFO = struct.Struct("6i")        # struct input_absinfo
NAMES = ("ADS7846", "touch", "Touch")


def _eviocgabs(axis: int) -> int:
    return (2 << 30) | (_ABSINFO.size << 16) | (ord("E") << 8) | (0x40 + axis)


def find_device() -> str | None:
    for ev in sorted(Path("/sys/class/input").glob("event*")):
        try:
            name = (ev / "device" / "name").read_text().strip()
        except OSError:
            continue
        if any(n in name for n in NAMES):
            return f"/dev/input/{ev.name}"
    return None


@dataclass(frozen=True)
class Tap:
    x: int
    y: int
    ranges: dict  # {"x": (min, max), "y": (min, max)}

    def frac(self, axis: str, invert: bool = False) -> float:
        lo, hi = self.ranges[axis]
        v = (getattr(self, axis) - lo) / max(1, hi - lo)
        v = min(1.0, max(0.0, v))
        return 1.0 - v if invert else v


class TouchReader:
    """Background thread; taps arrive on `.taps` (queue.Queue[Tap])."""

    def __init__(self, device: str | None = None):
        self.device = device or find_device()
        self.taps: "queue.Queue[Tap]" = queue.Queue()
        self.error = ""
        self._stop = threading.Event()
        self._fd = None
        if not self.device:
            self.error = "no touchscreen found"
            return
        try:
            self._fd = os.open(self.device, os.O_RDONLY)
        except OSError as e:
            self.error = f"{self.device}: {e.strerror} (is user in 'input' group?)"
            return
        self.ranges = {"x": self._range(ABS_X), "y": self._range(ABS_Y)}
        threading.Thread(target=self._run, daemon=True).start()

    @property
    def ok(self) -> bool:
        return self._fd is not None

    def _range(self, axis: int) -> tuple[int, int]:
        buf = bytearray(_ABSINFO.size)
        fcntl.ioctl(self._fd, _eviocgabs(axis), buf)
        _, lo, hi, *_ = _ABSINFO.unpack(buf)
        return lo, hi

    def _run(self):
        x = y = 0
        while not self._stop.is_set():
            try:
                data = os.read(self._fd, _EVENT.size * 32)
            except OSError:
                return
            for off in range(0, len(data) - _EVENT.size + 1, _EVENT.size):
                _, _, etype, code, value = _EVENT.unpack_from(data, off)
                if etype == EV_ABS and code == ABS_X:
                    x = value
                elif etype == EV_ABS and code == ABS_Y:
                    y = value
                elif etype == EV_KEY and code == BTN_TOUCH and value == 0:  # release
                    self.taps.put(Tap(x, y, self.ranges))

    def close(self):
        self._stop.set()
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def horizontal(tap: Tap, cal: dict) -> float | None:
    """0.0 = left edge, 1.0 = right edge, per calibration; None if uncalibrated."""
    if cal.get("axis") not in ("x", "y"):
        return None
    return tap.frac(cal["axis"], bool(cal.get("invert")))


def calibrate(left: Tap, right: Tap) -> dict:
    """Pick the axis that changed most between a left-edge and right-edge tap."""
    dx = right.frac("x") - left.frac("x")
    dy = right.frac("y") - left.frac("y")
    axis = "x" if abs(dx) >= abs(dy) else "y"
    d = dx if axis == "x" else dy
    return {"axis": axis, "invert": d < 0}
