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
MPH = 1.609344

# Drive scenarios for the bench (Settings > Simulator). Each loops. Segments are
# (seconds, start mph, end mph, engine load %). Problem scenarios show what the
# screen does when something goes wrong; the sim never touches a real truck.
SCENARIOS: dict[str, dict] = {
    "cycle": {"label": "Loop", "desc": "The original 2-minute loop (cold start)"},
    "normal": {"label": "Normal to 75", "desc": "Idle 3 s, normal acceleration to 75 mph, cruise, stop",
               "segs": [(3, 0, 0, 15), (22, 0, 75, 60), (25, 75, 75, 35), (15, 75, 0, 5)]},
    "hard": {"label": "Hard to 105", "desc": "Idle 3 s, hard acceleration to 105 mph, slow to 75, cruise, stop",
             "segs": [(3, 0, 0, 15), (16, 0, 105, 100), (12, 105, 75, 5), (20, 75, 75, 35), (14, 75, 0, 5)]},
    "tow": {"label": "Towing a hill", "desc": "Pull to 60 mph and hold it up a long grade: temps climb",
            "segs": [(3, 0, 0, 15), (20, 0, 60, 85), (80, 60, 60, 90), (15, 60, 0, 5)]},
    "overheat": {"label": "Overheat", "desc": "Coolant climbs past its red line and blinks", "problem": True,
                 "segs": [(3, 0, 0, 15), (22, 0, 75, 60), (40, 75, 75, 45), (15, 75, 0, 5)]},
    "overboost": {"label": "Overboost", "desc": "Hard pulls past 20 psi and 3,000 rpm: both blink, peak needles hold",
                  "problem": True, "segs": [(3, 0, 0, 15), (14, 0, 80, 100), (14, 80, 40, 5), (6, 40, 40, 30)]},
    "vgt": {"label": "VGT sticking", "desc": "Turbo vanes stuck at 30% while the ECU asks for more: DIFF goes red",
            "problem": True, "segs": [(3, 0, 0, 15), (22, 0, 75, 60), (25, 75, 75, 35), (15, 75, 0, 5)]},
    "cel": {"label": "Check engine", "desc": "Check-engine light on with 2 stored codes: the CEL banner shows",
            "problem": True, "segs": [(3, 0, 0, 15), (22, 0, 75, 60), (25, 75, 75, 35), (15, 75, 0, 5)]},
    "dropout": {"label": "Sensor dropout", "desc": "Trans, oil and rail stop answering for 20 s at a time: they show --",
                "problem": True, "segs": [(3, 0, 0, 15), (22, 0, 75, 60), (25, 75, 75, 35), (15, 75, 0, 5)]},
    "signal": {"label": "Signal loss", "desc": "Everything stops answering for 10 s every 45 s, like a loose plug",
               "problem": True, "segs": [(3, 0, 0, 15), (22, 0, 75, 60), (25, 75, 75, 35), (15, 75, 0, 5)]},
}
SIM_DTCS = ("P0299", "P2463")   # turbo underboost, DPF soot accumulation (examples)


def _dtc_bytes(code: str) -> bytes:
    first = "PCBU".index(code[0]) << 14
    return (first | int(code[1:], 16)).to_bytes(2, "big")


class SimVehicle:
    def __init__(self, clock: Callable[[], float] = time.monotonic, seed: int = 1, scenario: str = "cycle"):
        self.scenario = scenario if scenario in SCENARIOS else "cycle"
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
        if self.scenario != "cycle":
            return self._scenario_state()
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
            "gear": gear + 1 if spd > 1 else 0,
            "rpm": rpm, "speed": spd, "load": load,
            "baro": 99.0, "map": 99.0 + 2 + max(0.0, load - 15) * 2.2,
            "coolant": 20 + 68 * warm(300), "iat": 30.0, "ambient": 24.0,
            "maf": 5 + load * 2.5, "fuel_level": 63.0, "run_s": t,
            "fuel_rate": 1.2 + load * 0.25,
            "odo_km": self.odo_km, "trans": 20 + 65 * warm(500), "oil": 20 + 75 * warm(400),
            "hours": 3712.4 + t / 3600, "vgt_des": vgt_des, "vgt_act": vgt_act,
            "egt": [egt, egt - 40, egt - 60, egt - 90],
            "rail_des": 300 + load * 15, "rail_act": 300 + load * 15 + self.rng.uniform(-10, 10),
            "soot": 23.5, "regen": 0, "volts": 14.1,
        }


