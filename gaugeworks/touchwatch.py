"""Touch watchdog: restart GaugeWorks when the HDMI screen's touch goes dead.

Qt's evdev touch handler opens one /dev/input/eventN at startup and never
reopens it. If the USB touch drops and re-enumerates (vibration, a power dip),
the gauges keep running but touch is dead. This watches for that two ways:

- the event node was removed or re-created (new inode), or
- raw taps keep arriving on the device but no press reaches the Qt window.

Either one returns a reason from check(); the app logs it and exits, and
systemd restarts it with a fresh device. Local input only; nothing here
touches the vehicle.
"""

from __future__ import annotations

import os
from pathlib import Path


def locate(name: str, sys_input: str = "/sys/class/input") -> str | None:
    """Current /dev/input/eventN of the input device with this exact name, or None."""
    found = []
    for ev in Path(sys_input).glob("event*"):
        try:
            if (ev / "device" / "name").read_text().strip() == name:
                found.append(int(ev.name[5:]))
        except (OSError, ValueError):
            continue
    return f"/dev/input/event{min(found)}" if found else None


class TouchWatchdog:
    """Decides when GaugeWorks must restart to get its touch back.

    With `name` (the touch device's name), the device is followed by name: if it
    drops off USB the gauges keep running, and once it re-appears (usually as a
    new eventN) check() asks for a restart so Qt opens the new node.
    """

    def __init__(self, path: str, name: str = "", stuck_taps: int = 3, grace_s: float = 3.0,
                 stat=os.stat, locate_fn=locate, clock=None):
        import time

        self.path = path
        self.name = name
        self.stuck_taps = stuck_taps
        self.grace_s = grace_s    # a busy GUI thread may handle taps late; only count older ones
        self._stat = stat
        self._locate = locate_fn
        self._clock = clock or time.monotonic
        self._id = self._ident()
        self.raw = 0              # taps seen on the device (released)
        self.qt = 0               # presses seen by the Qt window
        self._pending: list[float] = []   # raw tap times since the last Qt press
        self._skip = 0            # releases still owed by presses Qt already saw
        self.events: dict[str, int] = {}  # Qt touch/mouse event counts, for the log

    def _ident(self):
        try:
            st = self._stat(self.path)
        except OSError:
            return None
        return (st.st_ino, st.st_rdev)

    def on_raw_tap(self, ts: float | None = None) -> None:
        self.raw += 1
        if self._skip:
            self._skip -= 1      # the release of a press Qt already saw
        else:
            self._pending.append(self._clock() if ts is None else ts)

    def on_qt_press(self) -> None:
        self.qt += 1
        if self._pending:
            self._pending.pop()  # this press matches a tap already released
        else:
            self._skip += 1      # its release comes later
        self._pending.clear()    # Qt is getting touches: anything older was handled

    def on_qt_event(self, kind: str) -> None:
        self.events[kind] = self.events.get(kind, 0) + 1

    def check(self) -> str:
        if self.name:
            now = self._locate(self.name)
            if now is None:
                return ""  # touch is off the bus: keep the gauges up and wait for it
            if now != self.path:
                return f"touch moved from {self.path} to {now}"
        cur = self._ident()
        if cur != self._id:
            if cur is None:
                return "" if self.name else f"touch device {self.path} is gone"
            return f"touch device {self.path} was re-created"
        now = self._clock()
        missed = sum(1 for t in self._pending if now - t >= self.grace_s)
        if missed >= self.stuck_taps:
            seen = " ".join(f"{k}={v}" for k, v in sorted(self.events.items())) or "none"
            return (f"{missed} taps on {self.path} never reached GaugeWorks "
                    f"(Qt events so far: {seen})")
        return ""


def install(app, view, path: str | None, name: str = "", interval_ms: int = 2000):
    """Wire the watchdog into a running Qt app. Returns it, or None if there's no touch path."""
    if not path:
        return None
    import sys

    from PySide6.QtCore import QEvent, QObject, QTimer

    from core.touch import TouchReader

    wd = TouchWatchdog(path, name)
    reader = None
    if os.path.exists(path):
        try:
            reader = TouchReader(path)
        except OSError as e:  # not an evdev node, ioctl failed
            print(f"GaugeWorks: touch watchdog: no raw reader ({e})", file=sys.stderr)
        if reader is not None and not reader.ok:
            print(f"GaugeWorks: touch watchdog: no raw reader ({reader.error})", file=sys.stderr)
            reader = None
    elif not name:
        return None  # nothing to watch and nothing to follow

    presses = (QEvent.TouchBegin, QEvent.MouseButtonPress)
    kinds = {QEvent.TouchBegin: "begin", QEvent.TouchUpdate: "update", QEvent.TouchEnd: "end",
             QEvent.TouchCancel: "cancel", QEvent.MouseButtonPress: "mouse"}

    class _Filter(QObject):
        def eventFilter(self, obj, ev):  # noqa: N802 (Qt name)
            t = ev.type()
            if t in kinds:
                wd.on_qt_event(kinds[t])
            if t in presses:
                wd.on_qt_press()
            return False

    filt = _Filter(view)
    view.installEventFilter(filt)

    def tick():
        while reader is not None and not reader.taps.empty():
            reader.taps.get_nowait()
            wd.on_raw_tap()
        reason = wd.check()
        if reason:
            print(f"GaugeWorks: touch watchdog: {reason}; restarting", file=sys.stderr, flush=True)
            sys.stdout.flush()
            os._exit(3)  # skip Qt teardown (it can crash); systemd restarts us

    timer = QTimer(view)
    timer.timeout.connect(tick)
    timer.start(interval_ms)
    wd._keep = (reader, filt, timer)  # keep Qt objects alive
    print(f"GaugeWorks: touch watchdog on {path}" + (f" ({name})" if name else ""),
          file=sys.stderr, flush=True)
    return wd
