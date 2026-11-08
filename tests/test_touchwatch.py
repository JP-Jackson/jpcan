import os
from types import SimpleNamespace

from gaugeworks.touchwatch import TouchWatchdog


def fake_stat(state):
    def stat(path):
        if state["ino"] is None:
            raise FileNotFoundError(path)
        return SimpleNamespace(st_ino=state["ino"], st_rdev=1)
    return stat


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_normal_taps_are_fine():
    st = {"ino": 7}
    clk = Clock()
    wd = TouchWatchdog("/dev/input/event5", stat=fake_stat(st), clock=clk)
    for _ in range(20):
        wd.on_qt_press()   # press reaches Qt first...
        wd.on_raw_tap()    # ...raw tap is counted on release
        clk.t += 1
    assert wd.check() == ""
    for _ in range(5):     # a busy GUI thread: Qt sees the presses after the releases
        wd.on_raw_tap()
        wd.on_qt_press()
        clk.t += 10
    assert wd.check() == ""


def test_taps_that_never_reach_qt_trip_it():
    clk = Clock()
    wd = TouchWatchdog("/dev/input/event5", stat=fake_stat({"ino": 7}), clock=clk)
    wd.on_qt_press(); wd.on_raw_tap()
    for _ in range(3):
        wd.on_raw_tap()
    assert wd.check() == ""          # within the grace period: Qt may just be busy
    clk.t += 1
    assert wd.check() == ""
    clk.t += 3
    wd.on_qt_event("update")
    msg = wd.check()
    assert "never reached" in msg and "update=1" in msg


def test_late_qt_press_clears_the_backlog():
    clk = Clock()
    wd = TouchWatchdog("/dev/input/event5", stat=fake_stat({"ino": 7}), clock=clk)
    for _ in range(3):
        wd.on_raw_tap()
    clk.t += 2
    wd.on_qt_press()                 # Qt caught up
    clk.t += 5
    assert wd.check() == ""


def test_device_gone_or_recreated():
    st = {"ino": 7}
    wd = TouchWatchdog("/dev/input/event5", stat=fake_stat(st))
    st["ino"] = None
    assert "gone" in wd.check()
    st["ino"] = 8
    assert "re-created" in wd.check()


def test_real_stat_on_a_file(tmp_path):
    f = tmp_path / "ev"
    f.write_text("")
    wd = TouchWatchdog(str(f))
    assert wd.check() == ""
    os.remove(f)
    assert "gone" in wd.check()


NAME = "wch.cn USB2IIC_CTP_CONTROL"


def named(state, where):
    """Watchdog following NAME; `where["path"]` is where locate() finds it (None = off the bus)."""
    return TouchWatchdog("/dev/input/event1", NAME, stat=fake_stat(state),
                         locate_fn=lambda n: where["path"] if n == NAME else None)


def test_drop_then_new_node_restarts():
    st, where = {"ino": 7}, {"path": "/dev/input/event1"}
    wd = named(st, where)
    assert wd.check() == ""
    st["ino"], where["path"] = None, None          # off the bus: keep running, no restart
    assert wd.check() == ""
    where["path"] = "/dev/input/event3"            # back, as a new node
    assert "moved" in wd.check()


def test_drop_and_back_on_same_node_restarts():
    st, where = {"ino": 7}, {"path": "/dev/input/event1"}
    wd = named(st, where)
    st["ino"] = None; where["path"] = None
    assert wd.check() == ""
    st["ino"] = 9; where["path"] = "/dev/input/event1"
    assert "re-created" in wd.check()


def test_missing_at_start_then_appears():
    st, where = {"ino": None}, {"path": None}
    wd = named(st, where)
    assert wd.check() == ""
    st["ino"] = 4; where["path"] = "/dev/input/event1"
    assert wd.check() != ""


def test_locate_by_name(tmp_path):
    from gaugeworks.touchwatch import locate

    for n, name in ((0, "ADS7846 Touchscreen"), (5, NAME), (12, NAME)):
        d = tmp_path / f"event{n}" / "device"
        d.mkdir(parents=True)
        (d / "name").write_text(name + "\n")
    assert locate(NAME, str(tmp_path)) == "/dev/input/event5"
    assert locate("nope", str(tmp_path)) is None
