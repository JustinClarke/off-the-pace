# WC-01 - Phase 0: data and reference

**Status: not started, not registered.** Waits on DD-WC1 (owner approves starting Phase 0). Design: [`WC-design-note.md`](WC-design-note.md).

**Goal.** Build the per-corner pass table from the bronze parquet: one row per driver, corner segment and lap, with the approach gap, both outcomes, the driver's own clean reference, and an exclusion reason where one applies.

**Inputs.**
- `data/bronze/telemetry/` (merged car + position samples; distance, speed, SessionTime, Status, DRS code).
- `data/bronze/laps/` (stint, compound, tyre life, pit in/out, track status per lap).
- `data/bronze/track_status/`, `data/bronze/race_control/` (SC, VSC, red, yellow sectors, blue flags), `data/bronze/weather/` (rain), `data/bronze/circuit_info/` (corner positions).

**What the table holds.**
- Corner segments per circuit layout (braking point to 100 m after the apex; flat kinks merged with the straight; slow / medium / fast class by clean-air apex speed).
- **Gap** in seconds, averaged **300 m to 50 m before the segment starts**; car ahead by on-track crossing order.
- **Outcomes:** segment time from the driver's own trace only; minimum speed in the segment.
- **Reference:** the driver's own clean passes of the segment **within ±4 laps**, same stint and compound (clean = over 3 s behind the car ahead and no car within 1 s behind).
- **Exclusions:** SC, VSC, red and yellow-sector laps; lap 1 and the 2 laps after a restart; pit in/out laps for either car; wet laps (rain flag or intermediate/wet tyre); OffTrack samples. Lapped car ahead within 3 s is tagged "lapped"; a blue-flagged follower is tagged "yielding".

**Done when.**
- The table builds on a scratch copy (never on `data/dev.duckdb` directly), with tests for the exclusions and for the gap window not overlapping the outcome window.
- Row counts per season, the share of passes with a measured reference, and the share with no clean reference are recorded in `_evidence/WC-01-<date>/` with PROVENANCE.txt.
- No coefficient, curve or gate is computed in this item.

**Stint coverage to check against (count-only, lap-end gap, whole stint).** 16.7% of stints (1,177) have no clean lap; about 86% of those can be filled from another stint of the same driver or the teammate; about 2% of all stints (162) are unavailable. The per-corner, ±4-lap measure will give a somewhat lower measured share.

**Risks.**
- Selection: the stints with no clean reference are the midfield trains where the loss is largest.
- Local baseline drift inside the ±4-lap window (tyre cliff, track evolution, following bunched at one end).
- 2018 gaps in bronze (no AUS or BHR telemetry; China and Germany track status starts around lap 30).
