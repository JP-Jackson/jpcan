# JpCAN / GaugeWorks

"JpCAN reads it. GaugeWorks shows it." A read-only OBD2/CAN gauge and logging
system on a Raspberry Pi.

## HARD RULE: read-only, enforced in code

Every byte sent to the adapter goes through `core/guard.py::RequestGuard`, via
`core/transport.py::GuardedPort`. There is no other write path, so don't add one.

- Allowed OBD services: `01` (current data), `03` (stored DTCs), `09` (vehicle
  info), `22` (read data by identifier).
- Allowed adapter commands: an explicit AT/ST **allowlist**, not a prefix match.
  `STPX` (raw frame transmit), `ATPP` (EEPROM), `ATCAF0` (raw mode), `ATWM`
  (wakeup messages), `ATMA`/`STM` (monitor) and anything not listed are blocked.
- Allowed headers (`ATSH`): `7DF` and `7E0`–`7E7` by default, plus the headers
  listed in the active vehicle profile.
- Everything else is blocked and logged at WARNING. That includes `04`/`14`
  (clear DTCs), `10`, `11`, `27`, `2E`, `2F`, `31`, `34`, `36`, `37`, `3B` and
  anything unknown.
- Clearing DTCs is out of scope. If it's ever added, it must be an explicit,
  separate opt-in.
- `tests/test_guard.py` must prove that blocked commands never reach the
  transport. Never weaken these tests to make something else pass.
- Polling is throttled: a minimum gap between requests and a cap on requests
  per second.
- Code borrowed from other repos must be license-checked (MIT/BSD/Apache OK,
  flag GPL to JP first) and stripped of any write/control services.
  `reference/` is for study only and is gitignored.

## Hardware

- Vehicles: 2014 Ford F-250 6.7L Powerstroke (automatic, no shift light) and
  2013 VW Jetta 2.0 TDI (manual, shift light on).
- Adapter: OBDLink EX (STN chip, ELM327 + ST commands, FTDI USB), shows up as
  `/dev/ttyUSB0`. It's powered by the OBD port, so it's dead on the bench.
- Compute: Pi 5 1GB on Raspberry Pi OS Lite 64-bit (Trixie, Python 3.13),
  booting from a SanDisk Extreme PRO 128GB card. The Pi 4 is the spare.
- Screens: 52Pi 3.5" SPI case screen (480x320, resistive) for Phase 0 text and
  compact layouts; 7" 1024x600 HDMI capacitive for GaugeWorks.
- Dev: Windows laptop with FORScan for verifying PIDs.
- For now: no wiring. Power is manual, and there's a Shut Down button.
  Ignition sense is Phase 4.

## Architecture decisions (see docs/decisions.md)

- Our own `pyserial` ELM/STN driver, not python-OBD (GPL, and it's hard to
  guard).
- Our own mock adapter plus replay of recorded sessions, not ELM327-emulator
  (non-commercial license).
- Core runs as a daemon (`jpcan run`, systemd `jpcan-core`) and is the ONLY
  process that opens the adapter. It publishes to MQTT (`jpcan/v/<key>`
  retained, `jpcan/meta`, `jpcan/status` with LWT). Its only MQTT inputs
  are `jpcan/cmd/trip_reset`, `jpcan/cmd/fillup` and `jpcan/cmd/fuel_edit`, and nothing from MQTT
  ever reaches the adapter.
  Clients: status screen (`live --bus`), GaugeWorks, later Node-RED/HA/phone.
  LocalSink is the in-process stand-in for the laptop simulator.
- Logging is SQLite per drive in long format `(ts, pid, value)`, with CSV
  export.
- Profiles are YAML (they need comments); settings and themes are JSON.
- Values are stored in each PID's native units (kPa, °C, km/h). The UI
  converts them, and Imperial/Metric is a setting.
- Shift state is per profile (`shift.enabled`, `shift.rpm`).
- UI is PySide6 + QML (Qt), EGLFS/linuxfb, with resolution-independent
  layouts.

## Layout

