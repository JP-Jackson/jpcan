# Decisions

Newest at the bottom. Each entry gives the decision, why, and what we turned
down.

## D1. Own pyserial driver instead of python-OBD
python-OBD is GPL-2.0. It also issues its own commands internally, which makes
it hard to guarantee that every request passes through the guard, and it has
weak Mode 22 and custom header support. pyserial is BSD.

## D2. Explicit AT/ST allowlist
A blanket "AT*/ST* allowed" rule would let `STPX` (arbitrary frame transmit),
`ATPP` (EEPROM writes) and `ATCAF0` (raw mode, which defeats the service check)
through. Only listed commands pass.

## D3. Header allowlist
`ATSH` targets are restricted to `7DF`, `7E0`–`7E7` and the headers declared in
the active profile, so nothing can query arbitrary modules.

## D4. Own mock adapter and session replay instead of ELM327-emulator
ELM327-emulator is CC BY-NC-SA (non-commercial) and heavy. A mock at the
transport layer exercises the real guard, driver and parser.

## D5. Core daemon plus a bus; UI as a client
This works like an OPC server feeding HMIs. A UI crash doesn't touch the
adapter or the logger, and Node-RED, Home Assistant and ESP32 rounds become
plain subscribers. Backends: in-process (sim) and local MQTT (Pi).

## D6. SQLite per drive, CSV on export
PIDs poll at mixed rates (10 Hz and 1 Hz), which doesn't fit a wide CSV
cleanly. The table is long format `(ts, pid, value)`, and CSV export resamples
it.

## D7. YAML for profiles, JSON for settings and themes
Profiles need comments (sources, caveats). Settings are machine-written, and
QML reads JSON natively.

## D8. Pi 5 1GB on Raspberry Pi OS Lite 64-bit (Trixie)
It's the only board on hand that can run Qt gauges well. The Zero 2 W is
headless only, and the Pico 2 can't run Linux. The Pi 4 is the spare.

## D9. Stock Pi OS, not vendor images
The 52Pi 3.5" SPI screen's wiki says to use their own image. We won't: we use
a stock OS overlay if one exists, or the screen gets skipped. It's the
reproducible approach.

## D10. Phase 0 text display before graphics
A curses status screen (stdlib, plus `windows-curses` on Windows, BSD) proves
the adapter, CAN and Mode 22 path at the truck before any Qt work. The values
are chosen so they can be confirmed on the dash.

## D11. Native units in profiles, conversion in the UI
Profiles store kPa, °C and km/h as the ECU reports them. Imperial/Metric is a
display setting.

## D12. Package names `core` and `gaugeworks`
The repo layout matches the spec: top-level packages `core/` and
`gaugeworks/`, with the CLI entry point `jpcan`. Install into a venv. On a
dedicated Pi the generic name `core` won't collide with anything.

## D13. MQTT topics and the one inbound command
`jpcan/v/<key>` values are retained, so late subscribers get everything at
once. `jpcan/meta` and `jpcan/status` are retained, with an LWT of `offline`.
The core subscribes ONLY to `jpcan/cmd/trip_reset`, and nothing from MQTT
reaches the adapter. Mosquitto stays localhost-only until the phone page
(Phase 1.5) adds a read-only websockets listener.

## D14. GaugeWorks layouts live in vehicle profiles
`gaugeworks:` in each profile sets gauge ranges and warn/alarm points in
imperial display units; metric mode converts them and picks nice tick steps.
Computed channels (MPG, trip) come from the core's trip computer.

## D15. GaugeWorks on the Pi: EGLFS on HDMI, one touch device, scoped sudo
The launcher picks the DRM card that has the connected HDMI output (the Pi 5
has several), uses evdev with ONLY the HDMI screen's USB touch (so touching
the 3.5" ADS7846 doesn't steer GaugeWorks), and falls back to linuxfb +
software rendering if EGLFS fails. The Shut Down button uses a sudoers rule
that allows exactly `systemctl poweroff`.

## D16. Phase 1 performance note
Each PID is its own request, so poll rate drops as layouts grow (~4 Hz cycle in
the sim with everything on). Next optimization: STN multi-PID Mode 01 requests
(up to 6 PIDs per request), which cut request count several times over.

## D17. Gear: estimated now, real TCM DID once found
Standard PID A4 isn't supported. Until didscan/didwatch finds Ford's TCM gear
DID, the core estimates the gear from rpm and speed with the 6R140 ratios,
the axle ratio and tire size from the profile (`gear:`). It's shown big in
the tach and marked unverified. When a real `gear` PID is added to the
profile, the estimator switches off.

## D18. MPG: tank / trip / last-N, fill-up log, correction factor
(Replaces the manual MPG adjust, which was a misread of "reset and adjust".)
- The core's trip computer keeps tank (since fill-up), trip (reset button) and
  rolling last 5/10/25/50 mi averages, all raw from the fuel-rate PID. They're
  saved every 60 s and at shutdown so they survive power-offs (SD wear is
  negligible).
- Fill-ups: GaugeWorks sends `jpcan/cmd/fillup` {gallons, price}. The core
  takes miles from the truck's odometer (falling back to tank distance),
  stores actual MPG, price and the raw estimate in `fuel.sqlite` per vehicle,
  and resets the tank average. History is published retained on
  `jpcan/fuel/history`.
- Correction factor = mean(actual / estimate) over the last 3 tanks, clamped
  to 0.7-1.3. The UI toggles Raw vs Corrected and tags corrected tiles "corr".
  Logs always stay raw.
- The core's only MQTT inputs are trip_reset and fillup, and neither reaches
  the adapter.

## D19. GaugeWorks pages and changeable slots
Profiles define `gaugeworks.pages` built from templates: dash (Daily), quad
(Towing), economy, and list (Diagnostic). Swipe between them, or tap a page
dot. Gauge ranges and warn/alarm points live in a per-channel `display`
table, so a channel looks right in any slot; channels without an entry get
automatic ranges from their PID min/max. Press-and-hold any slot or tile (not
a tap, so bumps on the road don't trigger it) to pick what it shows. Picks
are saved per vehicle and page in settings.json, and "Reset page" restores
the profile default. The picker hides PIDs the vehicle doesn't support.

## D20. USB export via a root-owned helper and a scoped sudoers rule
GaugeWorks detects a stick by reading /dev/disk/by-id, which needs no
privileges. Mounting uses /usr/local/sbin/jpcan-usb: root-owned and installed
by the installer, NOT the user-editable repo copy, since a sudoers rule
pointing into the repo would be a root escalation. It mounts FAT32/exFAT/NTFS
as the user with noexec,nosuid,nodev. The bundle (core/bundle.py) copies drive
logs as SQLite backup-API snapshots (safe while a log is being written) plus
CSV, fuel history (SQLite + CSV), scan files, and a diagnostics report with
versions, service status, journals, settings and guard counters. Nothing is
deleted from the Pi, and nothing talks to the truck. `jpcan export-all --dest`
does the same from SSH.
