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

## D21. Fuel history edits
Tap a History row to edit gallons, $/gal, odometer or date, or delete the line
(one confirm). "Delete all" takes two confirms and only affects the current
vehicle. The core does all edits via `jpcan/cmd/fuel_edit` (the third and
last MQTT input), and clear needs a "DELETE" token so a stray message can't
wipe history. It recomputes miles/MPG for the vehicle's whole chain (ordered
by date) and rejects an odometer or date that would break the order. Before
a delete-all it saves a backup to fuel_backups/ (10 kept), which the USB
export includes.

## D22. Themes choose a gauge style, not just colors
theme.json `style`: `gauge` is "needle" (face/ticks/needle image) or "arc"
(GPU QtQuick.Shapes arcs, smooth via an animated value, big digital
readout); `glow`, `shiftBar` (a 15-LED bar that fills from 55% of the shift
point or redline and flashes at the top), `fx` (hub effects: turbo-snail
spinner on boost, rev flame on rpm, leaf on MPG tiles) and `quips`
(occasional status-line jokes, rate limited). Themes: Classic, Classic
refined, Modern, Race, Night, Turbo Snail. Assets are SVG in the theme
folder.

## D23. Poll tiers: fast / medium / slow, spread out
In the truck, RPM lagged because every second all ~12 slow PIDs were read in
one burst (temps, fuel, odometer, and trans on another module), which froze
the fast ones for about half a second. Now:
- **fast** (every cycle): rpm, speed, boost inputs, VGT desired/actual.
- **medium** (~1 s): rail pressure, fuel rate, load, MAF, torque, timing.
- **slow** (~5 s): temps, fuel level, odometer, battery, baro, soot, CEL.
- **once**: engine hours.

Only one non-fast read happens per cycle, most overdue first, and PIDs that
share a request come free with it. The diagnostic background read uses the
slot only when nothing else is due. That leaves about 5 requests per cycle on
the truck, against 6 before plus a 12-request burst every second.

## D24. Premium theme: an OEM-style skin with bundled fonts
The first theme built as a full skin (`themes/oem/qml`). Static art (chrome
bezels, faces, ticks, numbers) is painted once with Canvas. Only the light
trail (a QtQuick.Shapes conical gradient) and the needles move, and there's a
key-on needle sweep. Fonts are Barlow and Barlow Semi Condensed under the OFL;
the license is in `themes/oem/fonts/OFL.txt`, and the app registers every
`themes/*/fonts/*.ttf` at startup. Pages now carry gauge configs for their
tile channels (`gauges`), so a skin can draw a tile as a dial or bar (fuel
sub-dial, oil bar). The OEM top bar (`style.topBar: "oem"`) shows the time
with the long date, telltales and outside temp, and moves the page dots to the
bottom. All designs are original: no OEM or aftermarket logos or trade dress.

## D25. Touch watchdog, one touch handler, persistent journal
On the 2026-11-08 drive, touch died while the gauges kept updating, and the
journal was RAM-only, so the reboot lost the evidence. Qt's evdev handler opens
one `/dev/input/eventN` at startup and never reopens it, so a USB touch that
drops and re-enumerates (vibration, a power dip) leaves touch dead. Now:
- The launcher waits up to ~20 s for the USB touch, and loads ONE evdev touch
  handler. The `evdevtouch` generic plugin was a second handler on the same
  device, and it's gone.
- GaugeWorks watches the touch device (`gaugeworks/touchwatch.py`). If the node
  is removed or re-created, or if 3+ taps reach the device but none reach the
  Qt window, it logs why and exits, and systemd restarts it (~8 s blank).
- `install-services.sh` makes the journal persistent, capped at 64 MB.
Not covered: touch that reaches Qt but gets stuck inside Qt Quick. If it
happens again, check `journalctl -u gaugeworks -b -1` for a watchdog line.

