"""jpcan command line: probe, scan22, live, profiles."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import threading
import time

from . import __version__
from .bus import Bus
from .elm import ElmError
from .poller import Poller
from .profile import list_profiles, load_profile
from .sysinfo import wifi_dbm, wifi_label
from .session import DEFAULT_PORT, Session, connect, why
from .units import display

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
            if p.verified or p.is_derived:
                continue
            hdr = s.profile.header_for(p)
            key = (hdr, p.request)
            if key not in seen:
                try:
                    seen[key] = s.elm.read(p.service, p.pid, hdr)
                except ElmError as e:
                    seen[key] = e
            data = seen[key]
            if isinstance(data, Exception):
                print(f"  {hdr} {p.request:8} {p.name:32} FAIL  {data}")
                continue
            try:
                v, u = fmt(p.formula(data), p.units, not args.metric)
            except Exception as e:  # noqa: BLE001 - show any scaling issue
                v, u = f"err:{e}", ""
            print(f"  {hdr} {p.request:8} {p.name:32} OK    {data.hex(' ').upper():24} -> {v} {u}")
        print(f"\nGuard: {s.guard.sent} sent, {s.guard.blocked} blocked")
    finally:
        s.close()
    return 0


def cmd_live(args) -> int:
    import curses

    return curses.wrapper(_live_bus if args.bus else _live_main, args)


def cmd_run(args) -> int:
    import signal

    from .mqtt import LocalSink, MqttPublisher
    from .service import run_core
    from .trip import TripComputer

    from . import settings as settings_mod

    bus = Bus()
    trip = TripComputer(bus)
    st = settings_mod.load()
    trip.set_cal(st.get("econ_cal_pct", 0.0))

    def econ_cal(pct: float) -> None:
        cur = settings_mod.load()
        cur["econ_cal_pct"] = trip.set_cal(pct)
        settings_mod.save(cur)

    if args.no_mqtt:
        sink = LocalSink(bus)
    else:
        sink = MqttPublisher(bus, args.mqtt_host, args.mqtt_port, on_trip_reset=trip.reset,
                             on_econ_cal=econ_cal)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    last = [""]

    def show(st):  # mirror status to stdout/journal when it changes
        line = f"{st.get('state')}: {' '.join(st.get('lines', []))}"
        if st.get("state") == "running":
            line = f"running: {st.get('hz')} Hz, sent {st.get('sent')}, blocked {st.get('blocked')}"
        if line.split(":")[0] != last[0].split(":")[0] or st.get("state") != "running":
            if line != last[0]:
                print(line, flush=True)
        last[0] = line

    orig = sink.publish_status
    sink.publish_status = lambda st: (orig(st), show(st))
    try:
        run_core(args, sink, bus, stop, trip)
    except KeyboardInterrupt:
        stop.set()
    return 0


# ---- live status screen ----------------------------------------------------
class DirectSource:
    """Live screen fed by this process's own adapter session (debug mode)."""

    def __init__(self, s: Session, poller: Poller, bus: Bus, thread):
        from .service import channel_info

        self.s, self.poller, self.bus, self.thread = s, poller, bus, thread
        self.mode = "SIM" if s.sim else "LIVE"
        self.title, self.vin = s.profile.name, s.vin
        self.info_map = channel_info(s.profile)
        self._c0, self._t0, self._rate = 0, time.monotonic(), 0.0

    def keys(self):
        return self.s.profile.layouts.get("status") or list(self.s.profile.pids)

    def latest(self):
        return self.bus.latest()

    def rate(self):
        now = time.monotonic()
        if now - self._t0 >= 1.0:
            self._rate = (self.poller.cycles - self._c0) / (now - self._t0)
            self._c0, self._t0 = self.poller.cycles, now
        return self._rate

    def counters(self):
        return self.s.guard.sent, self.s.guard.blocked, self.poller.errors

    def state(self):
        return ("running", []) if self.thread.is_alive() else ("lost", [])

    def info(self, k):
        return self.info_map.get(k, {"short": k[:10], "name": k, "verified": True})

    def skipped(self, k):
        p = self.s.profile.pids.get(k)
        return bool(p) and self.poller.is_skipped(p)


