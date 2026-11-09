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
STALE = 5.0  # s: minimum time without an update before a reading counts as stale


def stale_after(gap: float | None) -> float:
    """How long a reading may go without an update. Slow-tier readings arrive about every
    5 s and diagnostic ones every ~12-14 s, so a flat 5 s blanked them ("--") just before
    each update. Allow 2.5x the reading's own update interval, and never less than STALE."""
    return STALE if not gap else max(STALE, 2.5 * gap)


def track_gap(prev_ts: float | None, ts: float, gap: float | None) -> float | None:
    """Smoothed update interval for one reading (ignores repeats and big jumps)."""
    if prev_ts is None or ts <= prev_ts:
        return gap
    d = ts - prev_ts
    if d > 120:            # key off, clock jump: don't learn from it
        return gap
    return d if gap is None else 0.8 * gap + 0.2 * d


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
        "split": g.get("split"),
    }
    if not imperial and native in IMPERIAL:
        for k in ("min", "max", "warn", "alarm", "split"):
            c[k] = _imperial_to_metric(c[k], native)
        step = nice_step(c["max"] - c["min"])
        c["min"] = math.floor(c["min"] / step + 1e-9) * step
        c["max"] = math.ceil(c["max"] / step - 1e-9) * step
        c["major"] = step
    if not c["major"]:
        c["major"] = nice_step(c["max"] - c["min"])
    c["decimals"] = 0 if (c["max"] - c["min"]) * c["scale"] >= 100 or c["scale"] != 1 else 1
    for k in ("warn", "alarm", "split"):
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


def build_pages(meta: dict, imperial: bool, window_mi: int, overrides: dict,
                limits: dict | None = None) -> list[dict]:
    """Profile pages + JP's per-slot picks and red lines -> concrete config for QML."""
    limits = limits or {}
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
        if key in limits:
            g["alarm"] = limits[key]
        return {**gauge_config(g, ch[key].get("units", ""), imperial), "verified": ch[key].get("verified", True)}

    def tile_cfg(key: str) -> dict:
        info = ch.get(f"econ_last{window_mi}" if key == "econ_last" else key, {})
        return tile_config(key, info, imperial, window_mi)

    pages = []
    for p in gw.get("pages") or []:
        ov = overrides.get(p.get("name", ""), {})
        slots = {slot: slot_cfg(ov.get(slot, key)) for slot, key in (p.get("slots") or {}).items()}
        tiles = [tile_cfg(ov.get(f"tile{i}", k)) for i, k in enumerate(p.get("tiles") or [])]
        # gauge configs for tile channels, for theme skins that draw a tile as a dial or bar
        gauges = {t["key"]: slot_cfg(t["key"]) for t in tiles if t["key"] in ch}
        pages.append({"name": p.get("name", ""), "template": p.get("template", "dash"),
                      "slots": slots, "tiles": tiles, "gauges": gauges, "custom": bool(ov)})
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
    url = lambda rel: QUrl.fromLocalFile(str((d / rel).resolve())).toString()  # noqa: E731
    for k in ("face", "needle"):
        if k in t:
            t[k] = url(t[k])
    t["assets"] = {k: url(v) for k, v in (t.get("assets") or {}).items()}
    t.setdefault("style", {"gauge": "needle"})
    t["id"] = d.name
    t["pages"] = page_sources(d.name, themes_dir)
    return t


QML_DIR = Path(__file__).resolve().parent / "qml"
TEMPLATES = {"dash": "PageDash.qml", "quad": "PageQuad.qml", "economy": "PageEconomy.qml",
             "list": "PageList.qml", "towing": "PageTowing.qml"}
MODE_FILE = Path("/etc/default/jpcan-mode")   # written by jpcan-mode (Truck/Simulator switch)


