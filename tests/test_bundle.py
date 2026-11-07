import csv
import os
import sqlite3
import stat
import time

import pytest

from core.bundle import export_bundle
from core.bus import Bus, Reading
from core.fuelbook import FuelBook
from core.logger import DriveLogger
from core.trip import TripComputer


def make_data(tmp_path):
    data, cfg, scans = tmp_path / "logs", tmp_path / "cfg", tmp_path / "home"
    for d in (data, cfg, scans):
        d.mkdir()
    bus = Bus()
    log = DriveLogger(bus, data, "ford_f250_67_2014", {"units": {"speed": "km/h"}}, flush_every=0.05)
    for i in range(5):
        bus.publish(Reading("speed", 50.0 + i, "km/h", time.time() + i))
    trip = TripComputer(bus)
    book = FuelBook(data / "fuel.sqlite", "VIN1", bus, trip)
    book.add(20.0, 3.5)
    (cfg / "settings.json").write_text('{"units": "imperial"}')
    (data / "economy_VIN1.json").write_text("{}")
    (scans / "didscan_7E1_x.json").write_text("{}")
    (scans / "gear_watch.jsonl").write_text("{}\n")
    (scans / "unrelated.txt").write_text("nope")
    return data, cfg, scans, log


def test_bundle_contents(tmp_path):
    data, cfg, scans, log = make_data(tmp_path)
    usb = tmp_path / "usb"
    usb.mkdir()
    time.sleep(0.3)  # let the logger's first batch reach disk (5 s batches in the truck)
    msgs = []
    s = export_bundle(usb, data, cfg, scan_dirs=[scans], journals=False, progress=msgs.append,
                      extra={"status": {"state": "running", "blocked": 0}, "meta": {"name": "F-250"}})
    log.close()
    root = usb / "JpCAN_export" / os.path.basename(s["path"])
    names = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    drive = [n for n in names if n.startswith("drive_logs/") and n.endswith(".sqlite")]
    assert len(drive) == 1 and drive[0].replace(".sqlite", ".csv") in names   # active log + CSV
    assert "drive_logs/fuel.sqlite" not in names
    assert {"fuel/fuel.sqlite", "fuel/fuel_history.csv", "scans/didscan_7E1_x.json",
            "scans/gear_watch.jsonl", "diagnostics/report.txt", "diagnostics/settings.json",
            "diagnostics/economy_VIN1.json", "README.txt"} <= names
    assert "scans/unrelated.txt" not in names
    with open(root / "fuel/fuel_history.csv") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["gallons"] == "20.0" and rows[0]["vehicle"] == "VIN1"
    with sqlite3.connect(root / drive[0]) as db:   # snapshot of a log still being written
        assert db.execute("SELECT COUNT(*) FROM readings").fetchone()[0] >= 1
    assert "BLOCKED 0" in (root / "diagnostics/report.txt").read_text()
    assert s["drive_logs"] == 1 and s["fillups"] == 1 and msgs[-1] == "Done"


def test_friendly_names():
    from gaugeworks.usb import friendly

    assert friendly("usb-SanDisk_Cruzer_Blade_4C530001230719115442-0:0") == "SanDisk Cruzer Blade"
    assert friendly("usb-Generic_Flash_Disk_ABCD-0:0-part1") == "Generic Flash Disk ABCD"


def test_usb_exporter_end_to_end_with_fake_helper(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    import gaugeworks.usb as usbmod

    data, cfg, scans, log = make_data(tmp_path)
    log.close()
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    helper = tmp_path / "jpcan-usb"
    helper.write_text(f"#!/bin/sh\ncase \"$1\" in mount) echo {mnt};; unmount) echo ok;; esac\n")
    helper.chmod(helper.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(usbmod, "HELPER", [str(helper)])
    monkeypatch.setattr(usbmod, "default_log_dir", lambda: data)
    monkeypatch.setenv("JPCAN_CONFIG", str(cfg))
    monkeypatch.setenv("JPCAN_FAKE_USB", "Test Stick")
    ex = usbmod.UsbExporter(lambda: {"status": {}, "meta": {}})
    ex.poll()
    assert ex.state["present"] and ex.state["name"] == "Test Stick"
    assert ex.start()
    end = time.time() + 30
    while ex.state["state"] == "exporting" and time.time() < end:
        time.sleep(0.05)
    assert ex.state["state"] == "done", ex.state
    assert "Safe to remove" in ex.state["result"]
    assert list((mnt / "JpCAN_export").iterdir())


def test_usb_exporter_mount_failure(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    import gaugeworks.usb as usbmod

    helper = tmp_path / "jpcan-usb"
    helper.write_text("#!/bin/sh\necho 'unsupported filesystem' >&2; exit 3\n")
    helper.chmod(helper.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(usbmod, "HELPER", [str(helper)])
    ex = usbmod.UsbExporter(lambda: {})
    ex.start()
    end = time.time() + 10
    while ex.state["state"] == "exporting" and time.time() < end:
        time.sleep(0.05)
    assert ex.state["state"] == "error" and "unsupported filesystem" in ex.state["result"]
