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


JUMP_S = 60.0  # a gap this long inside a drive is the clock jumping (no RTC), not polling


def log_stats(db_path: Path, top: int = 5) -> dict:
    """Per-key sample rate and gaps for a drive log, to judge poll lag.

    Gaps over JUMP_S are treated as clock jumps (the Pi has no RTC battery and
    steps its clock when it gets network time) and left out of the rates.
    Returns {"meta", "duration", "jumps": [(ts, seconds)], "keys": {key: {...}}}.
    """
    import statistics

    with sqlite3.connect(db_path) as db:
        rows = db.execute("SELECT key, ts, err FROM readings ORDER BY key, ts").fetchall()
        all_ts = [t for (t,) in db.execute("SELECT DISTINCT ts FROM readings ORDER BY ts")]
    jumps = [(all_ts[i - 1], all_ts[i] - all_ts[i - 1]) for i in range(1, len(all_ts))
             if all_ts[i] - all_ts[i - 1] > JUMP_S]
    duration = (all_ts[-1] - all_ts[0] - sum(j for _, j in jumps)) if all_ts else 0.0
    out: dict = {"meta": read_meta(db_path), "duration": duration, "jumps": jumps, "keys": {}}
    by_key: dict[str, tuple[list, int]] = {}
    for key, ts, err in rows:
        lst, errs = by_key.get(key, ([], 0))
        lst.append(ts)
        by_key[key] = (lst, errs + (1 if err else 0))
    for key, (ts_list, errs) in by_key.items():
        gaps = [(ts_list[i - 1], ts_list[i] - ts_list[i - 1]) for i in range(1, len(ts_list))]
        real = sorted(g for _, g in gaps if g <= JUMP_S)
        span = sum(real)
        out["keys"][key] = {
            "n": len(ts_list),
            "hz": len(real) / span if span > 0 else 0.0,
            "median_gap": statistics.median(real) if real else 0.0,
            "p95_gap": real[int(0.95 * (len(real) - 1))] if real else 0.0,
            "p99_gap": real[int(0.99 * (len(real) - 1))] if real else 0.0,
            "max_gap": real[-1] if real else 0.0,
            "errors": errs,
            "gaps": sorted((g for g in gaps if g[1] <= JUMP_S), key=lambda g: -g[1])[:top],
        }
    return out


def format_log_stats(stats: dict) -> str:
    m = stats["meta"]
    lines = [f"profile {m.get('profile', '?')}  duration {stats['duration'] / 60:.1f} min  "
             f"started {time.strftime('%Y-%m-%d %H:%M', time.localtime(m.get('started', 0)))}"
             + ("" if m.get("ended") else "  (not closed cleanly)")]
    for ts, j in stats["jumps"]:
        lines.append(f"clock jump +{j / 3600:.1f} h at {time.strftime('%H:%M:%S', time.localtime(ts))}"
                     " (no RTC battery?), left out of the rates")
    lines.append(f"{'key':20} {'n':>7} {'Hz':>6} {'med':>6} {'p95':>6} {'p99':>6} {'max':>6} {'err':>5}")
    for key, s in sorted(stats["keys"].items(), key=lambda kv: -kv[1]["hz"]):
        lines.append(f"{key:20} {s['n']:7d} {s['hz']:6.2f} {s['median_gap']:6.2f} "
                     f"{s['p95_gap']:6.2f} {s['p99_gap']:6.2f} {s['max_gap']:6.1f} {s['errors']:5d}")
    return "\n".join(lines)
