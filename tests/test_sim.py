"""Full stack against the simulator: guard -> port -> driver -> profile formulas."""

import pytest

from core.elm import Elm, NegativeResponse, NoData
from core.guard import RequestGuard
from core.profile import load_profile
from core.sim import SIM_VIN, SimTransport, SimVehicle
from core.transport import GuardedPort


@pytest.fixture
def stack():
    now = [100.0]
    prof = load_profile("ford_f250_67_2014")
    sim = SimTransport(SimVehicle(clock=lambda: now[0]))
    elm = Elm(GuardedPort(sim, RequestGuard(extra_headers=prof.extra_headers), min_gap=0))
    elm.init()
    return elm, prof, now


def read(elm, prof, key):
    p = prof.pids[key]
    return p.formula(elm.read(p.service, p.pid, p.header))


def test_init_and_identity(stack):
    elm, _, _ = stack
    info = elm.info()
    assert "ELM327" in info.elm and "STN" in info.stn and "CAN 11/500" in info.protocol
    assert elm.voltage() == pytest.approx(14.1)
    assert elm.vin() == SIM_VIN


def test_supported_pids(stack):
    s = stack[0].supported_pids()
    assert {0x0C, 0x0D, 0x46, 0x67, 0x78, 0x87, 0x7F} <= s
    assert 0x05 not in s and 0x0B not in s   # like JP's truck


def test_values_scale_through_profile(stack):
    elm, prof, now = stack
    now[0] = 100.0 + 60  # cruise phase of cycle
    assert 95 <= read(elm, prof, "speed") <= 110
    assert 900 < read(elm, prof, "rpm") < 2600
    assert read(elm, prof, "ambient") == 24
    assert read(elm, prof, "odometer") == pytest.approx(182345.6, abs=5)
    assert 20 <= read(elm, prof, "trans_temp") <= 90
    egts = [read(elm, prof, k) for k in ("egt11", "egt12", "egt13", "egt14")]
    assert egts == sorted(egts, reverse=True)
    assert 0 < read(elm, prof, "vgt_actual") <= 100
    assert 20 <= read(elm, prof, "coolant2") <= 90
    assert read(elm, prof, "engine_hours") == pytest.approx(3712.4, abs=0.1)
    assert read(elm, prof, "def_level") == pytest.approx(72, abs=0.5)


def test_unsupported_paths(stack):
    elm, prof, _ = stack
    with pytest.raises(NoData):
        elm.read("01", "05")                 # 0105 unsupported, like the truck
    with pytest.raises(NegativeResponse):
        elm.read("22", "1234", "7E0")        # unknown DID -> NRC 31


def test_pcm_reads_after_cluster_read(stack):
    """Regression (truck 2026-11-07): after a 720 read, PCM reads must still work."""
    elm, prof, now = stack
    read(elm, prof, "odometer")            # header 720, filter 728
    assert read(elm, prof, "fuel_level") > 0   # back to PCM: filter must move to 7E8
    read(elm, prof, "trans_temp")          # 7E1
    assert read(elm, prof, "rpm") > 0


def test_multiframe_pids_complete(stack):
    """Regression (truck 2026-11-07): 017F and 016D cut off after first frame."""
    elm, prof, _ = stack
    from core.bus import Bus
    from core.poller import Poller

    bus = Bus()
    Poller(elm, prof, bus, keys=["engine_hours", "rail_actual", "egt14", "rpm"]).cycle()
    got = bus.latest()
    assert all(got[k].error == "" for k in got), {k: got[k].error for k in got}
    assert got["engine_hours"].value == pytest.approx(3712.4, abs=0.1)


def _scen(name):
    now = [0.0]
    prof = load_profile("ford_f250_67_2014")
    sim = SimTransport(SimVehicle(clock=lambda: now[0], scenario=name))
    elm = Elm(GuardedPort(sim, RequestGuard(extra_headers=prof.extra_headers), min_gap=0))
    elm.init()
    return elm, prof, now


def _boost_psi(elm, prof):
    return (read(elm, prof, "map_wide") - read(elm, prof, "baro")) * 0.145038


def test_scenario_normal_and_hard():
    elm, prof, now = _scen("normal")
    now[0] = 1.0
    assert read(elm, prof, "speed") == 0 and read(elm, prof, "rpm") >= 690       # idle 3 s
    now[0] = 40.0
    assert abs(read(elm, prof, "speed") * 0.621371 - 75) < 1.5                  # cruising at 75
    assert read(elm, prof, "mil") == 0
    elm, prof, now = _scen("hard")
    now[0] = 18.5
    assert read(elm, prof, "speed") * 0.621371 > 100                            # top of the pull
    for t in range(4, 19):
        now[0] = float(t)
        assert read(elm, prof, "rpm") < 3000 and _boost_psi(elm, prof) < 20     # hard, but under the red lines
    now[0] = 40.0
    assert abs(read(elm, prof, "speed") * 0.621371 - 75) < 1.5


def test_scenario_problems_show_up():
    elm, prof, now = _scen("overheat")
    now[0] = 60.0
    assert read(elm, prof, "coolant") * 9 / 5 + 32 > 235                        # past the coolant red line
    elm, prof, now = _scen("overboost")
    peak_b = peak_r = 0
    for t in range(3, 17):
        now[0] = float(t)
        peak_b, peak_r = max(peak_b, _boost_psi(elm, prof)), max(peak_r, read(elm, prof, "rpm"))
    assert peak_b > 20 and peak_r > 3000
    elm, prof, now = _scen("vgt")
    now[0] = 40.0
    assert read(elm, prof, "vgt_desired") - read(elm, prof, "vgt_actual") > 10
    elm, prof, now = _scen("cel")
    now[0] = 10.0
    assert read(elm, prof, "mil") == 1 and read(elm, prof, "dtc_count") == 2
    elm, prof, now = _scen("dropout")
    now[0] = 10.0
    read(elm, prof, "trans_temp")
    now[0] = 25.0
    with pytest.raises(NoData):
        read(elm, prof, "trans_temp")
    assert read(elm, prof, "rpm") > 0                                           # everything else still answers
    elm, prof, now = _scen("signal")
    now[0] = 40.0
    with pytest.raises(NoData):
        read(elm, prof, "rpm")


def test_coolant_and_trans_are_separate():
    elm, prof, now = _scen("normal")
    now[0] = 10.0
    assert abs(read(elm, prof, "coolant") - 88) < 1 and abs(read(elm, prof, "trans_temp") - 77) < 1
