"""JpCAN core service: the ONLY process that talks to the adapter.

Connects (retrying with hints), polls the profile's layout PIDs, runs the trip
computer and drive logger, and publishes values/meta/status to a sink
(MQTT on the Pi, LocalSink in-process for the laptop simulator).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from .bus import Bus
from .elm import ElmError
from .logger import DriveLogger, default_log_dir
from .poller import Poller
from .profile import Profile
from .session import Session, connect, why
from .trip import CHANNELS, TripComputer


def poll_keys(profile: Profile) -> list[str]:
    """Union of every layout's keys (status screen + GaugeWorks), in order."""
    keys: list[str] = []
    for layout in profile.layouts.values():
        keys += [k for k in layout if k in profile.pids and k not in keys]
    return keys or list(profile.pids)


def channel_info(profile: Profile) -> dict:
    info = {k: {"name": p.name, "short": p.label, "units": p.units, "min": p.min,
                "max": p.max, "verified": p.verified} for k, p in profile.pids.items()}
    for c in CHANNELS.values():
        info[c.key] = {"name": c.name, "short": c.short, "units": c.units, "min": c.min,
                       "max": c.max, "verified": True}
    return info


def build_meta(s: Session, poller: Poller) -> dict:
    p = s.profile
    return {
        "profile": p.id, "name": p.name, "vin": s.vin, "sim": s.sim,
        "shift": p.shift, "layouts": p.layouts,
        "adapter": {"elm": s.info.elm, "stn": s.info.stn, "protocol": s.info.protocol},
        "channels": channel_info(p),
        "skipped": [k for k in poller.state if poller.is_skipped(p.pids[k])],
    }


def run_core(args, sink, bus: Bus, stop: threading.Event, trip: TripComputer | None = None) -> None:
    """Main loop. `sink` has publish_meta/publish_status/close (MQTT or LocalSink)."""
    trip = trip or TripComputer(bus)
    logger: DriveLogger | None = None

    def status(state, lines, **extra):
        sink.publish_status({"state": state, "lines": lines, "ts": time.time(), **extra})

    try:
        while not stop.is_set():
            hints: list[str] = []

            def log(msg):
                hints.append(msg[:120])
                status("connecting", hints[-4:])

            try:
                s = connect(args, log=log)
            except (ElmError, OSError, ValueError) as e:
                status("waiting", [*why(e, args.port), "Retrying in 5 s"])
                stop.wait(5)
                continue
            poller = Poller(s.elm, s.profile, bus, keys=poll_keys(s.profile), supported=s.supported)
            meta = build_meta(s, poller)
            sink.publish_meta(meta)
            if logger is None and not getattr(args, "no_log", False):
                log_dir = Path(args.log_dir) if getattr(args, "log_dir", None) else default_log_dir()
                units = {k: v["units"] for k, v in meta["channels"].items()}
                logger = DriveLogger(bus, log_dir, s.profile.id,
                                     {"units": units, "vin": s.vin, "sim": s.sim})
            pstop = threading.Event()
            th = threading.Thread(target=poller.run, args=(pstop,), daemon=True)
            th.start()
            c0, t0 = 0, time.monotonic()
            try:
                while th.is_alive() and not stop.is_set():
                    stop.wait(1.0)
                    now = time.monotonic()
                    hz = (poller.cycles - c0) / max(1e-6, now - t0)
                    c0, t0 = poller.cycles, now
                    status("running", [], hz=round(hz, 1), sent=s.guard.sent,
                           blocked=s.guard.blocked, errors=poller.errors,
                           log=str(logger.path) if logger else "", rows=logger.rows if logger else 0)
            finally:
                pstop.set()
                th.join(timeout=2)
                s.close()
            if not stop.is_set():
                status("waiting", ["Link lost:", poller.fault[:60], "Reconnecting..."])
                stop.wait(3)
    finally:
        if logger:
            logger.close()
        sink.close()
