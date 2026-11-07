"""GaugeWorks backend: turns feed data (MQTT or in-process) into display values
and layout config for QML. Read-only: the only action that leaves this process
is the trip-reset message; nothing here can reach the adapter.
"""

from __future__ import annotations

import json
import math
import subprocess
import threading
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


def tile_config(key: str, info: dict, imperial: bool, window_mi: int = 10) -> dict:
    _, units = display(0.0, info.get("units", ""), imperial)
    if key == "trip_dist":
        decimals = 1
    elif units in ("mpg", "km/L", "V", "gal/h", "L/h", "psig", "psia", "psi", "kPa"):
        decimals = 1
    else:
        decimals = 0
    label = info.get("short") or key
    if key == "econ_last":
        label = f"Last {window_mi}" if imperial else f"Last {round(window_mi * 1.609)} km"
    elif key == "econ_inst" and units != "mpg":
        label = "Economy"
    return {"key": key, "label": label, "units": units, "decimals": decimals,
            "verified": bool(info.get("verified", True)), "econ": key.startswith("econ_")}


def auto_display(key: str, info: dict) -> dict:
    """Gauge settings for a channel with no `display` entry: its own min/max."""
    native = info.get("units", "")
    lo = display(float(info.get("min", 0)), native, True)[0]
    hi = display(float(info.get("max", 100)), native, True)[0]
    if hi <= lo:
        hi = lo + 1
    return {"min": lo, "max": hi, "major": 0, "minor": 5,
            "label": (info.get("short") or key).upper()}


def build_pages(meta: dict, imperial: bool, window_mi: int, overrides: dict) -> list[dict]:
    """Profile pages + JP's per-slot picks -> concrete config for QML."""
    ch = meta.get("channels", {})
    gw = meta.get("gaugeworks") or {}
    disp = gw.get("display") or {}
    dual = gw.get("dual") or {}

    def slot_cfg(key: str) -> dict:
        if key in dual:
            d = dual[key]
            return {"dual": True, "key": key, "desired": d.get("desired"), "actual": d.get("actual"),
                    "label": d.get("label", key.upper())}
        if key not in ch:
            return {"key": key, "missing": True}
        g = {**(disp.get(key) or auto_display(key, ch[key])), "key": key}
        return {**gauge_config(g, ch[key].get("units", ""), imperial), "verified": ch[key].get("verified", True)}

    def tile_cfg(key: str) -> dict:
        info = ch.get(f"econ_last{window_mi}" if key == "econ_last" else key, {})
        return tile_config(key, info, imperial, window_mi)

    pages = []
    for p in gw.get("pages") or []:
        ov = overrides.get(p.get("name", ""), {})
        slots = {slot: slot_cfg(ov.get(slot, key)) for slot, key in (p.get("slots") or {}).items()}
        tiles = [tile_cfg(ov.get(f"tile{i}", k)) for i, k in enumerate(p.get("tiles") or [])]
        pages.append({"name": p.get("name", ""), "template": p.get("template", "dash"),
                      "slots": slots, "tiles": tiles, "custom": bool(ov)})
    return pages


def picker_channels(meta: dict) -> list[dict]:
    """Channels JP can put in a slot: everything except PIDs this vehicle lacks."""
    ch = meta.get("channels", {})
    skipped = set(meta.get("skipped") or [])
    items = [{"key": k, "label": v.get("short") or k, "name": v.get("name", k),
              "verified": v.get("verified", True)} for k, v in ch.items() if k not in skipped]
    items.append({"key": "econ_last", "label": "Last N", "name": "Rolling economy (Last N)", "verified": True})
    return sorted(items, key=lambda i: i["label"].lower())


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


def fillup_message(res: dict) -> str:
    if res.get("error"):
        return f"Not saved: {res['error']}"
    action = res.get("action")
    if action == "edit":
        return "Fill-up updated"
    if action == "delete":
        return "Fill-up deleted"
    if action == "clear":
        return f"Deleted {res.get('deleted', 0)} fill-ups (backup saved)"
    if res.get("mpg"):
        src = "" if res.get("miles_src") == "odometer" else " (est. miles)"
        return f"Tank: {res['miles']:.0f} mi / {res['gallons']:.1f} gal = {res['mpg']:.1f} mpg{src}"
    return "First fill-up saved. MPG shows after the next one."


