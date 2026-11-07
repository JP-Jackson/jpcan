"""Proves the read-only rule. Do not weaken these tests."""

import logging

import pytest

from core.guard import GuardViolation, RequestGuard

BLOCKED_SERVICES = ["04", "14", "10", "11", "27", "2E", "2F", "31", "34", "36",
                    "37", "3B", "02", "05", "06", "07", "08", "0A", "19", "3E",
                    "85", "28", "FF", "00"]


@pytest.fixture
def guard():
    return RequestGuard(extra_headers={"7E1", "726"})


# ---- OBD services -------------------------------------------------------
@pytest.mark.parametrize("cmd", [
    "010C", "01 0C", "010C0D", "010C0D0B33", "010C0D0B330546", "010C1",
    "03", "0902", "0900", "22DD01", "22 DD 01", "22DD01DD02", "22F40C1",
])
def test_allowed_requests(guard, cmd):
    assert guard.check(cmd).allowed, guard.check(cmd).reason


@pytest.mark.parametrize("svc", BLOCKED_SERVICES)
@pytest.mark.parametrize("tail", ["", "00", "0101", "FF00FF"])
def test_blocked_services(guard, svc, tail):
    d = guard.check(svc + tail)
    assert not d.allowed


@pytest.mark.parametrize("cmd", [
    "01",              # no PID
    "0100010203040506",  # 7 PIDs
    "0300",            # data on 03
    "09",              # no PID
    "090201",          # 2 PIDs on 09
    "22",              # no DID
    "22DD",            # half DID
    "22DD01DD02DD03DD04",  # too many DIDs
    "010C0",           # response count 0
    "0",
])
def test_malformed_allowed_services(guard, cmd):
    assert not guard.check(cmd).allowed


@pytest.mark.parametrize("cmd", [
    "", " ", "010C\r04", "010C\n04", "010C;04", "010C\x00", "01-0C", "G1",
    "010C\t", "ÄT", None, 123,
])
def test_garbage_blocked(guard, cmd):
    assert not guard.check(cmd).allowed


# ---- adapter commands ---------------------------------------------------
@pytest.mark.parametrize("cmd", [
    "ATZ", "AT Z", "atz", "ATWS", "ATD", "ATI", "ATE0", "ATL0", "ATS0",
    "ATH1", "ATAT1", "ATST32", "ATSP6", "ATSPA6", "ATDP", "ATDPN", "ATRV",
    "ATPC", "ATSH7E0", "ATSH 7DF", "ATSH726", "ATCRA7E8", "ATCRA", "ATCAF1",
    "STI", "STDI", "STSN", "STP33", "STP53", "STPR", "STPRS",
])
def test_allowed_adapter(guard, cmd):
    assert guard.check(cmd).allowed, guard.check(cmd).reason


@pytest.mark.parametrize("cmd", [
    "STPX H:7E0, D:0401",  # raw frame transmit (also has invalid chars)
    "STPXH7E0D0401",       # raw frame transmit
    "STM", "STMA",         # monitor
    "STSBR115200",         # baud change
    "STWBR",               # write baud
    "ATPP0CSV23", "ATPP0CON",  # EEPROM programmable params
    "ATCAF0",              # raw mode would bypass service check
    "ATCFC0",              # flow control off
    "ATWM8210F13E",        # wakeup message (periodic tester present)
    "ATSW00",              # wakeup interval
    "ATMA", "ATMR10", "ATMT10",  # monitors
    "ATBI",                # bypass init
    "ATLP",                # low power
    "ATBRD23",             # baud rate divisor
    "ATFCSH7E0", "ATFCSD300000", "ATFCSM1",  # custom flow control
    "ATSH7A0",             # header not in allowlist
    "ATSH760",             # header not in allowlist
    "ATSH18DA10F1",        # 29-bit header not in allowlist
    "ATXYZ", "STXYZ", "AT", "ST",
])
def test_blocked_adapter(guard, cmd):
    assert not guard.check(cmd).allowed


def test_profile_headers_extend_allowlist():
    g = RequestGuard()
    assert not g.check("ATSH726").allowed
    g.extra_headers.add("726")
    assert g.check("ATSH726").allowed


# ---- enforce: counting + logging ---------------------------------------
def test_enforce_raises_counts_and_logs(guard, caplog):
    with caplog.at_level(logging.WARNING, logger="jpcan.guard"):
        with pytest.raises(GuardViolation):
            guard.enforce("04")
    assert guard.blocked == 1 and guard.sent == 0
    assert "BLOCKED" in caplog.text and "04" in caplog.text


def test_enforce_returns_normalized(guard):
    assert guard.enforce("01 0c") == "010C"
    assert guard.sent == 1


# ---- end-to-end: blocked commands never reach the wire --------------------
class SpyTransport:
    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)

    def read_until_prompt(self, timeout):
        return "OK\r\r>"

    def close(self):
        pass


@pytest.mark.parametrize("cmd", ["04", "14FFFFFF", "2EF19000", "31010203", "1003",
                                 "STPXH7E0D0401", "ATCAF0", "ATPP0CON", "ATSH7A0"])
def test_blocked_never_written(cmd):
    from core.transport import GuardedPort

    spy = SpyTransport()
    port = GuardedPort(spy, RequestGuard(), min_gap=0)
    with pytest.raises(GuardViolation):
        port.query(cmd)
    assert spy.written == []


def test_allowed_is_written():
    from core.transport import GuardedPort

    spy = SpyTransport()
    GuardedPort(spy, RequestGuard(), min_gap=0).query("01 0c")
    assert spy.written == [b"010C\r"]


def test_raw_transport_not_exposed():
    from core.transport import GuardedPort

    port = GuardedPort(SpyTransport(), RequestGuard())
    assert not any(n in ("raw", "_raw", "transport") for n in vars(port))


def test_throttle_enforces_min_gap():
    from core.transport import GuardedPort

    now = [0.0]
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        now[0] += s

    port = GuardedPort(SpyTransport(), RequestGuard(), min_gap=0.1,
                       clock=lambda: now[0], sleep=sleep)
    for _ in range(3):
        port.query("010C")
    assert sleeps == pytest.approx([0.1, 0.1])
