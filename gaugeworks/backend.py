"""GaugeWorks backend: turns feed data (MQTT or in-process) into display values
and layout config for QML. Read-only: the only action that leaves this process
is the trip-reset message; nothing here can reach the adapter.
"""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtQml import QQmlPropertyMap

from core import settings as settings_mod
from core.units import IMPERIAL, display

THEMES_DIR = Path(__file__).resolve().parent / "themes"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
STALE = 5.0  # s


# ---- pure helpers (unit-tested without Qt) ---------------------------------
def nice_step(span: float, target: int = 6) -> float:
    if span <= 0:
        return 1.0
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            return m * mag
    return 10 * mag


def _imperial_to_metric(v: float | None, native: str) -> float | None:
    """Imperial display value -> native/metric value (all conversions are linear)."""
    if v is None or native not in IMPERIAL:
        return v
    f = IMPERIAL[native][1]
    b = f(0.0)
    a = f(1.0) - b
    return (v - b) / a


def gauge_config(g: dict, native: str, imperial: bool) -> dict:
    """Layout entry (imperial display units) -> config in the active unit system."""
    _, units = display(0.0, native, imperial)
    c = {
        "key": g.get("key", ""), "label": g.get("label", ""), "units": units,
        "min": float(g.get("min", 0)), "max": float(g.get("max", 100)),
        "major": float(g.get("major", 0)) or 0.0, "minor": int(g.get("minor", 5)),
        "warn": g.get("warn"), "alarm": g.get("alarm"),
        "scale": float(g.get("scale", 1)), "scaleLabel": g.get("scale_label", ""),
    }
    if not imperial and native in IMPERIAL:
        for k in ("min", "max", "warn", "alarm"):
            c[k] = _imperial_to_metric(c[k], native)
        step = nice_step(c["max"] - c["min"])
        c["min"] = math.floor(c["min"] / step + 1e-9) * step
        c["max"] = math.ceil(c["max"] / step - 1e-9) * step
        c["major"] = step
    if not c["major"]:
        c["major"] = nice_step(c["max"] - c["min"])
    c["decimals"] = 0 if (c["max"] - c["min"]) * c["scale"] >= 100 or c["scale"] != 1 else 1
    for k in ("warn", "alarm"):
        c[k] = float("nan") if c[k] is None else float(c[k])
    return c


def tile_config(key: str, info: dict, imperial: bool) -> dict:
    _, units = display(0.0, info.get("units", ""), imperial)
    if key == "trip_dist":
        decimals = 1
    elif units in ("mpg", "km/L", "V", "gal/h", "L/h", "psig", "psia", "psi", "kPa"):
        decimals = 1
    else:
        decimals = 0
    label = info.get("short") or key
    if key in ("econ_inst", "econ_avg") and units != "mpg":
        label = "Economy" if key == "econ_inst" else "Avg econ"
    return {"key": key, "label": label, "units": units, "decimals": decimals,
            "verified": bool(info.get("verified", True))}


def load_theme(name: str, themes_dir: Path = THEMES_DIR) -> dict:
    d = themes_dir / name
    if not (d / "theme.json").exists():
        d = themes_dir / "classic"
    t = json.loads((d / "theme.json").read_text(encoding="utf-8"))
    for k in ("face", "needle"):
        if k in t:
            t[k] = QUrl.fromLocalFile(str(d / t[k])).toString()
    t["id"] = d.name
    return t


def list_themes(themes_dir: Path = THEMES_DIR) -> list[str]:
    return sorted(p.parent.name for p in themes_dir.glob("*/theme.json"))


