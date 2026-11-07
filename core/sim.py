"""Simulated OBDLink: speaks ELM/STN text at the transport layer.

Plugs in under GuardedPort exactly like SerialTransport, so the guard,
driver, parser and poller all run for real. A 120 s drive cycle (idle,
accelerate, cruise, decelerate) produces values that agree with each other.
Unknown Mode 22 DIDs return NRC 31 like a real module would.
"""

from __future__ import annotations

import math
import random
import time
from typing import Callable

CYCLE = 120.0
SIM_VIN = "1FT7W2BT0EEA12345"


class SimVehicle:
    def __init__(self, clock: Callable[[], float] = time.monotonic, seed: int = 1):
        self.clock = clock
        self.t0 = clock()
        self.rng = random.Random(seed)
        self.odo_km = 182_345.6
        self._last = self.t0

    def _speed(self, c: float) -> float:
        if c < 20:
            return 0.0
        if c < 40:
            return 105 * (c - 20) / 20
        if c < 90:
            return 105 + 3 * math.sin(c / 4)
        if c < 110:
            return 105 * (110 - c) / 20
        return 0.0

    def _load(self, c: float) -> float:
        return 80 if 20 <= c < 40 else 35 if 40 <= c < 90 else 5 if 90 <= c < 110 else 15

    def state(self) -> dict:
        now = self.clock()
        t = now - self.t0
        c = t % CYCLE
        spd = self._speed(c)
        self.odo_km += spd * (now - self._last) / 3600
        self._last = now
        load = self._load(c)
        kmh_per_krpm = [12, 20, 30, 42, 55, 70]
        gear = max([i for i, k in enumerate(kmh_per_krpm) if spd / k * 1000 >= 1300] or [0])
        rpm = max(700.0, spd / kmh_per_krpm[gear] * 1000 + (300 if load >= 80 else 0))
        rpm += self.rng.uniform(-8, 8)
        warm = lambda tau: 1 - math.exp(-t / tau)
        vgt_des = 40 + load * 0.5
        vgt_act = 40 + self._load((c - 0.7) % CYCLE) * 0.5
        egt = 180 + load * 4.5 + self.rng.uniform(-3, 3)
        return {
            "rpm": rpm, "speed": spd, "load": load,
            "baro": 99.0, "map": 99.0 + load * 1.8,
            "coolant": 20 + 68 * warm(300), "iat": 30.0, "ambient": 24.0,
            "maf": 5 + load * 2.5, "fuel_level": 63.0, "run_s": t,
            "fuel_rate": 1.2 + load * 0.25,
            "odo_km": self.odo_km, "trans": 20 + 65 * warm(500), "oil": 20 + 75 * warm(400),
            "hours": 3712.4 + t / 3600, "vgt_des": vgt_des, "vgt_act": vgt_act,
            "egt": [egt, egt - 40, egt - 60, egt - 90],
            "rail_des": 300 + load * 15, "rail_act": 300 + load * 15 + self.rng.uniform(-10, 10),
            "soot": 23.5, "regen": 0, "volts": 14.1,
        }


def _u16(v: float) -> bytes:
    return int(max(0, min(0xFFFF, round(v)))).to_bytes(2, "big")


def _u8(v: float) -> bytes:
    return bytes([int(max(0, min(255, round(v))))])


