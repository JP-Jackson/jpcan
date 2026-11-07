"""Find Ford-specific data IDs (DIDs) by asking a module for each one.

READ-ONLY: every request is service 22 (Read Data By Identifier) and goes
through Elm -> GuardedPort -> RequestGuard like everything else. The header
must be in the guard's allowlist. Requests are throttled by the port's
min_gap; scanning 256 DIDs at the default 0.1 s gap takes ~30 s.

scan():  try each DID once -> answered (bytes) / NRC (e.g. 31 = not supported,
         33 = exists but security-locked) / no reply.
watch(): poll a list of DIDs plus rpm/speed repeatedly, track how each value
         changes, and score how often a byte equals the estimated gear. The
         real gear DID is the one whose value steps 1..6 with the shifts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .elm import Elm, ElmError, NegativeResponse, NoData

MAX_SCAN = 4096


def parse_ranges(specs: list[str]) -> list[int]:
    """['1E00-1E3F', '1674'] -> sorted unique ints. Raises ValueError if too many."""
    out: set[int] = set()
    for spec in specs:
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = (int(x, 16) for x in part.split("-", 1))
                if b < a or not (0 <= a <= 0xFFFF and 0 <= b <= 0xFFFF):
                    raise ValueError(f"bad range {part}")
                out.update(range(a, b + 1))
            else:
                out.add(int(part, 16))
    if len(out) > MAX_SCAN:
        raise ValueError(f"{len(out)} DIDs requested; max {MAX_SCAN} per run")
    return sorted(out)


@dataclass
class ScanResult:
    did: int
    status: str            # "ok", "nrc", "none", "error"
    data: bytes = b""
    nrc: int | None = None

    def as_dict(self) -> dict:
        return {"did": f"{self.did:04X}", "status": self.status, "data": self.data.hex().upper(),
                "nrc": None if self.nrc is None else f"{self.nrc:02X}"}


def scan(elm: Elm, header: str, dids: list[int], progress=None) -> list[ScanResult]:
    results = []
    for i, did in enumerate(dids):
        try:
            r = ScanResult(did, "ok", elm.read("22", f"{did:04X}", header, timeout=0.6))
        except NegativeResponse as e:
            r = ScanResult(did, "nrc", nrc=e.nrc)
        except NoData:
            r = ScanResult(did, "none")
        except ElmError:
            r = ScanResult(did, "error")
        results.append(r)
        if progress:
            progress(i + 1, len(dids), r)
    return results


@dataclass
class WatchStat:
    did: int
    last: bytes = b""
    changes: int = 0
    first_byte_values: set = field(default_factory=set)
    samples: int = 0
    gear_hits: int = 0      # samples where some byte == estimated gear
    gear_samples: int = 0   # samples taken while a gear was estimated

    @property
    def gear_match(self) -> float:
        return self.gear_hits / self.gear_samples if self.gear_samples else 0.0


class Watcher:
    """Round-robin poll of DIDs plus rpm/speed; gear estimator optional."""

    def __init__(self, elm: Elm, header: str, dids: list[int], obd_header: str = "7DF",
                 estimator=None, log=None):
        self.elm, self.header, self.obd_header = elm, header, obd_header
        self.stats = {d: WatchStat(d) for d in dids}
        self.estimator = estimator
        self.log = log
        self.rpm: float | None = None
        self.kmh: float | None = None
        self.gear: int | None = None

    def _obd(self, pid: str, fn):
        try:
            return fn(self.elm.read("01", pid, self.obd_header))
        except ElmError:
            return None

    def cycle(self) -> None:
        for did, st in self.stats.items():
            self.rpm = self._obd("0C", lambda b: (b[0] * 256 + b[1]) / 4) or self.rpm
            self.kmh = self._obd("0D", lambda b: float(b[0]))
            if self.estimator and self.rpm is not None and self.kmh is not None:
                self.gear = self.estimator.estimate(self.rpm, self.kmh)[0]
            try:
                data = self.elm.read("22", f"{did:04X}", self.header, timeout=0.6)
            except ElmError:
                continue
            st.samples += 1
            if st.last and data != st.last:
                st.changes += 1
            st.last = data
            if data:
                st.first_byte_values.add(data[0])
            if self.gear is not None:
                st.gear_samples += 1
                st.gear_hits += int(self.gear in data)
            if self.log:
                self.log.write(f'{{"t":{time.time():.2f},"did":"{did:04X}","data":"{data.hex().upper()}",'
                               f'"rpm":{self.rpm or 0:.0f},"kmh":{self.kmh or 0:.0f},'
                               f'"gear_est":{self.gear or 0}}}\n')

    def ranked(self) -> list[WatchStat]:
        """Best gear candidates first: high match, values within 0..10, some changes."""
        def score(s: WatchStat):
            small = bool(s.first_byte_values) and max(s.first_byte_values) <= 10
            return (s.gear_match, small, s.changes)
        return sorted(self.stats.values(), key=score, reverse=True)
