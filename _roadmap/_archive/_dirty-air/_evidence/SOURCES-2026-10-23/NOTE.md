# Data sources after the livetiming 401 (2026-10-23)

**Question.** F1's livetiming archive now needs an F1 account (see `../FASTF1-401-2026-10-23/NOTE.md`). Is there a legitimate way to get the session data the dirty-air design needs for 2018-2025?

**Short answer.** We do not need a new source for 2018-2025. Bronze already holds every dataset the design needs for every race except 2018 rounds 1-2 (positions and car data). Those two races were missing from F1's own archive when they were ingested, so no source covers them, F1's included. The one thing that is not in bronze, the marshal-sector map, is served by the MultiViewer circuit API without a login. The 401 blocks only re-ingesting bronze from scratch, new raw fields, and 2026 or later. For 2023 or later, OpenF1 is a no-login fallback for positions, laps, race control, DRS and intervals, under a non-commercial licence.

No login, token or credential was used. Every request below was an anonymous GET to a public endpoint. No repo file changed except this note. Nothing was written to `data/`. Scratch: `/private/tmp/claude-501/-Users-justin-github-off-the-pace/1fdfffb0-6280-4ac0-900e-471f09f2c9ba/scratchpad/sources/` (venv with duckdb 2.0.0, in-memory connection only; `bronze_cov.py`, `loc_spacing.py`, `resp/`).

## 1. What bronze already has (read-only, in-memory duckdb over `data/bronze/**.parquet`)

Command: `venv/bin/python -I bronze_cov.py /Users/justin/github/off-the-pace/data/bronze` (counts per season), plus `ls`/`comm` diffs of the `race=` folders.

| Season | Races in schedule | laps (race) | telemetry (pos + car merged: X/Y, DRS, DriverAhead, RelativeDistance, Status) | track_status | race_control (rows with a marshal sector / yellow flags) | circuit_info (corners only) |
|---|---|---|---|---|---|---|
| 2018 | 21 | 21 (22,336 laps) | **19**: no Australia (R1) or Bahrain (R2) | 21 | 21 (363 / 190) | 19: no AUS or BHR |
| 2019 | 21 | 21 | 21 (16.6M rows) | 21 | 21 (273 / 144) | 21 |
| 2020 | 17 | 17 | 17 | 17 | 17 (221 / 120) | 17 files |
| 2021 | 22 | 22 | 22 | 22 | 22 (290 / 126) | 21: no Belgium |
| 2022 | 22 | 22 | 22 | 22 | 22 (356 / 185) | 22 |
| 2023 | 22 | 22 | 22 | 22 | 22 (332 / 163) | 22 |
| 2024 | 24 | 24 | 24 | 24 | 24 (356 / 165) | 24 files |
| 2025 | 24 | 24 | 24 (18.4M rows) | 24 | 24 (469 / 245) | 24 |

- **Raw DRS codes are kept.** The Abu Dhabi race shows codes {0,1,2,3,8,10,12,14} in every season (no 3 in 2023 or 2025). DRS code 8 needs a staging change, not a new ingest.
- **The 2018 R1/R2 gap is in F1's archive itself.** `data/README.md`: "F1's archive has the Rd1 race's car-data stream but no position stream ... and neither stream for the Rd2 race". It is accepted by ADR-009. Laps, track status and race control exist for both races (940 and 997 laps, 14 and 20 track-status rows, 55 and 69 race-control rows).
- **The track-status timeline is partial for 2018 China and Germany.** The rows start at session_time 3409 s and 2643 s; DA-01 puts the start around lap 30 and lap 29.
- **Marshal-sector maps are not in bronze for any season.** `ingest.py _write_circuit_info` stores `circuit.corners` only. DA-01 fetched marshal sectors from MultiViewer for 2018-2020 (58 of 59 races) but did not ingest them.

**What is actually missing for the design:** (a) positions and car data for 2018 R1/R2; (b) the marshal-sector-to-track map for every season (NEW INGESTION in the design note); (c) track status before about lap 30 in 2018 China and Germany; (d) corners for 2021 Belgium and 2018 AUS/BHR (not a design input). The 401 also blocks re-ingesting bronze from scratch and anything from 2026 on.

## 2. Sources checked

### F1 livetiming archive (official)
- `curl -A 'Mozilla/5.0' https://livetiming.formula1.com/static/2025/Index.json`: **401**. The same for `/static/2023/Index.json` and `/signalr/negotiate`. `/signalrcore/negotiate` (GET): 405, live feed only, not probed further.
- Not used. Access needs an F1 TV account token (FastF1 3.9.0a0). That is the owner's decision; see section 4.
- **Terms.** formula1.com terms of use ("F1 TV Terms of Use - United States 2024", headed "FORMULA1.COM - TERMS OF USE"), Intellectual Property Rights section:
  - "is for your personal, non-commercial use only (save where expressly provided)"
  - "you agree not to modify, copy, reproduce, republish, upload, frame, post, transmit or distribute by any means"
  - "to distribute, copy, extract or commercially exploit such material or content"
  - "You must not attempt to gain unauthorised access to this Site"
