from core.touch import Tap, calibrate, horizontal

R = {"x": (0, 4095), "y": (0, 4095)}


def test_calibrate_x_normal():
    cal = calibrate(Tap(200, 2000, R), Tap(3900, 2100, R))
    assert cal == {"axis": "x", "invert": False}
    assert horizontal(Tap(300, 0, R), cal) < 0.5 < horizontal(Tap(3800, 0, R), cal)


def test_calibrate_y_inverted():
    cal = calibrate(Tap(2000, 3800, R), Tap(2050, 300, R))
    assert cal == {"axis": "y", "invert": True}
    assert horizontal(Tap(0, 3700, R), cal) < 0.5   # left
    assert horizontal(Tap(0, 400, R), cal) > 0.5    # right


def test_uncalibrated():
    assert horizontal(Tap(1, 1, R), {"axis": None}) is None


def test_settings_roundtrip(tmp_path, monkeypatch):
    from core import settings

    monkeypatch.setenv("JPCAN_CONFIG", str(tmp_path))
    s = settings.load()
    assert s["touch"]["axis"] is None
    s["touch"] = {"axis": "y", "invert": True}
    settings.save(s)
    assert settings.load()["touch"] == {"axis": "y", "invert": True}
