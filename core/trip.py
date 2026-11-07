"""Trip computer: integrates speed and fuel rate into trip distance, fuel used,
instant and average economy. Native units: km, L, s, km/L (UI shows mpg).

Subscribes to the bus (speed in km/h, fuel_rate in L/h) and publishes its own
channels back onto the bus. Gaps longer than MAX_GAP are not integrated.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .bus import Bus, Reading

MAX_GAP = 2.0          # s; longer gaps (link drop) are skipped, not guessed
COAST_LPH = 0.05       # below this fuel rate instant economy is capped
ECON_CAP = 42.5        # km/L (~100 mpg) shown while coasting


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
    Channel("econ_avg", "Trip average economy", "Avg MPG", "km/L", 0, 42.5),
    Channel("trip_dist", "Trip distance", "Trip", "km", 0, 10000),
    Channel("trip_fuel", "Trip fuel used", "Fuel used", "L", 0, 1000),
    Channel("trip_time", "Trip time", "Trip time", "s", 0, 864000),
)}


class TripComputer:
    def __init__(self, bus: Bus, publish_every: float = 0.5, clock=time.monotonic):
        self.bus = bus
        self.clock = clock
        self.publish_every = publish_every
        self.dist_km = 0.0
        self.fuel_l = 0.0
        self.t_start = clock()
        self._speed: float | None = None
        self._fuel_rate: float | None = None
        self._last_t: float | None = None
        self._last_pub = 0.0
        bus.subscribe(self.on_reading)

    def reset(self) -> None:
        self.dist_km = self.fuel_l = 0.0
        self.t_start = self.clock()
        self._last_t = None

    def on_reading(self, r: Reading) -> None:
        if r.key not in ("speed", "fuel_rate") or r.value is None:
            return
        now = self.clock()
        if self._last_t is not None and self._speed is not None and self._fuel_rate is not None:
            dt = now - self._last_t
            if 0 < dt <= MAX_GAP:
                self.dist_km += self._speed * dt / 3600
                self.fuel_l += self._fuel_rate * dt / 3600
        self._last_t = now
        if r.key == "speed":
            self._speed = r.value
        else:
            self._fuel_rate = r.value
        if now - self._last_pub >= self.publish_every:
            self._last_pub = now
            self._publish(now)

    def instant(self) -> float | None:
        if self._speed is None or self._fuel_rate is None:
            return None
        if self._speed < 1:
            return 0.0
        if self._fuel_rate < COAST_LPH:
            return ECON_CAP
        return min(ECON_CAP, self._speed / self._fuel_rate)

    def average(self) -> float | None:
        return self.dist_km / self.fuel_l if self.fuel_l > 0.01 else None

    def _publish(self, now: float) -> None:
        ts = time.time()
        for key, value in (("econ_inst", self.instant()), ("econ_avg", self.average()),
                           ("trip_dist", self.dist_km), ("trip_fuel", self.fuel_l),
                           ("trip_time", now - self.t_start)):
            if value is not None:
                self.bus.publish(Reading(key, value, CHANNELS[key].units, ts))