- **Flag.** Even with a legitimate account, these terms restrict republishing, and our app republishes derived data. The terms do not say whether derived aggregates count as "content". That question is the same with or without the 401.

### OpenF1 (api.openf1.org)
- **Seasons.** `GET /v1/sessions?year=Y&session_name=Race`: **404 {"detail":"No results found."} for 2018, 2019 and 2022**; **200 for 2023 (23 rows, 22 not cancelled), 2024 (24), 2025 (24)** and 2026 (25). `meetings?year=2018`: 404. The docs say: "Historical data (from 2023 onwards) is free and accessible without authentication. Real-time data requires a paid subscription."
- Endpoints on the 2023 Bahrain race (session_key 7953), all no-auth GETs:

| Endpoint | Status | Sample / note |
|---|---|---|
| `location` (x,y,z) | 200 | 226 rows in 60 s. Spacing p10/p50/p90 = 0.16/0.26/0.40 s (2023 Abu Dhabi), 0.16/0.24/0.36 (2024), 0.16/0.24/0.40 (2025). Same jittered cadence as our 2022-25 bronze. No OnTrack/OffTrack status, DriverAhead or distance-to-ahead. |
| `car_data` | 200 | speed, rpm, n_gear, throttle, brake, **drs** (raw code), about 3.7 Hz |
| `laps` | 200 | lap_duration, sector durations, i1/i2/st speeds, mini-sector segment codes, is_pit_out_lap |
| `intervals` | 200 | interval and gap_to_leader, "updates approximately every 4 seconds", races only |
| `position` | 200 | running race position on change |
| `race_control` | 200 | category, flag, scope, **sector** (marshal sector, e.g. "YELLOW IN TRACK SECTOR 10"), SafetyCar, Drs |
| `stints`, `session_result`, `overtakes` | 200 | |
| `pit` (driver 1) | 404 "No results found." | |
| `track_status` | 404 | Not an endpoint (the docs list 18 endpoints and none is track status). Flag state has to be rebuilt from race_control. |

- **Terms** (openf1.org footer and repo LICENSE): "© OpenF1. Licensed under CC BY-NC-SA 4.0." FAQ: "OpenF1 is intended for educational purposes, personal learning projects, research, and non-commercial fan engagement. For other use cases, please contact us to discuss appropriate licensing". The free tier is labelled "Historical data | Personal use ... Up to 3 requests per second and 30 requests per minute". Also: "The project does not claim ownership of Formula 1 data".
- **Flags.** NonCommercial and **ShareAlike**: derived data we publish would have to carry the same licence and give attribution. The "Personal use" label on the free tier sits awkwardly with a public app; asking them is the safe route. The data is F1's timing feed, so F1's own terms above still apply to the underlying data. At 30 requests per minute, a 2023-2025 location pull (70 races × 20 drivers, chunked by time) is slow but feasible.

### Jolpica (Ergast successor, api.jolpi.ca)
- `GET /ergast/f1/2018/1/laps.json?limit=3`: 200, total 937 (lap times and position per lap). `2018/2/laps.json`: 200, total 997. `2025/24/laps.json`: 200, total 1156. `2018/1/pitstops.json`: 200, total 20.
- Has results, per-lap times and positions, pit stops and standings (1950 to present). **No position samples, track status, DRS, race control or sectors.** It is already used in bronze (`reference/jolpica`).
- **Terms** (TERMS.md, updated Aug 27 2025): "The API is freely available for **non-commercial use**." "The data is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)." "For commercial usage, please contact us via admin@jolpi.ca". Rate limits: "Burst Limit: 4 requests per second / Sustained Limit: 500 requests per hour".
- **Flag.** The same NC-SA terms already apply to the Jolpica data in bronze today.

### MultiViewer (api.multiviewer.app)
- `/api/v1/circuits`: 200 (index). `/api/v1/circuits/70/2018` and `/70/2025`: 200, with corners, marshalSectors, marshalLights, pitLoss, rotation and miniSectorsIndexes. `/api/v1`, `/events`, `/sessions`, `/positions`, `/live-timing` and `/api/v2/circuits`: **404**. **There is no public positions or timing endpoint.** MultiViewer's own live timing runs inside the desktop app on the user's F1 TV login (docs: "To use MultiViewer for F1, you need an F1 TV subscription").
- **Layout years in the index** (circuits per year): 2018: 11, 2019: 21, 2020: 15, 2021: 21, 2022: 12, 2023: 5, **2024: 0**, 2025: 1. A request for a missing year falls back to another year: `/70/2025` serves 2021 and `/2/2025` (Silverstone) serves 2022. Every circuit raced in 2018-2025 is in the index, including Miami (2022), Las Vegas (2023), Losail, Jeddah and Zandvoort. So **2022-2025 marshal sectors are mostly older layouts**, the same caveat DA-01 found for ten 2018 races.
- **Terms.** No terms page (`/terms`, `/terms-of-service`, `/tos` and `/legal` all 404). The API is undocumented. Site footer: "MultiViewer is a non-commercial, fan-made application. Data is used for non-commercial, fair use." and "MultiViewer doesn't help circumvent any content protection or limitations by F1 TV".
- **Flag.** We have no stated permission to reuse or republish the API; it is used on sufferance. Marshal-sector geometry is a small reference table, but credit MultiViewer and consider asking them.

