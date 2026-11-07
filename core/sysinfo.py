"""Small local system readings for the status screen (stdlib only)."""

from __future__ import annotations

from pathlib import Path


def wifi_dbm(path: str = "/proc/net/wireless") -> int | None:
    """Signal level of the first wireless interface in dBm, or None."""
    try:
        lines = Path(path).read_text().splitlines()[2:]
    except OSError:
        return None
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 4 and parts[0].endswith(":"):
            try:
                return int(float(parts[3].rstrip(".")))
            except ValueError:
                return None
    return None


def wifi_label(dbm: int | None) -> str:
    """Compact header text: W-62 plus a rough grade, or 'W--' if not connected."""
    if dbm is None:
        return "W--"
    grade = "ok" if dbm >= -67 else "weak" if dbm >= -75 else "BAD"
    return f"W{dbm}{'' if grade == 'ok' else ' ' + grade}"
