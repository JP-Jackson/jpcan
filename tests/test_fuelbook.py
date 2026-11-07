import time

import pytest

from core.bus import Bus, Reading
from core.fuelbook import FillupError, FuelBook, FuelHub
from core.trip import KM_PER_MI, TripComputer


def setup(tmp_path, vehicle="VIN1"):
    bus = Bus()
    trip = TripComputer(bus, clock=time.monotonic)
    return bus, trip, FuelBook(tmp_path / "fuel.sqlite", vehicle, bus, trip)


def odo(bus, miles):
    bus.publish(Reading("odometer", miles * KM_PER_MI, "km", time.time()))


def drive(trip, miles, mpg_est):
    """Pretend the trip computer integrated `miles` at `mpg_est` (raw)."""
    km = miles * KM_PER_MI
    trip.tank.add(km, km / (mpg_est / 2.35215), 3600)


def test_baseline_then_actual_mpg_from_odometer(tmp_path):
    bus, trip, book = setup(tmp_path)
    odo(bus, 148000)
    r1 = book.add(20.0, 3.50)
    assert r1["miles_src"] == "baseline" and r1["mpg"] is None and r1["total"] == 70.0
    drive(trip, 340, 17.0)
    odo(bus, 148340)
    r2 = book.add(22.0, 3.40)
    assert r2["miles_src"] == "odometer"
    assert r2["mpg"] == pytest.approx(340 / 22.0)
    assert r2["est_mpg"] == pytest.approx(17.0)
    assert trip.tank.dist_km == 0                       # tank average reset
    f, n = book.factor()
    assert n == 1 and f == pytest.approx((340 / 22.0) / 17.0)


def test_fallback_to_estimated_miles_without_odometer(tmp_path):
    bus, trip, book = setup(tmp_path)
    book.add(20.0)
    drive(trip, 300, 16.0)
    r = book.add(20.0)
    assert r["miles_src"] == "estimate" and r["mpg"] == pytest.approx(15.0)


def test_factor_uses_last_three_and_is_clamped(tmp_path):
    bus, trip, book = setup(tmp_path)
    odo(bus, 1000)
    book.add(20)
    for i, (miles, est) in enumerate([(300, 30.0), (300, 16.0), (300, 16.0), (300, 16.0)]):
        drive(trip, miles, est)
        odo(bus, 1000 + 300 * (i + 1))
        book.add(20)                                    # actual 15 mpg each time
    f, n = book.factor()
    assert n == 3 and f == pytest.approx(15 / 16)      # oldest (30 est) dropped
    h = book.history()
    assert h["lifetime"]["tanks"] == 4 and h["lifetime"]["mpg"] == pytest.approx(15.0)
    assert len(h["rows"]) == 5 and h["rows"][0]["id"] > h["rows"][-1]["id"]


@pytest.mark.parametrize("gal,price", [(0, 3), (200, 3), (10, -1), (10, 99)])
def test_rejects_bad_input(tmp_path, gal, price):
    _, _, book = setup(tmp_path)
    with pytest.raises(FillupError):
        book.add(gal, price)


def test_vehicles_kept_separate(tmp_path):
    bus, trip, a = setup(tmp_path, "F250")
    b = FuelBook(tmp_path / "fuel.sqlite", "JETTA", bus, trip)
    a.add(20)
    assert len(a.history()["rows"]) == 1 and b.history()["rows"] == []


def test_hub_publishes_result_and_errors(tmp_path):
    bus, trip, book = setup(tmp_path)
    got = []
    hub = FuelHub()
    assert hub.fillup(10) is None                       # no vehicle yet: ignored
    hub.attach(book, got.append)
    hub.fillup(18.5, 3.2)
    assert got[-1]["last_result"]["gallons"] == 18.5
    hub.fillup(999)
    assert "error" in got[-1]["last_result"]
