import pytest

from core.didscan import Watcher, parse_ranges, scan
from core.elm import Elm
from core.guard import GuardViolation, RequestGuard
from core.profile import load_profile
from core.sim import SimTransport, SimVehicle
from core.transport import GuardedPort


def test_parse_ranges():
    assert parse_ranges(["1E10-1E12", "1674", "1E11"]) == [0x1E10, 0x1E11, 0x1E12, 0x1674][:0] + sorted(
        {0x1E10, 0x1E11, 0x1E12, 0x1674})
    with pytest.raises(ValueError):
        parse_ranges(["0000-FFFF"])          # too many in one run
    with pytest.raises(ValueError):
        parse_ranges(["1E20-1E10"])


def make(now):
    prof = load_profile("ford_f250_67_2014")
    sim = SimTransport(SimVehicle(clock=lambda: now[0]))
    sent = []
    orig = sim.write
    sim.write = lambda d: (sent.append(d.decode().strip()), orig(d))[1]
    elm = Elm(GuardedPort(sim, RequestGuard(extra_headers=prof.extra_headers), min_gap=0))
    elm.init()
    return elm, prof, sent


def test_scan_finds_dids_and_only_reads():
    now = [100.0]
    elm, _, sent = make(now)
    sent.clear()
    res = {r.did: r for r in scan(elm, "7E1", parse_ranges(["1E00-1E2F"]))}
    assert res[0x1E12].status == "ok" and res[0x1E1C].status == "ok"
    assert res[0x1E00].status == "nrc" and res[0x1E00].nrc == 0x31
    obd = [c for c in sent if not c.startswith(("AT", "ST"))]
    assert obd and all(c.startswith("22") for c in obd)          # service 22 only


def test_scan_header_must_be_allowed():
    now = [100.0]
    elm, _, _ = make(now)
    with pytest.raises(GuardViolation):
        scan(elm, "7A0", [0x1E12])                                  # not in allowlist


def test_watch_ranks_gear_did_first():
    from core.gear import GearEstimator  # noqa: F401

    now = [100.0]
    elm, prof, _ = make(now)

    class SimGear:  # estimator that agrees with the simulator's own gear model
        def __init__(self, v):
            self.v = v

        def estimate(self, rpm, kmh):
            g = self.v.state()["gear"]
            return (g or None), None

    w = Watcher(elm, "7E1", [0x1E10, 0x1E12, 0x1E23], prof.obd_header,
                SimGear(elm.port._GuardedPort__raw.v))
    for t in range(20, 100, 3):                                   # through accel + cruise
        now[0] = 100.0 + t
        w.cycle()
    best = w.ranked()[0]
    assert best.did == 0x1E12 and best.gear_match > 0.9