# Mode 01 PID -> encoder(state) (data bytes only)
MODE01: dict[int, Callable[[dict], bytes]] = {
    0x01: lambda s: bytes([0x00, 0x07, 0xE5, 0x00]),          # MIL off, 0 DTCs
    0x04: lambda s: _u8(s["load"] * 255 / 100),
    0x0C: lambda s: _u16(s["rpm"] * 4),
    0x0D: lambda s: _u8(s["speed"]),
    0x0F: lambda s: _u8(s["iat"] + 40),
    0x10: lambda s: _u16(s["maf"] * 100),
    0x1F: lambda s: _u16(s["run_s"]),
    0x2F: lambda s: _u8(s["fuel_level"] * 255 / 100),
    0x33: lambda s: _u8(s["baro"]),
    0x46: lambda s: _u8(s["ambient"] + 40),
    0x5C: lambda s: _u8(s["oil"] + 40),
    0x87: lambda s: b"\x01" + _u16(s["map"] * 32) + b"\x00\x00",
    0x5E: lambda s: _u16(s["fuel_rate"] * 20),
    0x67: lambda s: b"\x03" + _u8(s["trans"] + 40) + _u8(s["coolant"] + 40),  # B low-temp loop, C engine
    0x6D: lambda s: b"\x03" + _u16(s["rail_des"] * 10) + _u16(s["rail_act"] * 10) + bytes(6),
    0x71: lambda s: b"\x07" + _u8(s["vgt_des"] * 2.55) + _u8(s["vgt_act"] * 2.55) + bytes(3),
    0x77: lambda s: b"\x01" + _u8(s["iat"] + 25 + 40) + bytes(3),
    0x78: lambda s: b"\x0F" + b"".join(_u16((e + 40) * 10) for e in s["egt"]),
    0x7F: lambda s: b"\x07" + int(s["hours"] * 3600).to_bytes(4, "big") + bytes(8),
    0x85: lambda s: b"\x1F" + bytes(4) + _u8(72 * 2.55) + bytes(4),
    0x8B: lambda s: bytes([0x07, s["regen"], 0x00, 0x00, 0x00, 0x00, 0x00]),
}
# Mirrors JP's 2014 F-250 bitmap: no PID 05 (coolant) or 0B (MAP); coolant
# comes from 67 and MAP from 87.

# (header, DID) -> encoder(state)
MODE22: dict[tuple[str, int], Callable[[dict], bytes]] = {
    ("720", 0x404C): lambda s: int(s["odo_km"] * 10).to_bytes(3, "big"),
    ("7E0", 0xDD01): lambda s: int(s["odo_km"]).to_bytes(3, "big"),
    ("7E1", 0x1E1C): lambda s: int(s["trans"] * 16).to_bytes(2, "big", signed=True),
    ("7E0", 0xF470): lambda s: b"\x01" + _u16(s["map"] * 32) + _u16(s["map"] * 32),
    ("7E0", 0xF471): lambda s: b"\x03" + _u8(s["vgt_des"] * 2.55) + _u8(s["vgt_act"] * 2.55),
    ("7E0", 0xF478): lambda s: b"\x0F" + b"".join(_u16((e + 40) * 10) for e in s["egt"]),
    ("7E0", 0xF46D): lambda s: b"\x03" + _u16(s["rail_des"] * 10) + _u16(s["rail_act"] * 10),
    ("7E0", 0xF45C): lambda s: _u8(s["oil"] + 40),
    ("7E0", 0x042C): lambda s: _u16(s["soot"] * 655.35),
    ("7E0", 0xF48B): lambda s: bytes([0x01, s["regen"], 0x00]),
}

RESPONDER = {"7DF": "7E8", "7E0": "7E8", "7E1": "7E9", "720": "728"}


def _bitmap(base: int, pids: set[int]) -> bytes:
    bits = 0
    for p in pids:
        if base < p <= base + 32:
            bits |= 1 << (32 - (p - base))
    return bits.to_bytes(4, "big")


