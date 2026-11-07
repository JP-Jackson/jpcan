from core.sysinfo import wifi_dbm, wifi_label

SAMPLE = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 wlan0: 0000   47.  -63.  -256        0      0      0      0      0        0
"""


def test_wifi_dbm(tmp_path):
    f = tmp_path / "wireless"
    f.write_text(SAMPLE)
    assert wifi_dbm(str(f)) == -63


def test_wifi_dbm_missing(tmp_path):
    assert wifi_dbm(str(tmp_path / "nope")) is None
    f = tmp_path / "wireless"
    f.write_text(SAMPLE.split("\n")[0] + "\n" + SAMPLE.split("\n")[1] + "\n")
    assert wifi_dbm(str(f)) is None


def test_wifi_label():
    assert wifi_label(None) == "W--"
    assert wifi_label(-60) == "W-60"
    assert wifi_label(-72) == "W-72 weak"
    assert wifi_label(-80) == "W-80 BAD"
