import os
from types import SimpleNamespace

from gaugeworks.touchwatch import TouchWatchdog


def fake_stat(state):
    def stat(path):
        if state["ino"] is None:
            raise FileNotFoundError(path)
        return SimpleNamespace(st_ino=state["ino"], st_rdev=1)
    return stat


def test_normal_taps_are_fine():
    st = {"ino": 7}
    wd = TouchWatchdog("/dev/input/event5", stat=fake_stat(st))
    for _ in range(20):
        wd.on_qt_press()   # press reaches Qt first...
        wd.on_raw_tap()    # ...raw tap is counted on release
    assert wd.check() == ""


def test_taps_that_never_reach_qt_trip_it():
    wd = TouchWatchdog("/dev/input/event5", stat=fake_stat({"ino": 7}))
    wd.on_qt_press(); wd.on_raw_tap()
    wd.on_raw_tap(); wd.on_raw_tap()
    assert wd.check() == ""
    wd.on_raw_tap()
    assert "never reached" in wd.check()


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
