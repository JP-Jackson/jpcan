"""Trip computer: instant economy plus tank, trip and rolling averages.

Integrates speed (km/h) and fuel rate (L/h) from the bus. Native units: km,
L, s, km/L (the UI shows mpg). Accumulators:
  tank  - since the last logged fill-up (reset by the fuel book)
  trip  - since JP pressed Reset trip
  last N miles - rolling window over the most recent 5 / 10 / 25 / 50 miles
State is saved to a small JSON file every `save_every` seconds and on close,
so averages survive power-offs (worst case: lose the last minute).
Values here are RAW (from the truck's fuel-rate PID); the fill-up correction
factor is applied by the UI when JP selects "corrected".
"""

from __future__ import annotations

import bisect
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .bus import Bus, Reading

MAX_GAP = 2.0          # s; longer gaps (link drop) are skipped, not guessed
COAST_LPH = 0.05       # below this fuel rate instant economy is capped
ECON_CAP = 42.5        # km/L (~100 mpg) shown while coasting
KM_PER_MI = 1.609344
ROLL_WINDOWS_MI = (5, 10, 25, 50)
SAMPLE_KM = 0.1        # rolling-window resolution


@dataclass(frozen=True)
class Channel:
    key: str
    name: str
    short: str
    units: str
    min: float
    max: float


CHANNELS = {c.key: c for c in (
    Channel("econ_inst", "Instant economy", "MPG", "km/L", 0, 42.5),
    Channel("econ_tank", "Tank average economy", "Tank", "km/L", 0, 42.5),
    Channel("econ_trip", "Trip average economy", "Trip avg", "km/L", 0, 42.5),
    *(Channel(f"econ_last{n}", f"Last {n} mi economy", f"Last {n}", "km/L", 0, 42.5)
      for n in ROLL_WINDOWS_MI),
    Channel("trip_dist", "Trip distance", "Trip", "km", 0, 100000),
    Channel("trip_fuel", "Trip fuel used", "Trip fuel", "L", 0, 10000),
    Channel("trip_time", "Trip driving time", "Trip time", "s", 0, 10 ** 7),
    Channel("tank_dist", "Distance since fill-up", "Tank dist", "km", 0, 10000),
    Channel("tank_fuel", "Fuel used since fill-up", "Tank fuel", "L", 0, 1000),
)}
# Estimated gear (core/gear.py) when the profile has a gear block and no gear PID.
GEAR_CHANNEL = Channel("gear", "Gear (estimated)", "Gear", "", 0, 10)


@dataclass
class Acc:
    dist_km: float = 0.0
    fuel_l: float = 0.0
    secs: float = 0.0

    def avg(self) -> float | None:
        return self.dist_km / self.fuel_l if self.fuel_l > 0.05 else None

    def add(self, dd: float, df: float, dt: float) -> None:
        self.dist_km += dd
        self.fuel_l += df
        self.secs += dt


