# PID research: 2014 F-250 6.7L Power Stroke (6R140) + 2013 Jetta 2.0 TDI (CJAA)

Status: **all entries are `verified: false`**. Research date 2026-11-07.

## How this was gathered (read first)

- From this session I could **not fetch** `www.ford-trucks.com` or `docs.bankspower.com` directly. Both failed DNS because they are outside this session's network allowlist. Everything below came from web-search result snippets of those pages and of mirrors such as thedieselstop.com and torque-bhp.com. As a result:
  - Equations are quoted as the snippets showed them. Exact page numbers inside the 80-page ford-trucks thread 1322804 are approximate.
  - The Banks iDash per-year parameter lists (for example the 2016 F350 list linked below) gave parameter names only. No DIDs were captured, and no 2014 F250 list turned up in search.
  - To verify these, allow `www.ford-trucks.com` and `docs.bankspower.com` in the session network settings and re-read the threads directly.
- **Key structural finding:** on the 6.7L PCM (header `7E0`), Ford mirrors the standard Mode 01 PIDs at DID `F4xx`, where `xx` is the Mode 01 PID number. Evidence from the community lists:
  - `22F478` = 01 78 (EGT bank 1, 4 sensors)
  - `22F45C` = 01 5C (oil temp)
  - `22F446` = 01 46 (ambient)
  - `22F46D` = 01 6D (fuel rail pressure control)
  - `22F48B` = 01 8B (diesel aftertreatment status)

  Their byte layouts match SAE J1979 exactly. Byte A is the "sensors supported" bitmask, and data starts at B. Rows marked **"derived (F4xx mirror)"** apply that pattern to PIDs where no 6.7-specific post was found. They will work only if the PCM supports the matching Mode 01 PID; check the `0160`/`0180` support bitmasks first.
- Torque byte letters: A = first data byte after the echoed DID. Torque supports letters beyond D (E, F, G, H, I, ...). In Torque, `SIGNED(A)` treats A as a signed int8.
- Write/control services (2E/2F/31) were skipped.

---

## Vehicle 1: 2014 Ford F-250 6.7L Power Stroke (2011-2016 gen), 6R140