## D26. Truck/Simulator switch in Settings
Settings has a "Data from: Truck | Simulator" row (two taps to confirm). It runs
the root-owned helper `/usr/local/sbin/jpcan-mode truck|sim`, which a sudoers
rule allows with exactly those arguments. The helper writes
`/etc/default/jpcan-mode` (`JPCAN_MODE_ARGS`) and restarts `jpcan-core`. It
doesn't go through MQTT and never reaches the adapter. In truck mode the guard
still covers every byte. In sim mode, a yellow SIMULATOR badge stays on screen
in every theme, so sim numbers can't pass for real ones. `JPCAN_ARGS` in
`/etc/default/jpcan` is for other flags and should no longer carry `--sim`.
The Settings rows now scroll, because they no longer fit the panel.

## D27. Touch lockups: never point a Qt input handler at /dev/null
The real cause of the touch lockups. The launcher used to "disable" the evdev
mouse with `QT_QPA_EVDEV_MOUSE_PARAMETERS=/dev/null`. Qt opens it anyway,
reads EOF forever and logs "evdevmouse: Got EOF" in a tight loop: 260k lines
in 2 s and one core at 100% (reproduced). The flood into journald starves
input. Now, when the USB touch is found, the launcher turns off Qt's built-in
input (`QT_QPA_EGLFS_DISABLE_INPUT`, `QT_QPA_FB_DISABLE_INPUT`) and loads one
`evdevtouch:<device>` generic plugin. With no touch found, Qt auto-detects.
`tests/test_launcher.py` guards it. The D25 watchdog stays as a backstop.