### FIA documents (fia.com)
- The F1 documents page (season 2025): 200. The season dropdown offers 2019-2026 and 2015, **no 2018**. Documents are PDFs: classifications, starting grid, stewards' decisions, Race Director's event notes and circuit maps. **Lap analysis, lap chart and history chart are not listed.** It has no position, DRS or track-status feed. The footer links a "Terms and conditions" PDF that was not read. Not useful for this design.

### Other "official open data"
- None found. F1 publishes no open data API. The livetiming archive was the de facto public feed and is now gated. The FastF1 mirror (`livetiming-mirror.fastf1.dev`) returned 404 for 2018 Abu Dhabi (previous note). It republishes F1's archive, so it was ruled out under the hard limits regardless.

## 3. Coverage by need

| Need | Bronze today | OpenF1 | Jolpica | MultiViewer | F1 archive (needs login) |
|---|---|---|---|---|---|
| Position samples ~0.3 s | 2018-2025, **except 2018 R1/R2** | 2023+ (0.24 s median), no Status/DriverAhead | no | no | blocked; 2018 R1/R2 absent there too |
| Lap times / sector times | 2018-2025 all races | 2023+ | 2018-2025 lap times (no sectors) | no | blocked |
| Track status (flag state) | 2018-2025; 2018 CHN/GER partial | none directly; rebuild from race_control 2023+ | no | no | blocked |
| DRS (incl. code 8) | 2018-2025 except 2018 R1/R2 | 2023+ raw code | no | no | blocked |
| Race control (yellows + marshal sector) | 2018-2025 all races | 2023+ | no | no | blocked |
| Marshal-sector map | **not ingested** | no | no | all circuits; exact year for 2018 (11), 2019-2021, part of 2022-2023; older layout otherwise | session_info circuit key only |
| Car ahead / distance (FastF1-derived) | 2018-2025 except 2018 R1/R2 | no (recompute from location) | no | no | blocked |

**Identification.** Bronze joins on FastF1 race slugs and `race_id` = `{year}_{round}`. OpenF1 uses `session_key`/`meeting_key` and driver_number; map them by year plus date or location. Jolpica uses `driverId` and season/round. MultiViewer needs the numeric F1 `circuit_key`, which comes from the `/circuits` index by name or country, not from session_info. Any OpenF1 import would need a new crosswalk and a check that it matches bronze timestamps (OpenF1 gives UTC `date`; bronze gives SessionTime and Date).

## 4. Verdict per need

| Need | Verdict |
|---|---|
| Position samples | **Already covered** 2018-2025 except 2018 R1/R2. **2018 R1/R2 cannot be covered by any source**, F1's archive included (the streams were missing there). Re-fetch fallback: OpenF1 for 2023+ only. |
| Lap times | **Already covered** 2018-2025. Jolpica covers all seasons and OpenF1 covers 2023+ as cross-checks. |
| Track status | **Already covered** 2018-2025, except about the first half of 2018 China and Germany, which no open source fills (OpenF1 starts in 2023; it may be partly reconstructible from 2018 race_control in bronze). |
| DRS | **Already covered** 2018-2025 except 2018 R1/R2 (same gap as positions). OpenF1 for 2023+ only. |
| Race control (yellows with sector) | **Already covered** 2018-2025. OpenF1 for 2023+. |
| Marshal-sector map | **Open source (MultiViewer), no login.** Exact layout year only for some seasons; the rest are served from an older layout. No published terms. |
| Any re-ingest of 2018-2022 raw data, or new raw fields | **Not coverable without F1's archive.** |

## 5. Owner decisions

1. **Protect the existing bronze.** It is append-only and cannot be rebuilt for 2018-2022 without an F1 account. Back it up before any re-ingest or CO-17 step that could overwrite it.
2. **Marshal sectors.** Approve ingesting the MultiViewer circuit API (undocumented, no terms, "non-commercial, fair use"). Accept older layouts for most 2022-2025 circuits, or skip the local-yellow exclusion where the layout year does not match.
3. **Only if a re-fetch or 2026+ is needed.** Either provide an F1 TV account for FastF1 3.9.0a0 (the formula1.com terms still say "personal, non-commercial use only" and forbid republishing), or use OpenF1 for 2023+ under CC BY-NC-SA 4.0 (ShareAlike plus attribution on published derived data; the free tier is labelled "Personal use", so ask OpenF1).
4. **Licence check.** The app is public, free and AGPL. Bronze already contains Jolpica data under CC BY-NC-SA 4.0. Decide whether the app's published derived data meets NC-SA (attribution and ShareAlike), regardless of the 401.

## Unverified
- OpenF1 location completeness for every 2023-2025 race and driver (sampled 4 races, 1 driver, 60 s each).
- Whether 2018 China and Germany track status can be rebuilt from bronze race_control.
- The FIA "Terms and conditions" PDF (not read).
- Whether F1 now serves 2018 R1/R2 streams to logged-in users (not testable without an account).
