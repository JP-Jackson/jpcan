import pytest
import yaml

from core.profile import ProfileError, list_profiles, load_profile, select_profile

F250_VIN = "1FT7W2BT0EEA12345"


def test_all_profiles_load():
    names = list_profiles()
    assert {"ford_f250_67_2014", "vw_jetta_20tdi_2013"} <= set(names)
    for n in names + ["base_mode01"]:
        load_profile(n)


def test_inheritance_and_fields():
    p = load_profile("ford_f250_67_2014")
    assert "rpm" in p.pids and "odometer" in p.pids
    assert p.pids["rpm"].formula([0x1A, 0xF8]) == 1726
    assert p.pids["odometer"].header == "720"
    assert not p.pids["odometer"].verified
    assert p.shift["enabled"] is False
    assert {"720", "7E1"} <= p.extra_headers


def test_mode22_verified_only_with_evidence():
    """Mode 22 PIDs start unverified; flipping one requires a 'Verified <date>' note."""
    for n in list_profiles():
        for pid in load_profile(n).pids.values():
            if pid.service == "22" and pid.verified:
                assert "Verified 20" in pid.notes, f"{n}:{pid.key} verified without evidence note"


def test_vin_selection():
    assert select_profile(F250_VIN).id == "ford_f250_67_2014"
    assert select_profile("3VWDX7AJ0DM000000").id == "vw_jetta_20tdi_2013"
    assert select_profile("WDB0000000A000000").id == "base_mode01"
    assert select_profile(None).id == "base_mode01"


def _write(tmp_path, name, data):
    (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(data))


ENTRY = dict(name="x", service="01", pid="0C", header="7DF", formula="A", units="",
             min=0, max=1, poll_rate="fast", verified=True, source="t")


@pytest.mark.parametrize("override", [
    {"service": "04", "pid": ""},       # clear DTCs
    {"service": "2E", "pid": "F190"},   # write DID
    {"service": "31", "pid": "0102"},   # routine control
    {"service": "22", "pid": "F190", "header": "7A0"},  # unlisted header... declared on pid
])
def test_blocked_requests_rejected(tmp_path, override):
    entry = {**ENTRY, **override}
    _write(tmp_path, "bad", {"id": "bad", "pids": {"x": entry}})
    if override.get("header") == "7A0":
        # A PID's own header is added to the allowlist, so this one loads:
        load_profile("bad", tmp_path)
    else:
        with pytest.raises(ProfileError):
            load_profile("bad", tmp_path)


def test_missing_field(tmp_path):
    entry = dict(ENTRY)
    del entry["source"]
    _write(tmp_path, "bad", {"pids": {"x": entry}})
    with pytest.raises(ProfileError):
        load_profile("bad", tmp_path)


def test_unsafe_formula_rejected(tmp_path):
    _write(tmp_path, "bad", {"pids": {"x": {**ENTRY, "formula": "__import__('os')"}}})
    with pytest.raises(ValueError):
        load_profile("bad", tmp_path)
