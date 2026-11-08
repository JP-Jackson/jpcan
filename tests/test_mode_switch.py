"""Truck/Simulator switch: the root helper and the GaugeWorks slot."""

import subprocess
from pathlib import Path

import pytest

HELPER = Path(__file__).resolve().parent.parent / "scripts" / "jpcan-mode"


@pytest.fixture
def helper(tmp_path):
    """A copy of jpcan-mode with its paths pointed into tmp (the real one is root-owned)."""
    log = tmp_path / "systemctl.log"
    fake = tmp_path / "systemctl"
    fake.write_text(f'#!/bin/sh\necho "$@" >> {log}\n')
    fake.chmod(0o755)
    mode_file = tmp_path / "jpcan-mode"
    src = HELPER.read_text().replace("/etc/default/jpcan-mode", str(mode_file)) \
                            .replace("/usr/bin/systemctl", str(fake))
    h = tmp_path / "helper.sh"
    h.write_text(src)
    h.chmod(0o755)

    def run(*args):
        return subprocess.run(["sh", str(h), *args], capture_output=True, text=True)
    return run, mode_file, log


def test_sim_then_truck(helper):
    run, mode_file, log = helper
    assert run("status").stdout.strip() == "truck"
    assert run("sim").returncode == 0
    assert 'JPCAN_MODE_ARGS="--sim"' in mode_file.read_text()
    assert run("status").stdout.strip() == "sim"
    assert run("truck").returncode == 0
    assert 'JPCAN_MODE_ARGS=""' in mode_file.read_text()
    assert run("status").stdout.strip() == "truck"
    assert log.read_text().splitlines() == ["restart jpcan-core.service"] * 2


@pytest.mark.parametrize("bad", [[], ["--sim"], ["truck; reboot"], ["SIM"], ["poweroff"]])
def test_anything_else_is_refused(helper, bad):
    run, mode_file, log = helper
    r = run(*bad)
    assert r.returncode == 64
    assert not mode_file.exists() and not log.exists()


def test_backend_calls_only_the_helper(monkeypatch):
    pytest.importorskip("PySide6")
    from gaugeworks import backend as be

    calls = []
    monkeypatch.setattr(be.subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    started = []

    class FakeThread:
        def __init__(self, target, daemon):
            started.append(target)

        def start(self):
            pass
    monkeypatch.setattr(be.threading, "Thread", FakeThread)
    b = be.Backend.__new__(be.Backend)
    msgs = []
    monkeypatch.setattr(be.Backend, "message", type("S", (), {"emit": lambda self, m: msgs.append(m)})())
    be.Backend.setSource(b, "bogus")
    assert not started
    be.Backend.setSource(b, "sim")
    started[0]()
    assert calls == [["sudo", "-n", "/usr/local/sbin/jpcan-mode", "sim"]]
    assert msgs and "simulator" in msgs[0]