class BusSource:
    """Live screen fed by the core service over MQTT."""

    def __init__(self, feed):
        self.feed = feed

    @property
    def mode(self):
        return "SIM" if self.feed.meta.get("sim") else "LIVE"

    @property
    def title(self):
        return self.feed.meta.get("name", "JpCAN")

    @property
    def vin(self):
        return self.feed.meta.get("vin")

    def keys(self):
        lay = self.feed.meta.get("layouts", {})
        return lay.get("status") or list(self.feed.meta.get("channels", {}))

    def latest(self):
        return self.feed.bus.latest()

    def rate(self):
        return float(self.feed.status.get("hz") or 0)

    def counters(self):
        st = self.feed.status
        return st.get("sent", 0), st.get("blocked", 0), st.get("errors", 0)

    def state(self):
        if not self.feed.connected:
            return "offline", ["No MQTT broker.", "mosquitto running?"]
        st = self.feed.status
        if not st:
            return "offline", ["Waiting for", "JpCAN core..."]
        if st.get("state") == "running" and not self.keys():
            return "connecting", ["Waiting for", "profile info..."]
        return st.get("state", "offline"), st.get("lines", [])

    def info(self, k):
        return self.feed.meta.get("channels", {}).get(k, {"short": k[:10], "name": k, "verified": True})

    def skipped(self, k):
        return k in self.feed.meta.get("skipped", [])


def _message(scr, lines, title="JpCAN"):
    import curses

    h, w = scr.getmaxyx()
    scr.erase()
    scr.addnstr(0, 0, title.ljust(w - 1), w - 1, curses.A_REVERSE)
    for i, ln in enumerate(lines[: h - 1]):
        scr.addnstr(1 + i, 0, ln, w - 1)
    scr.refresh()


def _wait_or_quit(scr, secs: float) -> bool:
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if scr.getch() in (ord("q"), ord("Q"), 27):
            return True
        time.sleep(0.1)
    return False


def _setup_screen(scr):
    import curses

    from . import settings
    from .touch import TouchReader

    curses.curs_set(0)
    scr.nodelay(True)
    scr.keypad(True)
    return TouchReader(), settings.load()["touch"]


def _live_bus(scr, args) -> int:
    from .mqtt import MqttFeed

    touch, cal = _setup_screen(scr)
    feed = MqttFeed(args.mqtt_host, args.mqtt_port, "jpcan-status")
    try:
        _live_screen(scr, BusSource(feed), not args.metric, touch, cal)
    finally:
        feed.close()
        touch.close()
    return 0


def _live_main(scr, args) -> int:
    touch, cal = _setup_screen(scr)
    try:
        while True:
            status: list[str] = []

            def log(msg):
                status.append(msg[:200])
                _message(scr, status[-6:])

            try:
                s = connect(args, log=log)
            except (ElmError, OSError, ValueError) as e:
                _message(scr, [*why(e, args.port), "", "Retrying in 5 s"])
                if _wait_or_quit(scr, 5):
                    return 0
                continue
            keys = s.profile.layouts.get("status") or list(s.profile.pids)
            bus = Bus()
            poller = Poller(s.elm, s.profile, bus, keys=keys, supported=s.supported)
            stop = threading.Event()
            th = threading.Thread(target=poller.run, args=(stop,), daemon=True)
            th.start()
            try:
                result = _live_screen(scr, DirectSource(s, poller, bus, th), not args.metric, touch, cal)
            finally:
                stop.set()
                th.join(timeout=2)
                s.close()
            if result == "quit":
                return 0
            _message(scr, ["Link lost:", poller.fault[:60], "", "Reconnecting..."])
            if _wait_or_quit(scr, 3):
                return 0
    finally:
        touch.close()


def _row_text(src, latest, k, imperial):
    """Return (info, value, units, status) for one channel."""
    info = src.info(k)
    r = latest.get(k)
    if src.skipped(k):
        return info, "n/s", "", ""
    if r is None:
        return info, "...", "", ""
    if r.error:
        return info, "ERR", "", "err"
    val, u = fmt(r.value, r.units, imperial)
    return info, val, u, ("old" if time.time() - r.ts > 5 else "")


