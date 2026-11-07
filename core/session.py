"""Adapter session: open the transport, init the adapter, pick the profile.

Shared by the CLI and the core service. Everything goes through GuardedPort.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO

from .elm import AdapterInfo, Elm, NoData
from .guard import RequestGuard
from .profile import Profile, load_profile, select_profile
from .transport import GuardedPort, SerialTransport

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
    try:
        log(f"Connecting via {log_src} ...")
        info = elm.init()
        log(f"Adapter: {info.elm} | {info.stn} | {info.voltage} | {info.protocol}")
        vin = elm.vin()
        profile = load_profile(args.profile) if args.profile else select_profile(vin)
        guard.extra_headers |= profile.extra_headers
        supported = elm.supported_pids()
    except BaseException:
        port.close()
        if trace:
            trace.close()
        raise
    return Session(elm, port, guard, info, vin, profile, supported, args.sim, trace)


def why(e: BaseException, port: str) -> list[str]:
    """Short human hint lines for a connect failure (fits a 30-col screen)."""
    if isinstance(e, NoData):
        return ["Adapter OK.", "No vehicle response.", "Key on?"]
    if isinstance(e, OSError):
        return ["No adapter on", str(port), "Plugged in?"]
    return ["Error:", str(e)[:60]]