class SimTransport:
    """Drop-in RawTransport that behaves like an OBDLink on a running truck."""

    def __init__(self, vehicle: SimVehicle | None = None, vin: str = SIM_VIN):
        self.v = vehicle or SimVehicle()
        self.vin = vin
        self.echo, self.spaces, self.headers = True, True, False
        self.header = "7DF"
        self.cra: str | None = None
        self._reply = ""
        supported = set(MODE01) | {0x20, 0x40, 0x60, 0x80}
        self.mode01 = dict(MODE01)
        for base in (0x00, 0x20, 0x40, 0x60, 0x80):
            self.mode01[base] = (lambda b: lambda s: _bitmap(b, supported))(base)

    # -- RawTransport --------------------------------------------------
    def write(self, data: bytes) -> None:
        cmd = data.decode("ascii").strip().replace(" ", "").upper()
        body = self._handle(cmd)
        self._reply = (cmd + "\r" if self.echo else "") + body

    def read_until_prompt(self, timeout: float) -> str:
        return self._reply + "\r\r>"

    def close(self) -> None:
        pass

    # -- behaviour -----------------------------------------------------
    def _handle(self, cmd: str) -> str:
        if cmd.startswith("AT"):
            return self._at(cmd[2:])
        if cmd.startswith("ST"):
            return {"I": "STN2230 v5.10.3 (JpCAN sim)", "DI": "OBDLink EX r1.0 (sim)",
                    "SN": "SIM000001"}.get(cmd[2:], "OK")
        return self._obd(bytes.fromhex(cmd[: len(cmd) // 2 * 2]))

    def _at(self, a: str) -> str:
        if a in ("Z", "WS"):
            self.echo, self.spaces, self.headers, self.header = True, True, False, "7DF"
            self.cra = None
            return "\rELM327 v1.4b"
        if a == "I":
            return "ELM327 v1.4b"
        if a == "RV":
            return f"{self.v.state()['volts']:.1f}V"
        if a == "DP":
            return "AUTO, ISO 15765-4 (CAN 11/500)"
        if a == "DPN":
            return "A6"
        if a[:1] in "ESH" and a[1:] in ("0", "1"):
            setattr(self, {"E": "echo", "S": "spaces", "H": "headers"}[a[0]], a[1] == "1")
            return "OK"
        if a.startswith("SH"):
            self.header = a[2:]
            return "OK"
        if a == "CRA":
            return "?"  # like JP's STN2232 v5.9.5: bare CRA unsupported, filter unchanged
        if a.startswith("CRA"):
            self.cra = a[3:]
            return "OK"
        return "OK"

    def _obd(self, req: bytes) -> str:
        if not req:
            return "?"
        svc, s = req[0], self.v.state()
        resp_id = RESPONDER.get(self.header)
        if resp_id is None or (self.cra and resp_id != self.cra):
            return "NO DATA"  # no responder, or receive filter blocks it
        if svc == 0x01 and len(req) >= 2 and self.header in ("7DF", "7E0"):
            out = bytearray([0x41])
            for pid in req[1:]:
                if pid not in self.mode01:
                    continue
                out += bytes([pid]) + self.mode01[pid](s)
            return self._frames(resp_id, bytes(out)) if len(out) > 1 else "NO DATA"
        if svc == 0x09 and req[1:2] == b"\x02" and self.header in ("7DF", "7E0"):
            return self._frames(resp_id, b"\x49\x02\x01" + self.vin.encode())
        if svc == 0x03 and self.header in ("7DF", "7E0"):
            return self._frames(resp_id, b"\x43\x00")
        if svc == 0x22 and len(req) == 3:
            did = int.from_bytes(req[1:3], "big")
            enc = MODE22.get((self.header, did))
            if enc is None:
                return self._frames(resp_id, bytes([0x7F, 0x22, 0x31]))
            return self._frames(resp_id, b"\x62" + req[1:3] + enc(s))
        return "NO DATA"

    def _frames(self, cid: str, payload: bytes) -> str:
        if len(payload) <= 7:
            frames = [bytes([len(payload)]) + payload]
        else:
            n = len(payload)
            frames = [bytes([0x10 | (n >> 8), n & 0xFF]) + payload[:6]]
            rest, seq = payload[6:], 1
            while rest:
                frames.append(bytes([0x20 | (seq & 0x0F)]) + rest[:7])
                rest, seq = rest[7:], seq + 1
        lines = []
        for f in frames:
            data = f if self.headers else f[1:]
            hexes = [f"{b:02X}" for b in data]
            body = " ".join(hexes) if self.spaces else "".join(hexes)
            if self.headers:
                body = cid + (" " if self.spaces else "") + body
            lines.append(body)
        return "\r".join(lines)
