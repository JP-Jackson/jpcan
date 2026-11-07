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


def three_fills(tmp_path):
    bus, trip, book = setup(tmp_path)
    for odo_mi, gal in ((1000, 20.0), (1300, 20.0), (1640, 20.0)):
        odo(bus, odo_mi)
        book.add(gal, 3.0)
    rows = sorted(book.history()["rows"], key=lambda r: r["ts"])
    return bus, trip, book, [r["id"] for r in rows]


def test_edit_recomputes_chain(tmp_path):
    _, _, book, ids = three_fills(tmp_path)
    book.edit(ids[1], odo_mi=1320, gallons=22.0, price=3.5)
    rows = {r["id"]: r for r in book.history()["rows"]}
    assert rows[ids[1]]["miles"] == pytest.approx(320) and rows[ids[1]]["mpg"] == pytest.approx(320 / 22)
    assert rows[ids[1]]["total"] == pytest.approx(77.0)
    assert rows[ids[2]]["miles"] == pytest.approx(320)       # next line recalculated too
    assert rows[ids[0]]["miles_src"] == "baseline"


@pytest.mark.parametrize("odo_mi", [900, 1000, 1700])
def test_edit_rejects_out_of_order_odometer(tmp_path, odo_mi):
    _, _, book, ids = three_fills(tmp_path)
    with pytest.raises(FillupError, match="odometer"):
        book.edit(ids[1], odo_mi=odo_mi)


def test_edit_date_and_bad_values(tmp_path):
    _, _, book, ids = three_fills(tmp_path)
    book.edit(ids[0], date="2020-01-15")                       # oldest moved earlier: still in order
    r = next(r for r in book.history()["rows"] if r["id"] == ids[0])
    assert time.strftime("%Y-%m-%d", time.localtime(r["ts"])) == "2020-01-15"
    with pytest.raises(FillupError, match="odometer"):
        book.edit(ids[2], date="2020-01-01")                   # newest moved first: odometer out of order
    with pytest.raises(FillupError):
        book.edit(ids[2], date="11/05/2026")
    with pytest.raises(FillupError):
        book.edit(ids[2], gallons=500)
    with pytest.raises(FillupError):
        book.edit(9999, gallons=10)


def test_delete_line_recomputes(tmp_path):
    _, _, book, ids = three_fills(tmp_path)
    book.delete(ids[1])
    rows = {r["id"]: r for r in book.history()["rows"]}
    assert ids[1] not in rows and rows[ids[2]]["miles"] == pytest.approx(640)
    book.delete(ids[0])                                       # oldest gone: next is the new baseline
    assert book.history()["rows"][0]["miles_src"] == "baseline"


def test_clear_current_vehicle_only_with_backup(tmp_path):
    bus, trip, book, ids = three_fills(tmp_path)
    other = FuelBook(tmp_path / "fuel.sqlite", "JETTA", bus, trip)
    other.add(10.0)
    with pytest.raises(FillupError):
        book.clear("yes")                                     # needs the token
    res = book.clear("DELETE")
    assert res["deleted"] == 3 and book.history()["rows"] == []
    assert len(other.history()["rows"]) == 1                 # Jetta untouched
    backups = list((tmp_path / "fuel_backups").glob("fuel_*.sqlite"))
    assert len(backups) == 1
    import sqlite3
    with sqlite3.connect(backups[0]) as db:
        assert db.execute("SELECT COUNT(*) FROM fillups WHERE vehicle='VIN1'").fetchone()[0] == 3


def test_hub_edit_actions(tmp_path):
    _, _, book, ids = three_fills(tmp_path)
    got = []
    hub = FuelHub()
    hub.attach(book, got.append)
    hub.edit({"action": "edit", "id": ids[2], "gallons": 21.0})
    assert got[-1]["last_result"]["action"] == "edit"
    hub.edit({"action": "delete", "id": ids[2]})
    assert got[-1]["last_result"]["action"] == "delete"
    hub.edit({"action": "nuke"})
    assert "error" in got[-1]["last_result"]
    hub.edit({"action": "clear"})                              # no token -> refused
    assert "error" in got[-1]["last_result"] and len(got[-1]["rows"]) == 2
