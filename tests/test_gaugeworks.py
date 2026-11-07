"""GaugeWorks: pure helpers, and a full offscreen render of every demo scene."""

import math
import os
import subprocess
import sys

import pytest

pytest.importorskip("PySide6")

from gaugeworks.backend import gauge_config, list_themes, load_theme, nice_step, tile_config  # noqa: E402


def test_nice_step():
    assert nice_step(100) == 20
    assert nice_step(276) == 50
    assert nice_step(4000) == 1000


def test_gauge_config_imperial_passthrough():
    g = {"key": "boost", "min": 0, "max": 40, "major": 5, "warn": 33, "alarm": 38, "label": "BOOST"}
    c = gauge_config(g, "kPag", imperial=True)
    assert (c["min"], c["max"], c["major"], c["units"]) == (0, 40, 5, "psig")
    assert c["warn"] == 33 and c["decimals"] == 1


def test_gauge_config_metric_converts_range_and_thresholds():
    g = {"key": "coolant", "min": 100, "max": 260, "major": 40, "warn": 225, "alarm": 235}
    c = gauge_config(g, "°C", imperial=False)
    assert c["units"] == "°C"
    assert c["warn"] == pytest.approx((225 - 32) * 5 / 9)
    assert c["min"] <= (100 - 32) * 5 / 9 and c["max"] >= (260 - 32) * 5 / 9
    assert math.isnan(gauge_config({"key": "x"}, "", True)["warn"])


def test_tile_labels_follow_units():
    assert tile_config("econ_tank", {"short": "Tank", "units": "km/L"}, True)["label"] == "Tank"
    assert tile_config("econ_last", {"short": "Last 10", "units": "km/L"}, True, 25)["label"] == "Last 25"
    assert tile_config("econ_inst", {"short": "MPG", "units": "km/L"}, False)["label"] == "Economy"
    assert tile_config("econ_tank", {"units": "km/L"}, True)["econ"] is True


def test_theme_loads():
    assert "classic" in list_themes()
    t = load_theme("does-not-exist")
    assert t["id"] == "classic" and t["face"].startswith("file://")


@pytest.mark.parametrize("scene", ["cruise", "alarm", "shift"])
def test_render_scene_without_qml_errors(tmp_path, scene):
    out = tmp_path / f"{scene}.png"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
           "JPCAN_CONFIG": str(tmp_path)}
    r = subprocess.run([sys.executable, "-m", "gaugeworks.app", "--demo", scene, "--screenshot", str(out)],
                       env=env, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 and "libEGL" in r.stderr:
        pytest.skip("no GL libs in this environment")
    assert r.returncode == 0, r.stderr[-2000:]
    assert out.stat().st_size > 50_000
