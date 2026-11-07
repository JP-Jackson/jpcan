"""Export everything worth keeping to a folder (a USB stick, or any directory).

  <dest>/JpCAN_export/<YYYYmmdd-HHMMSS>/
      drive_logs/   every drive's SQLite (consistent snapshot) + CSV (1 s rows)
      fuel/         fuel.sqlite snapshot + fuel_history.csv (all vehicles)
      scans/        didscan / didwatch / trace files
      diagnostics/  report.txt, settings, economy state, recent service logs
      README.txt

Read-only with respect to the truck: nothing here talks to the adapter. SQLite
files are copied with the backup API, so a log being written mid-drive is
still a consistent copy.
"""

from __future__ import annotations

import csv
import json
import platform
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Callable

from . import __version__
from .export import export_csv

SCAN_GLOBS = ("didscan_*.json", "*scan*.json", "*watch*.jsonl", "probe*.jsonl", "scan22*.jsonl",
              "trace*.jsonl")
SERVICES = ("jpcan-core", "jpcan-status", "gaugeworks", "mosquitto")


def _snapshot_sqlite(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as s, sqlite3.connect(dst) as d:
        s.backup(d)


def _run(cmd: list[str], timeout: float = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return f"({cmd[0]} unavailable: {e})"


def fuel_csv(db: Path, out: Path) -> int:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(fillups)")]
        rows = c.execute(f"SELECT {', '.join(cols)} FROM fillups ORDER BY vehicle, id").fetchall()
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", *cols])
        for r in rows:
            d = dict(zip(cols, r))
            w.writerow([time.strftime("%Y-%m-%d %H:%M", time.localtime(d["ts"])), *r])
    return len(rows)


def report(extra: dict | None = None) -> str:
    repo = Path(__file__).resolve().parent.parent
    lines = [
        f"JpCAN export report  {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"jpcan {__version__}  commit {_run(['git', '-C', str(repo), 'rev-parse', '--short', 'HEAD'])}"
        f"  branch {_run(['git', '-C', str(repo), 'rev-parse', '--abbrev-ref', 'HEAD'])}",
        f"python {platform.python_version()}  {platform.platform()}",
    ]
    model = Path("/proc/device-tree/model")
    if model.exists():
        lines.append("hardware " + model.read_text(errors="replace").strip("\x00"))
    os_rel = Path("/etc/os-release")
    if os_rel.exists():
        lines += [ln for ln in os_rel.read_text().splitlines() if ln.startswith("PRETTY_NAME")]
    lines.append("throttled " + _run(["vcgencmd", "get_throttled"]))
    lines.append("disk " + _run(["df", "-h", str(Path.home())]).replace("\n", " | "))
    lines.append("services " + ", ".join(f"{s}={_run(['systemctl', 'is-active', s])}" for s in SERVICES))
    if extra:
        st = extra.get("status") or {}
        lines.append(f"core status {st.get('state')}  hz {st.get('hz')}  requests sent {st.get('sent')}"
                     f"  BLOCKED {st.get('blocked')}  errors {st.get('errors')}")
        meta = extra.get("meta") or {}
        lines.append(f"vehicle {meta.get('name')}  profile {meta.get('profile')}  vin {meta.get('vin')}")
        lines.append(f"adapter {json.dumps(meta.get('adapter'))}")
    return "\n".join(lines) + "\n"


def export_bundle(dest: Path, data_dir: Path, config_dir: Path, scan_dirs: list[Path] | None = None,
                  extra: dict | None = None, journals: bool = True,
                  progress: Callable[[str], None] = lambda m: None) -> dict:
    """Write the bundle under dest/JpCAN_export/<timestamp>. Returns a summary."""
    root = Path(dest) / "JpCAN_export" / time.strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=False)
    files = 0
    data_dir, config_dir = Path(data_dir), Path(config_dir)

    logs = sorted(f for f in data_dir.glob("*.sqlite") if f.name != "fuel.sqlite") if data_dir.exists() else []
    for i, src in enumerate(logs, 1):
        progress(f"Drive log {i}/{len(logs)}: {src.name}")
        dst = root / "drive_logs" / src.name
        _snapshot_sqlite(src, dst)
        try:
            export_csv(dst, dst.with_suffix(".csv"), rate=1.0)
            files += 2
        except (sqlite3.Error, ValueError, KeyError) as e:
            (root / "drive_logs" / f"{src.stem}.csv.error.txt").write_text(str(e))
            files += 1

    fuel_db = data_dir / "fuel.sqlite"
    fillups = 0
    if fuel_db.exists():
        progress("Fuel history")
        _snapshot_sqlite(fuel_db, root / "fuel" / "fuel.sqlite")
        fillups = fuel_csv(root / "fuel" / "fuel.sqlite", root / "fuel" / "fuel_history.csv")
        files += 2
        for b in sorted((data_dir / "fuel_backups").glob("fuel_*.sqlite")):
            _snapshot_sqlite(b, root / "fuel" / "backups" / b.name)
            files += 1

    progress("Scan files")
    seen: set[Path] = set()
    for d in scan_dirs or []:
        for pattern in SCAN_GLOBS:
            for f in Path(d).glob(pattern):
                if f.is_file() and f.resolve() not in seen:
                    seen.add(f.resolve())
                    (root / "scans").mkdir(exist_ok=True)
                    shutil.copy2(f, root / "scans" / f.name)
                    files += 1

    progress("Diagnostics")
    diag = root / "diagnostics"
    diag.mkdir()
    (diag / "report.txt").write_text(report(extra))
    files += 1
    for f in [config_dir / "settings.json", *data_dir.glob("economy_*.json")]:
        if f.exists():
            shutil.copy2(f, diag / f.name)
            files += 1
    if extra:
        (diag / "core_status_meta.json").write_text(json.dumps(extra, indent=1, default=str))
        files += 1
    if journals:
        for svc in SERVICES:
            (diag / f"journal_{svc}.txt").write_text(
                _run(["journalctl", "-u", svc, "-n", "400", "--no-pager"], timeout=20))
            files += 1

    (root / "README.txt").write_text(
        "JpCAN export\n"
        "drive_logs/*.csv   one row per second, imperial units; open in Excel\n"
        "drive_logs/*.sqlite raw long-format log (ts, key, value) for analysis\n"
        "fuel/fuel_history.csv  every fill-up: miles, gallons, price, actual and estimated MPG\n"
        "scans/             didscan / didwatch / trace files\n"
        "diagnostics/       versions, service logs, settings (for troubleshooting)\n")
    size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    progress("Done")
    return {"path": str(root), "files": files + 1, "drive_logs": len(logs), "fillups": fillups,
            "bytes": size}
