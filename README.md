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

Phase 0 is in progress: proving we can get data. The GaugeWorks UI is Phase 1.

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
