"""Fill-up log: actual MPG from the pump, price, and the correction factor.

At each fill-up JP enters gallons and $/gal. Miles come from the truck's
odometer (falls back to the trip computer's tank distance if there's no
odometer). JP always fills to full, so actual MPG = miles since the previous
fill-up / gallons. The first fill-up for a vehicle is the baseline.

Each record also stores the truck's own (raw, fuel-rate based) estimate for
that tank, so the correction factor = mean(actual / estimate) over the last
CORR_TANKS tanks, clamped to CORR_RANGE. One SQLite file, keyed by vehicle.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from .bus import Bus
from .trip import KM_PER_MI, TripComputer

KML_TO_MPG = 2.35215
CORR_TANKS = 3
CORR_RANGE = (0.7, 1.3)
GALLONS_RANGE = (0.5, 80.0)
PRICE_RANGE = (0.0, 25.0)
ODO_MAX_AGE = 600.0  # s; older odometer readings aren't trusted for a fill-up

SCHEMA = """
CREATE TABLE IF NOT EXISTS fillups (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, vehicle TEXT NOT NULL,
    odo_mi REAL, miles REAL, miles_src TEXT, gallons REAL NOT NULL,
    price REAL, total REAL, mpg REAL, est_mpg REAL
);
"""


class FillupError(ValueError):
    pass


class FuelBook:
    def __init__(self, db_path: Path, vehicle: str, bus: Bus, trip: TripComputer):
        self.db_path = Path(db_path)
        self.vehicle = vehicle
        self.bus = bus
        self.trip = trip
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(SCHEMA)

    def _db(self):
        return sqlite3.connect(self.db_path)

    def _odometer_mi(self) -> float | None:
        r = self.bus.latest().get("odometer")
        if r is None or r.value is None or r.error or time.time() - r.ts > ODO_MAX_AGE:
            return None
        return r.value / KM_PER_MI

    def add(self, gallons: float, price: float | None = None) -> dict:
        gallons = float(gallons)
        if not GALLONS_RANGE[0] <= gallons <= GALLONS_RANGE[1]:
            raise FillupError(f"gallons {gallons} out of range")
        if price is not None:
            price = float(price)
            if not PRICE_RANGE[0] <= price <= PRICE_RANGE[1]:
                raise FillupError(f"price {price} out of range")
        with self._lock, self._db() as db:
            prev = db.execute("SELECT odo_mi FROM fillups WHERE vehicle=? ORDER BY id DESC LIMIT 1",
                              (self.vehicle,)).fetchone()
            odo = self._odometer_mi()
            tank_miles = self.trip.tank.dist_km / KM_PER_MI
            if prev is None:
                miles, src = None, "baseline"
            elif odo is not None and prev[0] is not None and odo > prev[0]:
                miles, src = odo - prev[0], "odometer"
            else:
                miles, src = tank_miles, "estimate"
            mpg = miles / gallons if miles else None
            est = self.trip.tank.avg()
            est_mpg = est * KML_TO_MPG if (est and prev is not None and self.trip.tank.fuel_l > 2) else None
            total = round(gallons * price, 2) if price is not None else None
            db.execute("INSERT INTO fillups (ts, vehicle, odo_mi, miles, miles_src, gallons, price, total, "
                       "mpg, est_mpg) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (time.time(), self.vehicle, odo, miles, src, gallons, price, total, mpg, est_mpg))
        self.trip.reset_tank()
        return {"miles": miles, "miles_src": src, "gallons": gallons, "mpg": mpg, "est_mpg": est_mpg,
                "total": total}

    def factor(self) -> tuple[float | None, int]:
        with self._db() as db:
            rows = db.execute("SELECT mpg, est_mpg FROM fillups WHERE vehicle=? AND mpg IS NOT NULL "
                              "AND est_mpg IS NOT NULL ORDER BY id DESC LIMIT ?",
                              (self.vehicle, CORR_TANKS)).fetchall()
        if not rows:
            return None, 0
        f = sum(m / e for m, e in rows) / len(rows)
        return max(CORR_RANGE[0], min(CORR_RANGE[1], f)), len(rows)

    def history(self, limit: int = 50) -> dict:
        with self._db() as db:
            cols = ("id", "ts", "odo_mi", "miles", "miles_src", "gallons", "price", "total", "mpg", "est_mpg")
            rows = [dict(zip(cols, r)) for r in db.execute(
                f"SELECT {', '.join(cols)} FROM fillups WHERE vehicle=? ORDER BY id DESC LIMIT ?",
                (self.vehicle, limit))]
            tot = db.execute("SELECT SUM(miles), SUM(gallons), SUM(total), COUNT(*) FROM fillups "
                             "WHERE vehicle=? AND mpg IS NOT NULL", (self.vehicle,)).fetchone()
        miles, gal, cost, n = tot
        f, fn = self.factor()
        return {"vehicle": self.vehicle, "rows": rows, "factor": f, "factor_tanks": fn,
                "lifetime": {"tanks": n or 0, "miles": miles or 0.0, "gallons": gal or 0.0,
                             "mpg": (miles / gal) if miles and gal else None,
                             "cost": cost or 0.0,
                             "cost_per_mile": (cost / miles) if cost and miles else None}}


class FuelHub:
    """Bridges MQTT commands to the current vehicle's FuelBook (set after connect)."""

    def __init__(self):
        self.book: FuelBook | None = None
        self.publish = lambda history: None

    def attach(self, book: FuelBook, publish) -> None:
        self.book, self.publish = book, publish
        publish(book.history())

    def fillup(self, gallons, price=None) -> dict | None:
        if self.book is None:
            return None
        try:
            result = self.book.add(gallons, price)
        except (FillupError, TypeError, ValueError) as e:
            h = self.book.history()
            h["last_result"] = {"error": str(e), "ts": time.time()}
            self.publish(h)
            return None
        h = self.book.history()
        h["last_result"] = {**result, "ts": time.time()}
        self.publish(h)
        return result