| # | Name | Mode/DID | Header / module | Torque formula | Units | Min / Max | MY claimed by source | Source URL | Confidence | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1a | Odometer (IPC) | 22 `404C` | `720` IPC | `((A*65536)+(B*256)+C)*0.1` | km | 0 / 1,000,000 | 6.7L thread (2011+ owners); poster said it matched the dash | https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids-37.html | med | Posted as `((A<16)+(B<8)+C)*.1`; the `<` is a mangled `<<` shift. Worked example: bytes 08 24 60 → 53,360.0 km, matching the dash. Page number found by search only; the post may instead be in https://www.ford-trucks.com/forums/1388479-2015-5-torque-pro-pids-6.html |
| 1b | Odometer (generic Ford DID) | 22 `DD01` | try `7E0` PCM, `726` BCM, `720` IPC | `((A*65536)+(B*256)+C)` (try `*0.1` if 10x too big) | km | - | none found | no source located | low | Common Ford DID convention, but no 6.7L post confirms it. Searches for DD01 + 6.7 returned nothing. Try only as a fallback. |
| 1c | Odometer (SAE Mode 01 A6) | 01 `A6` | `7DF` / `7E0` | `((A*16777216)+(B*65536)+(C*256)+D)/10` | km | - | evidence only on 2021+ F-150 | https://www.f150gen14.com/forum/threads/pid-experimenting.20273/post-393942 | low (that it exists on 2014) | PID A6 is a late J1979 addition (regulatory odometer reporting came around MY2019+). **Expect it to be unsupported on a 2014**; check the `01A0` support bitmask. No Super Duty 2011-2016 report of it working. |
| 2a | Trans fluid temp (TFT) | 22 `1E1C` | `7E1` TCM (most lists); some lists say `7E0` | `((SIGNED(A)*256)+B)*(9/80)+32` | °F | -40 / 300 | 2011-2014 lists; 15+ "might need a different equation" | https://www.ford-trucks.com/forums/1319750-pids-and-calibrations-for-torque-pro.html ; https://www.thedieselstop.com/threads/torque-pro-app-ford-6-7l-extended-pids.446986/ ; https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids-14.html | **high-med** | Raw value is signed 1/16 °C. The °C variant `((SIGNED(A)*256)+B)/16` (posted as `*(5/80)`) is reported as "Done Testing" at https://www.ford-trucks.com/forums/1465324-torque-pro-and-forscan-question.html. Readings run 5-15 °F off the dash, which likely filters its value. Try 7E1 first. |
| 2b | Trans fluid temp (alt) | 22 `1674` | `7E1` (assumed) / `7E0` | `((A*256)+B)/8` | °F (per posts) | 0 / 300 | mostly 2015.5+ and other Fords | https://www.ford-trucks.com/forums/1388479-2015-5-torque-pro-pids-7.html ; https://www.ford-trucks.com/forums/1692085-torque-pro-custom-pids.html | low (for 2014) | Suggested where 221E1C "was the wrong PID". Several posts say a wrong TFT PID tracks coolant temp exactly. Use as a fallback only. |
| 3 | Engine hours (total run time) | 22 `F47F` (derived) or 01 `7F` | `7E0` PCM | `((B*16777216)+(C*65536)+(D*256)+E)/3600` | h | 0 / 100000 | none 6.7-specific | SAE layout from the Cummins 017F example: https://mopar1973man.com/forums/topic/14570-electrical-article-using-torque-pro-for-gauges-extended-pid-sensors/ | low | No Ford 6.7 engine-hours PID was found in any searched list. J1979 PID 7F: A = support, B-E = total run time in seconds, F-I = idle, J-M = PTO. Derived (F4xx mirror). |
| 4a | Boost / MAP actual | 01 `87` (or 22 `F487` derived) | `7E0` | MAP abs: `((B*256)+C)/32` kPa. Gauge psi: `(((B*256)+C)/32 - BARO)*0.145038` | kPa abs / psi | 0 / 40 psi | 2011+ (in the 6.7 extended list) | https://www.thedieselstop.com/threads/torque-pro-app-ford-6-7l-extended-pids.446986/ ; https://torque-bhp.com/community/main-forum/ford-6-7l-extended-pid-list/ | med | The lists use 0187 with an equation that subtracts barometric pressure (Torque `Baro()`), range 0-40 psi. The exact text wasn't captured; the formula given is the J1979 layout (0.03125 kPa/bit, A = support). |
| 4b | Boost desired (commanded) | 22 `F470` (derived) or 01 `70` | `7E0` | Desired: `((B*256)+C)/32` kPa abs. Actual: `((D*256)+E)/32` kPa abs | kPa abs | 0 / 400 | none | SAE J1979 PID 70 layout; no 6.7 post found | low | No desired-boost PID turned up in any 6.7 list. Derived (F4xx mirror). |
| 5 | VGT vane position, commanded and actual | 22 `F471` (derived) or 01 `71` | `7E0` | Commanded: `B*100/255`. Actual: `C*100/255` | % (closed) | 0 / 100 | none | SAE J1979 PID 71 layout. Context: https://www.ford-trucks.com/forums/1577554-vgt.html (WDS shows `VGTDC#`, % closed) | low | No 6.7 2011-2016 VGT PID turned up in any searched list. One forum says VGT % is a command, not a measured vane position. Repair sites for 2020+ list `VGT_POS_CMD`/`VGT_POS`. Derived (F4xx mirror). |
| 6a | Fuel rate (SAE) | 01 `5E` | `7E0` | `((A*256)+B)*0.05` | L/h | 0 / 100 | in 6.7 list as "PID E5" | https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids.html | low-med | The list says "Fuel Rate - PID E5"; the formula matches SAE 5E, so E5 is probably a 5E typo. One user couldn't get MPG working because they found no fuel-rate PID. If 015E is unsupported, try below. |
| 6b | Engine fuel rate (g/s) | 22 `F49D` (derived) or 01 `9D` | `7E0` | Engine: `((A*256)+B)*0.02`. Vehicle: `((C*256)+D)*0.02` | g/s | 0 / 50 | none | SAE J1979 PID 9D layout | low | For L/h of diesel: g/s × 3.6 / 0.835 ≈ ×4.31. Derived (F4xx mirror). No mg/stroke injection-quantity PID found for the 6.7. The 7.3L one, `221412` `((A*256)+B)*.0625` mg/stroke, is not a 6.7 PID. |
| 7a | EGT11 (post-turbo / pre-DOC) | 22 `F478` | `7E0` | `(((B*256)+C)*0.18)-40` | °F | 0 / 1800 | 2011+ (July 2014 list) | https://www.thedieselstop.com/threads/torque-pro-app-ford-6-7l-extended-pids.446986/ ; https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids.html | **med-high** | Same as SAE 0178: (raw×0.1 °C) − 40 °C, expressed in °F. One user got a steady "122" reading, likely from the wrong bytes. Sources found no **pre-turbo** EGT on 2011-2016; EGT11 is in the downpipe. |
| 7b | EGT12 (post-DOC / pre-SCR) | 22 `F478` | `7E0` | `(((D*256)+E)*0.18)-40` | °F | 0 / 1800 | 2011+ | same as 7a | med-high | One poster treats EGT12 above 1150 °F as "active regen". Sensor naming varies between posters. |
| 7c | EGT13 (pre-DPF) | 22 `F478` | `7E0` | `(((F*256)+G)*0.18)-40` | °F | 0 / 1800 | 2011+ | same as 7a | med-high | Byte pair F/G confirmed in snippets. |
| 7d | EGT14 (post-DPF) | 22 `F478` | `7E0` | `(((H*256)+I)*0.18)-40` | °F | 0 / 1800 | 2011+ | same as 7a | med-high | Byte pair H/I confirmed. One commenter said "off by 40°", probably a °C/°F mixup. |
| 8a | Fuel rail pressure, actual | 22 `F46D` | `7E0` | Posted: `((D*65536)+(E*256)+F)/2560`. Simplified: `((D*256)+E)/10` | bar | 0 / 2000 | 6.7 "TEST version" list | https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids-18.html | med | Posted with a 0-100 range, which is too small; the 6.7 runs 300-1800 bar. One poster got a "can't read ECU" error. SAE PID 6D: B,C = commanded; D,E = actual (10 kPa/bit); F = fuel temp. |
| 8b | Fuel rail pressure, desired | 22 `F46D` | `7E0` | `((B*256)+C)/10` | bar | 0 / 2000 | - | derived from same PID (SAE 6D layout) | low-med | Same response as 8a. |
| 8c | Fuel pressure, low side | 22 `064E` | `7E0` | `((A*256)+B)/2` | kPa | 0 / 1000 | 6.7 list ("non-test version") | https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids-18.html | med | Supply/low-pressure side. |
| 8d | Rail pressure control (regulator) | 22 `03C3` | `7E0` | `A/2` | % | 0 / 100 | 6.7 list | same as 8c | low-med | A read-only regulator duty/command value, not a pressure. |
| 9a | DPF soot load (mass) | 22 `042C` | `7E0` | `((A*256)+B)*(100/65535)` | g/L | 0 / 100 | 2011-2014 | https://www.thedieselstop.com/threads/torque-pro-app-ford-6-7l-extended-pids.446986/ ; https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids.html | med | A 2015 owner said the g/L version "seems to work fine". |
| 9b | DPF soot load % | 22 `042C` | `7E0` | Variants: `((((A*256)+B)*(100/65535))-1)*37` / `((((A*256)+B)*(100/65535))-1)/1.75*100` / `(((A*256)+B)-768)*0.1302` ("still testing") | % | 0 / 100 | 2013 | same as 9a, plus https://powerstroke.org/forum/general-6-7-discussion-2011-2016/806153-2015-torque-pro.html | low | Calibration fit, not a real scaling. Broke after a dealer PCM reflash. Read ~150% on a 2015. Prefer logging raw g/L (9a). |
| 9c | DPF regen status | 22 `F48B` | `7E0` | `{B:0}` (bit 0 of byte B) | on/off | 0 / 1 | 2011+ (July 2014 list) | https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids.html | med | Matches SAE PID 8B byte B bit 0 (regen in progress). Candidate in the same response: `C*100/255` = normalized regen trigger %. That one is derived, low confidence, and could serve as a soot proxy. |
| 9d | DPF distance since last complete regen | DID not captured | `7E0` | `((B*256)+C)*0.03625` | mi? | - | 2011+ | same as 9c | low | The equation appeared in the snippet, but the DID did not. Re-read the thread to get it. |
| 10a | Engine oil temp (EOT) | 22 `F45C` | `7E0` | `A*(9/5)-40` | °F | -40 / 400 | 2011+ | https://www.thedieselstop.com/threads/torque-pro-app-ford-6-7l-extended-pids.446986/ | **med-high** | SAE 015C mirror (A − 40 °C). Fallback: plain `015C`. |
| 10b | Intake air temp after CAC (CACT / IAT2) | 22 `F477` (derived) or 01 `77` | `7E0` | B1S1: `B-40` °C. B1S2: `C-40` °C (°F: `(B*9/5)-40`) | °C / °F | -40 / 215 | none | SAE J1979 PID 77 layout | low | No 6.7 CACT post found. Alternatives: `22F468` / `0168` (IAT sensors; B = sensor 1, C = sensor 2, then −40). Derived (F4xx mirror). |
| x1 | Ambient air temp | 22 `F446` | `7E0` | `A*(9/5)-40` | °F | -40 / 150 | 2011+ | https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids-62.html | med | Extra. Mirror of 0146. |
| x2 | DEF level | 22 `0487` (one list); `F485` (another) | `7E0` | `A/4` | L (per post) | 0 / 100 | 2011+ | https://www.ford-trucks.com/forums/1322804-torque-pro-ford-6-7l-extended-pids-69.html | low | Extra. The DID differs between list versions. |