def _seg_state(segs, c: float) -> tuple[float, float, bool]:
    """Speed (km/h), load and 'accelerating' at time c into a segment list."""
    t = 0.0
    for dur, v0, v1, load in segs:
        if c < t + dur:
            f = (c - t) / dur
            return (v0 + (v1 - v0) * f) * MPH, load, v1 > v0
        t += dur
    return 0.0, 15, False


def _scenario_state(self) -> dict:
    sc = SCENARIOS[self.scenario]
    segs = sc["segs"]
    period = sum(d for d, *_ in segs)
    now = self.clock()
    t = now - self.t0
    c = t % period
    spd, load, accel = _seg_state(segs, c)
    self.odo_km += spd * (now - self._last) / 3600
    self._last = now
    name = self.scenario
    # shift point: higher under load (hard pulls rev out), low at cruise
    shift = 1700 + (load / 100) * 1200 if accel else 1750
    if name == "overboost" and accel:
        shift = 3400
    kmh_per_krpm = [12, 20, 30, 42, 55, 70]
    gear = 5
    for i, k in enumerate(kmh_per_krpm):
        if spd / k * 1000 <= shift:
            gear = i
            break
    rpm = max(700.0, spd / kmh_per_krpm[gear] * 1000) + self.rng.uniform(-8, 8)
    boost = max(0.0, load - 15) * 0.2                      # psi: about 17 at full load
    if name == "overboost" and accel:
        boost = max(0.0, load - 15) * 0.33                 # about 28 psi
    boost += self.rng.uniform(-0.15, 0.15) if boost > 1 else 0
    baro = 99.0
    coolant, trans, oil, iat = 88.0, 77.0, 96.0, 30.0       # warmed up: 190, 171, 205, 86 F
    if name == "tow":
        heat = min(1.0, max(0.0, (c - 23) / 80))
        coolant, trans, oil, iat = 88 + 14 * heat, 77 + 30 * heat, 96 + 14 * heat, 30 + 22 * heat
    if name == "overheat":
        coolant = 88 + min(30.0, t * 0.6)                   # past 235 F after ~40 s, then holds
    vgt_des = 40 + load * 0.5
    vgt_act = vgt_des + self.rng.uniform(-1.5, 1.5)
    if name == "vgt":
        vgt_act = 30.0
    egt = 180 + load * 4.5 + self.rng.uniform(-3, 3)
    st = {
        "gear": gear + 1 if spd > 1 else 0,
        "rpm": rpm, "speed": spd, "load": load,
        "baro": baro, "map": baro + 2 + boost / 0.145038,
        "coolant": coolant, "coolant2": coolant - 8, "iat": iat, "ambient": 32.0,
        "maf": 5 + load * 2.5, "fuel_level": 63.0, "run_s": t,
        "fuel_rate": 1.2 + load * 0.25,
        "odo_km": self.odo_km, "trans": trans, "oil": oil,
        "hours": 3712.4 + t / 3600, "vgt_des": vgt_des, "vgt_act": vgt_act,
        "egt": [egt, egt - 40, egt - 60, egt - 90],
        "rail_des": 300 + load * 15, "rail_act": 300 + load * 15 + self.rng.uniform(-10, 10),
        "soot": 23.5, "regen": 0, "volts": 14.1,
    }
    if name == "cel":
        st["mil"], st["dtcs"] = True, SIM_DTCS
    if name == "dropout" and t % 40 >= 20:
        st["_drop"] = {"trans", "oil", "rail"}
    if name == "signal" and t % 45 >= 35:
        st["_dead"] = True
    return st


SimVehicle._scenario_state = _scenario_state

# readings each "_drop" name silences (Mode 01 PIDs and Mode 22 DIDs)
DROP01 = {"oil": {0x5C}, "rail": {0x6D}}
DROP22 = {"trans": {("7E1", 0x1E1C)}, "oil": {("7E0", 0xF45C)}, "rail": {("7E0", 0xF46D)}}


