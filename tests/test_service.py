"""Core service end to end with the simulator: LocalSink, and real MQTT if mosquitto exists."""

import shutil
import socket
import subprocess
import threading
import time
from argparse import Namespace

import pytest

from core.bus import Bus
from core.mqtt import CORE_SUBSCRIPTIONS, T_TRIP_RESET, LocalSink
from core.service import poll_keys, run_core
from core.profile import load_profile
from core.trip import TripComputer


def args(tmp_path, **kw):
    base = dict(sim=True, port="SIM", baud=115200, profile=None, trace=None, min_gap=0.0,
                log_dir=str(tmp_path), no_log=False)
    return Namespace(**{**base, **kw})


def wait_for(cond, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_poll_keys_cover_layouts():
    p = load_profile("ford_f250_67_2014")
    keys = poll_keys(p)
    assert "boost" in keys and "rpm" in keys and len(keys) == len(set(keys))


def test_core_local_sink(tmp_path):
    bus, stop = Bus(), threading.Event()
    sink = LocalSink(bus)
    th = threading.Thread(target=run_core, args=(args(tmp_path), sink, bus, stop), daemon=True)
    th.start()
    assert wait_for(lambda: sink.status.get("state") == "running" and sink.status.get("hz", 0) > 0)
    assert sink.meta["profile"] == "ford_f250_67_2014"
    assert "econ_tank" in sink.meta["channels"]
    assert wait_for(lambda: {"rpm", "boost", "econ_inst"} <= set(bus.latest()))
    assert sink.status["blocked"] == 0
    stop.set()
    th.join(10)
    assert sink.status["state"] == "offline"
    logs = list(tmp_path.glob("*.sqlite"))
    assert len(logs) == 1 and logs[0].stat().st_size > 0


def test_core_only_listens_to_its_two_commands():
    """The core's ONLY MQTT inputs; neither can reach the adapter."""
    from core.mqtt import T_FILLUP
    assert CORE_SUBSCRIPTIONS == (T_TRIP_RESET, T_FILLUP)
    assert all(t.startswith("jpcan/cmd/") for t in CORE_SUBSCRIPTIONS)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def broker(tmp_path):
    exe = shutil.which("mosquitto") or ("/usr/sbin/mosquitto" if shutil.os.path.exists("/usr/sbin/mosquitto") else None)
    if not exe:
        pytest.skip("mosquitto not installed")
    port = _free_port()
    conf = tmp_path / "m.conf"
    conf.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
    proc = subprocess.Popen([exe, "-c", str(conf)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert wait_for(lambda: socket.socket().connect_ex(("127.0.0.1", port)) == 0, 5)
    yield port
    proc.terminate()
    proc.wait(5)


def test_core_over_mqtt(tmp_path, broker):
    from core.mqtt import MqttFeed, MqttPublisher

    bus, stop = Bus(), threading.Event()
    trip = TripComputer(bus)
    from core.fuelbook import FuelHub

    hub = FuelHub()
    pub = MqttPublisher(bus, "127.0.0.1", broker, on_trip_reset=trip.handle_reset, on_fillup=hub.fillup)
    th = threading.Thread(target=run_core, args=(args(tmp_path, no_log=True), pub, bus, stop, trip, hub),
                          daemon=True)
    th.start()
    feed = MqttFeed("127.0.0.1", broker)
    try:
        assert wait_for(lambda: feed.status.get("state") == "running")
        assert feed.meta.get("profile") == "ford_f250_67_2014"
        assert wait_for(lambda: {"rpm", "boost", "econ_inst"} <= set(feed.bus.latest()))
        assert feed.bus.latest()["boost"].units == "kPag"
        late = MqttFeed("127.0.0.1", broker, "late")   # joins after the once-read
        assert wait_for(lambda: "odometer" in late.bus.latest())
        late.close()
        assert wait_for(lambda: "rows" in feed.fuel)            # history published, retained
        assert wait_for(lambda: trip.trip.secs > 0.5)
        feed.trip_reset()
        assert wait_for(lambda: trip.trip.secs < 0.5)
        trip._s_dist, trip._s_fuel = [0.0, 50.0], [0.0, 5.0]   # pretend 30 mi of history
        feed.trip_reset("roll")                                 # Last N reset over MQTT
        assert wait_for(lambda: len(trip._s_dist) == 1)
        feed.fillup(20.0, 3.459)                                 # baseline fill
        assert wait_for(lambda: len(feed.fuel.get("rows", [])) == 1)
        feed.fillup(500, 3.0)                                    # rejected: out of range
        assert wait_for(lambda: "error" in (feed.fuel.get("last_result") or {}))
        feed.c.publish("jpcan/cmd/fillup", b"garbage")           # ignored
        feed.c.publish("jpcan/cmd/anything_else", b"x")          # ignored; not subscribed
        time.sleep(0.3)
        assert len(feed.fuel["rows"]) == 1 and th.is_alive()
        stop.set()
        th.join(10)
        assert wait_for(lambda: feed.status.get("state") == "offline")
    finally:
        stop.set()
        feed.close()


def test_core_estimates_gear_in_sim(tmp_path):
    bus, stop = Bus(), threading.Event()
    sink = LocalSink(bus)
    th = threading.Thread(target=run_core, args=(args(tmp_path, no_log=True), sink, bus, stop), daemon=True)
    th.start()
    try:
        assert wait_for(lambda: "gear" in bus.latest())
        assert sink.meta["channels"]["gear"]["verified"] is False   # estimated -> shows "?"
        assert wait_for(lambda: sink.status.get("state") == "running")
    finally:
        stop.set()
        th.join(10)
