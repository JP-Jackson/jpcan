import os
import subprocess

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_bootlogo_raw_sizes(tmp_path):
    from gaugeworks.bootlogo import write

    out = {p.name: p for p in write(tmp_path)}
    assert out["bootlogo-1024x600-16.raw"].stat().st_size == 1024 * 600 * 2
    assert out["bootlogo-1024x600-32.raw"].stat().st_size == 1024 * 600 * 4
    raw = out["bootlogo-1024x600-32.raw"].read_bytes()
    assert raw[:4] == b"\x00\x00\x00\xff"          # black corner, XRGB8888 little-endian
    assert any(raw[i] for i in range(0, len(raw), 4))   # something was drawn


def test_bootlogo_script_syntax():
    root = os.path.dirname(os.path.dirname(__file__))
    subprocess.run(["sh", "-n", os.path.join(root, "scripts", "jpcan-bootlogo")], check=True)
    subprocess.run(["bash", "-n", os.path.join(root, "scripts", "install-services.sh")], check=True)
