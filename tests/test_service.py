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
    assert "econ_avg" in sink.meta["channels"]
    assert wait_for(lambda: {"rpm", "boost", "econ_inst"} <= set(bus.latest()))
    assert sink.status["blocked"] == 0
    stop.set()
    th.join(10)
    assert sink.status["state"] == "offline"
    logs = list(tmp_path.glob("*.sqlite"))
    assert len(logs) == 1 and logs[0].stat().st_size > 0


def test_core_only_listens_to_trip_reset():
    assert CORE_SUBSCRIPTIONS == (T_TRIP_RESET,)


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
    pub = MqttPublisher(bus, "127.0.0.1", broker, on_trip_reset=trip.reset)
    th = threading.Thread(target=run_core, args=(args(tmp_path, no_log=True), pub, bus, stop, trip),
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
        assert wait_for(lambda: trip.t_start < time.monotonic() - 1.0)
        before = trip.t_start
        feed.trip_reset()
        assert wait_for(lambda: trip.t_start > before)
        feed.c.publish("jpcan/cmd/anything_else", b"x")  # ignored; core doesn't subscribe
        stop.set()
        th.join(10)
        assert wait_for(lambda: feed.status.get("state") == "offline")
    finally:
        stop.set()
        feed.close()
