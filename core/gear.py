"""Estimated transmission gear from engine RPM and vehicle speed.

The truck doesn't report gear over standard OBD, so we compare the measured
overall ratio (engine rpm / wheel rpm) with the transmission's gear ratios
times the axle ratio. Needs the profile's `gear:` block:

    gear: {ratios: [3.97, 2.32, 1.52, 1.15, 0.86, 0.67], axle: 3.55, tire_diameter_in: 33.2}

Reports None (shown as "-") when stopped, coasting with the converter unlocked,
or mid-shift (no ratio within `tolerance`). Holds the last gear briefly so the
display doesn't flicker during a shift.
"""

from __future__ import annotations

import math
import time

from .bus import Bus, Reading

KMH_PER_MS = 3.6


class GearEstimator:
    def __init__(self, bus: Bus, cfg: dict, clock=time.monotonic):
        self.bus = bus
        self.clock = clock
        self.ratios = [float(r) for r in cfg["ratios"]]
        self.axle = float(cfg["axle"])
        self.tire_m = float(cfg["tire_diameter_in"]) * 0.0254
        self.tol = float(cfg.get("tolerance", 0.12))       # relative ratio error allowed
        self.min_kmh = float(cfg.get("min_speed_kmh", 8))
        self.hold = float(cfg.get("hold_s", 1.0))
        self._rpm: float | None = None
        self._kmh: float | None = None
        self._gear: int | None = None
        self._last_match = 0.0
        bus.subscribe(self.on_reading)

    def estimate(self, rpm: float, kmh: float) -> tuple[int | None, float | None]:
        """(gear, measured transmission ratio) or (None, ratio) if no match."""
        if kmh < self.min_kmh or rpm < 300:
            return None, None
        wheel_rpm = (kmh / KMH_PER_MS) / (math.pi * self.tire_m) * 60
        trans_ratio = rpm / (wheel_rpm * self.axle)
        best = min(range(len(self.ratios)), key=lambda i: abs(trans_ratio / self.ratios[i] - 1))
        if abs(trans_ratio / self.ratios[best] - 1) <= self.tol:
            return best + 1, trans_ratio
        return None, trans_ratio

    def on_reading(self, r: Reading) -> None:
        if r.key == "rpm":
            self._rpm = r.value
        elif r.key == "speed":
            self._kmh = r.value
        else:
            return
        if r.key != "speed" or self._rpm is None or self._kmh is None:
            return
        now = self.clock()
        gear, _ = self.estimate(self._rpm, self._kmh)
        if gear is not None:
            self._gear, self._last_match = gear, now
        elif self._kmh < self.min_kmh or now - self._last_match > self.hold:
            self._gear = None
        self.bus.publish(Reading("gear", None if self._gear is None else float(self._gear), "",
                                 time.time(), "" if self._gear is not None else "no gear"))