class TripComputer:
    def __init__(self, bus: Bus, publish_every: float = 0.5, clock=time.monotonic,
                 save_every: float = 60.0):
        self.bus = bus
        self.clock = clock
        self.publish_every = publish_every
        self.save_every = save_every
        self.tank = Acc()
        self.trip = Acc()
        self.cum_dist = 0.0       # running totals for the rolling windows
        self.cum_fuel = 0.0
        self._s_dist: list[float] = []   # samples every SAMPLE_KM (parallel lists)
        self._s_fuel: list[float] = []
        self.state_path: Path | None = None
        self._speed: float | None = None
        self._fuel_rate: float | None = None
        self._last_t: float | None = None
        self._last_pub = 0.0
        self._last_save = clock()
        bus.subscribe(self.on_reading)

    # -- persistence ---------------------------------------------------------
    def attach(self, state_path: Path) -> None:
        """Load saved state for this vehicle (called once the VIN/profile is known)."""
        self.state_path = Path(state_path)
        try:
            d = json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return
        self.tank = Acc(**d.get("tank", {}))
        self.trip = Acc(**d.get("trip", {}))
        self.cum_dist, self.cum_fuel = d.get("cum", [0.0, 0.0])
        self._s_dist = list(d.get("s_dist", []))
        self._s_fuel = list(d.get("s_fuel", []))

    def save(self) -> None:
        if not self.state_path:
            return
        d = {"tank": vars(self.tank), "trip": vars(self.trip), "cum": [self.cum_dist, self.cum_fuel],
             "s_dist": [round(x, 3) for x in self._s_dist], "s_fuel": [round(x, 4) for x in self._s_fuel],
             "saved": time.time()}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        os.replace(tmp, self.state_path)  # atomic: a power cut leaves the old file
        self._last_save = self.clock()

    # -- resets ----------------------------------------------------------------
    def reset(self) -> None:
        """Trip reset (JP's button)."""
        self.trip = Acc()
        self._last_pub = 0.0
        self.save()

    def reset_tank(self) -> None:
        """Called by the fuel book after a fill-up is logged."""
        self.tank = Acc()
        self._last_pub = 0.0
        self.save()

    # -- integration -----------------------------------------------------------
    def on_reading(self, r: Reading) -> None:
        if r.key not in ("speed", "fuel_rate") or r.value is None:
            return
        now = self.clock()
        if self._last_t is not None and self._speed is not None and self._fuel_rate is not None:
            dt = now - self._last_t
            if 0 < dt <= MAX_GAP:
                dd = self._speed * dt / 3600
                df = self._fuel_rate * dt / 3600
                self.tank.add(dd, df, dt)
                self.trip.add(dd, df, dt)
                self.cum_dist += dd
                self.cum_fuel += df
                if not self._s_dist or self.cum_dist - self._s_dist[-1] >= SAMPLE_KM:
                    self._s_dist.append(self.cum_dist)
                    self._s_fuel.append(self.cum_fuel)
                    self._trim()
        self._last_t = now
        if r.key == "speed":
            self._speed = r.value
        else:
            self._fuel_rate = r.value
        if now - self._last_pub >= self.publish_every:
            self._last_pub = now
            self._publish()
        if now - self._last_save >= self.save_every:
            self.save()

    def _trim(self) -> None:
        keep_from = self.cum_dist - (max(ROLL_WINDOWS_MI) + 1) * KM_PER_MI
        i = bisect.bisect_left(self._s_dist, keep_from)
        if i > 0:
            del self._s_dist[:i]
            del self._s_fuel[:i]

    def instant(self) -> float | None:
        if self._speed is None or self._fuel_rate is None:
            return None
        if self._speed < 1:
            return 0.0
        if self._fuel_rate < COAST_LPH:
            return ECON_CAP
        return min(ECON_CAP, self._speed / self._fuel_rate)

    def rolling(self, miles: float) -> float | None:
        """Average over the last `miles`; None until that much distance is recorded."""
        target = self.cum_dist - miles * KM_PER_MI
        i = bisect.bisect_right(self._s_dist, target) - 1
        if i < 0:
            return None
        dd = self.cum_dist - self._s_dist[i]
        df = self.cum_fuel - self._s_fuel[i]
        return dd / df if df > 0.05 else None

    def average(self) -> float | None:  # trip average (kept for compatibility)
        return self.trip.avg()

    def _publish(self) -> None:
        ts = time.time()
        vals = {"econ_inst": self.instant(), "econ_tank": self.tank.avg(), "econ_trip": self.trip.avg(),
                "trip_dist": self.trip.dist_km, "trip_fuel": self.trip.fuel_l, "trip_time": self.trip.secs,
                "tank_dist": self.tank.dist_km, "tank_fuel": self.tank.fuel_l}
        for n in ROLL_WINDOWS_MI:
            vals[f"econ_last{n}"] = self.rolling(n)
        for key, value in vals.items():
            if value is not None:
                self.bus.publish(Reading(key, value, CHANNELS[key].units, ts))
