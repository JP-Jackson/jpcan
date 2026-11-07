import pytest

from core.elm import Elm, NegativeResponse, NoData, parse_frames
from core.guard import RequestGuard
from core.transport import GuardedPort


class ScriptedTransport:
    """Replies from a dict keyed by command; records what was written."""

    def __init__(self, replies):
        self.replies, self.sent, self._last = replies, [], None

    def write(self, data):
        self._last = data.decode().strip()
        self.sent.append(self._last)

    def read_until_prompt(self, timeout):
        return self.replies.get(self._last, "OK") + "\r\r>"

    def close(self):
        pass


def make(replies, headers=()):
    t = ScriptedTransport(replies)
    return Elm(GuardedPort(t, RequestGuard(extra_headers=set(headers)), min_gap=0)), t


def test_single_frame():
    assert parse_frames("7E804410C1AF8\r\r>") == {"7E8": bytes.fromhex("410C1AF8")}


def test_multi_frame_vin():
    reply = ("7E81014490201314654\r"
             "7E82137573242543045\r"
             "7E82245413132333435\r>")
    p = parse_frames(reply)["7E8"]
    assert len(p) == 0x14 and p[:3] == bytes.fromhex("490201")


def test_two_ecus_and_noise():
    reply = "SEARCHING...\r7E906410D00\r7E803410D37\rNO DATA\r>"
    assert parse_frames(reply) == {"7E8": bytes.fromhex("410D37"), "7E9": bytes.fromhex("410D00")}


def test_read_prefers_7e8_and_strips_echo():
    elm, _ = make({"010D": "7E906410D00\r7E803410D37"})
    assert elm.read("01", "0D") == bytes([0x37])


def test_read_mode22_sets_header_and_filter():
    elm, t = make({"22404C1": "7280662404C01ABCD"}, headers={"720"})
    assert elm.read("22", "404C", "720") == bytes.fromhex("01ABCD")
    assert t.sent[:2] == ["ATSH720", "ATCRA728"]
    elm.read("22", "404C", "720")
    assert t.sent.count("ATSH720") == 1  # header cached


def test_negative_response():
    elm, _ = make({"22DD011": "7E803 7F2231".replace(" ", "")})
    with pytest.raises(NegativeResponse) as e:
        elm.read("22", "DD01", "7E0")
    assert e.value.nrc == 0x31


def test_no_data():
    elm, _ = make({"015E": "NO DATA"})
    with pytest.raises(NoData):
        elm.read("01", "5E")


def test_supported_pids_chain():
    elm, _ = make({"0100": "7E8064100BE3EA813", "0120": "7E8064120A007B019",
                   "0140": "7E8064140FED00400"})
    s = elm.supported_pids()
    assert {0x0C, 0x0D, 0x20, 0x21, 0x40, 0x41} <= s
    assert 0x60 not in s


def test_vin():
    reply = "7E81014490201314654\r7E82137573242543045\r7E82245413132333435"
    elm, _ = make({"0902": reply})
    assert elm.vin() == "1FT7W2BT0EEA12345"


def test_physical_requests_get_response_count_broadcast_does_not():
    elm, t = make({"010C1": "7E804410C1AF8", "010C": "7E804410C1AF8"})
    elm.read("01", "0C", "7E0")
    elm.read("01", "0C", "7DF")
    obd = [c for c in t.sent if not c.startswith("AT")]
    assert obd == ["010C1", "010C"]
