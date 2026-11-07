"""User settings (JSON). Machine-written; profiles stay YAML."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS: dict = {
    "units": "imperial",
    "touch": {"axis": None, "invert": False},  # set by `jpcan touch-cal`
    "econ_corrected": False,                    # show fill-up-corrected MPG
    "econ_window_mi": 10,                       # "Last N" tile: 5/10/25/50
}


def path() -> Path:
    base = os.environ.get("JPCAN_CONFIG") or Path.home() / ".config" / "jpcan"
    return Path(base) / "settings.json"


def load() -> dict:
    data = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    try:
        user = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k].update(v)
        else:
            data[k] = v
    return data


def save(data: dict) -> Path:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)  # atomic: survives power loss mid-write
    return p
