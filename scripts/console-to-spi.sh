#!/bin/sh
# Put tty1 (the status screen) on the 3.5" SPI display, whatever fb number it got.
# With HDMI connected at boot, HDMI becomes fb0 and the SPI screen fb1, and the
# console would otherwise follow fb0 (hidden behind GaugeWorks).
FONT=/usr/share/consolefonts/Lat15-TerminusBold32x16.psf.gz
for f in /sys/class/graphics/fb*; do
    if grep -q ili9486 "$f/name" 2>/dev/null; then
        n="${f##*/fb}"
        con2fbmap 1 "$n" && echo "tty1 -> fb$n (SPI)"
        break
    fi
done
setfont -C /dev/tty1 "$FONT"
