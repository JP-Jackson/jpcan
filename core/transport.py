"""Transports and the GuardedPort: the ONLY path that writes to the adapter.

Raw transports (serial or sim) are handed to GuardedPort and never used
directly anywhere else. GuardedPort enforces RequestGuard, throttles, and
optionally traces every exchange to a JSONL file (for replay + FORScan compare).
"""

from __future__ import annotations

import json
import time
from typing import Callable, Protocol, TextIO

from .guard import RequestGuard

PROMPT = ">"


class RawTransport(Protocol):
    def write(self, data: bytes) -> None: ...
    def read_until_prompt(self, timeout: float) -> str: ...
    def close(self) -> None: ...


class SerialTransport:
    """ELM/STN over a serial port (FTDI on /dev/ttyUSB0 or COMx)."""

    def __init__(self, port: str, baud: int = 115200):
        import serial  # pyserial (BSD)

        self._ser = serial.Serial(port, baud, timeout=0.05)

    def write(self, data: bytes) -> None:
        self._ser.reset_input_buffer()
        self._ser.write(data)
        self._ser.flush()

    def read_until_prompt(self, timeout: float) -> str:
        buf = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self._ser.read(self._ser.in_waiting or 1)
            if chunk:
                buf += chunk
                if buf.rstrip().endswith(PROMPT.encode()):
                    break
        return buf.decode("ascii", errors="replace")

    def close(self) -> None:
        self._ser.close()


class GuardedPort:
    """Guard + throttle + trace in front of a raw transport."""

    def __init__(
        self,
        raw: RawTransport,
        guard: RequestGuard,
        *,
        min_gap: float = 0.02,      # seconds between requests (<= 50 req/s)
        trace: TextIO | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.__raw = raw
        self.guard = guard
        self.min_gap = min_gap
        self._trace = trace
        self._clock, self._sleep = clock, sleep
        self._last = -1e9

    def query(self, command: str, timeout: float = 1.0) -> str:
        """Send one command (after the guard) and return the raw reply text."""
        cmd = self.guard.enforce(command)  # raises GuardViolation; nothing sent
        wait = self._last + self.min_gap - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last = self._clock()
        self.__raw.write((cmd + "\r").encode("ascii"))
        reply = self.__raw.read_until_prompt(timeout)
        if self._trace:
            self._trace.write(json.dumps({"t": round(time.time(), 3), "tx": cmd, "rx": reply}) + "\n")
        return reply

    def close(self) -> None:
        self.__raw.close()
