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
    assert "classic" in [t["id"] for t in list_themes()]
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


def _meta(profile="ford_f250_67_2014", skipped=()):
    from core.profile import load_profile
    from core.service import channel_info

    p = load_profile(profile)
    return {"profile": p.id, "name": p.name, "gaugeworks": p.gaugeworks, "channels": channel_info(p),
            "layouts": p.layouts, "skipped": list(skipped)}


def test_build_pages_defaults_and_overrides():
    from gaugeworks.backend import build_pages

    meta = _meta()
    pages = build_pages(meta, True, 10, {})
    assert [p["name"] for p in pages] == ["Daily", "Towing", "Economy", "Diagnostic"]
    daily = pages[0]
    assert daily["slots"]["center"]["key"] == "rpm" and daily["slots"]["center"]["max"] == 5000
    assert daily["slots"]["panel"]["dual"] is True                     # VGT
    assert daily["tiles"][3]["label"] == "Last 10"
    pages = build_pages(meta, True, 25, {"Daily": {"right": "egt11", "tile0": "battery"}})
    d = pages[0]
    assert d["slots"]["right"]["key"] == "egt11" and d["custom"] is True
    assert d["slots"]["right"]["max"] > d["slots"]["right"]["min"]     # auto range (no display entry)
    assert d["tiles"][0]["key"] == "battery" and d["tiles"][3]["label"] == "Last 25"
    assert pages[1]["custom"] is False                                 # overrides are per page


def test_picker_hides_unsupported():
    from gaugeworks.backend import picker_channels

    keys = {c["key"] for c in picker_channels(_meta(skipped=["map"]))}
    assert "map" not in keys and "map_wide" in keys and "econ_last" in keys


@pytest.mark.parametrize("page", [0, 1, 2, 3])
def test_render_every_page(tmp_path, page):
    out = tmp_path / f"p{page}.png"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
           "JPCAN_CONFIG": str(tmp_path)}
    r = subprocess.run([sys.executable, "-m", "gaugeworks.app", "--demo", "cruise", "--page", str(page),
                        "--screenshot", str(out)], env=env, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 and "libEGL" in r.stderr:
        pytest.skip("no GL libs in this environment")
    assert r.returncode == 0, r.stderr[-2000:]


def test_all_themes_load():
    from gaugeworks.backend import list_themes, load_theme

    themes = list_themes()
    ids = [t["id"] for t in themes]
    assert ids[:6] == ["classic", "classic_refined", "modern", "race", "night", "turbo_snail"]
    for t in themes:
        th = load_theme(t["id"])
        assert th["style"]["gauge"] in ("needle", "arc")
        for k in ("background", "text", "accent", "warn", "alarm", "panel"):
            assert k in th["colors"], (t["id"], k)
        from pathlib import Path
        from urllib.parse import urlparse
        for url in [th["face"], *th.get("assets", {}).values()]:
            assert Path(urlparse(url).path).exists(), (t["id"], url)
    assert load_theme("turbo_snail")["assets"].keys() >= {"snail", "flame", "leaf"}


@pytest.mark.parametrize("theme", ["classic_refined", "modern", "race", "night", "turbo_snail"])
def test_render_every_theme(tmp_path, theme):
    out = tmp_path / f"{theme}.png"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
           "JPCAN_CONFIG": str(tmp_path)}
    r = subprocess.run([sys.executable, "-m", "gaugeworks.app", "--demo", "alarm", "--theme", theme,
                        "--screenshot", str(out)], env=env, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 and "libEGL" in r.stderr:
        pytest.skip("no GL libs in this environment")
    assert r.returncode == 0, r.stderr[-2000:]
