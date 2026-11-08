"""GaugeWorks entry point.

  gaugeworks                 Pi: subscribe to the core service over MQTT
  gaugeworks --sim           laptop: run the core + simulator in-process
  gaugeworks --demo cruise --screenshot out.png   static scene to PNG
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from argparse import Namespace
from pathlib import Path

QML_DIR = Path(__file__).resolve().parent / "qml"

# Demo scenes in native units (km/h, °C, kPa...). Used for screenshots/review.
DEMO_SCENES = {
    "cruise": {"gear": 6, "rpm": 1650, "speed": 104.6, "boost": 55, "baro": 99, "coolant": 88, "trans_temp": 77,
               "vgt_desired": 45, "vgt_actual": 48, "econ_inst": 7.2, "econ_tank": 6.6, "econ_trip": 6.4, "econ_last10": 7.0,
               "ambient": 32, "oil_temp_std": 96, "battery": 14.2, "fuel_level": 70, "mil": 0,
               "trip_dist": 52.3, "map": 155, "iat": 30, "dpf_dp": 1.2},
    "alarm": {"gear": 3, "rpm": 2900, "speed": 88.5, "boost": 240, "coolant": 115, "trans_temp": 110,
              "vgt_desired": 70, "vgt_actual": 74, "econ_inst": 2.1, "econ_tank": 5.9, "econ_trip": 5.7, "econ_last10": 3.1,
              "ambient": 40, "oil_temp_std": 118, "battery": 14.1, "fuel_level": 22, "mil": 1, "dtc_count": 2,
              "trip_dist": 140.2, "map": 250, "iat": 45, "dpf_dp": 2.0},
    "vgtfault": {"rpm": 2100, "speed": 96.6, "boost": 90, "baro": 99, "coolant": 89, "trans_temp": 80,
                 "vgt_desired": 40, "vgt_actual": 75, "econ_inst": 5.8, "econ_tank": 6.3, "econ_trip": 6.1, "econ_last10": 5.5,
                 "ambient": 32, "oil_temp_std": 99, "battery": 14.2, "fuel_level": 68, "mil": 0,
                 "trip_dist": 61.0, "gear": 5},
    "shift": {"rpm": 3200, "speed": 72.4, "map": 210, "baro": 99, "boost": 111, "coolant": 90, "iat": 35,
              "econ_inst": 6.0, "econ_tank": 16.0, "econ_trip": 15.2, "econ_last10": 15.8, "ambient": 22, "battery": 14.0,
              "fuel_level": 55, "mil": 0, "trip_dist": 30.0, "dpf_dp": 0.8},
}


_D = 86400
DEMO_FUEL = {
    "vehicle": "demo", "factor": 0.93, "factor_tanks": 3,
    "lifetime": {"tanks": 4, "miles": 1412.0, "gallons": 92.1, "mpg": 15.33, "cost": 318.65,
                 "cost_per_mile": 0.226},
    "rows": [
        {"id": 5, "ts": time.time() - 2 * _D, "odo_mi": 148197, "miles": 351.2, "miles_src": "odometer",
         "gallons": 22.4, "price": 3.459, "total": 77.48, "mpg": 15.68, "est_mpg": 16.9},
        {"id": 4, "ts": time.time() - 9 * _D, "odo_mi": 147846, "miles": 338.0, "miles_src": "odometer",
         "gallons": 23.1, "price": 3.399, "total": 78.52, "mpg": 14.63, "est_mpg": 15.8},
        {"id": 3, "ts": time.time() - 16 * _D, "odo_mi": 147508, "miles": 377.4, "miles_src": "odometer",
         "gallons": 24.0, "price": 3.499, "total": 83.98, "mpg": 15.73, "est_mpg": 16.7},
        {"id": 2, "ts": time.time() - 24 * _D, "odo_mi": 147131, "miles": 345.4, "miles_src": "estimate",
         "gallons": 22.6, "price": 3.489, "total": 78.85, "mpg": 15.28, "est_mpg": None},
        {"id": 1, "ts": time.time() - 31 * _D, "odo_mi": 146786, "miles": None, "miles_src": "baseline",
         "gallons": 21.0, "price": 3.549, "total": 74.53, "mpg": None, "est_mpg": None},
    ],
}


class InProcFeed:
    """Core service + simulator in this process (laptop dev)."""

    def __init__(self, args):
        import tempfile

        from core.bus import Bus
        from core.fuelbook import FuelHub
        from core.mqtt import LocalSink
        from core.service import run_core
        from core.trip import TripComputer

        self.bus = Bus()
        self.trip = TripComputer(self.bus)
        self.hub = FuelHub()
        self._sink = LocalSink(self.bus)
        self.stop = threading.Event()
        cargs = Namespace(sim=True, port="SIM", baud=115200, profile=args.profile, trace=None,
                          min_gap=0.02, no_log=True, log_dir=tempfile.mkdtemp(prefix="jpcan-sim-"))
        threading.Thread(target=run_core, args=(cargs, self._sink, self.bus, self.stop, self.trip, self.hub),
                         daemon=True).start()
        self.connected = True

    meta = property(lambda self: self._sink.meta)
    status = property(lambda self: self._sink.status)
    fuel = property(lambda self: self._sink.fuel)

    def trip_reset(self, kind="trip"):
        self.trip.handle_reset(kind)

    def fillup(self, gallons, price=None):
        threading.Thread(target=self.hub.fillup, args=(gallons, price), daemon=True).start()

    def fuel_edit(self, cmd):
        threading.Thread(target=self.hub.edit, args=(cmd,), daemon=True).start()

    def close(self):
        self.stop.set()


class DemoFeed:
    """Static values for screenshots."""

    def __init__(self, scene: str, profile_id: str | None):
        from core.bus import Bus, Reading
        from core.profile import load_profile
        from core.service import channel_info

        if profile_id is None:
            profile_id = "vw_jetta_20tdi_2013" if scene == "shift" else "ford_f250_67_2014"
        p = load_profile(profile_id)
        ch = channel_info(p)
        self.meta = {"profile": p.id, "name": p.name, "vin": None, "sim": True, "shift": p.shift,
                     "layouts": p.layouts, "gaugeworks": p.gaugeworks, "channels": ch, "skipped": []}
        self.status = {"state": "running", "hz": 10.0, "sent": 1234, "blocked": 0, "lines": []}
        self.fuel = DEMO_FUEL
        self.connected = True
        self.bus = Bus()
        now = time.time()
        for k, v in DEMO_SCENES[scene].items():
            if k in ch:
                self.bus.publish(Reading(k, float(v), ch[k]["units"], now))
        self._refresh = threading.Thread(target=self._keep_fresh, daemon=True)
        self._refresh.start()

    def _keep_fresh(self):
        from core.bus import Reading

        while True:
            time.sleep(1)
            now = time.time()
            for r in self.bus.latest().values():
                self.bus.publish(Reading(r.key, r.value, r.units, now))

    def close(self):
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gaugeworks", description="JpCAN reads it. GaugeWorks shows it.")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--sim", action="store_true", help="run core + simulator in-process (laptop)")
    src.add_argument("--demo", choices=sorted(DEMO_SCENES), help="static demo scene")
    ap.add_argument("--profile", help="profile for --sim/--demo")
    ap.add_argument("--mqtt-host", default="localhost")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    ap.add_argument("--windowed", action="store_true", help="window instead of fullscreen")
    ap.add_argument("--splash-ms", type=int, default=2500)
    ap.add_argument("--screenshot", help="render to this PNG and exit")
    ap.add_argument("--settings", action="store_true", help="open the settings menu (screenshots)")
    ap.add_argument("--panel", choices=["settings", "fillup", "history", "picker", "export", "confirm", "edit", "deleteall"], help="open a panel (screenshots)")
    ap.add_argument("--page", type=int, help="start on this page index (screenshots)")
    ap.add_argument("--theme", help="theme id (screenshots)")
    args = ap.parse_args(argv)

    from PySide6.QtCore import QObject, QTimer, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView

    from .backend import Backend

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("GaugeWorks")
    from PySide6.QtGui import QFontDatabase

    for f in sorted((Path(__file__).resolve().parent / "themes").glob("*/fonts/*.ttf")):
        QFontDatabase.addApplicationFont(str(f))  # theme fonts (OFL), by family name
    if args.demo:
        feed = DemoFeed(args.demo, args.profile)
    elif args.sim:
        feed = InProcFeed(args)
    else:
        from core.mqtt import MqttFeed
        feed = MqttFeed(args.mqtt_host, args.mqtt_port, "gaugeworks")

    from core import settings as settings_mod
    st = settings_mod.load() if not args.screenshot else {**settings_mod.DEFAULTS}
    if args.page is not None:
        st["page"] = args.page
    if args.theme:
        st["theme"] = args.theme
    backend = Backend(feed, st)
    view = QQuickView()
    view.setTitle("GaugeWorks")
    view.setColor("#000000")
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    ctx = view.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("demoMode", bool(args.demo))
    ctx.setContextProperty("splashMs", 0 if args.screenshot else args.splash_ms)
    errors: list[str] = []
    view.statusChanged.connect(lambda s: errors.extend(e.toString() for e in view.errors()))
    view.engine().warnings.connect(lambda ws: errors.extend(w.toString() for w in ws))
    view.setSource(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if view.status() == QQuickView.Error:
        for e in view.errors():
            print(e.toString(), file=sys.stderr)
        return 1
    view.resize(1024, 600)
    if args.screenshot or args.windowed:
        view.show()
    else:
        view.showFullScreen()

    want = "settings" if args.settings else args.panel
    if want in ("confirm", "deleteall", "edit"):  # real prompts, for screenshots
        from PySide6.QtCore import Q_ARG, QMetaObject
        root = view.rootObject()
        if want == "confirm":
            QMetaObject.invokeMethod(root, "askReset", Q_ARG("QVariant", "trip"))
        elif want == "deleteall":
            QMetaObject.invokeMethod(root, "askDeleteAll")
        else:
            fu = root.findChild(QObject, "fillupPanel")
            rows = (feed.fuel or {}).get("rows") or []
            if fu is not None and rows:
                QMetaObject.invokeMethod(fu, "openEdit", Q_ARG("QVariant", rows[0]))
        want = None
    if want:
        panel = view.rootObject().findChild(QObject, f"{want}Panel")
        if panel is not None:
            panel.setProperty("visible", True)

    if not (args.screenshot or args.demo or args.windowed):
        import os

        from .touchwatch import install as install_touchwatch
        install_touchwatch(app, view, os.environ.get("GAUGEWORKS_TOUCH"),
                           os.environ.get("GAUGEWORKS_TOUCH_NAME", ""))

    if args.screenshot:
        QTimer.singleShot(2600, lambda: (view.grabWindow().save(args.screenshot), app.quit()))

    rc = app.exec()
    view.setSource(QUrl())  # tear down QML before the backend goes away
    feed.close()
    for e in errors:
        print("QML:", e, file=sys.stderr)
    return 2 if (args.screenshot and errors) else rc


if __name__ == "__main__":
    sys.exit(main())
