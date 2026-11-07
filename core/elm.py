"""ELM327/STN driver on top of GuardedPort.

Runs with echo off, spaces off, headers on (ATH1) so every reply line carries
its CAN ID; multi-frame (ISO-TP) replies are reassembled per CAN ID.
11-bit CAN only for now.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .transport import GuardedPort

ERROR_MARKERS = ("NO DATA", "CAN ERROR", "STOPPED", "UNABLE TO CONNECT", "BUS ERROR",
                 "BUFFER FULL", "DATA ERROR", "FB ERROR", "BUS BUSY", "RX ERROR",
                 "LV RESET", "ACT ALERT", "ERR")
OBD_HEADERS = {"7DF"} | {f"7E{i}" for i in range(8)}


class ElmError(Exception):
    pass


class NoData(ElmError):
    pass


class NegativeResponse(ElmError):
    def __init__(self, service: int, nrc: int):
        super().__init__(f"negative response to {service:02X}: NRC {nrc:02X}")
        self.service, self.nrc = service, nrc


def clean(reply: str) -> list[str]:
    """Split a raw reply into meaningful lines (drop prompt, blanks, SEARCHING)."""
    lines = []
    for ln in reply.replace(">", "").replace("\n", "\r").split("\r"):
        ln = ln.strip()
        if ln and not ln.startswith("SEARCHING") and not ln.startswith("BUS INIT"):
            lines.append(ln)
    return lines


def parse_frames(reply: str) -> dict[str, bytes]:
    """Reassemble headers-on, spaces-off CAN reply lines into {can_id: payload}."""
    out: dict[str, bytearray] = {}
    total: dict[str, int] = {}
    for ln in clean(reply):
        ln = ln.replace(" ", "")
        if any(m in ln for m in ERROR_MARKERS) or not re.fullmatch(r"[0-9A-F]{3}[0-9A-F]{2,16}", ln):
            continue
        cid, frame = ln[:3], bytes.fromhex(ln[3:] if len(ln[3:]) % 2 == 0 else ln[3:-1])
        if not frame:
            continue
        kind = frame[0] >> 4
        if kind == 0:  # single frame
            out[cid] = bytearray(frame[1:1 + (frame[0] & 0x0F)])
            total[cid] = len(out[cid])
        elif kind == 1 and len(frame) >= 2:  # first frame
            total[cid] = ((frame[0] & 0x0F) << 8) | frame[1]
            out[cid] = bytearray(frame[2:])
        elif kind == 2 and cid in out:  # consecutive frame
            out[cid] += frame[1:]
    return {cid: bytes(buf[:total.get(cid, len(buf))]) for cid, buf in out.items()}


@dataclass
class AdapterInfo:
    elm: str = ""
    stn: str = ""
    voltage: str = ""
    protocol: str = ""


class Elm:
    def __init__(self, port: GuardedPort):
        self.port = port
        self.header: str | None = None

    # -- adapter-local ---------------------------------------------------
    def at(self, cmd: str, timeout: float = 1.0) -> str:
        lines = [ln for ln in clean(self.port.query(cmd, timeout)) if ln.replace(" ", "") != cmd]
        return " ".join(lines)

    def init(self) -> AdapterInfo:
        self.at("ATZ", timeout=3.0)
        for cmd in ("ATE0", "ATL0", "ATS0", "ATH1", "ATAT1", "ATSP0"):
            self.at(cmd)
        # Detect the protocol with the power-on defaults (header 7DF, automatic
        # receive filter). CAN-only commands like ATCRA are rejected ('?')
        # until the protocol is known, so no ATSH/ATCRA before this.
        self.header = None
        if not parse_frames(self.port.query("0100", 6.0)):
            raise NoData("0100 (protocol detect): no vehicle response")
        self.header = "7DF"  # default header; filter still automatic
        return self.info()

    def info(self) -> AdapterInfo:
        return AdapterInfo(elm=self.at("ATI"), stn=self.at("STI"),
                           voltage=self.at("ATRV"), protocol=self.at("ATDP"))

    def voltage(self) -> float | None:
        m = re.search(r"(\d+(?:\.\d+)?)", self.at("ATRV"))
        return float(m.group(1)) if m else None

    def set_header(self, header: str) -> None:
        header = header.upper()
        if header == self.header:
            return
        # Always set an explicit receive filter: bare "ATCRA" (reset) isn't
        # supported by all firmware (JP's STN2232 v5.9.5 left it stuck on 728).
        # Broadcast 7DF listens to the PCM (7E8); physical IDs reply on id + 8.
        rx = "7E8" if header == "7DF" else f"{int(header, 16) + 8:03X}"
        self.header = None  # unknown state until both commands succeed
        for cmd in (f"ATSH{header}", f"ATCRA{rx}"):
            reply = self.at(cmd)
            if "OK" not in reply:
                raise ElmError(f"adapter rejected {cmd}: {reply!r}")
        self.header = header

    # -- requests --------------------------------------------------------
    def request(self, cmd: str, header: str = "7DF", timeout: float = 1.0) -> dict[str, bytes]:
        self.set_header(header)
        if header.upper() != "7DF":
            cmd += "1"  # physical request: one responder, STN returns as soon as it answers
        frames = parse_frames(self.port.query(cmd, timeout))
        if not frames:
            raise NoData(cmd)
        return frames

    def read(self, service: str, pid: str, header: str = "7DF", timeout: float = 1.0) -> bytes:
        """Return data bytes after the echoed service/PID. Raises NoData/NegativeResponse."""
        svc = int(service, 16)
        echo = bytes.fromhex(pid)
        frames = self.request(f"{service}{pid}", header, timeout)
        neg = None
        for cid in sorted(frames):
            p = frames[cid]
            if len(p) >= 3 and p[0] == 0x7F and p[1] == svc:
                neg = NegativeResponse(svc, p[2])
            elif p[:1] == bytes([svc + 0x40]) and p[1:1 + len(echo)] == echo:
                return p[1 + len(echo):]
        raise neg or NoData(f"{service}{pid}")

    def supported_pids(self) -> set[int]:
        """Mode 01 PIDs advertised via the 00/20/40/... bitmaps."""
        supported: set[int] = set()
        base = 0
        while base <= 0xE0:
            try:
                data = self.read("01", f"{base:02X}", "7DF", timeout=2.0)
            except ElmError:
                break
            bits = int.from_bytes(data[:4], "big")
            for i in range(32):
                if bits & (1 << (31 - i)):
                    supported.add(base + i + 1)
            if base + 0x20 not in supported:
                break
            base += 0x20
        return supported

    def vin(self) -> str | None:
        try:
            data = self.read("09", "02", "7DF", timeout=2.0)
        except ElmError:
            return None
        text = bytes(b for b in data if 0x30 <= b <= 0x5A).decode("ascii")
        return text[-17:] if len(text) >= 17 else None
