"""GaugeWorks: pure helpers, and a full offscreen render of every demo scene."""

import math
import os
import subprocess
import sys
from pathlib import Path

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
    assert ids[:7] == ["oem", "classic", "classic_refined", "modern", "race", "night", "turbo_snail"]
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


@pytest.mark.parametrize("theme", ["oem", "classic_refined", "modern", "race", "night", "turbo_snail"])
def test_render_every_theme(tmp_path, theme):
    out = tmp_path / f"{theme}.png"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
           "JPCAN_CONFIG": str(tmp_path)}
    r = subprocess.run([sys.executable, "-m", "gaugeworks.app", "--demo", "alarm", "--theme", theme,
                        "--screenshot", str(out)], env=env, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 and "libEGL" in r.stderr:
        pytest.skip("no GL libs in this environment")
    assert r.returncode == 0, r.stderr[-2000:]


def test_theme_skin_pages_override_and_fallback(tmp_path):
    from gaugeworks.backend import QML_DIR, page_sources

    (tmp_path / "skinny" / "qml").mkdir(parents=True)
    (tmp_path / "skinny" / "qml" / "PageDash.qml").write_text("import QtQuick\nItem {}\n")
    src = page_sources("skinny", tmp_path)
    assert src["dash"].endswith("/skinny/qml/PageDash.qml")          # theme's own layout
    assert src["quad"].endswith(str(QML_DIR / "PageQuad.qml"))       # standard fallback
    assert set(src) == {"dash", "quad", "economy", "list", "towing"}


def test_towing_page_limits_and_split():
    from gaugeworks.backend import build_pages, limit_info, to_imperial

    meta = _meta()
    tow = build_pages(meta, True, 10, {})[1]
    assert tow["template"] == "towing"
    s = tow["slots"]
    assert s["center"]["key"] == "speed" and s["ring"]["key"] == "rpm" and s["inner"]["key"] == "boost"
    assert s["ring"]["alarm"] == 3000 and s["ring"]["split"] == 3000
    assert s["inner"]["alarm"] == 20 and s["inner"]["split"] == 20
    assert s["r4"]["dual"] is True                                   # VGT: commanded and actual
    # a red line JP set overrides the profile, per reading
    tow = build_pages(meta, True, 10, {}, {"trans_temp": 225, "rpm": 2800})[1]["slots"]
    assert tow["l2"]["alarm"] == 225 and tow["ring"]["alarm"] == 2800 and tow["box1"]["alarm"] == 2800
    li = limit_info(meta, "boost", True, {})
    assert li["value"] == 20 and li["step"] > 0 and li["custom"] is False
    assert limit_info(meta, "rpm", True, {"rpm": 2800})["custom"] is True
    # metric: limits are stored in imperial; a typed °C value converts back to °F
    assert abs(to_imperial(100.0, "°C", False) - 212.0) < 1e-9
    assert to_imperial(212.0, "°C", True) == 212.0
    met = build_pages(meta, False, 10, {}, {"trans_temp": 212})[1]["slots"]
    assert abs(met["l2"]["alarm"] - 100.0) < 1e-6


def test_backend_red_lines_colors_background_and_drive_minmax(tmp_path, monkeypatch):
    monkeypatch.setenv("JPCAN_CONFIG", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    from core import settings as settings_mod
    from gaugeworks.app import DemoFeed
    from gaugeworks.backend import Backend

    b = Backend(DemoFeed("cruise", "ford_f250_67_2014"), {**settings_mod.DEFAULTS}, poll_ms=10_000)
    # red lines: per reading, per vehicle, survive a reload
    assert b.limitFor("trans_temp")["value"] == 240 and not b.limitFor("trans_temp")["custom"]
    b.setLimit("trans_temp", 225)
    assert b.limitFor("trans_temp")["value"] == 225 and b.limitFor("trans_temp")["custom"]
    assert settings_mod.load()["limits"]["ford_f250_67_2014"]["trans_temp"] == 225
    tow = b._config["pages"][1]["slots"]
    assert tow["l2"]["alarm"] == 225
    b.resetLimit("trans_temp")
    assert b.limitFor("trans_temp")["value"] == 240
    # metric: a typed °C red line is stored as °F
    b.setImperial(False)
    b.setLimit("coolant", 110.0)
    assert abs(settings_mod.load()["limits"]["ford_f250_67_2014"]["coolant"] - 230.0) < 1e-6
    b.setImperial(True)
    # appearance
    assert b.background == "carbon" and b.backgroundUrl.endswith("/bg/carbon.png")
    b.setBackground("diamond")
    assert b.background == "diamond"
    b.setBackground("plaid")                       # not a choice: ignored
    assert b.background == "diamond"
    b.setAccent(0, "#12AB34")
    assert b.accent == "#12ab34"
    b.setAccent(1, "red")                          # not a hex color: ignored
    assert b.accent2 == "#ffb340"
    b.resetColors()
    assert b.accent == "#29c4ff"
    # this drive's min/max follow the readings
    assert b.lo.value("rpm") == 1650 and b.hi.value("rpm") == 1650
    b.resetDriveMinMax()
    assert b.lo.value("rpm") is None


def test_stale_timeout_follows_each_readings_update_rate():
    from gaugeworks.backend import STALE, stale_after, track_gap

    assert stale_after(None) == STALE                       # nothing learned yet
    assert stale_after(0.13) == STALE                       # fast tier: still 5 s minimum
    gap = None
    t = 0.0
    for _ in range(10):                                     # slow tier: every ~5.2 s
        gap = track_gap(t, t + 5.2, gap)
        t += 5.2
    assert abs(gap - 5.2) < 0.01 and stale_after(gap) > 12  # 5.6 s gaps no longer blank it
    assert track_gap(t, t + 300, gap) == gap                # key-off gap isn't learned
    assert track_gap(t, t, gap) == gap                      # same reading seen again


def test_long_press_survives_finger_drift():
    """A finger drifting ~12-20 px during a press-and-hold must still open the picker;
    the page swipe used to take the touch at Qt's ~10 px default."""
    src = (Path(__file__).resolve().parent.parent / "gaugeworks" / "app.py").read_text()
    assert "setStartDragDistance(30)" in src


def test_edit_mode_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("JPCAN_CONFIG", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    from core import settings as settings_mod
    from gaugeworks.app import DemoFeed
    from gaugeworks.backend import Backend

    b = Backend(DemoFeed("cruise", "ford_f250_67_2014"), {**settings_mod.DEFAULTS}, poll_ms=10_000)
    seen = []
    b.editModeChanged.connect(lambda: seen.append(b.editMode))
    assert b.editMode is False
    b.setEditMode(True)
    b.setEditMode(True)                 # no repeat signal
    b.setEditMode(False)
    assert seen == [True, False]
    assert "editMode" not in settings_mod.load()   # not saved: always off after a restart


def test_sim_scenario_pick_is_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("JPCAN_CONFIG", str(tmp_path))
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    from core import settings as settings_mod
    from gaugeworks.app import DemoFeed
    from gaugeworks.backend import Backend

    b = Backend(DemoFeed("cruise", "ford_f250_67_2014"), {**settings_mod.DEFAULTS}, poll_ms=10_000)
    keys = [s["key"] for s in b.simScenarios]
    assert {"cycle", "normal", "hard", "overheat", "signal"} <= set(keys)
    started = []
    monkeypatch.setattr(b, "setSource", lambda mode: started.append(mode))
    b.setSimScenario("overheat")
    assert settings_mod.load()["sim_scenario"] == "overheat" and started == ["sim"]
    b.setSimScenario("nope")                         # not a scenario: ignored
    assert settings_mod.load()["sim_scenario"] == "overheat" and started == ["sim"]
