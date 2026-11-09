# WC-07 - Archived-race replay dashboard (measurement only)

**Status: not started, not registered.** Depends on WC-01. **Pulled forward (owner, 2026-10-27): built as an internal debugging view alongside WC-02**, not an owner-facing view before WC-02 passes. It becomes the owner-facing replay only after WC-02 check 1 (gap vs timing) has passed; until then every page carries "internal debugging view: gap not yet checked against timing (WC-02)". Design: [`WC-design-note.md`](WC-design-note.md). Recommendation on when to build it: [`../_evidence/WC-01-2026-10-27/DECISION-next-steps.md`](../_evidence/WC-01-2026-10-27/DECISION-next-steps.md).

**Goal.** Replay a past race lap by lap so the owner can see what the pass table measured: for each car, who is ahead, how close, and whether the driver has a clean reference at that corner.

**Shows, per lap and car (and per corner on demand).**
- Car ahead (on-track crossing order) and the **gap to it in seconds** (the WC-01 approach gap) and **in metres** (distance between the two cars at the same moment; a new derived column, built from the same traces).
- **Reference status**: measured (own clean passes within ±4 laps, same stint and compound), no clean reference, or excluded with the reason (neutralised, yellow_sector, restart, pit, wet, track_limits, ...).
- The **label**: measured / modelled / unavailable. Until WC-05 lands there is no modelled reference, so a pass without a measured reference shows "unavailable" with the reason, never 0.
- Diagnostics worth seeing: `segment_basis` (braking vs flat-out corner), lapped / yielding tags, `leader_track_limits`, the approximate marshal sector, `layout_changed` / `layout_note` (DD-WC6 layout flag).

**Does not show.** No loss, delta, coefficient, curve or scale. The pass table's `delta_time_s` column is not displayed or aggregated. No archived dirty-air (DA-03) number.

**Inputs.** The WC-01 pass table (rebuilt to a scratch folder or a committed export; never `data/dev.duckdb` directly) and bronze telemetry for the metre gap.

**Input interface (DD-WC3 is OPEN: no live code).** The replay reads one race at a time through a single documented input, so a live feed can be plugged in later without changing the page:
- `ReplaySource.passes(season, race) -> DataFrame` with exactly the WC-01 `PASS_COLUMNS` (`transform/tasks/wake_calibration/build_pass_table.py`), one row per driver, corner and lap, laps in order. The archived source reads the builder's `pass_table_<season>.parquet` from a scratch folder.
- `ReplaySource.traces(season, race, driver) -> DataFrame` with the bronze telemetry columns the builder reads (`SessionTime`, `driver_id`, `lap_number`, `distance_m`, `speed_kph`, `brake`, `Status`, `X`, `Y`), for the metre gap.
- `ReplaySource.is_live -> bool`; an archived source returns False. The page shows "archived" or "live" from it and nothing else changes.
- A future live source would have to produce the same columns, lap by lap. It is NOT written: no OpenF1 client, no polling, no credentials, until the owner rules on DD-WC3 (the OpenF1 licence).

**Done when.** One race per season replays end to end; every displayed number is a measurement with its label; the owner has looked at it. Test: no loss-type column reaches the page.

**Risks.**
- An owner-facing page that looks finished invites adding the loss scale before WC-03/WC-04 pass (that is WC-08, gated). Kept internal until WC-02 passes for this reason.
- The approach gap is not yet checked against the timing feed (WC-02 check 1); until it is, the seconds shown are unvalidated.
- Neighbouring corners' windows overlap (PROVENANCE choice 20), so per-corner values are not independent.
