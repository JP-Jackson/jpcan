# GaugeWorks design mockups

Concept renders at 1024x600 using the F-250's real ranges (65 mph cruise).
These are static designs for picking a direction, not running themes yet.
All are original designs in the style of OEM clusters and aftermarket race and
EFI dashes. None of them use any brand's artwork or trade dress.

| Design | Style |
|---|---|
| prestige | factory-premium twin dials, chrome rings, center info card |
| cockpit | wide digital cockpit, arcs around a huge speed readout |
| track | motorsport race dash: bar tach, shift lights, data fields |
| street | aftermarket-EFI style: segmented tach, side gauges, trend cells |
| sweep | minimal single sweep tach, large readouts |
| steampunk | brass, Nixie tubes, sight glasses, clockwork |

Re-render (Playwright): open `designs.html?d=<name>` or `steampunk.html`.
Fonts come from Google Fonts (all OFL); the Pi themes will bundle them.

`current_themes.png` (2026-11-08) shows Premium, Classic and Classic refined
on all four pages before the theme rework. Only Daily differs between themes.

## v2 theme mockups (2026-11-08)

The rework keeps two themes, Premium and Classic, and each theme gets its own
layout on every page. Numbers are big: the main readouts are 100 px or more,
values 45 px or more, and no label is under 16 px. Render with
`v2.html?t=premium|classic&p=<page>`. The renders are in `v2/` and the
overview is `v2/sheet.png`.

| Theme | Page | Based on |
|---|---|---|
| Premium | Daily | wide twin-dial cluster: tach wraps from the left dial into a top bar, big gear and speed, center card |
| Premium | Sport | single big center tach, speed and gear inside, red-zone glow, side arc bars |
| Premium | Towing | diesel-monitor style: carbon, segmented boost arc, 8 big data panels |
| Premium | Economy | modern digital: open arc tach around a huge speed, curved fuel bar and range, MPG bar |
| Premium | Trend | pick up to 2 channels, 1/5/15 min or Drive window, tap the chart for a cursor |
| Classic | Daily | vintage pickup: horizontal sweep speedo, round LCD and tach, twin-gauge windows, green lighting |
| Classic | Towing | four big analog gauges, each with a big number and a peak marker |
| Classic | Economy | big analog MPG gauge with a tank-average marker, fuel gauge, tank/trip/last-10 boxes |
| Classic | Trend | paper strip-chart recorder with two pens |

EGT isn't used: the truck's EGT reads a fixed placeholder (deleted), so boost,
oil and intake temperature take its place.

## Reference styles JP liked (for later themes)

Saved 2026-11-07 for detail and feel only. Any theme built from these must be
original: no logos, brand names or copied artwork.

- **Semi-truck chrome**: heavy chrome bezels, red glow rings, four chrome
  sub-dials nested inside each main dial, a center photo panel and a telltale
  strip. JP: "not my favorite, but look at the detail".
- **Aftermarket ECU dash**: a big pod tach with a shift-light housing, a
  carbon-fiber background, a row of small analog gauges (coolant, oil
  pressure/temp, fuel pressure/level), and round telltale buttons along the top.
- **Sport-coupe cluster**: three overlapping chrome-ringed dials in gunmetal,
  red needles with big center caps, an LCD odometer window, and fuel/temp
  half-dials with LCD voltage and oil-pressure boxes.
- **Classic white-face**: white faces, chrome rings, red needles, a big
  speedo and tach, and four small gauges below (volts, temp, oil, fuel).