def _live_screen(scr, src, imperial, touch, cal) -> str:
    import curses

    from .touch import horizontal

    page = 0
    while True:
        ch = scr.getch()
        if ch in (ord("q"), ord("Q"), 27):
            return "quit"
        state, lines = src.state()
        if state == "lost":
            return "reconnect"
        step = {curses.KEY_RIGHT: 1, ord("n"): 1, ord(" "): 1,
                curses.KEY_LEFT: -1, ord("b"): -1}.get(ch, 0)
        while touch.ok and not touch.taps.empty():
            f = horizontal(touch.taps.get_nowait(), cal)
            step += 1 if f is None or f >= 0.5 else -1  # uncalibrated: any tap = next
        page += step
        if state != "running":
            _message(scr, lines or [state])
            time.sleep(0.25)
            continue
        h, w = scr.getmaxyx()
        keys = src.keys()
        rate = src.rate()
        sent, blocked, errors = src.counters()
        scr.erase()
        put = lambda y, x, txt, a=0: 0 <= y < h and scr.addnstr(y, x, txt, max(0, w - x - 1), a)
        latest = src.latest()
        wide = w >= 56 and h >= len(keys) + 5
        if wide:
            put(0, 0, f"JpCAN {__version__}  {src.title}", curses.A_BOLD)
            put(1, 0, f"VIN {src.vin or '?'}  {src.mode}  {rate:4.1f} Hz  WiFi {wifi_label(wifi_dbm())}")
            put(2, 0, "-" * (w - 1))
            for i, k in enumerate(keys):
                info, val, u, st = _row_text(src, latest, k, imperial)
                flag = "" if info.get("verified") else "?"
                put(3 + i, 0, f"{info['name'][:24] + flag:25} {val:>10} {u:5} {st}")
            y = 4 + len(keys)
            put(y, 0, "-" * (w - 1))
            put(y + 1, 0, f"req {sent}  blocked {blocked}  err {errors}   q=quit")
        else:
            rows = max(1, h - 1)
            pages = max(1, (len(keys) + rows - 1) // rows)
            page %= pages
            alert = f" BLK{blocked}" if blocked else ""
            pg = f"<{page + 1}/{pages}>" if pages > 1 else ""
            left = f"{src.mode} {rate:2.0f}Hz {wifi_label(wifi_dbm())}{alert}"
            put(0, 0, (left + pg.rjust(max(0, w - 1 - len(left)))).ljust(w - 1), curses.A_REVERSE)
            unit_w = 4
            val_w = max(4, w - 1 - 10 - 1 - unit_w)
            for i, k in enumerate(keys[page * rows:(page + 1) * rows]):
                info, val, u, st = _row_text(src, latest, k, imperial)
                label = info.get("short", k)[:10 - (0 if info.get("verified") else 1)] + (
                    "" if info.get("verified") else "?")
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


def cmd_logs(args) -> int:
    from .export import read_meta
    from .logger import default_log_dir

    d = Path(args.dir) if args.dir else default_log_dir()
    files = sorted(d.glob("*.sqlite"))
    if not files:
        print(f"No drive logs in {d}")
    for f in files:
        m = read_meta(f)
        dur = (m.get("ended") or m.get("started", 0)) - m.get("started", 0)
        print(f"{f.name:48} {f.stat().st_size / 1e6:7.1f} MB  {dur / 60:6.1f} min")
    return 0


def cmd_export(args) -> int:
    from .export import export_csv
    from .logger import default_log_dir

    src = Path(args.log)
    if not src.exists():
        src = (Path(args.dir) if args.dir else default_log_dir()) / args.log
    out = Path(args.out) if args.out else src.with_suffix(".csv")
    n = export_csv(src, out, rate=args.rate, imperial=not args.metric)
    print(f"Wrote {n} rows to {out}")
    return 0


def cmd_didscan(args) -> int:
    import json

    from .didscan import parse_ranges, scan

    dids = parse_ranges(args.range or ["1E00-1EFF"])
    s = connect(args)
    try:
        hdr = args.header.upper()
        if not s.guard.check(f"ATSH{hdr}").allowed:
            print(f"error: header {hdr} not allowed (add it to the profile's headers)", file=sys.stderr)
            return 1
        print(f"Scanning {len(dids)} DIDs on {hdr} (service 22, read-only), "
              f"~{len(dids) * max(args.min_gap, 0.05) * 1.5:.0f} s ...")

        def prog(i, n, r):
            if r.status == "ok":
                print(f"  {r.did:04X}  {r.data.hex(' ').upper()}")
            elif r.status == "nrc" and r.nrc == 0x33:
                print(f"  {r.did:04X}  (exists, security-locked: NRC 33)")
            if i % 64 == 0 or i == n:
                print(f"  ... {i}/{n}", flush=True)

        results = scan(s.elm, hdr, dids, prog)
        ok = [r for r in results if r.status == "ok"]
        out = Path(args.out or f"didscan_{hdr}_{time.strftime('%Y%m%d-%H%M%S')}.json")
        out.write_text(json.dumps({"header": hdr, "profile": s.profile.id, "vin": s.vin,
                                   "results": [r.as_dict() for r in results]}, indent=1))
        print(f"\n{len(ok)} of {len(dids)} DIDs answered. Saved {out}")
        print(f"Guard: {s.guard.sent} sent, {s.guard.blocked} blocked")
        if ok:
            print(f"Next, on a drive:  jpcan didwatch --header {hdr} --from {out}")
    finally:
        s.close()
    return 0


def cmd_didwatch(args) -> int:
    import curses
    import json

    from .didscan import Watcher, parse_ranges

    if args.from_file:
        data = json.loads(Path(args.from_file).read_text())
        dids = [int(r["did"], 16) for r in data["results"]
                if r["status"] == "ok" and len(r["data"]) // 2 <= args.max_bytes]
        hdr = (args.header or data["header"]).upper()
    else:
        dids, hdr = parse_ranges(args.dids or []), (args.header or "7E1").upper()
    if not dids:
        print("No DIDs to watch (use --from a didscan file or --dids).", file=sys.stderr)
        return 1
    s = connect(args)
    est = None
    if s.profile.gear:
        from .gear import GearEstimator
        est = GearEstimator(Bus(), s.profile.gear)
    log = open(args.log, "a", encoding="utf-8") if args.log else None
    w = Watcher(s.elm, hdr, dids, s.profile.obd_header, est, log)

    def screen(scr):
        scr.nodelay(True)
        while scr.getch() not in (ord("q"), 27):
            w.cycle()
            scr.erase()
            h, wd = scr.getmaxyx()
            g = "-" if w.gear is None else str(w.gear)
            scr.addnstr(0, 0, f"{hdr}  rpm {w.rpm or 0:5.0f}  mph {(w.kmh or 0) * 0.621:4.0f}  est gear {g}"
                              f"   q=quit", wd - 1, curses.A_REVERSE)
            scr.addnstr(1, 0, "DID   now                 chg  values(1st byte)   gear%", wd - 1)
            for i, st in enumerate(w.ranked()[: h - 3]):
                vals = ",".join(str(v) for v in sorted(st.first_byte_values)[:8])
                scr.addnstr(2 + i, 0, f"{st.did:04X}  {st.last.hex(' ').upper():18}  {st.changes:4}  "
                                      f"{vals:18} {st.gear_match * 100:5.0f}", wd - 1)
            scr.refresh()

    try:
        curses.wrapper(screen)
    finally:
        s.close()
        if log:
            log.close()
    print("Top gear candidates:")
    for st in w.ranked()[:5]:
        print(f"  {hdr} 22{st.did:04X}  gear match {st.gear_match * 100:.0f}%  "
              f"changes {st.changes}  values {sorted(st.first_byte_values)[:10]}")
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
    def mqtt_args(p):
        p.add_argument("--mqtt-host", default="localhost")
        p.add_argument("--mqtt-port", type=int, default=1883)
        return p

    lv = mqtt_args(conn(sub.add_parser("live", help="live text status screen")))
    lv.add_argument("--bus", action="store_true", help="read from the core service over MQTT")
    lv.set_defaults(func=cmd_live)
    rp = mqtt_args(conn(sub.add_parser("run", help="core service: poll, log, publish to MQTT")))
    rp.add_argument("--no-log", action="store_true", help="don't write a drive log")
    rp.add_argument("--log-dir", help="drive log directory (default ~/jpcan-logs)")
    rp.add_argument("--no-mqtt", action="store_true", help="don't publish (testing)")
    rp.set_defaults(func=cmd_run)
    lp = sub.add_parser("logs", help="list drive logs")
    lp.add_argument("--dir", help="log directory (default ~/jpcan-logs)")
    lp.set_defaults(func=cmd_logs)
    ep = sub.add_parser("export", help="export a drive log to CSV")
    ep.add_argument("log", help="log file name or path")
    ep.add_argument("--out", help="CSV path (default: next to the log)")
    ep.add_argument("--rate", type=float, default=1.0, help="seconds per row (default 1)")
    ep.add_argument("--dir", help="log directory (default ~/jpcan-logs)")
    ep.add_argument("--metric", action="store_true")
    ep.set_defaults(func=cmd_export)
    ds = conn(sub.add_parser("didscan", help="find Ford DIDs on a module (service 22 reads)"))
    ds.add_argument("--header", default="7E1", help="module to scan (default 7E1 = TCM)")
    ds.add_argument("--range", action="append", default=None,
                    help="hex DID range(s), e.g. 1E00-1EFF (repeatable)")
    ds.add_argument("--out", help="JSON results file")
    ds.set_defaults(func=cmd_didscan, min_gap=0.1)
    dw = conn(sub.add_parser("didwatch", help="watch DIDs live to spot the gear (or any) value"))
    dw.add_argument("--header", help="module (default: from --from file, else 7E1)")
    src = dw.add_mutually_exclusive_group()
    src.add_argument("--from", dest="from_file", help="didscan JSON file")
    src.add_argument("--dids", action="append", help="hex DIDs/ranges to watch")
    dw.add_argument("--max-bytes", type=int, default=4, help="skip DIDs with longer replies (default 4)")
    dw.add_argument("--log", help="append every sample to this JSONL file")
    dw.set_defaults(func=cmd_didwatch)
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
