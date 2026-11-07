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
