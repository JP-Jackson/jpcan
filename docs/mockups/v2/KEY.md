# v2 mockup key

Refer to parts as page-number, for example "P2-4" or "C3-6". The numbered
renders are in `numbered/`.

| Page | Parts |
|---|---|
| **P1** Premium Daily | 1 tach that wraps into the top bar · 2 gear dial · 3 center card (boost/trans/MPG) · 4 speedo · 5 odometer · 6 coolant · 7 fuel % and range · 8 clock/date bar |
| **P2** Premium Sport | 1 big center tach · 2 speed · 3 gear · 4 red-zone glow · 5 coolant bar · 6 trans bar · 7 boost bar · 8 oil bar |
| **P3** Premium Towing (rev 3) | 1 speed (big, center) · 2 RPM wedge pointer with a light trail (lit wedge on the face from 0 to the pointer) · 3 boost wedge pointer on the inner scale with its own light trail. Each has a user alarm limit (red marker; red zone starts there); at or above it the whole trail, the pointer and the digits turn red (`premium_towing_alarm.png`, limits popup `premium_towing_limits.png`) · 4 RPM digits with boost under them · 5 gear (bottom of the circle) · 6 left panels (intake/trans/coolant/oil) · 7 right panels (fuel/load/rail/VGT) · 8 premium vertical bars: outline frame, red zone fading down, fill fading down from a bright top edge, pointer at now, scale min/max, this drive's min–max bracket (also under the value) · 9 VGT vane: CMD, ACT and DIFF (amber at 5%, red at 10%) · 10 top bar: time, date, page, outside temp, settings |
| **P4** Premium Economy | 1 open-arc tach · 2 speed · 3 gear · 4 fuel bar · 5 fuel % and range · 6 trip/tank boxes · 7 MPG bar with tank-avg marker · 8 MPG now/trip/last 10 · 9 telltales |
| **P5** Premium Trend | 1 channel list · 2 live values · 3 chart · 4 tap cursor · 5 min/avg/max · 6 time window buttons |
| **C1** Classic Daily | 1 digital speed/gear window · 2 sweep speedo · 3 odometer · 4 round tach · 5 temp/trans window · 6 boost/fuel window · 7 clock |
| **C2** Classic Towing | 1 top strip (gear/speed/rpm/clock) · 2 boost · 3 trans · 4 coolant · 5 oil · 6 peak marker · 7 big number with peak |
| **C3** Classic Economy | 1 MPG gauge · 2 tank-avg marker · 3 MPG digital window · 4 fuel gauge with range · 5 tank/trip/last-10 boxes · 6 Fill-up/History buttons |
| **C4** Classic Trend | 1 pen readouts · 2 pen selector · 3 strip chart · 4 time window buttons · 5 peaks |

Every reading on P3 can be swapped: press and hold it to open the picker (`premium_towing_picker.png`).

## Options (P3 for now)

Render with `&bg=` and `&acc=`/`&sec=` (sheets in `options/`).

- Backgrounds (a setting, default B1 carbon): B1 carbon, B2 expanded metal, B3 diamond plate, B4 brushed aluminum, B5 honeycomb, B6 plain black (night).
- Colors: a color picker (hue ring, brightness, quick picks) for two picks, a main accent (frames, RPM needle, bar fills, glow) and a second accent (boost needle and scale).
  Presets: cyan, green, orange, purple, white for main; amber, cyan, green, orange, purple, white for second.
  Red, amber and green keep their meaning (danger, warning, OK) and don't change. Red as the main accent (K4) is shown
  but not recommended: everything looks like an alarm.
