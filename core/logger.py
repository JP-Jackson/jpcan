"""Drive logger: one SQLite file per drive, long format (ts, key, value).

Readings are queued from the bus and written by a background thread in
batches every 5 s (WAL mode, so a power cut loses at most the last batch;
batching also keeps SD-card write cycles down). Errors are
logged once per key until a good value returns, to keep files small.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
from pathlib import Path

from .bus import Bus, Reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS readings (ts REAL NOT NULL, key TEXT NOT NULL, value REAL, err TEXT);
"""


def default_log_dir() -> Path:
    return Path.home() / "jpcan-logs"


class DriveLogger:
    def __init__(self, bus: Bus, log_dir: Path, profile_id: str, meta: dict,
                 flush_every: float = 5.0):
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_{profile_id}.sqlite"
        self._q: "queue.Queue[Reading | None]" = queue.Queue()
        self._flush_every = flush_every
        self._last_err: dict[str, str] = {}
        self.rows = 0
        self._meta = {**meta, "profile": profile_id, "started": time.time()}
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._ready = threading.Event()
        self._thread.start()
        self._ready.wait(5)
        bus.subscribe(self.on_reading)

    def on_reading(self, r: Reading) -> None:
        if r.error:
            if self._last_err.get(r.key) == r.error:
                return
            self._last_err[r.key] = r.error
        else:
            self._last_err.pop(r.key, None)
        self._q.put(r)

    def _run(self) -> None:
        db = sqlite3.connect(self.path)
        db.executescript(SCHEMA)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                       [(k, json.dumps(v)) for k, v in self._meta.items()])
        db.commit()
        self._ready.set()
        batch: list[tuple] = []
        last = time.monotonic()
        done = False
        while not done:
            try:
                r = self._q.get(timeout=self._flush_every)
                if r is None:
                    done = True
                else:
                    batch.append((r.ts, r.key, r.value, r.error or None))
            except queue.Empty:
                pass
            if batch and (done or time.monotonic() - last >= self._flush_every):
                db.executemany("INSERT INTO readings VALUES (?, ?, ?, ?)", batch)
                db.commit()
                self.rows += len(batch)
                batch.clear()
                last = time.monotonic()
        db.execute("INSERT OR REPLACE INTO meta VALUES ('ended', ?)", (json.dumps(time.time()),))
        db.commit()
        db.close()

    def close(self) -> None:
        self._q.put(None)
        self._thread.join(timeout=10)
