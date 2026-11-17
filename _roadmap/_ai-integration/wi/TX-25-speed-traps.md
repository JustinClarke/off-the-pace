# TX-25 — Speed-trap facts: measured top speed per driver, team and season

**Group:** 1b new-data · **Depends on:** TX-15 · **Model / cost:** `sonnet-5`, 0.5-1d

**Evidence:** data-use audit, read-only, 2026-11-16 (relayed to the board session; no evidence file on disk). References re-checked 2026-11-16.
**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread (rule 5). Never write `data/dev.duckdb`, `data/bronze/` or `data/fits/`. No data-writing make target without the owner. Nothing staged or committed by an agent.
**Class:** measured, transform class (rule 4: live since AX-07). Missing stays NULL with a reason, never 0. A card on this mart is AX-28, not this item.

## Why
`stg_laps.sql` already casts `speed_st_kph`, `speed_fl_kph` (and I1/I2), but no mart publishes them. About 400 laps have no SpeedST.

## Method
Mart per driver-race-session: max and median of each trap over valid laps, n laps with a reading, n without. Team and season roll-ups carry n. NULL where no reading; never 0.

## Done when
Every value has n; the 400-odd laps without SpeedST are counted as missing, not as 0; tests enforce both.

## Sources
`transform/models/staging/stg_laps.sql`, `transform/models/marts/schema.yml`, `transform/models/marts/fct_speed_traps.sql` (new).

## 2026-11-16 (fixall session), scratch only, not exported
New marts: models/marts/new_data/fct_speed_traps.sql (per driver, race and session: max, median and n per trap over valid laps; n_st_missing_all_laps over all laps) and fct_speed_traps_season.sql (driver and team roll-ups with n). Test assert_speed_traps_missing_not_zero passes. Race laps without SpeedST: 400 (all counted missing; Q 1,296); no reading is 0. 145 driver-sessions have no valid-lap reading, so their max is NULL. Output: /private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/new_marts_check.txt.
