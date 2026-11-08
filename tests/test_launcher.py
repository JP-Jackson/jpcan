"""The GaugeWorks launcher's Qt input setup (D25, D27)."""

import re
from pathlib import Path

LAUNCH = (Path(__file__).resolve().parent.parent / "scripts" / "gaugeworks-launch.sh").read_text()
CODE = "\n".join(l for l in LAUNCH.splitlines() if not l.lstrip().startswith("#"))


def test_no_input_handler_on_dev_null():
    # /dev/null reads EOF forever: Qt spins at 100% CPU and touch locks up.
    assert not re.search(r"QT_QPA_\w+=.*?/dev/null", CODE)


def test_one_touch_handler_with_builtin_input_off():
    assert 'QT_QPA_EGLFS_DISABLE_INPUT=1' in CODE
    assert 'QT_QPA_FB_DISABLE_INPUT=1' in CODE
    assert 'QT_QPA_GENERIC_PLUGINS="evdevtouch:${TOUCH}"' in CODE
    assert "export QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS" not in CODE
    assert "export QT_QPA_EVDEV_MOUSE_PARAMETERS" not in CODE


def test_watchdog_gets_the_touch_path():
    assert 'GAUGEWORKS_TOUCH="${TOUCH}"' in CODE