# ---- Qt backend -------------------------------------------------------------
class Backend(QObject):
    configChanged = Signal()
    themeChanged = Signal()
    statusChanged = Signal()
    settingsChanged = Signal()
    fuelChanged = Signal()
    usbChanged = Signal()
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
        self._fuel: dict = {}
        self._last_result_ts = None
        self._meta_sig = None
        from .usb import UsbExporter

        self._usb = UsbExporter(lambda: {"status": self.feed.status, "meta": self.feed.meta})
        self._usb_seen: dict = {}
        self._usb_timer = QTimer(self)
        self._usb_timer.timeout.connect(self._usb.poll)
        self._usb_timer.start(2000)
        self._usb.poll()
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
    fuel = Property("QVariantMap", lambda self: self._fuel, notify=fuelChanged)
    econCorrected = Property(bool, lambda self: bool(self._settings.get("econ_corrected")),
                             notify=settingsChanged)
    econWindow = Property(int, lambda self: int(self._settings.get("econ_window_mi", 10)),
                          notify=settingsChanged)
    econFactor = Property(float, lambda self: float(self._fuel.get("factor") or 0.0), notify=fuelChanged)

    def _factor(self) -> float:
        f = self._fuel.get("factor")
        return float(f) if (f and self._settings.get("econ_corrected")) else 1.0

    # -- periodic update
    @Slot()
    def tick(self) -> None:
        meta = self.feed.meta or {}
        sig = (meta.get("profile"), json.dumps(meta.get("gaugeworks", {}), sort_keys=True),
               self._settings.get("units"), json.dumps(self._settings.get("shift_rpm", {})),
               self._settings.get("econ_window_mi"), json.dumps(self._settings.get("slots", {})),
               len(meta.get("channels", {})))
        if sig != self._meta_sig and meta:
            self._meta_sig = sig
            self._rebuild_config(meta)
        self._update_status(meta)
        self._update_fuel()
        self._update_values()
        if self._usb.state != self._usb_seen:
            prev = self._usb_seen
            self._usb_seen = dict(self._usb.state)
            self.usbChanged.emit()
            if self._usb_seen.get("state") in ("done", "error") and prev.get("state") == "exporting":
                self.message.emit(self._usb_seen.get("result", ""))

    def _rebuild_config(self, meta: dict) -> None:
        imp = self._settings.get("units", "imperial") == "imperial"
        ch = meta.get("channels", {})
        gw = meta.get("gaugeworks") or {}
        win = int(self._settings.get("econ_window_mi", 10))
        prof = meta.get("profile", "")
        overrides = (self._settings.get("slots") or {}).get(prof, {})
        pages = build_pages(meta, imp, win, overrides)
        status_keys = (meta.get("layouts") or {}).get("status") or []
        diag = status_keys + sorted(k for k in ch if k not in status_keys)
        self._config = {"pages": pages, "profile": meta.get("name", ""), "gear": gw.get("gear", ""),
                        "channels": picker_channels(meta), "diag": [
                            {"key": k, "name": ch[k].get("name", k),
                             "units": display(0.0, ch[k].get("units", ""), imp)[1],
                             "verified": ch[k].get("verified", True)} for k in diag if k in ch]}
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
               "profile": meta.get("name", "")}
        if new != self._status:
            self._status = new
            self.statusChanged.emit()

    def _update_fuel(self) -> None:
        fuel = getattr(self.feed, "fuel", None) or {}
        if fuel != self._fuel:
            self._fuel = fuel
            self.fuelChanged.emit()
            res = fuel.get("last_result") or {}
            if res.get("ts") and res["ts"] != self._last_result_ts:
                if self._last_result_ts is not None or time.time() - res["ts"] < 30:
                    self.message.emit(fillup_message(res))
                self._last_result_ts = res["ts"]

    def _update_values(self) -> None:
        imp = self._settings.get("units", "imperial") == "imperial"
        now = time.time()
        running = (self.feed.status or {}).get("state") == "running"
        factor = self._factor()
        win = int(self._settings.get("econ_window_mi", 10))
        latest = dict(self.feed.bus.latest())
        if f"econ_last{win}" in latest:
            latest["econ_last"] = latest[f"econ_last{win}"]
        for k, r in latest.items():
            ok = (running and r.value is not None and not r.error and now - r.ts <= STALE)
            raw = r.value * factor if (r.value is not None and k.startswith("econ_")) else r.value
            v = display(raw, r.units, imp)[0] if raw is not None else 0.0
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

    currentPage = Property(int, lambda self: int(self._settings.get("page", 0)), notify=settingsChanged)
    usb = Property("QVariantMap", lambda self: {**self._usb_seen,
                                                "dismissed": self._usb.dismissed == self._usb_seen.get("name")},
                   notify=usbChanged)

    @Slot()
    def exportUsb(self) -> None:
        self._usb.start()

    @Slot()
    def ejectUsb(self) -> None:
        threading.Thread(target=self._usb.eject, daemon=True).start()

    @Slot()
    def dismissUsb(self) -> None:
        self._usb.dismissed = self._usb.state.get("name", "")
        self._usb_seen = {}

    @Slot(int)
    def setPage(self, index: int) -> None:
        if int(self._settings.get("page", 0)) != index:
            self._settings["page"] = int(index)
            try:
                settings_mod.save(self._settings)
            except OSError:
                pass

    @Slot(str, str, str)
    def setSlot(self, page: str, slot: str, key: str) -> None:
        """JP picked a channel for one slot/tile; saved per vehicle profile and page."""
        prof = (self.feed.meta or {}).get("profile", "")
        slots = self._settings.setdefault("slots", {}).setdefault(prof, {}).setdefault(page, {})
        slots[slot] = key
        self._save()

    @Slot(str)
    def resetPage(self, page: str) -> None:
        prof = (self.feed.meta or {}).get("profile", "")
        (self._settings.get("slots") or {}).get(prof, {}).pop(page, None)
        self._save()

    @Slot(bool)
    def setEconCorrected(self, on: bool) -> None:
        self._settings["econ_corrected"] = bool(on)
        self._save()

    @Slot(int)
    def setEconWindow(self, miles: int) -> None:
        self._settings["econ_window_mi"] = int(miles)
        self._save()

    @Slot(int, float, float, float, str)
    def fuelEdit(self, row_id: int, gallons: float, price: float, odo: float, date: str) -> None:
        if not 0.5 <= gallons <= 80:
            self.message.emit("Enter gallons (0.5 - 80)")
            return
        if hasattr(self.feed, "fuel_edit"):
            self.feed.fuel_edit({"action": "edit", "id": int(row_id), "gallons": round(gallons, 3),
                                 "price": round(price, 3), "odo_mi": odo if odo > 0 else None,
                                 "date": date or None})

    @Slot(int)
    def fuelDelete(self, row_id: int) -> None:
        if hasattr(self.feed, "fuel_edit"):
            self.feed.fuel_edit({"action": "delete", "id": int(row_id)})

    @Slot()
    def fuelClear(self) -> None:
        """Delete all fill-ups for THIS vehicle; the core backs up the database first."""
        if hasattr(self.feed, "fuel_edit"):
            self.feed.fuel_edit({"action": "clear", "confirm": "DELETE"})

    @Slot(float, float)
    def fillup(self, gallons: float, price: float) -> None:
        """Log a fill-up; the core validates, records and resets the tank average."""
        if not 0.5 <= gallons <= 80:
            self.message.emit("Enter gallons (0.5 - 80)")
            return
        if hasattr(self.feed, "fillup"):
            self.feed.fillup(round(gallons, 3), round(price, 3) if price > 0 else None)
            self.message.emit("Saving fill-up...")

    @Slot(str)
    def resetEcon(self, kind: str) -> None:
        """Tile tap -> confirm -> here. 'trip' or 'roll' (Last N)."""
        if hasattr(self.feed, "trip_reset"):
            self.feed.trip_reset("roll" if kind == "roll" else "trip")
            win = int(self._settings.get("econ_window_mi", 10))
            self.message.emit(f"Last {win} average reset" if kind == "roll" else "Trip reset")

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