def read_source_mode(path: Path = MODE_FILE) -> str | None:
    """'sim' or 'truck' from the switch's file, or None if there's no switch (laptop)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.strip().startswith("JPCAN_MODE_ARGS="):
            return "sim" if "--sim" in line else "truck"
    return "truck"


BACKGROUNDS = ["carbon", "expanded", "diamond", "brushed", "honeycomb", "black"]
DEFAULT_ACCENTS = ("#29c4ff", "#ffb340")


def limit_info(meta: dict, key: str, imperial: bool, limits: dict) -> dict:
    """Red line for one reading in display units, with a sensible +/- step."""
    ch = (meta.get("channels") or {}).get(key)
    if not ch:
        return {}
    disp = ((meta.get("gaugeworks") or {}).get("display") or {})
    g = {**(disp.get(key) or auto_display(key, ch)), "key": key}
    if key in limits:
        g["alarm"] = limits[key]
    c = gauge_config(g, ch.get("units", ""), imperial)
    step = c["major"] / max(1, c["minor"])
    if step * c["scale"] >= 1 and c["max"] - c["min"] >= 1000:
        step = max(step / 2, 50.0)
    alarm = c["alarm"]
    return {"key": key, "value": None if math.isnan(alarm) else alarm, "step": step, "min": c["min"],
            "max": c["max"], "units": c["units"], "custom": key in limits, "label": c["label"] or key}


def to_imperial(v: float, native: str, imperial: bool) -> float:
    """A value typed in the current display units -> imperial display units (how limits are stored)."""
    if imperial or native not in IMPERIAL:
        return v
    return IMPERIAL[native][1](v)


def page_sources(theme_id: str, themes_dir: Path = THEMES_DIR, qml_dir: Path = QML_DIR) -> dict:
    """Template -> QML file URL. A theme may ship its own page layouts in
    themes/<id>/qml/Page*.qml (a "skin"); otherwise the standard page is used.
    Theme pages import the standard components with: import "../../../qml"."""
    out = {}
    for template, fname in TEMPLATES.items():
        skin = themes_dir / theme_id / "qml" / fname
        out[template] = QUrl.fromLocalFile(str(skin if skin.exists() else qml_dir / fname)).toString()
    return out


THEME_ORDER = ["oem", "classic", "classic_refined", "modern", "race", "night", "turbo_snail"]


def list_themes(themes_dir: Path = THEMES_DIR) -> list[dict]:
    ids = [p.parent.name for p in themes_dir.glob("*/theme.json")]
    ids.sort(key=lambda i: (THEME_ORDER.index(i) if i in THEME_ORDER else 99, i))
    out = []
    for i in ids:
        try:
            name = json.loads((themes_dir / i / "theme.json").read_text()).get("name", i)
        except (OSError, ValueError):
            name = i
        out.append({"id": i, "name": name})
    return out


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
    sourceChanged = Signal()
    editModeChanged = Signal()
    message = Signal(str)

    def __init__(self, feed, settings: dict | None = None, poll_ms: int = 50):
        super().__init__()
        self.feed = feed
        self._settings = settings if settings is not None else settings_mod.load()
        self._values = QQmlPropertyMap(self)
        self._fresh = QQmlPropertyMap(self)
        self._last_ts: dict[str, float] = {}   # per reading: last timestamp and smoothed update interval
        self._gap: dict[str, float | None] = {}
        self._lo = QQmlPropertyMap(self)   # lowest value seen this drive (display units)
        self._hi = QQmlPropertyMap(self)   # highest value seen this drive
        self._config: dict = {"gauges": {}, "tiles": []}
        self._theme = load_theme(self._settings.get("theme", "classic"))
        self._status = {"state": "offline", "text": "Starting...", "mode": ""}
        self._fuel: dict = {}
        self._last_result_ts = None
        self._source = read_source_mode()
        self._edit = False
        self._source_checked = 0.0
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
    lo = Property(QObject, lambda self: self._lo, constant=True)
    hi = Property(QObject, lambda self: self._hi, constant=True)

    # -- appearance: background texture and the two accent colors
    def _bg(self) -> str:
        b = self._settings.get("background", "carbon")
        return b if b in BACKGROUNDS else "carbon"

    def _bg_url(self) -> str:
        f = ASSETS_DIR / "bg" / f"{self._bg()}.png"
        return QUrl.fromLocalFile(str(f)).toString() if f.exists() else ""

    # Truck/Simulator: from the switch's own file, so it's right even when the core
    # hasn't connected (bench, adapter unpowered) and its last meta is stale.
    def _source_mode(self) -> str:
        if self._source is not None:
            return self._source
        return "sim" if (self.feed.meta or {}).get("sim") else "truck"

    sourceMode = Property(str, _source_mode, notify=sourceChanged)

    # Edit mode: a single tap on any reading opens the picker. The 7" screen's touch
    # controller drops a still finger after ~0.1 s, so press-and-hold can't work on it.
    editMode = Property(bool, lambda self: self._edit, notify=editModeChanged)

    @Slot(bool)
    def setEditMode(self, on: bool) -> None:
        if bool(on) != self._edit:
            self._edit = bool(on)
            self.editModeChanged.emit()

    def _refresh_source(self) -> None:
        m = read_source_mode()
        if m != self._source:
            self._source = m
            self.sourceChanged.emit()

    background = Property(str, _bg, notify=settingsChanged)
    backgroundUrl = Property(str, _bg_url, notify=settingsChanged)
    backgrounds = Property("QVariantList", lambda self: list(BACKGROUNDS), constant=True)
    accent = Property(str, lambda self: self._settings.get("accent") or DEFAULT_ACCENTS[0], notify=settingsChanged)
    accent2 = Property(str, lambda self: self._settings.get("accent2") or DEFAULT_ACCENTS[1], notify=settingsChanged)
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
               json.dumps(self._settings.get("limits", {}), sort_keys=True),
               len(meta.get("channels", {})))
        if sig != self._meta_sig and meta:
            self._meta_sig = sig
            self._rebuild_config(meta)
        self._update_status(meta)
        if time.monotonic() - self._source_checked > 1.0:
            self._source_checked = time.monotonic()
            self._refresh_source()
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
        pages = build_pages(meta, imp, win, overrides, self._limits(meta))
        status_keys = (meta.get("layouts") or {}).get("status") or []
        diag = status_keys + sorted(k for k in ch if k not in status_keys)
        rpm_cfg = (gauge_config({**(gw.get("display") or {}).get("rpm", auto_display("rpm", ch["rpm"])),
                                 "key": "rpm"}, ch["rpm"].get("units", ""), imp) if "rpm" in ch else {})
        self._config = {"pages": pages, "profile": meta.get("name", ""), "gear": gw.get("gear", ""),
                        "rpm": rpm_cfg,
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
            if r.ts != self._last_ts.get(k):
                self._gap[k] = track_gap(self._last_ts.get(k), r.ts, self._gap.get(k))
                self._last_ts[k] = r.ts
            ok = (running and r.value is not None and not r.error and now - r.ts <= stale_after(self._gap.get(k)))
            raw = r.value * factor if (r.value is not None and k.startswith("econ_")) else r.value
            v = display(raw, r.units, imp)[0] if raw is not None else 0.0
            if self._values.value(k) != v:
                self._values.insert(k, v)
            if ok:
                lo, hi = self._lo.value(k), self._hi.value(k)
                if lo is None or v < lo:
                    self._lo.insert(k, v)
                if hi is None or v > hi:
                    self._hi.insert(k, v)
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

    # -- red lines (per vehicle; stored in imperial display units like the profile)
    def _limits(self, meta: dict | None = None) -> dict:
        prof = (meta or self.feed.meta or {}).get("profile", "")
        return dict((self._settings.get("limits") or {}).get(prof, {}))

    @Slot(str, result="QVariantMap")
    def limitFor(self, key: str) -> dict:
        imp = self._settings.get("units", "imperial") == "imperial"
        return limit_info(self.feed.meta or {}, key, imp, self._limits())

    @Slot(str, float)
    def setLimit(self, key: str, value: float) -> None:
        meta = self.feed.meta or {}
        native = ((meta.get("channels") or {}).get(key) or {}).get("units", "")
        imp = self._settings.get("units", "imperial") == "imperial"
        prof = meta.get("profile", "")
        self._settings.setdefault("limits", {}).setdefault(prof, {})[key] = round(to_imperial(value, native, imp), 3)
        self._save()

    @Slot(str)
    def resetLimit(self, key: str) -> None:
        prof = (self.feed.meta or {}).get("profile", "")
        (self._settings.get("limits") or {}).get(prof, {}).pop(key, None)
        self._save()

    @Slot()
    def resetDriveMinMax(self) -> None:
        for m in (self._lo, self._hi):
            for k in list(m.keys()):
                m.clear(k)

    # -- appearance
    @Slot(str)
    def setBackground(self, name: str) -> None:
        if name in BACKGROUNDS:
            self._settings["background"] = name
            self._save()

    @Slot(int, str)
    def setAccent(self, which: int, color: str) -> None:
        if isinstance(color, str) and len(color) == 7 and color.startswith("#"):
            self._settings["accent2" if which else "accent"] = color.lower()
            self._save()

    @Slot()
    def resetColors(self) -> None:
        self._settings.pop("accent", None)
        self._settings.pop("accent2", None)
        self._save()

    @Slot(str)
    def setSource(self, mode: str) -> None:
        """Settings: Truck or Simulator. A root-owned helper rewrites the mode and restarts
        the core; GaugeWorks itself never touches the adapter."""
        if mode not in ("truck", "sim"):
            return
        self.message.emit("Switching to " + ("the simulator" if mode == "sim" else "the truck") + "...")

        def run():
            try:
                r = subprocess.run(["sudo", "-n", "/usr/local/sbin/jpcan-mode", mode],
                                   capture_output=True, text=True, timeout=30)
                ok = r.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
            if not ok:
                self.message.emit("Mode switch not permitted here")

        threading.Thread(target=run, daemon=True).start()

    @Slot()
    def shutdown(self) -> None:
        r = subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.message.emit("Shutdown not permitted here")
