import sqlite3

import pytest

from core.bus import Bus, Reading
from core.export import export_csv, read_meta
from core.logger import DriveLogger
from core.trip import TripComputer
from core.units import display


def feed(bus, clock, seconds, speed_kmh, lph, step=0.1):
    for _ in range(int(seconds / step)):
        clock[0] += step
        bus.publish(Reading("speed", speed_kmh, "km/h", clock[0]))
        bus.publish(Reading("fuel_rate", lph, "L/h", clock[0]))


def test_trip_distance_fuel_and_mpg():
    bus, clock = Bus(), [0.0]
    trip = TripComputer(bus, clock=lambda: clock[0])
    feed(bus, clock, 3600, 100.0, 12.5)           # 1 h at 100 km/h, 12.5 L/h
    assert trip.dist_km == pytest.approx(100, rel=0.01)
    assert trip.fuel_l == pytest.approx(12.5, rel=0.01)
    assert trip.average() == pytest.approx(8.0, rel=0.01)   # km/L
    mpg, u = display(trip.average(), "km/L")
    assert u == "mpg" and mpg == pytest.approx(18.8, abs=0.2)
    assert trip.instant() == pytest.approx(8.0)
    got = bus.latest()
    assert {"econ_inst", "econ_avg", "trip_dist", "trip_fuel", "trip_time"} <= set(got)


def test_trip_idle_coast_and_gaps():
    bus, clock = Bus(), [0.0]
    trip = TripComputer(bus, clock=lambda: clock[0])
    feed(bus, clock, 10, 0.0, 2.0)
    assert trip.instant() == 0.0                   # stopped
    feed(bus, clock, 1, 80.0, 0.0)
    assert trip.instant() == pytest.approx(42.5)   # coasting cap
    before = trip.dist_km
    clock[0] += 30                                 # link drop: not integrated
    bus.publish(Reading("speed", 80.0, "km/h", clock[0]))
    assert trip.dist_km == pytest.approx(before)


def test_logger_and_export(tmp_path):
    bus = Bus()
    log = DriveLogger(bus, tmp_path, "ford_f250_67_2014",
                      {"units": {"speed": "km/h", "boost": "kPag"}}, flush_every=0.05)
    t0 = 1_700_000_000.0
    for i in range(30):
        bus.publish(Reading("speed", 10.0 * i, "km/h", t0 + i * 0.5))
        bus.publish(Reading("boost", 100.0, "kPag", t0 + i * 0.5))
    bus.publish(Reading("egt11", None, "°C", t0, "NO DATA"))
    bus.publish(Reading("egt11", None, "°C", t0 + 1, "NO DATA"))   # duplicate error dropped
    log.close()
    db = sqlite3.connect(log.path)
    assert db.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == 61
    assert read_meta(log.path)["profile"] == "ford_f250_67_2014"
    out = tmp_path / "drive.csv"
    n = export_csv(log.path, out, rate=1.0)
    lines = out.read_text().splitlines()
    assert lines[0] == "time,elapsed_s,speed (mph),boost (psig)"
    assert n == len(lines) - 1 == 15
    last = lines[-1].split(",")
    assert float(last[2]) == pytest.approx(280 * 0.621371, abs=0.01)
    assert float(last[3]) == pytest.approx(14.5, abs=0.01)
