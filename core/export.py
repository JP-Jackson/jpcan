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


def log_stats(db_path: Path, top: int = 5) -> dict:
    """Per-key sample rate and gaps for a drive log, to judge poll lag.

    Returns {"meta": {...}, "keys": {key: {"n", "hz", "max_gap", "p95_gap", "errors",
    "gaps": [(ts, gap), ...]}}} where gaps are the `top` longest gaps.
    """
    import statistics

    out: dict = {"meta": read_meta(db_path), "keys": {}}
    with sqlite3.connect(db_path) as db:
        rows = db.execute("SELECT key, ts, err FROM readings ORDER BY key, ts").fetchall()
    cur, ts_list, errs = None, [], 0

    def flush():
        if cur is None or not ts_list:
            return
        gaps = [(ts_list[i], ts_list[i] - ts_list[i - 1]) for i in range(1, len(ts_list))]
        gaps_only = sorted(g for _, g in gaps)
        span = ts_list[-1] - ts_list[0]
        out["keys"][cur] = {
            "n": len(ts_list),
            "hz": (len(ts_list) - 1) / span if span > 0 else 0.0,
            "max_gap": gaps_only[-1] if gaps_only else 0.0,
            "p95_gap": gaps_only[int(0.95 * (len(gaps_only) - 1))] if gaps_only else 0.0,
            "median_gap": statistics.median(gaps_only) if gaps_only else 0.0,
            "errors": errs,
            "gaps": sorted(gaps, key=lambda g: -g[1])[:top],
        }

    for key, ts, err in rows:
        if key != cur:
            flush()
            cur, ts_list, errs = key, [], 0
        ts_list.append(ts)
        if err:
            errs += 1
    flush()
    return out


def format_log_stats(stats: dict) -> str:
    m = stats["meta"]
    dur = (m.get("ended") or 0) - m.get("started", 0)
    lines = [f"profile {m.get('profile', '?')}  duration {dur / 60:.1f} min  "
             f"started {time.strftime('%Y-%m-%d %H:%M', time.localtime(m.get('started', 0)))}",
             f"{'key':20} {'n':>7} {'Hz':>6} {'med':>6} {'p95':>6} {'max':>7} {'err':>5}"]
    for key, s in sorted(stats["keys"].items(), key=lambda kv: -kv[1]["hz"]):
        lines.append(f"{key:20} {s['n']:7d} {s['hz']:6.2f} {s['median_gap']:6.2f} "
                     f"{s['p95_gap']:6.2f} {s['max_gap']:7.1f} {s['errors']:5d}")
    return "\n".join(lines)
