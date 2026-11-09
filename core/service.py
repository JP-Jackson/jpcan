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
from .trip import CHANNELS, GEAR_CHANNEL, TripComputer


def poll_keys(profile: Profile) -> list[str]:
    """Union of every layout's keys (status screen + GaugeWorks), in order."""
    keys: list[str] = []
    for layout in [*profile.layouts.values(), profile.gauge_keys()]:
        for k in layout:
            if k in profile.pids and k not in keys:
                keys.append(k)
    return keys or list(profile.pids)


def background_keys(profile: Profile) -> list[str]:
    """Every PID not on a screen layout: read round-robin for the Diagnostic page."""
    fg = set(poll_keys(profile))
    return [k for k, p in profile.pids.items() if k not in fg and not p.is_derived]


def channel_info(profile: Profile) -> dict:
    info = {k: {"name": p.name, "short": p.label, "units": p.units, "min": p.min,
                "max": p.max, "verified": p.verified} for k, p in profile.pids.items()}
    computed = list(CHANNELS.values())
    if profile.gear and "gear" not in profile.pids:
        computed.append(GEAR_CHANNEL)
    for c in computed:
        info[c.key] = {"name": c.name, "short": c.short, "units": c.units, "min": c.min,
                       "max": c.max, "verified": c.key != "gear"}
    return info


def build_meta(s: Session, poller: Poller) -> dict:
    p = s.profile
    return {
        "profile": p.id, "name": p.name, "vin": s.vin, "sim": s.sim, "scenario": s.scenario,
        "shift": p.shift, "layouts": p.layouts, "gaugeworks": p.gaugeworks,
        "adapter": {"elm": s.info.elm, "stn": s.info.stn, "protocol": s.info.protocol},
        "channels": channel_info(p),
        "skipped": [k for k in p.pids if not p.pids[k].is_derived and poller.is_skipped(p.pids[k])],
    }


def vehicle_key(s: Session) -> str:
    return s.vin or s.profile.id


def run_core(args, sink, bus: Bus, stop: threading.Event, trip: TripComputer | None = None,
             fuel_hub=None) -> None:
    """Main loop. `sink` has publish_meta/publish_status/publish_fuel/close."""
    from .fuelbook import FuelBook

    trip = trip or TripComputer(bus)
    data_dir = Path(args.log_dir) if getattr(args, "log_dir", None) else default_log_dir()
    attached = None
    logger: DriveLogger | None = None
    gear_est = None

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
            poller = Poller(s.elm, s.profile, bus, keys=poll_keys(s.profile),
                            background=background_keys(s.profile), supported=s.supported)
            if s.profile.gear and "gear" not in s.profile.pids and gear_est is None:
                from .gear import GearEstimator
                gear_est = GearEstimator(bus, s.profile.gear)
            meta = build_meta(s, poller)
            sink.publish_meta(meta)
            vkey = vehicle_key(s)
            if attached != vkey and not getattr(args, "no_state", False):
                safe = "".join(c for c in vkey if c.isalnum() or c in "_-")
                trip.attach(data_dir / f"economy_{safe}.json")
                if fuel_hub is not None:
                    fuel_hub.attach(FuelBook(data_dir / "fuel.sqlite", vkey, bus, trip), sink.publish_fuel)
                attached = vkey
            if logger is None and not getattr(args, "no_log", False):
                units = {k: v["units"] for k, v in meta["channels"].items()}
                logger = DriveLogger(bus, data_dir, s.profile.id,
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
        trip.save()
        sink.close()
