"""USB stick detection and background export for GaugeWorks.

Detection only reads /dev/disk/by-id (no privileges). Mounting goes through
the root-owned helper /usr/local/sbin/jpcan-usb via a sudoers rule that allows
exactly that command. Nothing here talks to the truck.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path

from core import settings as settings_mod
from core.bundle import export_bundle
from core.logger import default_log_dir

USB_GLOB_DIR = Path("/dev/disk/by-id")
HELPER = ["sudo", "-n", "/usr/local/sbin/jpcan-usb"]
REPO = Path(__file__).resolve().parent.parent


def friendly(by_id: str) -> str:
    """'usb-SanDisk_Cruzer_Blade_4C530001-0:0-part1' -> 'SanDisk Cruzer Blade'."""
    name = by_id[4:] if by_id.startswith("usb-") else by_id
    name = re.sub(r"-0:\d+(-part\d+)?$", "", name)
    tokens = [t for t in name.split("_") if t]
    if tokens and len(tokens[-1]) >= 8 and any(c.isdigit() for c in tokens[-1]):
        tokens = tokens[:-1]  # drop serial number
    return " ".join(tokens) or "USB drive"


def usb_drives() -> list[str]:
    fake = os.environ.get("JPCAN_FAKE_USB")  # screenshots/tests
    if fake:
        return [fake]
    try:
        names = sorted(p.name for p in USB_GLOB_DIR.glob("usb-*"))
    except OSError:
        return []
    disks = [n for n in names if "-part" not in n] or names
    return [friendly(n) for n in disks]


class UsbExporter:
    """State machine: idle -> exporting -> done | error. Thread-safe enough for a
    UI that polls `state` (single writer thread, dict replaced atomically)."""

    def __init__(self, get_extra):
        self.get_extra = get_extra
        self.state = {"present": False, "name": "", "state": "idle", "progress": "", "result": ""}
        self.dismissed = ""

    def poll(self) -> None:
        drives = usb_drives()
        st = dict(self.state)
        st["present"] = bool(drives)
        st["name"] = drives[0] if drives else ""
        if not drives:
            self.dismissed = ""
            if st["state"] in ("done", "error"):
                st.update(state="idle", progress="", result="")
        self.state = st

    def _set(self, **kw) -> None:
        self.state = {**self.state, **kw}

    def start(self) -> bool:
        if self.state["state"] == "exporting":
            return False
        self._set(state="exporting", progress="Mounting...", result="")
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self) -> None:
        mounted = False
        try:
            r = subprocess.run([*HELPER, "mount"], capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip() or "could not mount the drive")
            mounted = True
            summary = export_bundle(
                Path(r.stdout.strip().splitlines()[-1]), default_log_dir(), settings_mod.path().parent,
                scan_dirs=[Path.home(), REPO], extra=self.get_extra(),
                progress=lambda m: self._set(progress=m))
            self._set(progress="Finishing (sync)...")
            subprocess.run([*HELPER, "unmount"], capture_output=True, text=True, timeout=60)
            mounted = False
            mb = summary["bytes"] / 1e6
            self._set(state="done", progress="",
                      result=f"Exported {summary['files']} files ({mb:.1f} MB): "
                             f"{summary['drive_logs']} drive logs, {summary['fillups']} fill-ups. "
                             "Safe to remove.")
        except Exception as e:  # noqa: BLE001 - surface any failure on screen
            if mounted:
                subprocess.run([*HELPER, "unmount"], capture_output=True, text=True, timeout=60)
            self._set(state="error", progress="", result=f"Export failed: {e}")

    def eject(self) -> None:
        subprocess.run([*HELPER, "unmount"], capture_output=True, text=True, timeout=60)
        self._set(state="done", result="Safe to remove.")
