"""Poller: reads profile PIDs by rate class and publishes to the bus.

Rate classes:
  fast   = every cycle (rpm, boost, VGT, speed: things the eye tracks)
  medium = about every `medium_interval` s (rail pressure, fuel rate)
  slow   = about every `slow_interval` s (temps, fuel level, odometer)
  once   = first success only (engine hours, VIN-like values)
Only `extra_per_cycle` non-fast reads happen per cycle, most overdue first, so
slow PIDs never burst together and stall the fast ones. A cycle with no extra
read due reads one diagnostic-list PID instead (background).
PIDs sharing one request (e.g. EGT11-14 from 22F478) cost one request.
Failing PIDs back off to one retry every `retry_after` s. All traffic goes
through Elm -> GuardedPort, so the guard and throttle always apply.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from .bus import Bus, Reading
from .elm import Elm, ElmError
from .formula import FormulaError
from .profile import Pid, Profile


@dataclass
class PidState:
    last_ok: float = 0.0
    last_try: float = 0.0
    fails: int = 0
    done: bool = False


@dataclass
class Poller:
    elm: Elm
    profile: Profile
    bus: Bus
    keys: list[str] | None = None
    background: list[str] | None = None  # read one per cycle, round-robin (diagnostic list)
    supported: set[int] | None = None   # Mode 01 bitmap from the ECU, if known
    fast_interval: float = 0.1          # ~10 Hz cap for the fast class
    medium_interval: float = 1.0
    slow_interval: float = 5.0
    extra_per_cycle: int = 1            # non-fast reads per cycle
    retry_after: float = 30.0
    max_fails: int = 3
    state: dict[str, PidState] = field(default_factory=dict)
    cycles: int = 0
    errors: int = 0
    fault: str = ""      # set if the link dies (adapter unplugged)

    def __post_init__(self):
        keys = list(self.keys or self.profile.pids)
        wanted = [self.profile.pids[k] for k in keys]
        self.derived: list[Pid] = [p for p in wanted if p.is_derived]
        for d in self.derived:  # make sure inputs get polled
            keys += [v for v in sorted(d.formula.vars) if v not in keys]
        self.pids: list[Pid] = [self.profile.pids[k] for k in keys if not self.profile.pids[k].is_derived]
        self.bg: list[Pid] = [self.profile.pids[k] for k in (self.background or [])
                              if k not in keys and not self.profile.pids[k].is_derived]
        self.state = {p.key: PidState() for p in [*self.pids, *self.bg]}
        self._bg_i = 0

    def is_skipped(self, p: Pid) -> bool:
        if p.is_derived:
            return any(self.is_skipped(self.profile.pids[v]) for v in p.formula.vars)
        return (self.supported is not None and p.service == "01"
                and int(p.pid, 16) not in self.supported)

    def _blocked(self, p: Pid, now: float) -> bool:
        st = self.state[p.key]
        return (st.done or self.is_skipped(p)
                or (st.fails >= self.max_fails and now - st.last_try < self.retry_after))

    def _interval(self, p: Pid) -> float:
        return {"medium": self.medium_interval, "slow": self.slow_interval}.get(p.poll_rate, 0.0)

    def cycle(self) -> None:
        now = time.monotonic()
        cache: dict[tuple[str, str], bytes | Exception] = {}
        for p in self.pids:
            if p.poll_rate == "fast" and not self._blocked(p, now):
                self._read(p, now, cache)
        # non-fast: most overdue first, a few per cycle; siblings sharing the request come free
        due = [(now - self.state[p.key].last_try - self._interval(p), p) for p in self.pids
               if p.poll_rate != "fast" and not self._blocked(p, now)
               and now - self.state[p.key].last_try >= self._interval(p)]
        due.sort(key=lambda t: -t[0])
        reads = 0
        for _, p in due:
            if reads >= self.extra_per_cycle:
                break
            if p.service != "AT" and (self.profile.header_for(p), p.request) in cache:
                continue  # already read as a sibling this cycle
            self._read(p, now, cache)
            reads += 1
            if p.service != "AT":
                k = (self.profile.header_for(p), p.request)
                for q in self.pids:
                    if (q is not p and q.poll_rate != "fast" and q.service != "AT" and not self._blocked(q, now)
                            and (self.profile.header_for(q), q.request) == k):
                        self._read(q, now, cache)
        if reads == 0:
            self._background(now, cache)
        self._compute_derived()
        self.cycles += 1

    def _background(self, now: float, cache) -> None:
        """One diagnostic-list PID per cycle, so the full list never slows the gauges."""
        for _ in range(len(self.bg)):
            p = self.bg[self._bg_i % len(self.bg)]
            self._bg_i += 1
            st = self.state[p.key]
            if self.is_skipped(p) or (st.fails >= self.max_fails and now - st.last_try < self.retry_after):
                continue
            self._read(p, now, cache)
            return

    def _read(self, p: Pid, now: float, cache) -> None:
        st = self.state[p.key]
        st.last_try = now
        try:
            if p.service == "AT":
                value = self.elm.voltage()
                if value is None:
                    raise ElmError("no voltage")
            else:
                hdr = self.profile.header_for(p)
                k = (hdr, p.request)
                if k not in cache:
                    try:
                        cache[k] = self.elm.read(p.service, p.pid, hdr)
                    except ElmError as e:
                        cache[k] = e
                if isinstance(cache[k], Exception):
                    raise cache[k]
                value = p.formula(cache[k])
        except (ElmError, FormulaError) as e:
            st.fails += 1
            self.errors += 1
            self.bus.publish(Reading(p.key, None, p.units, time.time(), str(e) or type(e).__name__))
            return
        st.fails, st.last_ok = 0, now
        st.done = p.poll_rate == "once"
        self.bus.publish(Reading(p.key, value, p.units, time.time()))

    def _compute_derived(self) -> None:
        latest = self.bus.latest()
        for d in self.derived:
            inputs = {v: latest.get(v) for v in d.formula.vars}
            if any(r is None or r.value is None for r in inputs.values()):
                continue  # wait until every input has a good value
            try:
                value = d.formula({v: r.value for v, r in inputs.items()})
            except (FormulaError, ZeroDivisionError) as e:
                self.bus.publish(Reading(d.key, None, d.units, time.time(), str(e)))
                continue
            self.bus.publish(Reading(d.key, value, d.units, time.time()))

    def run(self, stop: threading.Event) -> None:
        while not stop.is_set():
            start = time.monotonic()
            try:
                self.cycle()
            except OSError as e:  # serial gone (pyserial errors are OSError)
                self.fault = str(e) or "adapter disconnected"
                return
            stop.wait(max(0.0, start + self.fast_interval - time.monotonic()))