## D28. Lock HDMI0 to the panel mode on the kernel command line
The 7" advertises 1024x600 as preferred, but if it isn't connected at boot,
the Pi sizes the HDMI framebuffer at 1024x768 and keeps it until reboot.
GaugeWorks then centres its 600-tall layout, 84 px low, and the panel shows
only the top 600 lines, so the bottom gets cut. `install-services.sh` adds
`video=HDMI-A-1:1024x600@60D` to `cmdline.txt` (`GW_MODE` overrides it for
another screen, such as the 10.1" 1280x800).

## D29. GaugeWorks uses Raspberry Pi OS's PySide6 (GPU), not the pip wheel
The pip PySide6 wheel ships the EGLFS KMS plugin without
`libQt6EglFsKmsGbmSupport.so.6`, so on the Pi, EGLFS failed and GaugeWorks
always fell back to linuxfb with CPU drawing (confirmed in the journal
2026-11-08). `install-services.sh` now installs PySide6 6.8.2 and the Qt
plugins and QML modules from apt. It turns on the venv's
`include-system-site-packages` and removes the venv's own PySide6. Everything
else stays in the venv from pip. Before switching, the full test suite and
every theme were checked on PySide6 6.8.2. The install script checks the
EGLFS, KMS, linuxfb and evdevtouch plugins and does an offscreen render of the
Premium theme. `GW_QT=pip` goes back to the wheel. The linuxfb fallback in the
launcher stays as a safety net.

## D30. Touch watchdog follows the touch by name
The 7" touch board keeps dropping off USB and re-enumerating as a new
`eventN`, even with the screen on its own supply. Qt's evdevtouch can't follow
it, so the watchdog now tracks the device by name (`GAUGEWORKS_TOUCH_NAME`).
While the touch is off the bus, the gauges keep running. When it's back on a
new node, or on a re-created one, GaugeWorks exits with code 3 and systemd
restarts it, about 8 s blank. It exits with `os._exit` to skip a Qt teardown
that crashed. The launcher doesn't treat rc 3 as an EGLFS failure.
Taps get a 3 s grace period before they count as missed, because with CPU
drawing a busy GUI thread can handle them late. When the watchdog fires, it
logs the Qt touch events it saw (begin/update/end/cancel). A burst of `update`
with no `begin` means Qt has a stuck contact. No events at all means touch
isn't reaching Qt.
Confirmed on the Pi on 2026-11-08: EGLFS starts and GaugeWorks uses 10-20% CPU.
The Qt packages install with `--no-install-recommends`, which skips GTK and
friends. That makes `qt6-svg-plugins` an explicit package, because the themes
draw their faces and needles from SVGs.

## D31. Towing page (P3), settable red lines, split scales, appearance settings
Built from the v2 mockup P3 (`docs/mockups/v2/`), as a new page template,
`towing` (`gaugeworks/qml/PageTowing.qml`, with `TowGauge`, `TowPanel` and
`RangeBar`). It's a standard page, so every theme uses it until a theme ships
its own skin.
- Slots: `center` (speed), `ring` (RPM), `inner` (boost), `box1`/`box2` (RPM
  and boost digits), `l1`-`l4` and `r1`-`r4` (panels; `r4` is the VGT dual).
  Gear comes from the profile's `gaugeworks.gear`. Every slot can be swapped
  with press and hold.
- Red lines are per reading. The default is the profile's `display.<key>.alarm`.
  JP can override it from the picker (press and hold), and it's saved per
  vehicle in settings `limits`, in imperial display units like the profile. At
  or over the red line, that reading's trail, pointer, digits and bar blink at
  3 Hz. Defaults on the F-250: 3,000 rpm and 20 psi.
- Split scales: `display.<key>.split` puts min..split on 7/8 of the sweep and
  squeezes split..max into the last 1/8. That's 3,000 rpm and 20 psi on the F-250.
- GaugeWorks tracks each reading's min and max since it started (this drive),
  shown as a bracket on the bars and as text under the value.
- Settings: Background (carbon, expanded metal, diamond plate, brushed,
  honeycomb, black; default carbon; textures in `gaugeworks/assets/bg/`) and
  Colors (two accents from a hue-ring picker; red, amber and green stay fixed).
- No new Qt modules: shadows and glow are drawn, not effects, and static art is
  painted once with Canvas.
- Look picked on 2026-11-09: blade needles (N3) with a drop shadow and a dark gap
  in the trail just behind them; scale marks the needle has passed change color
  (S2: white on both scales); white side-panel pointers pointing
  out toward the screen edge; bigger RPM/boost digits.
- Peak hold (G1): a thin white line across the trail at the highest recent RPM
  and boost, 5 px and shaded like a rounded bar, with a soft trail behind it.
  It holds 3.5 s, then eases back to the needle in about 2.5 s. White,
  because red means "over the red line" here and amber and blue are taken.
  Light trail T3: 4° dark gap behind the needle, full strength, little fade.
- Peak marker changed (O3): a copy of the blade needle in deep orange (#ff6a00)
  at 90% with an orange glow trail, on RPM and boost. Same 3.5 s hold, ~2.5 s fall.
- Center ring C3: gunmetal chrome tube with real-chrome reflections (sky band,
  dark horizon, crisp highlights), a soft shadow on the face, and the accent
  backlight spilling onto the background from behind the gauge. The RPM light
  trail reflects only in the bezel's inner lip (the part curving down toward
  the dial) as a thin sliver fading outward, with a glint where the needle is. Also K4 peak trail (32°, 75%), panel outlines at 35%, deep red scale zone.
- Peak needle only shows once it's 4° of sweep above the needle (fades in and
  out over 0.15 s), so steady cruising and small wiggles show nothing. Its glow
  trail shows only while it falls back, on the high side, and is longer when
  it falls faster.

## D32. Edit mode instead of press-and-hold on the 7" screen
evtest on the truck's 7" touch board (wch.cn USB2IIC_CTP_CONTROL) shows a
finger held still for 3 s reported as a 0.1 s press, a 0.16 s press, then
nothing for 2 s. The controller stops reporting a stationary finger, so a
long press can never complete. Settings has an Edit page button: a bar says
"Tap a reading to change it" and has Done, and a single tap on any reading, on
any page, opens the picker. Edit mode isn't saved. Long press still works where
the screen supports it. Also, the Qt drag threshold went up to 30 px, so a
drifting finger isn't taken by the page swipe.
- Center dish M2 (mockup `docs/mockups/depth.html?r=2`): a 14 px angled slope
  from the bezel down to the RPM floor, then a deeper 26 px straight wall down
  to the boost floor. Lighting: cab light from above, so the slope is dark at
  the top and lit at the bottom, and the visible boost wall is the shaded top
  crescent. Steps cast shadows onto the floor below, and deeper floors are
  darker. The trails are emissive: drawn above the shadows, they wash their
  color onto the slope and the boost wall from 0 up to the needle.