# ---- Qt backend -------------------------------------------------------------
class Backend(QObject):
    configChanged = Signal()
    themeChanged = Signal()
    statusChanged = Signal()
    settingsChanged = Signal()
    message = Signal(str)

    def __init__(self, feed, settings: dict | None = None, poll_ms: int = 50):
        super().__init__()
        self.feed = feed
        self._settings = settings if settings is not None else settings_mod.load()
        self._values = QQmlPropertyMap(self)
        self._fresh = QQmlPropertyMap(self)
        self._config: dict = {"gauges": {}, "tiles": []}
        self._theme = load_theme(self._settings.get("theme", "classic"))
        self._status = {"state": "offline", "text": "Starting...", "mode": ""}
        self._meta_sig = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)
        self._timer.start(poll_ms)
        self.tick()

    # -- properties
    def _get_values(self):
        return self._values

    def _get_fresh(self):
        return self._fresh

    values = Property(QObject, _get_values, constant=True)
    fresh = Property(QObject, _get_fresh, constant=True)
    config = Property("QVariantMap", lambda self: self._config, notify=configChanged)
    theme = Property("QVariantMap", lambda self: self._theme, notify=themeChanged)
    status = Property("QVariantMap", lambda self: self._status, notify=statusChanged)
    imperial = Property(bool, lambda self: self._settings.get("units", "imperial") == "imperial",
                        notify=settingsChanged)
    themes = Property("QVariantList", lambda self: list_themes(), constant=True)
    splash = Property(str, lambda self: QUrl.fromLocalFile(str(ASSETS_DIR / "jpcan_logo.svg")).toString(),
                      constant=True)

    def _shift(self) -> dict:
        meta_shift = (self.feed.meta or {}).get("shift") or {}
        prof = (self.feed.meta or {}).get("profile", "")
        rpm = self._settings.get("shift_rpm", {}).get(prof, meta_shift.get("rpm", 3000))
        return {"enabled": bool(meta_shift.get("enabled")), "rpm": float(rpm)}

    shift = Property("QVariantMap", lambda self: self._shift(), notify=configChanged)
    econCal = Property(float, lambda self: float((self.feed.status or {}).get("econ_cal", 0.0)),
                       notify=statusChanged)

    # -- periodic update
    @Slot()
    def tick(self) -> None:
        meta = self.feed.meta or {}
        sig = (meta.get("profile"), json.dumps(meta.get("gaugeworks", {}), sort_keys=True),
               self._settings.get("units"), json.dumps(self._settings.get("shift_rpm", {})))
        if sig != self._meta_sig and meta:
            self._meta_sig = sig
            self._rebuild_config(meta)
        self._update_status(meta)
        self._update_values()

    def _rebuild_config(self, meta: dict) -> None:
        imp = self._settings.get("units", "imperial") == "imperial"
        ch = meta.get("channels", {})
        gw = meta.get("gaugeworks") or {}
        gauges = {}
        for name, g in (gw.get("gauges") or {}).items():
            if "desired" in g:  # dual (VGT)
                gauges[name] = {"desired": g["desired"], "actual": g["actual"],
                                "label": g.get("label", name.upper())}
            elif g.get("key") in ch:
                gauges[name] = gauge_config(g, ch[g["key"]].get("units", ""), imp)
        tiles = [tile_config(k, ch.get(k, {}), imp) for k in (gw.get("tiles") or [])]
        self._config = {"gauges": gauges, "tiles": tiles, "profile": meta.get("name", ""),
                        "gear": gw.get("gear", "")}
        self.configChanged.emit()

    def _update_status(self, meta: dict) -> None:
        st = self.feed.status or {}
        state = st.get("state", "offline")
        if not getattr(self.feed, "connected", True):
            state, text = "offline", "No MQTT broker"
        elif state == "running":
            text = f"{st.get('hz', 0):.0f} Hz"
            if st.get("blocked"):
                text += f"  BLOCKED {st['blocked']}"
        else:
            text = " ".join(st.get("lines", [])) or state
        new = {"state": state, "text": text, "mode": "SIM" if meta.get("sim") else "LIVE",
               "profile": meta.get("name", ""), "econ_cal": st.get("econ_cal", 0.0)}
        if new != self._status:
            self._status = new
            self.statusChanged.emit()

    def _update_values(self) -> None:
        imp = self._settings.get("units", "imperial") == "imperial"
        now = time.time()
        running = (self.feed.status or {}).get("state") == "running"
        for k, r in self.feed.bus.latest().items():
            ok = (running and r.value is not None and not r.error and now - r.ts <= STALE)
            v = display(r.value, r.units, imp)[0] if r.value is not None else 0.0
            if self._values.value(k) != v:
                self._values.insert(k, v)
            if self._fresh.value(k) != ok:
                self._fresh.insert(k, ok)

    # -- actions from QML (local only; none reach the adapter)
    def _save(self):
        try:
            settings_mod.save(self._settings)
        except OSError as e:
            self.message.emit(f"Settings not saved: {e}")
        self._meta_sig = None
        self.settingsChanged.emit()
        self.tick()

    @Slot(bool)
    def setImperial(self, imperial: bool) -> None:
        self._settings["units"] = "imperial" if imperial else "metric"
        self._save()

    @Slot(str)
    def setTheme(self, name: str) -> None:
        self._settings["theme"] = name
        self._theme = load_theme(name)
        self.themeChanged.emit()
        self._save()

    @Slot(int)
    def adjustShift(self, delta: int) -> None:
        prof = (self.feed.meta or {}).get("profile", "")
        rpm = int(self._shift()["rpm"]) + delta
        self._settings.setdefault("shift_rpm", {})[prof] = max(1000, min(8000, rpm))
        self._save()
        self.configChanged.emit()

    @Slot(int)
    def adjustEcon(self, delta: int) -> None:
        """MPG adjust: the core applies and saves it, so every screen agrees."""
        if hasattr(self.feed, "set_econ_cal"):
            pct = max(-30.0, min(30.0, float((self.feed.status or {}).get("econ_cal", 0.0)) + delta))
            self.feed.set_econ_cal(pct)

    @Slot()
    def tripReset(self) -> None:
        if hasattr(self.feed, "trip_reset"):
            self.feed.trip_reset()
            self.message.emit("Trip reset")

    @Slot()
    def shutdown(self) -> None:
        r = subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.message.emit("Shutdown not permitted here")
