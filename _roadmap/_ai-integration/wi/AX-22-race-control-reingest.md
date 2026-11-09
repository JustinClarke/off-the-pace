# AX-22 — Re-ingest race control with the corrected session clock (DEFERRED)

**Group:** 3 foundations · **Depends on:** none · **Model / cost:** `sonnet-5`, about 1d plus download time
**Status:** deferred by the owner. Do this later, before anything is published that joins race-control messages to laps.

## Why
`race_control.session_time_s` is measured from UTC midnight, not from the session start. Probe 4 found it. The fix adds `session_time_corrected_s` (Time minus the session start, from the laps `LapStartDate - LapStartTime`). The fix is in the working tree of `ingestion/src/ingest.py` and is not yet committed. Audit: `experiments/12-race-control-clock-fix/race_control_clock_fix_audit.md` in the f1-chat repo.

No current model or mart reads the corrected column, so nothing published is wrong today. The re-ingest is needed before any feature joins race-control events to laps.

## What is needed
1. Commit the fix (owner decision D3).
2. Re-download race control for all 173 races, 2018 to 2025. The timing server now needs F1 account credentials (`F1_USERNAME` and `F1_PASSWORD`).
3. Rewrite all 173 race-control files together. Mixed old and new files break the dbt source glob, or drop the new column silently. Alternatively, set `union_by_name=true` on that source first.
4. Re-run the join check (0 of 334 before the fix, about 95% after).
5. Re-run `dbt build` for the affected models. Confirm no mart value changes (the audit expects none).
6. Publish only after the owner approves the validation.

## Done when
All 173 files carry `session_time_corrected_s`, the join check passes on at least Monza 2024, Silverstone 2024 and Austria 2022, and the owner has approved publishing.

## Sources
- `ingestion/src/ingest.py` (the conversion, around line 284 before the fix)
- `transform/models/staging/stg_race_control.sql`
