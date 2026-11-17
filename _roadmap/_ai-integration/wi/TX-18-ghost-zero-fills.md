# TX-18 — Ghost marts: say which zeros are a declared field-average prior and which are missing values

**Group:** 1a bronze-honesty · **Depends on:** TX-15 · **Model / cost:** `opus-5`, 1d · **Blocks:** ghost-car cards (AX-15b)

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
- `fct_ghost_race_finish.sql:334`: `COALESCE(pa.finish_pos_se, 0.0)`. An SE of 0 claims certainty (audit: 4 of 30,344 rows).
- `fct_ghost_car_pace.sql:206-221`: constructor pace, its SE, circuit interaction and both degradation slopes are filled with 0 (audit: 1,135 and 82,298 of 1,384,558 rows). The comment says the slope fill is deliberate ("field-average", so ego == host is an exact zero), so part of this is a modelling choice, not a bug.

## Method
1. Per column, rule: (a) a declared prior (0 = field average) that stays, but with a flag column saying the cell had no estimate; or (b) missing, which becomes NULL with a reason.
2. An SE is never filled with 0: missing SE is NULL, and anything that reads it (`app/src/features/hidden-performance/`, `scripts/mc_finish_order.py`) handles NULL as unavailable.
3. Owner sees the diff; hash baselines re-taken by the owner.

## Done when
No SE column in either mart is 0 where its estimate is missing, every remaining 0-fill is named in `schema.yml` as a prior with its flag, and tests enforce both.

## Sources
`transform/models/marts/fct_ghost_race_finish.sql`, `transform/models/marts/fct_ghost_car_pace.sql`, `transform/models/marts/schema.yml`, `app/src/features/hidden-performance/`, `scripts/mc_finish_order.py`.

## 2026-11-16 (fixall session): SE half done, priors flagged and pending a ruling
- fct_ghost_car_pace.sql: host_constructor_pace_se_s, host/ego_deg_slope_sd_s_per_lap and host/ego_cliff_shift_se_laps are no longer 0-filled (NULL when there is no cell). The point estimates keep the 0 fill, flagged by new host_constructor_pace_is_prior, circuit_interaction_is_prior, host_deg_slope_is_prior and ego_deg_slope_is_prior. Whether that 0 is a declared prior is PENDING an owner ruling.
- fct_ghost_race_finish.sql: lap_pace_sd is no longer 0 for a single-lap scenario. sd_diff is guarded, because DuckDB GREATEST would turn NULL into the 1e-6 floor (near-certainty). finish_pos_se is NULL if any pairwise probability is NULL, with new finish_pos_se_unavailable_reason (SINGLE_DRIVER_SCENARIO, NO_SE_ESTIMATE). The COALESCE(...,0.0) is gone.
- App: hidden-performance shows 'n/a' for a NULL SE and writes an empty CSV cell (vitest pass; tsc clean). scripts/mc_finish_order.py is a simulator over arrays and does not read the mart.
- Scratch diff against TX-15 base (/private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/fix_diff), 2018-2025: finish_pos_se becomes NULL on 8,178 of 30,054 rows (all NO_SE_ESTIMATE, including the 4 that were 0), and moves by more than 0.01 on 354 more (max +0.162, 2018_12 GAS in Williams 0.992 to 1.154). predicted_mean_lap_se_s is NULL on 1,619 rows. p_beats_next is NULL on 2,029 more rows. Lap level: SE fills become NULL on 1,122 (host pace), 77,430 and 77,151 (deg sd), 207,945 and 193,353 (cliff-shift SE) rows. Prior flags: host pace 1,122, host deg 77,430, ego deg 77,151, circuit interaction 0 (its zeros are estimates, not fills).
- Tests: assert_ghost_se_never_zero_filled plus schema tests; 41 of 41 pass on the fix build.
