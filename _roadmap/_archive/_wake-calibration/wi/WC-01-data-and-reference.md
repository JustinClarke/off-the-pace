# WC-01 - Phase 0: data and reference

**Status: not started, not registered.** Waits on DD-WC1 (owner approves starting Phase 0). Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Build the per-corner pass table from the bronze parquet: one row per driver, corner segment and lap, with the approach gap, both outcomes, the driver's own clean reference, and an exclusion reason where one applies.

**Inputs.**
- `data/bronze/telemetry/` (merged car + position samples; distance, speed, SessionTime, Status, DRS code).
- `data/bronze/laps/` (stint, compound, tyre life, pit in/out, track status per lap).
- `data/bronze/track_status/`, `data/bronze/race_control/` (SC, VSC, red, yellow sectors, blue flags), `data/bronze/weather/` (rain), `data/bronze/circuit_info/` (corner positions).

**What the table holds.**
- Corner segments per race layout, ending 100 m after the apex. **Braking corners** start at the braking point (the corner's median clear-air brake onset, `segment_basis = brake_onset`). **Flat-out corners** (under half of clear-air passes brake) start a fixed **100 m before the apex** (`segment_basis = fixed_before_apex`); their passes are kept, not merged with the straight, and `segment_basis` keeps them separable. Slow / medium / fast class by clean-air apex speed. A corner with no clear-air pass in the race has no segment and its passes carry `no_segment`.
- **Gap** in seconds, averaged **300 m to 50 m before the segment starts**; car ahead by on-track crossing order.
- **Outcomes:** segment time from the driver's own trace only; minimum speed in the segment.
- **Reference:** the driver's own clean passes of the segment **within ±4 laps**, same stint and compound (clean = over 3 s behind the car ahead and no car within 1 s behind).
- **Exclusions:** SC, VSC and red laps (whole lap); **yellow by sector**: a race_control sector yellow in marshal sector k during the lap excludes the passes whose corner lies in sector k or the following sector k+1 (`yellow_sector`; marshal sectors approximated as evenly spaced, since bronze has no marshal-sector positions); lap 1 and the 2 laps after a restart; pit in/out laps for either car; wet laps (rain flag or intermediate/wet tyre); **track-limits laps** (the follower's own lap deleted for track limits, `track_limits`; the car ahead's track-limits lap is flagged in `leader_track_limits`, not excluded); OffTrack samples. Lapped car ahead within 3 s is tagged "lapped"; a blue-flagged follower is tagged "yielding".
- **Layout flag (DD-WC6, flag only, never an exclusion):** `layout_changed` and `layout_note` on every pass row. A race is flagged when, against the previous race at the same circuit, its corner count differs, a corner moved over 40 m after a rigid alignment, its median telemetry lap length differs by over 50 m from the previous up-to-3 races since the last change, or its corners came from another season's circuit_info (fallback). The marshal-sector count is not compared (bronze holds none).

**Done when.**
- The table builds on a scratch copy (never on `data/dev.duckdb` directly), with tests for the exclusions and for the gap window not overlapping the outcome window.
- Row counts per season, the share of passes with a measured reference, and the share with no clean reference are recorded in `_evidence/WC-01-<date>/` with PROVENANCE.txt.
- No coefficient, curve or gate is computed in this item.

**Stint coverage to check against (count-only, lap-end gap, whole stint).** 16.7% of stints (1,177) have no clean lap; about 86% of those can be filled from another stint of the same driver or the teammate; about 2% of all stints (162) are unavailable. The per-corner, ±4-lap measure will give a somewhat lower measured share.

**Risks.**
- Selection: the stints with no clean reference are the midfield trains where the loss is largest.
- Local baseline drift inside the ±4-lap window (tyre cliff, track evolution, following bunched at one end).
- 2018 gaps in bronze (no AUS or BHR telemetry; China and Germany track status starts around lap 30).
- Flat-out segments may measure the tow (a gain) as well as wake loss; nothing in the table separates the two yet (see the WC-01 evidence, DECISION-next-steps.md and the WC-03 pre-registration).

_Spec edited 2026-10-27 (owner ruling) to match the build: fixed 100 m start for flat-out corners replaces "flat kinks merged with the straight"; no_segment, track_limits and the sector-yellow rule added. Layout flag added 2026-10-27 (DD-WC6). State is in the build log._
