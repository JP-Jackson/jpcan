# JpCAN

**JpCAN reads it. GaugeWorks shows it.**

JpCAN is a read-only OBD2/CAN gauge and logging system for a Raspberry Pi with
an OBDLink (STN/ELM327) adapter. It supports multiple vehicles through YAML
profiles. The first profiles are a 2014 F-250 6.7L Powerstroke and a 2013
Jetta 2.0 TDI.

> **Read-only by design.** Every request passes through `RequestGuard`. Only
> services 01/03/09/22 and an allowlist of adapter config commands can be
> sent. See [CLAUDE.md](CLAUDE.md).

## Status

- **Phase 0 (done):** the adapter driver, the guard, probe/scan and the curses
  status screen on the 3.5". Verified on the F-250 on 2026-11-07.
- **Phase 1 (current):** the core daemon (`jpcan-core`) owns the adapter and
  publishes to MQTT. It logs every drive to SQLite and runs the trip computer
  (tank, trip and last-N MPG, plus a fill-up log with an actual-MPG correction).
  GaugeWorks on the HDMI touch screen has swipeable pages (Daily, Towing,
  Economy, Diagnostic), press-and-hold to change any gauge, USB export, and
  themes. Premium is the OEM-style default. The others are Classic, Classic
  refined, Modern, Race, Night and Turbo Snail. The first test drive in GaugeWorks led to
  the fast/medium/slow polling tiers (decision D23).
- **Next:** see "Open items" in [CLAUDE.md](CLAUDE.md).

## Using it on the Pi

- **Logging is automatic.** Each drive becomes its own file in
  `~/jpcan-logs/` while `jpcan-core` runs.
  - `jpcan logs` lists the drives.
  - `jpcan export <file>` writes a CSV (1 row/s; `--rate`, `--metric`).
  - `jpcan export-all --dest <folder>` bundles everything. A USB stick in the
    Pi does the same from the screen.
- **Truck or simulator:** set `JPCAN_ARGS` in `/etc/default/jpcan` (`""` for
  the truck, `"--sim"` for a bench demo), then run
  `sudo systemctl restart jpcan-core`.
- **Theme:** ⚙ → Theme. Units, MPG raw/corrected and the Last-N window are in ⚙
  too.
- **Update:** `cd ~/jpcan && git pull && bash scripts/install-services.sh`

## Quick start (laptop, simulator)

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -e ".[dev]"
```

```bash
.venv/bin/jpcan live --sim
```

On Windows, use `.venv\Scripts\` in place of `.venv/bin/`.

## Docs

- [docs/decisions.md](docs/decisions.md): architecture decisions and why
- [docs/pi-setup.md](docs/pi-setup.md): flashing and setting up the Pi
