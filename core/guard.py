"""RequestGuard: the single gate every outgoing adapter command passes through.

Read-only by construction:
  * OBD requests: only services 01, 03, 09, 22, in their expected shapes.
  * Adapter commands: an explicit AT/ST allowlist (not a prefix match).
  * ATSH headers: only 7DF, 7E0-7E7, plus headers declared by the active profile.
Everything else is blocked and logged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("jpcan.guard")

ALLOWED_SERVICES = {"01", "03", "09", "22"}
DEFAULT_HEADERS = frozenset({"7DF"} | {f"7E{i}" for i in range(8)})

_HEX = "[0-9A-F]"

# Adapter-local commands, matched against the text after "AT" / "ST".
# Anything not listed here is blocked. Add entries deliberately, with a reason.
AT_ALLOW: dict[str, str] = {
    r"Z": "reset",
    r"WS": "warm start",
    r"D": "set defaults",
    r"I": "version id",
    r"E[01]": "echo off/on",
    r"L[01]": "linefeeds off/on",
    r"S[01]": "spaces off/on",
    r"H[01]": "headers off/on",
    r"R[01]": "responses off/on",
    r"AT[012]": "adaptive timing",
    rf"ST{_HEX}{{2}}": "response timeout",
    rf"SPA?{_HEX}": "set protocol",
    rf"TPA?{_HEX}": "try protocol",
    r"DPN?": "describe protocol",
    r"PC": "protocol close",
    r"RV": "read voltage",
    rf"SH(?:{_HEX}{{3}}|{_HEX}{{6}})": "set header (header allowlist applies)",
    rf"CRA(?:{_HEX}{{3}})?": "set/clear CAN receive address",
    r"CAF1": "CAN auto formatting ON only (CAF0 would allow raw frames)",
    r"CFC1": "CAN flow control ON only",
}

ST_ALLOW: dict[str, str] = {
    r"I": "firmware id",
    r"DI": "device id",
    r"SN": "serial number",
    r"P\d{1,3}": "set protocol (HS-CAN/MS-CAN select)",
    r"PRS?": "report protocol",
}

_AT_RE = [(re.compile(p), why) for p, why in AT_ALLOW.items()]
_ST_RE = [(re.compile(p), why) for p, why in ST_ALLOW.items()]


class GuardViolation(Exception):
    """Raised when a command is blocked. The command was NOT sent."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    command: str  # normalized
    reason: str


@dataclass
class RequestGuard:
    extra_headers: set[str] = field(default_factory=set)
    sent: int = 0
    blocked: int = 0

    @property
    def allowed_headers(self) -> frozenset[str]:
        return DEFAULT_HEADERS | {h.upper() for h in self.extra_headers}

    # -- public API -------------------------------------------------------
    def check(self, command: str) -> Decision:
        """Classify a command without side effects."""
        if not isinstance(command, str):
            return Decision(False, repr(command), "not a string")
        if re.search(r"[\r\n\x00-\x1f;]", command):
            return Decision(False, command, "control chars / multiple commands not allowed")
        norm = command.replace(" ", "").upper()
        if not norm:
            return Decision(False, norm, "empty command")
        if not re.fullmatch(r"[0-9A-Z]+", norm):
            return Decision(False, norm, "invalid characters")
        if norm.startswith("AT"):
            return self._check_adapter(norm, norm[2:], _AT_RE, "AT")
        if norm.startswith("ST"):
            return self._check_adapter(norm, norm[2:], _ST_RE, "ST")
        return self._check_obd(norm)

    def enforce(self, command: str) -> str:
        """Return the normalized command if allowed; else log, count and raise."""
        d = self.check(command)
        if not d.allowed:
            self.blocked += 1
            log.warning("BLOCKED %r: %s", d.command, d.reason)
            raise GuardViolation(f"{d.command}: {d.reason}")
        self.sent += 1
        return d.command

    # -- internals --------------------------------------------------------
    def _check_adapter(self, norm, body, table, prefix) -> Decision:
        for rx, why in table:
            if rx.fullmatch(body):
                if prefix == "AT" and body.startswith("SH"):
                    hdr = body[2:]
                    if hdr not in self.allowed_headers:
                        return Decision(False, norm, f"header {hdr} not in allowlist")
                return Decision(True, norm, why)
        return Decision(False, norm, f"{prefix} command not in allowlist")

    def _check_obd(self, norm: str) -> Decision:
        if not re.fullmatch(r"[0-9A-F]+", norm):
            return Decision(False, norm, "not hex")
        data = norm
        # ELM/STN allow one trailing hex digit = expected response count.
        if len(data) % 2 == 1:
            data = data[:-1]
            if data == "" or norm[-1] == "0":
                return Decision(False, norm, "malformed request")
        svc, payload = data[:2], data[2:]
        nbytes = len(payload) // 2
        if svc not in ALLOWED_SERVICES:
            return Decision(False, norm, f"service {svc} not allowed (read-only)")
        if svc == "01" and not 1 <= nbytes <= 6:
            return Decision(False, norm, "service 01 needs 1-6 PIDs")
        if svc == "03" and nbytes != 0:
            return Decision(False, norm, "service 03 takes no data")
        if svc == "09" and nbytes != 1:
            return Decision(False, norm, "service 09 needs exactly 1 PID")
        if svc == "22" and (nbytes == 0 or nbytes % 2 or nbytes > 6):
            return Decision(False, norm, "service 22 needs 1-3 two-byte DIDs")
        return Decision(True, norm, f"service {svc}")
