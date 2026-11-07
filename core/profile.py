"""Vehicle profiles: YAML, with `extends` inheritance and guard validation.

A profile can never contain a request the guard would block: load fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .formula import Formula
from .guard import RequestGuard

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
REQUIRED = ("name", "service", "pid", "header", "formula", "units", "min", "max",
            "poll_rate", "verified", "source")
POLL_RATES = {"fast", "slow", "once"}


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class Pid:
    key: str
    name: str
    service: str        # "01", "09", "22", or "AT" for adapter reads (ATRV)
    pid: str
    header: str
    formula: Formula
    units: str
    min: float
    max: float
    poll_rate: str
    verified: bool
    source: str
    notes: str = ""

    @property
    def request(self) -> str:
        return f"{self.service}{self.pid}"


@dataclass
class Profile:
    id: str
    name: str
    pids: dict[str, Pid]
    headers: dict[str, str] = field(default_factory=dict)
    shift: dict = field(default_factory=lambda: {"enabled": False, "rpm": 3000})
    match: dict = field(default_factory=dict)
    layouts: dict[str, list[str]] = field(default_factory=dict)

    @property
    def extra_headers(self) -> set[str]:
        return {p.header for p in self.pids.values()} | set(self.headers.values())

    def matches_vin(self, vin: str | None) -> bool:
        if not vin or len(vin) != 17 or not self.match:
            return False
        m = self.match
        return (vin[:3] in m.get("wmi", [])
                and vin[9] == m.get("year", vin[9])
                and vin[7] == m.get("engine", vin[7]))


def _s(v) -> str:
    return str(v).strip().upper()


def _raw(name_or_path: str | Path, base_dir: Path, seen=()) -> dict:
    path = Path(name_or_path)
    if path.suffix not in (".yaml", ".yml"):
        path = base_dir / f"{name_or_path}.yaml"
    if path.stem in seen:
        raise ProfileError(f"circular extends: {path.stem}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parent = data.get("extends")
    if not parent:
        return data
    base = _raw(parent, path.parent, (*seen, path.stem))
    merged = {**base, **{k: v for k, v in data.items() if k != "pids"}}
    merged["pids"] = {**(base.get("pids") or {}), **(data.get("pids") or {})}
    merged["layouts"] = {**(base.get("layouts") or {}), **(data.get("layouts") or {})}
    return merged


def load_profile(name_or_path: str | Path, base_dir: Path = PROFILES_DIR) -> Profile:
    data = _raw(name_or_path, base_dir)
    pids: dict[str, Pid] = {}
    for key, e in (data.get("pids") or {}).items():
        missing = [f for f in REQUIRED if f not in e]
        if missing:
            raise ProfileError(f"{key}: missing {missing}")
        if e["poll_rate"] not in POLL_RATES:
            raise ProfileError(f"{key}: poll_rate must be one of {POLL_RATES}")
        pids[key] = Pid(key=key, name=e["name"], service=_s(e["service"]).zfill(2),
                        pid=_s(e["pid"]), header=_s(e["header"]), formula=Formula(str(e["formula"])),
                        units=str(e["units"]), min=float(e["min"]), max=float(e["max"]),
                        poll_rate=e["poll_rate"], verified=bool(e["verified"]),
                        source=str(e["source"]), notes=str(e.get("notes", "")))
    prof = Profile(id=data.get("id", Path(str(name_or_path)).stem), name=data.get("name", ""),
                   pids=pids, headers={k: _s(v) for k, v in (data.get("headers") or {}).items()},
                   shift=data.get("shift") or {"enabled": False, "rpm": 3000},
                   match=data.get("match") or {}, layouts=data.get("layouts") or {})
    _validate(prof)
    return prof


def _validate(prof: Profile) -> None:
    guard = RequestGuard(extra_headers=prof.extra_headers)
    for p in prof.pids.values():
        req = "AT" + p.pid if p.service == "AT" else p.request
        d = guard.check(req)
        if not d.allowed:
            raise ProfileError(f"{p.key}: request {req} blocked by guard ({d.reason})")
        if p.service != "AT" and not guard.check(f"ATSH{p.header}").allowed:
            raise ProfileError(f"{p.key}: header {p.header} invalid")
    for name, keys in prof.layouts.items():
        bad = [k for k in keys if k not in prof.pids]
        if bad:
            raise ProfileError(f"layout {name}: unknown pids {bad}")


def list_profiles(base_dir: Path = PROFILES_DIR) -> list[str]:
    return sorted(p.stem for p in base_dir.glob("*.yaml") if not p.stem.startswith("base_"))


def select_profile(vin: str | None, base_dir: Path = PROFILES_DIR) -> Profile:
    """Pick a vehicle profile by VIN; fall back to the universal base."""
    for name in list_profiles(base_dir):
        prof = load_profile(name, base_dir)
        if prof.matches_vin(vin):
            return prof
    return load_profile("base_mode01", base_dir)
