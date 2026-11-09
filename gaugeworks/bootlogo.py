"""Boot logo for the HDMI screen: the GaugeWorks splash (logo + tagline on black)
rendered to raw framebuffer images, so jpcan-bootlogo can 'cat' it to /dev/fbN
early in boot before Qt is up. Writes RGB565 (16 bpp) and XRGB8888 (32 bpp)
little-endian files plus a PNG to check by eye.

  python -m gaugeworks.bootlogo OUTDIR [--size 1024x600]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
TAGLINE = "JpCAN reads it. GaugeWorks shows it."


def render(width: int = 1024, height: int = 600):
    from PySide6.QtCore import QRect, QSize, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QImageReader, QPainter

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (fonts need an app)
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(QColor("black"))
    # same placement as the splash in Main.qml: logo 600x260 centered, tagline 90 px from the bottom
    rd = QImageReader(str(ASSETS / "jpcan_logo.svg"))
    rd.setScaledSize(QSize(600, 260))
    logo = rd.read()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    if not logo.isNull():
        p.drawImage((width - 600) // 2, (height - 260) // 2, logo)
    f = QFont("DejaVu Sans")
    f.setPixelSize(22)
    p.setFont(f)
    p.setPen(QColor("#8a929c"))
    p.drawText(QRect(0, height - 90, width, 40), int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), TAGLINE)
    p.end()
    return img, not logo.isNull()


def write(outdir: Path, width: int = 1024, height: int = 600) -> list[Path]:
    from PySide6.QtGui import QImage

    outdir.mkdir(parents=True, exist_ok=True)
    img, ok = render(width, height)
    if not ok:
        print("WARNING: couldn't load jpcan_logo.svg (Qt SVG image plugin missing?); tagline only")
    out = []
    for bpp, fmt in ((16, QImage.Format.Format_RGB16), (32, QImage.Format.Format_RGB32)):
        im = img.convertToFormat(fmt)
        stride = width * bpp // 8
        data = bytes(im.constBits())
        rows = b"".join(data[y * im.bytesPerLine(): y * im.bytesPerLine() + stride] for y in range(height))
        path = outdir / f"bootlogo-{width}x{height}-{bpp}.raw"
        path.write_bytes(rows)
        out.append(path)
    png = outdir / "bootlogo.png"
    img.save(str(png))
    out.append(png)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("outdir")
    ap.add_argument("--size", default="1024x600")
    a = ap.parse_args(argv)
    w, h = (int(x) for x in a.size.lower().split("x"))
    for p in write(Path(a.outdir), w, h):
        print(p)


if __name__ == "__main__":
    main()