### Year split and module notes (Ford)
- **2011-2014 vs 2015-2016:** posts say the trans temp equation "might need to be different for the 15+". A powerstroke.org thread warns that the 2011-14 custom PIDs "are not for 15s", and soot % gave impossible values on a 2015. No source documented a header change, so `7E0`/`7E1` are assumed for all years.
- **TCM:** the 6R140 TCM is reported on `7E1`, and some lists put TFT on `7E0`. Try both.
- **PCM firmware:** reflashes changed the soot % behaviour. Treat calibration-fitted equations as fragile.
- **Banks iDash:** per-vehicle lists exist (for example https://docs.bankspower.com/bids/files/PID_2016_Ford_F350_6_DOT_7L_V_281_E.html and https://docs.bankspower.com/bids/files/PID_2016_Ford_F450_6_DOT_7L_V_283_E.html, plus a 2012 F250 6.7L entry in the index at https://docs.bankspower.com/bids/). They give names and units only (for example trans fluid temp, DPF regen status, HP/TQ-ECU) and no DIDs. They are useful only to confirm that a parameter exists for a model year. The host could not be fetched, so none were read.

---

## Vehicle 2: 2013 VW Jetta 2.0 TDI (CJAA, EDC17, 6MT). Brief.

No CJAA-specific Torque or OBDLink custom PID list was found. The closest sources:

| Name | Mode/DID | Header | Formula | Units | Source URL | Confidence | Notes |
|---|---|---|---|---|---|---|---|
| DPF soot mass, calculated | 22 `114F` | `7E0` | `((A*256)+B)/100` | g | https://www.t6forum.com/threads/vw-t6-custom-pid-codes-for-dpf.33964/ | low | T6 (EA288). A 2018 CXEB needed `22208B` instead. The EA189 CJAA may differ. Regen is blocked at about 45 g. |
| DPF soot mass, measured | 22 `114E` | `7E0` | `((A*256)+B)/100` (assumed same) | g | same | low | Same caveat. |
| DPF ash | 22 `178C` | `7E0` | `((A*256)+B)/10` | g | same | low | |
| Distance since last regen | 22 `1156` | `7E0` | not captured | km | same | low | |
| DPF differential pressure | 01 `7A` | `7DF`/`7E0` | SAE: `((B*256)+C)/100` kPa (signed) | kPa | https://forums.tdiclub.com/index.php?threads/obd-pid-7a-is-this-dpf-soot-load-2012-jsw-tdi.379398/ | med | Thread is about a 2012 JSW TDI (CJAA). Consensus: 7A is DPF delta-P, not soot load. |
| Boost / MAP | 01 `0B` (or 01 `87`) | `7DF`/`7E0` | `A` kPa abs (0B) | kPa | standard SAE; context: https://idpartsblog.com/2017/04/19/using-scangauge-on-a-passat-tdi/ | med | The ID Parts blog covers ScanGauge boost, EGT and cat-temp gauges on a 2012+ Passat TDI (EDC17, similar to CJAA). A Competition Diesel post says Passat codes may differ from Jetta: https://competitiondiesel.com/threads/2013-vw-2-0-tdi.155239/ |
| EGT (pre-turbo G235 etc.) | 01 `78` if supported | `7E0` | `((B*256)+C)/10-40` (sensor 1), `((D*256)+E)/10-40` ... | °C | https://idpartsblog.com/2017/04/19/using-scangauge-on-a-passat-tdi/ ; sensor test reference: https://diagnostics.vis4vag.com/en/engines/diesel/2-0-103kw-tdi-cr-cbax/test-of-exhaust-gases-temperature-sensor-g235-g495-648-cbax | low | EGT1 = pre-turbo on the Passat. Whether 0178 is supported on CJAA is unconfirmed. |
| Oil temp | 01 `5C` if supported; VAG alt 22 `005C`? | `7E0` | `A-40` | °C | https://www.audiworld.com/forums/tdi-discussion-101/obdlink-usable-gauges-including-def-tank-gauge-2916157/ | low | An OBDLink user lists engine oil temp as a usable TDI gauge, but no PID is given. |

Other leads: tdiclub.com searches for "Torque" or "ScanGauge xgauge" for the 2009-2014 CR TDI, and the VCDS measuring-block pages at diagnostics.vis4vag.com (EDC17 UDS).
