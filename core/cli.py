"""jpcan command line: probe, scan22, live, profiles."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass
from typing import TextIO

from . import __version__
from .bus import Bus
from .elm import AdapterInfo, Elm, ElmError
from .guard import RequestGuard
from .poller import Poller
from .profile import Profile, list_profiles, load_profile, select_profile
from .transport import GuardedPort, SerialTransport
from .units import display

DEFAULT_PORT = "COM3" if sys.platform == "win32" else "/dev/ttyUSB0"


@dataclass
class Session:
    elm: Elm
    port: GuardedPort
    guard: RequestGuard
    info: AdapterInfo
    vin: str | None
    profile: Profile
    supported: set[int]
    sim: bool
    trace: TextIO | None = None

    def close(self):
        self.port.close()
        if self.trace:
            self.trace.close()


def connect(args, log=print) -> Session:
    guard = RequestGuard()
    trace = open(args.trace, "a", encoding="utf-8") if args.trace else None
    if args.sim:
        from .sim import SimTransport
        raw, log_src = SimTransport(), "simulator"
    else:
        raw, log_src = SerialTransport(args.port, args.baud), f"{args.port} @ {args.baud}"
    port = GuardedPort(raw, guard, min_gap=args.min_gap, trace=trace)
    elm = Elm(port)
    log(f"Connecting via {log_src} ...")
    info = elm.init()
    log(f"Adapter: {info.elm} | {info.stn} | {info.voltage} | {info.protocol}")
    vin = elm.vin()
    profile = load_profile(args.profile) if args.profile else select_profile(vin)
    guard.extra_headers |= profile.extra_headers
    supported = elm.supported_pids()
    return Session(elm, port, guard, info, vin, profile, supported, args.sim, trace)


def fmt(value, units, imperial=True) -> tuple[str, str]:
    if value is None:
        return "--", units
    v, u = display(value, units, imperial)
    if u in ("mi", "km") or abs(v) >= 1000:
        return f"{v:,.1f}" if u in ("mi", "km") else f"{v:,.0f}", u
    return (f"{v:.0f}" if abs(v) >= 100 or v == int(v) else f"{v:.1f}"), u


# ---- commands ------------------------------------------------------------
def cmd_profiles(args) -> int:
    for n in ["base_mode01", *list_profiles()]:
        p = load_profile(n)
        shift = f"shift@{p.shift['rpm']}" if p.shift.get("enabled") else "no shift"
        print(f"{n:28} {p.name}  ({len(p.pids)} PIDs, {shift})")
    return 0


def cmd_probe(args) -> int:
    s = connect(args)
    try:
        print(f"VIN: {s.vin or 'not reported'}")
        print(f"Profile: {s.profile.id} ({s.profile.name})")
        print("Mode 01 supported: " + " ".join(f"{p:02X}" for p in sorted(s.supported)))
        keys = s.profile.layouts.get("status") or list(s.profile.pids)
        print()
        _read_table(s, keys, imperial=not args.metric)
        print(f"\nGuard: {s.guard.sent} sent, {s.guard.blocked} blocked")
    finally:
        s.close()
    return 0


def _read_table(s: Session, keys, imperial):
    bus = Bus()
    poller = Poller(s.elm, s.profile, bus, keys=keys, supported=s.supported, max_fails=1)
    poller.cycle()
    latest = bus.latest()
    for k in keys:
        p = s.profile.pids[k]
        r = latest.get(k)
        if poller.is_skipped(p):
            val, u, note = "--", p.units, "not supported (bitmap)"
        elif r is None:
            val, u, note = "--", p.units, "not polled"
        else:
            val, u = fmt(r.value, r.units, imperial)
            note = r.error or ""
        flag = "" if p.verified else " ?"
        print(f"  {p.name + flag:34} {val:>12} {u:6} {note}")


def cmd_scan22(args) -> int:
    s = connect(args)
    try:
        print(f"Profile: {s.profile.id}   VIN: {s.vin}")
        print("Unverified PIDs (raw bytes for FORScan comparison):\n")
        seen = {}
        for p in s.profile.pids.values():
            if p.verified:
                continue
            key = (p.header, p.request)
            if key not in seen:
                try:
                    seen[key] = s.elm.read(p.service, p.pid, p.header)
                except ElmError as e:
                    seen[key] = e
            data = seen[key]
            if isinstance(data, Exception):
                print(f"  {p.header} {p.request:8} {p.name:32} FAIL  {data}")
                continue
            try:
                v, u = fmt(p.formula(data), p.units, not args.metric)
            except Exception as e:  # noqa: BLE001 - show any scaling issue
                v, u = f"err:{e}", ""
            print(f"  {p.header} {p.request:8} {p.name:32} OK    {data.hex(' ').upper():24} -> {v} {u}")
        print(f"\nGuard: {s.guard.sent} sent, {s.guard.blocked} blocked")
    finally:
        s.close()
    return 0


def cmd_live(args) -> int:
    import curses

    s = connect(args)
    keys = s.profile.layouts.get("status") or list(s.profile.pids)
    bus = Bus()
    poller = Poller(s.elm, s.profile, bus, keys=keys, supported=s.supported)
    stop = threading.Event()
    th = threading.Thread(target=poller.run, args=(stop,), daemon=True)
    th.start()
    try:
        curses.wrapper(_live_screen, s, poller, bus, keys, not args.metric)
    finally:
        stop.set()
        th.join(timeout=2)
        s.close()
    return 0


def _row_text(s: Session, poller: Poller, latest, k, imperial):
    """Return (label, value, units, status) for one PID."""
    p = s.profile.pids[k]
    r = latest.get(k)
    if poller.is_skipped(p):
        return p, "n/s", "", ""
    if r is None:
        return p, "...", "", ""
    if r.error:
        return p, "ERR", "", "err"
    val, u = fmt(r.value, r.units, imperial)
    return p, val, u, ("old" if time.time() - r.ts > 5 else "")


def _live_screen(scr, s: Session, poller: Poller, bus: Bus, keys, imperial):
    import curses

    from . import settings
    from .touch import TouchReader, horizontal

    curses.curs_set(0)
    scr.nodelay(True)
    scr.keypad(True)
    cal = settings.load()["touch"]
    touch = TouchReader()
    t0, c0 = time.monotonic(), 0
    rate = 0.0
    page = 0
    src = "SIM" if s.sim else "LIVE"
    while True:
        ch = scr.getch()
        if ch in (ord("q"), ord("Q"), 27):
            touch.close()
            return
        step = {curses.KEY_RIGHT: 1, ord("n"): 1, ord(" "): 1,
                curses.KEY_LEFT: -1, ord("b"): -1}.get(ch, 0)
        while touch.ok and not touch.taps.empty():
            f = horizontal(touch.taps.get_nowait(), cal)
            step += 1 if f is None or f >= 0.5 else -1  # uncalibrated: any tap = next
        page += step
        h, w = scr.getmaxyx()
        now = time.monotonic()
        if now - t0 >= 1.0:
            rate, t0, c0 = (poller.cycles - c0) / (now - t0), now, poller.cycles
        scr.erase()
        put = lambda y, x, txt, a=0: 0 <= y < h and scr.addnstr(y, x, txt, max(0, w - x - 1), a)
        latest = bus.latest()
        wide = w >= 56 and h >= len(keys) + 5
        if wide:
            put(0, 0, f"JpCAN {__version__}  {s.profile.name}", curses.A_BOLD)
            put(1, 0, f"VIN {s.vin or '?'}  {src}  {rate:4.1f} Hz")
            put(2, 0, "-" * (w - 1))
            for i, k in enumerate(keys):
                p, val, u, st = _row_text(s, poller, latest, k, imperial)
                flag = "" if p.verified else "?"
                put(3 + i, 0, f"{p.name[:24] + flag:25} {val:>10} {u:5} {st}")
            y = 4 + len(keys)
            put(y, 0, "-" * (w - 1))
            put(y + 1, 0, f"req {s.guard.sent}  blocked {s.guard.blocked}  err {poller.errors}   q=quit")
        else:
            rows = max(1, h - 1)
            pages = (len(keys) + rows - 1) // rows
            page %= pages
            alert = f" BLK{s.guard.blocked}" if s.guard.blocked else ""
            pg = f"< {page + 1}/{pages} >" if pages > 1 else ""
            left = f"{src} {rate:3.0f}Hz{alert}"
            put(0, 0, (left + pg.rjust(max(0, w - 1 - len(left)))).ljust(w - 1), curses.A_REVERSE)
            unit_w = 4
            val_w = max(4, w - 1 - 10 - 1 - unit_w)
            for i, k in enumerate(keys[page * rows:(page + 1) * rows]):
                p, val, u, st = _row_text(s, poller, latest, k, imperial)
                label = p.label + ("" if p.verified else "?")
                put(1 + i, 0, f"{label:<10}")
                put(1 + i, 10, f"{val:>{val_w}}", curses.A_BOLD)
                put(1 + i, 10 + val_w + 1, f"{u:<{unit_w}}"[:unit_w])
        scr.refresh()
        time.sleep(0.25)


def cmd_touch_cal(args) -> int:
    from . import settings
    from .touch import TouchReader, calibrate

    t = TouchReader()
    if not t.ok:
        print(f"error: {t.error}", file=sys.stderr)
        return 1
    print(f"Touchscreen: {t.device}  ranges {t.ranges}")
    taps = []
    for where in ("LEFT", "RIGHT"):
        print(f"Tap near the {where} edge of the screen (middle height)...")
        taps.append(t.taps.get())
        print(f"  got x={taps[-1].x} y={taps[-1].y}")
        time.sleep(0.3)
        while not t.taps.empty():  # drop bounce
            t.taps.get_nowait()
    t.close()
    cal = calibrate(*taps)
    data = settings.load()
    data["touch"] = cal
    print(f"Saved {cal} to {settings.save(data)}")
    return 0


# ---- entry point ---------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="jpcan", description="JpCAN reads it. GaugeWorks shows it.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def conn(p):
        p.add_argument("--sim", action="store_true", help="use the simulated adapter")
        p.add_argument("--port", default=DEFAULT_PORT, help=f"serial port (default {DEFAULT_PORT})")
        p.add_argument("--baud", type=int, default=115200)
        p.add_argument("--profile", help="force a profile (default: pick by VIN)")
        p.add_argument("--trace", help="append every request/reply to this JSONL file")
        p.add_argument("--min-gap", type=float, default=0.02, help="seconds between requests")
        p.add_argument("--metric", action="store_true", help="show metric units")
        return p

    sub.add_parser("profiles", help="list vehicle profiles").set_defaults(func=cmd_profiles)
    conn(sub.add_parser("probe", help="connect, identify, read status PIDs once")).set_defaults(func=cmd_probe)
    conn(sub.add_parser("scan22", help="try every unverified PID, show raw bytes")).set_defaults(func=cmd_scan22)
    conn(sub.add_parser("live", help="live text status screen")).set_defaults(func=cmd_live)
    sub.add_parser("touch-cal", help="calibrate left/right taps on the touchscreen").set_defaults(func=cmd_touch_cal)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (ElmError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
