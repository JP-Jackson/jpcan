"""Export a drive log to CSV, resampled to a fixed rate with forward-fill."""

from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path

from .units import display

STALE = 5.0  # s; a value older than this at a sample time is left blank


def read_meta(db_path: Path) -> dict:
    with sqlite3.connect(db_path) as db:
        return {k: json.loads(v) for k, v in db.execute("SELECT k, v FROM meta")}


def export_csv(db_path: Path, out_path: Path, rate: float = 1.0, imperial: bool = True) -> int:
    """Write CSV; returns number of data rows."""
    meta = read_meta(db_path)
    units: dict[str, str] = meta.get("units", {})
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT ts, key, value FROM readings WHERE value IS NOT NULL ORDER BY ts").fetchall()
    if not rows:
        Path(out_path).write_text("time,elapsed_s\n")
        return 0
    keys: list[str] = []
    for _, k, _ in rows:
        if k not in keys:
            keys.append(k)
    heads = []
    for k in keys:
        _, u = display(0.0, units.get(k, ""), imperial)
        heads.append(f"{k} ({u})" if u else k)
    t0, t_end = rows[0][0], rows[-1][0]
    last: dict[str, tuple[float, float]] = {}
    i, n = 0, 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", "elapsed_s", *heads])
        t = t0
        while t <= t_end + 1e-9:
            while i < len(rows) and rows[i][0] <= t:
                ts, k, v = rows[i]
                last[k] = (ts, v)
                i += 1
            line = [time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)), f"{t - t0:.1f}"]
            for k in keys:
                if k in last and t - last[k][0] <= STALE:
                    v, _ = display(last[k][1], units.get(k, ""), imperial)
                    line.append(f"{v:.3f}".rstrip("0").rstrip("."))
                else:
                    line.append("")
            w.writerow(line)
            n += 1
            t += rate
    return n
