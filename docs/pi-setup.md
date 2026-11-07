# Pi setup

Target: Pi 5 1GB on Raspberry Pi OS Lite 64-bit (Trixie), with a SanDisk
Extreme PRO 128GB card.

## 1. Flash (Windows)
Use Raspberry Pi Imager. Choose **Raspberry Pi 5**, then **Raspberry Pi OS
(other) → Lite (64-bit)**. Under **Edit settings**: hostname `jpcan`, your
user, Wi-Fi, locale, and enable SSH (a public key is preferred).

## 2. First boot
Power it with USB-C. The first boot takes 1–2 minutes because it resizes the
filesystem.

```bash
ssh jp@jpcan.local
```

## 3. Update
```bash
sudo apt update && sudo apt full-upgrade -y
```
```bash
sudo rpi-eeprom-update -a
```
```bash
sudo reboot
```

## 4. Packages
```bash
sudo apt install -y git python3-venv python3-pip picocom evtest
```

## 5. 52Pi 3.5" SPI screen (stock OS only, see D9)
```bash
ls /boot/firmware/overlays | grep -iE "mhs|piscreen|ili"
```
If `mhs35` is listed, add `dtoverlay=mhs35` to `/boot/firmware/config.txt`
and reboot. Then check:
```bash
ls /dev/fb* /dev/dri/
```
```bash
dmesg | grep -iE "mhs|ili|ads7846|fb"
```

## 6. 7" HDMI screen (Phase 1)
Use HDMI0, the port next to USB-C. Check:
```bash
cat /sys/class/drm/card*-HDMI-A-1/modes
```
If the first mode isn't `1024x600`, add `video=HDMI-A-1:1024x600@60` to the
end of the single line in `/boot/firmware/cmdline.txt`.

## 7. Adapter check (in the truck, key on)
```bash
ls -l /dev/serial/by-id/
```
```bash
picocom -b 115200 /dev/ttyUSB0
```
Type **only** `ATZ`, `ATI`, `STI` and `ATRV`. picocom bypasses
`RequestGuard`. Exit with Ctrl-A, then Ctrl-X. If you only get garbage, try
`-b 38400`.

## 8. Install JpCAN
```bash
git clone https://github.com/JP-Jackson/jpcan.git && cd jpcan
```
```bash
python3 -m venv .venv && .venv/bin/pip install -e .
```
```bash
.venv/bin/jpcan probe --port /dev/ttyUSB0
```

Your user is already in the `dialout` group on Pi OS, so it can open the
serial port.