```
core/        adapter comms, guard, poller, scaling, logging, MQTT
gaugeworks/  PySide6 + QML UI, themes/
profiles/    base_mode01.yaml + one YAML per vehicle
reference/   third-party repos, study only (gitignored)
tests/       pytest
docs/        decisions, setup, verification guides
scripts/     Pi setup helpers
```

## Profiles

Each PID entry has: `name`, `service`, `pid`, `header`, `formula` (bytes A, B,
...), `units`, `min`, `max`, `poll_rate` (fast|slow), `verified`, `source`.
Every Ford/VW Mode 22 PID starts as `verified: false` until JP confirms it
against FORScan or the dash.

## Phases

- **0 (done):** CLI probe/scan plus a curses status screen on the 3.5". Truck
  verified 2026-11-07: odometer, outside temp, fuel, RPM, boost, rail, VGT.
  Truck is off-road (DEF/EGR cooler removed, tuned): EGT and coolant2 read
  fixed placeholder values.
- **1 (current):** core service, MQTT, SQLite logging and the trip computer
  are done, with fill-up log, correction factor and fuel-history edits.
  GaugeWorks on the HDMI screen is also done: pages, press-and-hold slot
  picker, USB export, CEL banner and themes. The Premium theme is an
  OEM-style skin with chrome dials, a centre economy/engine card, long date
  and time, and telltales. First drive 2026-11-07 showed RPM lag, so polling
  now uses tiers (D23); retest on the next drive.
- 1.5: Phone web dashboard (view-only) over mosquitto websockets plus a Pi
  hotspot on the road.
- 2: EGT1-4, rail pressure, soot, regen, trans temp, alarms, trailer layout.
- 3: Theme editor, more themes, round screens (Pi HDMI or ESP32).
- 4: Power: buck converter, ignition sense, safe shutdown, systemd, fast boot.
- 5: MQTT/Home Assistant sync, maintenance reminders.

## Open items

- Touch died on the 2026-11-08 drive while the gauges kept running (D25).
  The touch watchdog and the persistent journal are in. If it happens again,
  read `journalctl -u gaugeworks -b -1` and the kernel USB log.
- The 2026-11-08 drive ran pre-D23 code (the Pi wasn't pulled), so the lag
  there was the old poller.
- Retest RPM smoothness on the truck with the D23 polling tiers. If it's still
  slow, try STN multi-PID Mode 01 batching (up to 6 PIDs per request).
- Find the 6R140 TCM gear DID with `jpcan didscan`/`didwatch` on a drive.
  Until then the gear is estimated (D17).
- Turn signal and headlight telltales are wired to optional channels
  `turn_left`, `turn_right`, `headlights` and `high_beam`. They need body
  module (BCM) Mode 22 DIDs that haven't been found yet, so they stay dim
  until then.
- Premium theme: check the direction of the light-trail fade on the real
  screen.
- A screen upgrade is under consideration: 10.1" 1280x800 IPS HDMI with
  capacitive touch, ideally ~900 nits for daylight. GaugeWorks scales to it.
- The Pi 5 clock needs the RTC coin battery to keep time off Wi-Fi. Without
  it, the 2026-11-08 drive booted on the 11-07 clock and jumped +6.3 h mid-log
  (`jpcan logstats` flags and skips such jumps).
- Phone page (Phase 1.5) comes later.
- GPU: the PySide6 wheel lacks `libQt6EglFsKmsGbmSupport.so.6`, so EGLFS
  probably can't load on the Pi and GaugeWorks falls back to linuxfb with
  software rendering. Confirm in the journal, then pick a fix with JP.
- Truck/Simulator switch is in Settings (D26).
- Reference dash styles JP liked are noted in `docs/mockups/README.md`.

## Working style

- JP is an automation tech (PLCs, Modbus, Node-RED). Don't over-explain the
  basics. Keep replies short.
- Check in before big architecture changes or new major dependencies.
- Work in small, tested steps and commit after each one.
- Keep this file and `docs/` current as decisions change.
- Run tests with `python -m pytest`.
