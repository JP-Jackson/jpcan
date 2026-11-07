import math

from core.bus import Bus, Reading
from core.gear import GearEstimator

CFG = {"ratios": [3.97, 2.32, 1.52, 1.15, 0.86, 0.67], "axle": 3.55, "tire_diameter_in": 33.2}


def rpm_for(gear, kmh):
    wheel_rpm = (kmh / 3.6) / (math.pi * 33.2 * 0.0254) * 60
    return wheel_rpm * 3.55 * CFG["ratios"][gear - 1]


def test_each_gear_and_stopped():
    est = GearEstimator(Bus(), CFG)
    for g, kmh in [(1, 15), (2, 30), (3, 45), (4, 60), (5, 90), (6, 110)]:
        assert est.estimate(rpm_for(g, kmh), kmh)[0] == g
    assert est.estimate(700, 0)[0] is None
    assert est.estimate(rpm_for(4, 60) * 1.15, 60)[0] is None  # between 3rd and 4th: mid-shift


def test_publishes_and_holds_briefly():
    bus, t = Bus(), [0.0]
    GearEstimator(bus, CFG, clock=lambda: t[0])
    bus.publish(Reading("rpm", rpm_for(3, 45), "rpm", 0))
    bus.publish(Reading("speed", 45, "km/h", 0))
    assert bus.latest()["gear"].value == 3
    t[0] = 0.5
    bus.publish(Reading("rpm", rpm_for(3, 45) * 1.25, "rpm", 0))  # between 2nd and 3rd
    bus.publish(Reading("speed", 45, "km/h", 0))
    assert bus.latest()["gear"].value == 3                         # held
    t[0] = 2.0
    bus.publish(Reading("speed", 45, "km/h", 0))
    assert bus.latest()["gear"].value is None