def _u16(v: float) -> bytes:
    return int(max(0, min(0xFFFF, round(v)))).to_bytes(2, "big")


def _u8(v: float) -> bytes:
    return bytes([int(max(0, min(255, round(v))))])


# Mode 01 PID -> encoder(state) (data bytes only)
MODE01: dict[int, Callable[[dict], bytes]] = {
    0x01: lambda s: bytes([(0x80 if s.get("mil") else 0) | len(s.get("dtcs", ())), 0x07, 0xE5, 0x00]),
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
    0x67: lambda s: b"\x03" + _u8(s["coolant"] + 40) + _u8(s.get("coolant2", s["coolant"] - 8) + 40),  # B engine, C sensor 2
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
    # Fictional TCM DIDs so didscan/didwatch can be exercised in the sim. The
    # real Ford gear DID is what didscan is for; these are NOT real IDs.
    ("7E1", 0x1E10): lambda s: b"\x00",
    ("7E1", 0x1E12): lambda s: bytes([s["gear"]]),
    ("7E1", 0x1E23): lambda s: _u16(s["rpm"]),
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

    def __init__(self, vehicle: SimVehicle | None = None, vin: str = SIM_VIN, scenario: str = "cycle"):
        self.v = vehicle or SimVehicle(scenario=scenario)
        self.vin = vin
        self.echo, self.spaces, self.headers = True, True, False
        self.header = "7DF"
        self.cra: str | None = None
        self.protocol_known = False
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
        self._count1 = len(cmd) % 2 == 1 and cmd.endswith("1")
        return self._obd(bytes.fromhex(cmd[: len(cmd) // 2 * 2]))

    def _at(self, a: str) -> str:
        if a in ("Z", "WS"):
            self.echo, self.spaces, self.headers, self.header = True, True, False, "7DF"
            self.cra = None
            self.protocol_known = False
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
        if a.startswith("CRA") and not self.protocol_known:
            return "?"  # CAN-only command before protocol auto-detect
        if a.startswith("CRA"):
            self.cra = a[3:]
            return "OK"
        return "OK"

    def _obd(self, req: bytes) -> str:
        if not req:
            return "?"
        svc, s = req[0], self.v.state()
        self.protocol_known = True
        if s.get("_dead"):
            return "NO DATA"
        drop = s.get("_drop") or ()
        drop01 = set().union(*(DROP01.get(d, set()) for d in drop)) if drop else set()
        drop22 = set().union(*(DROP22.get(d, set()) for d in drop)) if drop else set()
        resp_id = RESPONDER.get(self.header)
        if resp_id is None or (self.cra and resp_id != self.cra):
            return "NO DATA"  # no responder, or receive filter blocks it
        if svc == 0x01 and len(req) >= 2 and self.header in ("7DF", "7E0"):
            out = bytearray([0x41])
            for pid in req[1:]:
                if pid not in self.mode01 or pid in drop01:
                    continue
                out += bytes([pid]) + self.mode01[pid](s)
            return self._frames(resp_id, bytes(out)) if len(out) > 1 else "NO DATA"
        if svc == 0x09 and req[1:2] == b"\x02" and self.header in ("7DF", "7E0"):
            return self._frames(resp_id, b"\x49\x02\x01" + self.vin.encode())
        if svc == 0x03 and self.header in ("7DF", "7E0"):
            codes = s.get("dtcs") or ()
            return self._frames(resp_id, b"\x43" + bytes([len(codes)]) + b"".join(_dtc_bytes(x) for x in codes))
        if svc == 0x22 and len(req) == 3:
            did = int.from_bytes(req[1:3], "big")
            enc = MODE22.get((self.header, did))
            if (self.header, did) in drop22:
                return "NO DATA"
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
        if getattr(self, "_count1", False):
            frames = frames[:1]  # like the STN: response count 1 = stop after first frame
        lines = []
        for f in frames:
            data = f if self.headers else f[1:]
            hexes = [f"{b:02X}" for b in data]
            body = " ".join(hexes) if self.spaces else "".join(hexes)
            if self.headers:
                body = cid + (" " if self.spaces else "") + body
            lines.append(body)
        return "\r".join(lines)
