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
git clone -b phase0 https://github.com/JP-Jackson/jpcan.git && cd jpcan
```
```bash
python3 -m venv .venv && .venv/bin/pip install -e .
```
Bench test with no truck (simulator):
```bash
.venv/bin/jpcan live --sim
```
In the truck, key on:
```bash
.venv/bin/jpcan probe --trace probe.jsonl
```
```bash
.venv/bin/jpcan scan22 --trace scan22.jsonl
```
```bash
.venv/bin/jpcan live
```
`?` marks unverified PIDs. Compare them to the dash and FORScan. The
`--trace` files hold every request and reply, so send them back for review.

Your user is already in the `dialout` group on Pi OS, so it can open the
serial port.

## 9. Services: core + status screen
```bash
sudo ~/jpcan/scripts/install-services.sh
```
Re-run it after any `git pull` that changes services. It installs:
- **mosquitto**: the local MQTT broker, localhost only.
- **jpcan-core**: the only process that talks to the OBDLink. It polls through
  the guard, writes one SQLite log per drive to `~/jpcan-logs`, runs the trip
  computer, and publishes everything to MQTT (`jpcan/#`).
- **jpcan-status**: the 3.5" text screen on tty1, which reads from MQTT.

With no adapter it shows "No adapter... Plugged in?"; with the key off it
shows "Key on?". For a bench demo, set `JPCAN_ARGS="--sim"` in
`/etc/default/jpcan`, then run:
```bash
sudo systemctl restart jpcan-core
```
Logs and data:
```bash
journalctl -u jpcan-core -f
```
```bash
~/jpcan/.venv/bin/jpcan logs
```
```bash
~/jpcan/.venv/bin/jpcan export <file>.sqlite
```
```bash
mosquitto_sub -t 'jpcan/#' -v
```
The last one shows the raw live feed, the same data Node-RED/HA can subscribe to.

Note: `jpcan probe`, `scan22` and `live` (without `--bus`) open the adapter
themselves. Stop the core first: `sudo systemctl stop jpcan-core`.

Touch: run `jpcan touch-cal` once (tap left edge, then right edge). Tap the
right half of the screen for the next page, the left half to go back.

## Troubleshooting

**Pi not on Wi-Fi after first boot** (it isn't in the router list, and
`ping jpcan.local` fails):
1. Plug an Ethernet cable straight from the laptop to the Pi. IPv6 link-local
   plus mDNS lets `ssh jp@jpcan.local` work with no DHCP. The SSH session may
   drop now and then while eth0 retries DHCP, which is harmless.
2. Run `nmcli device status`. If `wlan0` shows no connection, Imager's Wi-Fi
   settings weren't applied.
3. Run `nmcli device wifi list` and check the exact SSID. **Watch for leading
   spaces**: JP's SSID starts with a space, which Imager dropped.
4. Connect manually, quoting the SSID exactly:
   ```bash
   sudo nmcli device wifi connect " SSID with leading space" password "PASSWORD"
   ```
   NetworkManager saves this connection, so it reconnects on every boot.
