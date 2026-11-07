"""In-process pub/sub. MQTT backend comes later with the same interface."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Reading:
    key: str
    value: float | None
    units: str
    ts: float
    error: str = ""


class Bus:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest: dict[str, Reading] = {}
        self._subs: list[Callable[[Reading], None]] = []

    def subscribe(self, cb: Callable[[Reading], None]) -> None:
        with self._lock:
            self._subs.append(cb)

    def publish(self, r: Reading) -> None:
        with self._lock:
            self._latest[r.key] = r
            subs = list(self._subs)
        for cb in subs:
            cb(r)

    def latest(self) -> dict[str, Reading]:
        with self._lock:
            return dict(self._latest)
