import pytest
from core.bus import Bus
from core.elm import Elm
from core.guard import RequestGuard
from core.poller import Poller
from core.profile import load_profile
from core.sim import SimTransport
from core.transport import GuardedPort


class CountingSim(SimTransport):
    def __init__(self):
        super().__init__()
        self.obd = []

    def write(self, data):
        cmd = data.decode().strip()
        if not cmd.startswith(("AT", "ST")):
            self.obd.append(cmd[:-1] if len(cmd) % 2 else cmd)  # drop response-count digit
        super().write(data)


def setup(keys):
    prof = load_profile("ford_f250_67_2014")
    sim = CountingSim()
    elm = Elm(GuardedPort(sim, RequestGuard(extra_headers=prof.extra_headers), min_gap=0))
    elm.init()
    sim.obd.clear()
    bus = Bus()
    return Poller(elm, prof, bus, keys=keys, supported=elm.supported_pids()), sim, bus


def test_shared_request_polled_once_per_cycle():
    p, sim, bus = setup(["egt11", "egt12", "egt13", "egt14"])
    sim.obd.clear()
    p.cycle()
    assert sim.obd.count("0178") == 1
    assert all(bus.latest()[k].value is not None for k in ("egt11", "egt14"))


def test_unsupported_mode01_skipped():
    p, sim, _ = setup(["map", "rpm"])      # base 010B: truck lacks it
    sim.obd.clear()
    p.cycle()
    assert "010B" not in sim.obd and "010C" in sim.obd


def test_once_and_backoff():
    p, sim, bus = setup(["engine_hours", "trans_temp_pcm"])
    sim.obd.clear()
    for _ in range(5):
        p._last_slow = 0  # force slow due
        p.cycle()
    assert sim.obd.count("017F") == 1            # once: read a single time
    assert sim.obd.count("221E1C") == p.max_fails  # NRC 31 via PCM, then backs off
    assert bus.latest()["trans_temp_pcm"].error


def test_derived_boost_psig():
    from core.units import display

    p, sim, bus = setup(["boost"])          # inputs map_wide + baro polled automatically
    p.cycle()
    got = bus.latest()
    assert {"map_wide", "baro", "boost"} <= set(got)
    b = got["boost"]
    assert b.value == pytest.approx(got["map_wide"].value - got["baro"].value)
    v, u = display(b.value, b.units)
    assert u == "psig" and v >= 0
