# AUD-00 — Transform model triage: every model, one tier, one owner decision

**Owner request, 2026-11-18:** make the transform layer as confident as possible with the data we have, model by model. Skim the robust models, put real effort on the ones that need fixing. This doc is the triage. Items AUD-01 to AUD-15 in [`../status/build-log.json`](../status/build-log.json) run it, one item per dependency group, upstream first.

**Read-only.** Nothing here was built or run against data. No dbt build, no dbt compile, no file under `transform/`, `data/` or `app/` changed. Every count below that says "rows" comes from an existing WI doc and is cited; the rest are code reads.

## What the tiers mean

| Tier | Meaning | What its AUD item does |
| :--- | :--- | :--- |
| **ROBUST** | No fill was found that feeds a sum, an SE or a measurement. Only counts, row flags, labels, join keys, or fills that are already NULL-with-reason or already tested. | Skim: confirm the cited tests exist and pass on the TX-15 scratch build. No number changes. |
| **CHECK** | A fill or an inherited fill exists, but its consumers are unclear or the covering test or fix item is not confirmed. | Read-only consumer trace and a count on the TX-15 scratch build. Re-tier to ROBUST or FIX in this doc. |
| **FIX** | A dangerous fill (sum term, SE or measurement) with a known consumer. | Count the fill on the TX-15 scratch build, put the decision to the owner with the count, then (after the ruling only) apply it in scratch and add the test. |

**ROBUST does not mean the numbers are proven right.** It means this pass found no dangerous fill. Method errors that are not fills (the DriverAhead air state, the unvalidated 0.331 tax, the car-FE refit with a different pyfixest version, TX-31's restart labels) are out of this tier's scope and stay with the items that own them.

## How the triage was done

1. **Graph.** Dependencies were parsed from `ref()` calls in the source tree (108 model files), and compared with `transform/target/manifest.json`. See "Stale manifest" below: the tree, not the manifest, is the basis.
2. **Fill sites.** Every `COALESCE`, `IFNULL`, `NVL`, `ELSE 0` and pandas `fillna` in `transform/models/**` was parsed: 448 grep hits in 69 files, of which 395 are in code (53 are in comments). Each code site got its target column, the function wrapping it, and a heuristic class. The class counts in the table come from that parser; the **tier is a manual read** of each risky site in context.
3. **Missed by the grep.** Fills that are not a COALESCE were searched separately (`WHEN x IS NULL THEN 0`, declared SE conventions, CI fallbacks). That search found three the grep misses: `int_lap_residual_decomposed.sql:310-319` (dirty-air tax and SE 0.0 where no dirty-air row), `int_pit_strategy_value.sql:469-491` (opportunity cost 0.0 where the optimum is unknown) and the SE convention in `int_dirty_air_tax_component.sql:354-359`.
4. **Consumers.** dbt children from the graph; external readers by name match in `scripts/export_app_data.py`, `scripts/assistant_query_views.py`, `ml/src/**/*.py` and `app/src/**/*.ts` (tests excluded). For each FIX, the filled column itself was grepped in `app/src` to confirm a page reads it.
5. **Tests.** Generic tests per model from the manifest (`g`, stale for 13 files, see below) and singular tests from `ref()` in `transform/tests/*.sql` (`s`).

**Fill-class legend** (parser, heuristic): `Z` zero into a value or a sum term, `SE` zero into an SE, SD or CI, `K` a non-zero constant default, `C` a count, share or 0/1 inside an aggregate, `F` a boolean or label default, `X` a join key, filter, fallback to another column, or Python.

## Tier counts

**108 models** (102 in the manifest, 6 only in the tree): **78 ROBUST, 9 CHECK, 21 FIX.**

| Item | Group | Models | Group tier | ROBUST / CHECK / FIX |
| :--- | :--- | ---: | :--- | :--- |
| AUD-01 | Staging and reference | 24 | **ROBUST** | 24 / 0 / 0 |
| AUD-02 | Lap spine, fuel, stint regime, SC hazard, pit loss | 10 | **ROBUST** | 10 / 0 / 0 |
| AUD-03 | Telemetry, corners, proximity, air state | 14 | **ROBUST** | 14 / 0 / 0 |
| AUD-04 | New-data marts (not in manifest) | 5 | **ROBUST** | 5 / 0 / 0 |
| AUD-05 | Compound curve, field pace, thermal, synthetic teammate | 4 | **FIX** | 2 / 1 / 1 |
| AUD-06 | Track evolution and its readers | 4 | **FIX** | 3 / 0 / 1 |
| AUD-07 | Constructor structural pace (race) | 1 | **FIX** | 0 / 0 / 1 |
| AUD-08 | Dirty-air tax | 1 | **FIX** | 0 / 0 / 1 |
| AUD-09 | Lap residual identity and lap marts | 8 | **FIX** | 5 / 2 / 1 |
| AUD-10 | Driver ratings, affinities, race and season marts | 8 | **FIX** | 2 / 2 / 4 |
| AUD-11 | Qualifying chain | 6 | **FIX** | 2 / 1 / 3 |
| AUD-12 | Stint features, pit strategy, tyre decoupling | 4 | **FIX** | 1 / 0 / 3 |
| AUD-13 | Ghost chain | 4 | **FIX** | 0 / 1 / 3 |
| AUD-14 | Driver isolation | 8 | **ROBUST** | 8 / 0 / 0 |
| AUD-15 | ML features and the degradation envelope | 7 | **FIX** | 2 / 2 / 3 |

## FIX groups in priority order

Priority is: published and read by a page today, then no existing item owns it, then size.

1. **AUD-09 Lap residual identity.** `int_lap_residual_decomposed` feeds every published lap mart. The constructor term is 0 on filled laps (flagged, not carried: DM-03). Dirty-air tax and its SE are 0.0 where there is no dirty-air row (tested as declared). Rubber and ambient are already NULL + reason in the working tree (TX-30 e). Decision: **HD25**. Fix owner: DM-03.
2. **AUD-11 Qualifying chain (new).** `int_qualifying_decomposed.sql:146` makes a driver with no race skill read as exactly field average, and the quali-vs-race-skill page averages that delta and derives race skill from it. Upstream, `int_lap_residual_decomposed_qualifying` fills constructor pace, its SE and compound wear with 0 and sums them; `int_constructor_structural_pace_qualifying` fills its SE with 0 unconditionally and collapses its CI to the point. DM-06 lists only the quali SE and calls it ML-only; it is not: `int_qualifying_decomposed` is exported and on a page. Decisions: **HD25, HD27**. No item owns it today.
3. **AUD-12 Pit strategy and tyre decoupling (new).** `int_pit_strategy_value` grades a stint whose optimum is unknown as opportunity cost 0.0 (perfect) and confidence 0.0; the pit-strategy page and cards read both. `int_tyre_surface_vs_bulk_decoupling` defaults the surface/bulk ratio to 0.5 (steady push) and the tyre-recovery page reads the ratio, the thermal attribution and the recovery probability built from it. `int_pit_strategy_cost_curve` uses 21 s, 30 C and 20 C defaults and a 0 SC hazard for 2018. Decisions: **HD25, HD26**. No item owns it.
4. **AUD-10 Ratings and affinities (new).** Three models pool the within-cell variance as `AVG(POWER(COALESCE(sd, 0), 2))`: a single-observation cell adds 0 variance, which lowers the pooled sigma2 that sets every posterior SE. The SEs are published (driver-circuit-affinity page, ghost-race-standings reads `shrunk_affinity_se_s`, the era rating SE reaches `mart_driver_season_summary.rating_se_s`). Decision: **HD27**. DM-07 owns only the era-rating SE COALESCE (0 rows today).
5. **AUD-07 Constructor structural pace.** DM-02 covers the SE fill, the centring and the all-wet rows. Not in DM-02: the CI falls back to the point estimate when the SD is missing (`:189-198`), a zero-width interval on a page that draws the CI. Decisions: **HD25, HD27** and the all-wet ruling BUILD-ORDER lists as waiting (it has no decision entry).
6. **AUD-13 Ghost chain.** Owned by TX-18 and DM-05. Adds to their scope: `int_constructor_deg_sensitivity.sql:548` posterior SD 0 when tau2 <= 0, and `int_circuit_x_constructor_interaction.sql:157` SE 0 (no test covers either). Decisions: **HD20** (values), **HD25** (SEs).
7. **AUD-06 Track evolution.** Owned by DM-01. DM-01 says "pick one in the build" for the rubber clamp, which is a logic choice rule 10 gives the owner: raised as **HD28**. Ambient fill: **HD25**.
8. **AUD-05 Compound curve (new).** `int_compound_cliff_predicted.sql:122-123` uses 30 C track temperature and 20 C optimum when either is missing, unflagged. That reaches `compound_component_s`, a term of the lap identity, at 0.005 s per degree (at most 0.15 s). How often it fires is not counted yet; the item counts it first. Decision: **HD26**.
9. **AUD-08 Dirty-air tax (held fix).** The SE is 0.15 x tax by convention, so it is 0 on every clean-air lap, and `assert_dirty_air_se_is_declared_convention` pins that. Under HD25's "no SE filled with 0" the test itself has to change. Fix owner: DM-04, held after AX-20. AUD-08 only counts and records.
10. **AUD-15 ML features (held fix).** DM-06 owns the drift and power-law zeros; TX-09 (XM) owns the isotonic fit behind `mart_degradation_history_envelope`'s three constant defaults, which the degradation-simulator page reads (HD26). AUD-15 only counts and records; it gates DM-06.

## New owner decisions raised

Added to `decisions` as OPEN. HD25 and HD20 are reused where they fit.

- **HD26 — non-zero constant defaults.** 21 s pit loss, 30 C track temperature, 20 C compound optimum, 0.5 surface/bulk ratio, 0.5 s pair SD, and the envelope's 1.0 / 8 C / 0.010 defaults. Same two options as HD25: NULL with a reason, or a declared prior with a flag. Blocks AUD-05, AUD-12.
- **HD27 — zeros inside an uncertainty.** (a) A single-observation cell enters a pooled variance as 0 (three rating models); (b) a CI falls back to the point estimate when the SD is missing (both structural-pace models). Options: (a) leave such cells out of the pool, or keep 0 and say so; (b) NULL CI, or keep it and flag it. Blocks AUD-10 and AUD-11; listed against DM-02 in `blocking`.
- **HD28 — track-evolution rubber clamp.** DM-01 leaves "NULL where clamped" or "raw plus clamped columns" to the builder. Blocks DM-01.

## Findings that change the triage

- **Stale manifest.** `transform/target/manifest.json` is from 2026-11-16 09:46 UTC: 102 models. The tree has 108. Missing: `stg_jolpica_pit_stops`, `fct_pit_stop_crosscheck`, `fct_speed_traps`, `fct_speed_traps_season`, `fct_track_limits`, `fct_track_limits_driver_session`. Seven model files are newer than it: `stg_laps`, `stg_laps_qualifying`, `int_lap_residual_decomposed`, `fct_ghost_car_pace`, `fct_ghost_race_finish`, `fct_stint_features`, `mart_race_coverage`. Two dependency sets differ: `fct_stint_features` now also reads `int_lap_air_state`, and `mart_race_coverage` now also reads `stg_laps`. Manifest checksums differ from the files for every model, so they were not used; the triage uses the tree. Generic-test counts come from the stale manifest.
- **A missing test.** `stg_jolpica_pit_stops` has no model tests (only the source entry in `src_jolpica.yml`).
- **Fills with no test on the filled column.** `int_constructor_structural_pace_qualifying` (SE, CI), `int_lap_residual_decomposed_qualifying` (no singular test refs it), `int_circuit_x_constructor_interaction` (SE), `int_constructor_deg_sensitivity` (posterior SD), the pooled sigma2 in the three rating models, `int_compound_cliff_predicted`'s temperature default, `int_pit_strategy_value`'s opportunity cost, and `int_tyre_surface_vs_bulk_decoupling`'s 0.5 ratio.
- **A test that pins a fill.** `assert_dirty_air_se_is_declared_convention` asserts the 0.15 x tax SE, so SE = 0 on clean-air laps. It is correct for today's convention and has to change with DM-04.
- **A scope error in DM-06.** It calls the quali SE fill "ML only". `int_qualifying_decomposed` is exported and the quali-vs-race-skill page reads it.
- **Orphans.** No dbt child and no export, app or ML reader: `int_lap_normalized_pace` (its 0.004 theta fallback has no reader), `int_track_geometry`, `int_microsector_proximity`, `int_microsector_corner_class`, `int_traffic_exposure_race`, `dim_driver_seasons`, `stg_events`, `stg_session_status`. The four new-data marts are orphans only because their pages (AP-09) are not built. Whether to drop any orphan is the owner's call.

## Existing items: what gates what, and proposals

**Gated by AUD items (new `depends_on`):**
- **TX-30** now depends on AUD-01 to AUD-03 and AUD-05 to AUD-14. TX-30's step k is ONE owner diff review of every mart-level change and ONE re-export decision; the audit's fixes change mart-level numbers, so they belong in that one review. AUD-04 and AUD-15 are left out: the new-data marts are not in the sweep, and ML is held (HD23).
- **AP-09** depends on AUD-04: its pages are built on the new-data marts.
- **DM-06** depends on AUD-15: AUD-15's counts set DM-06's scope.
- DM-01, DM-02, DM-03, DM-05, DM-07 and DM-04 already wait on TX-30, so they wait on the audit through it. No extra link was added.
- **HD28** lists DM-01 in `blocking`. HD27 lists DM-02. DM-01's and DM-02's own `blocked_by_decision` were left unchanged; whether to add them is the owner's call.

**Proposed for the owner (nothing deleted or merged):**
- **Merge DM-07 into AUD-10.** Both touch `int_era_normalized_driver_rating`'s SE; one build, one test.
- **Move the quali SE part of DM-06 into AUD-11.** It reaches a page now, not only ML.
- **Add the CI collapse to DM-02's scope** (HD27 b), or let AUD-07 own it.
- **Fold DM-01, DM-02, DM-03, DM-05 and DM-07 into the TX-30 review.** As planned, they run after TX-30 and each needs its own diff review and re-export, which works against TX-30's "one review, one re-export".
- **TX-30's doc header** still says `opus-5`; the log says `sonnet-5` (rule 10). Doc fix for whoever next edits TX-30.
- **The generated BUILD-ORDER table files every AUD item under "Held or after launch".** `board.py`'s hard-coded `CATEGORIES` does not list the AUD ids; this pass may not edit `board.py` or the hand-written index. Add `AUD-01 ... AUD-14` to category 1 and `AUD-15` to category 5. The position numbers (#) are right either way.

## What this pass did not check, and why

- **No row counts of its own.** Counting needs a built warehouse; this pass may not build one, and the TX-15 scratch build belongs to the agent running TX-15 now. The AUD items count on that build once TX-15 is done.
- **No test was run.** Test pass or fail is taken from the TX-15 note (1,360 pass, 54 fail).
- **Manifest generic-test counts** are stale for the 13 files above.
- **`int_lap_physical_ahead.py`** (Python) was read only at its two `fillna` sites.
- **Macros** (`clamp_or_null`, `bayesian_shrinkage`, `trailing_sum`, `cliff_ramp_slope_s_per_lap`) were not opened. A fill inside a macro would be missed.
- **App and ML consumers** were found by name match, which can miss dynamic reads and can over-count mentions in comments.
- **ml/src fills** (e.g. `powerlaw_ceiling.py:281`) are outside `transform/`; listed under AUD-15 only through DM-06.

## Every model

Sorted by item, then FIX, CHECK, ROBUST, then upstream first. `g/s` = generic/singular tests. Consumers: `N dbt` children, then `export`, `qv` (assistant query views), `ml:` files, `app:` feature folders.

| Model | Item | Tier | Fill sites by class | Consumers | Tests g/s | Decision needed | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `dim_circuits` | AUD-01 | **ROBUST** | 0 | 9 dbt; export; qv; app:cards,constructor-circuit-interaction,degradation-simulator,hidden-performance,query-lab | 7g/4s | — | no fill site in code |
| `dim_compounds_season` | AUD-01 | **ROBUST** | 0 | 5 dbt; export; qv; ml:powerlaw.py; app:cards,degradation-simulator,tyre-cliff-survival | 12g/1s | — | no fill site in code |
| `dim_constructors` | AUD-01 | **ROBUST** | 0 | 2 dbt; export | 4g/1s | — | no fill site in code |
| `dim_driver_seasons` | AUD-01 | **ROBUST** | 0 | no dbt | 5g/0s | — | no fill site in code |
| `stg_circuit_info` | AUD-01 | **ROBUST** | F1 | 1 dbt | 6g/1s | — | :17 corner letter label only |
| `stg_events` | AUD-01 | **ROBUST** | 0 | no dbt | 4g/0s | — | no fill site in code |
| `stg_jolpica_pit_stops` (not in manifest) | AUD-01 | **ROBUST** | 0 | 1 dbt | 0g/0s | — | no fill site; NO model tests (only src_jolpica.yml source entry) - add not_null/unique in AUD-01 |
| `stg_laps` | AUD-01 | **ROBUST** | F1 | 32 dbt | 15g/16s | — (TX-31 owns the restart-label defect, not a fill) | :95 is_pit_lap boolean only; 15 generic + 16 singular tests; edited after manifest |
| `stg_laps_qualifying` | AUD-01 | **ROBUST** | F1 | 8 dbt | 14g/4s | — | :95 is_pit_lap boolean only; edited after manifest |
| `stg_pits` | AUD-01 | **ROBUST** | 0 | 6 dbt; export; app:cards | 6g/6s | — | no fill site in code |
| `stg_results` | AUD-01 | **ROBUST** | 0 | 7 dbt; export; app:cards | 11g/6s | — | no fill site in code |
| `stg_results_qualifying` | AUD-01 | **ROBUST** | 0 | 1 dbt | 9g/1s | — | no fill site in code |
| `stg_session_status` | AUD-01 | **ROBUST** | 0 | no dbt | 8g/0s | — | no fill site in code |
| `stg_session_status_qualifying` | AUD-01 | **ROBUST** | 0 | 1 dbt | 8g/0s | — | no fill site in code |
| `stg_telemetry` | AUD-01 | **ROBUST** | X1 | 2 dbt; export; ml:schema.py | 11g/1s | — (HD16 via TX-20) | :98 6,500 m floor in a WHERE (filter, not a value); assert_stg_telemetry_distance_bound |
| `stg_telemetry_position` | AUD-01 | **ROBUST** | 0 | 3 dbt | 8g/1s | — | no fill site in code |
| `stg_track_status` | AUD-01 | **ROBUST** | 0 | 3 dbt; export; app:race-control | 7g/2s | — | no fill site in code |
| `stg_tyre_allocations` | AUD-01 | **ROBUST** | 0 | 1 dbt | 10g/1s | — | no fill site in code |
| `dim_corners` | AUD-01 | **ROBUST** | Z1 F3 X2 | 2 dbt | 13g/1s | — | :62-171 corner-letter labels and apex-window geometry fallback; 13 generic tests, assert_corner_window_geometry |
| `dim_drivers` | AUD-01 | **ROBUST** | 0 | 2 dbt; export; app:hooks | 2g/0s | — | no fill site in code |
| `stg_lap_tyre_qa` | AUD-01 | **ROBUST** | K2 C4 F7 | 4 dbt | 6g/3s | — | flags, counts, -1 sentinels only (:67-343); assert_pit_ended_stints_have_stop, assert_stint_boundaries_match_pits |
| `stg_race_control` | AUD-01 | **ROBUST** | F1 | 1 dbt | 7g/3s | — | :98 flag = 'BLUE' label compare only |
| `stg_sector_times` | AUD-01 | **ROBUST** | 0 | 2 dbt | 6g/0s | — | no fill site in code |
| `stg_weather` | AUD-01 | **ROBUST** | Z3 C1 F2 | 3 dbt; ml:schema.py | 5g/5s | — | :137-172 rain votes and wet-tyre share (a ratio of a CASE), :206 flag; assert_rain_flag_matches_tyres |
| `int_constructor_car_fe` | AUD-02 | **ROBUST** | 0 | 1 dbt | 8g/0s | — (TX-15 note: car-FE fits refitted with pyfixest 0.60; not a fill) | no fill site; reads source fits |
| `int_constructor_car_fe_isolation` | AUD-02 | **ROBUST** | 0 | 1 dbt | 11g/0s | — (TX-15 note: car-FE fits refitted with pyfixest 0.60; not a fill) | no fill site; reads source fits |
| `int_track_geometry` | AUD-02 | **ROBUST** | 0 | no dbt | 4g/0s | — (orphan: no dbt, export, app or ml reader) | no fill site |
| `int_event_corrections` | AUD-02 | **ROBUST** | F5 X2 | 8 dbt; qv | 9g/1s | — | :107-122 FALSE defaults on restart/yellow flags, :190-192 manual-exception fallback |
| `int_lap_fuel_state_qualifying` | AUD-02 | **ROBUST** | 0 | 1 dbt | 9g/0s | — | no fill site |
| `int_pit_loss_circuit` | AUD-02 | **ROBUST** | X1 | 2 dbt | 9g/1s | — | :79 circuit_id key fallback only; assert_pit_loss_excludes_neutralised |
| `int_sc_hazard_history` | AUD-02 | **ROBUST** | Z12 C4 | 2 dbt; export; qv; ml:features.py; app:race-control | 17g/2s | — | :192-237 prior counts 0 are facts (comment :185-191); rates stay NULL via NULLIF; assert_sc_hazard_no_forward_leakage, assert_sc_hazard_probability_bounds |
| `int_stint_geometry` | AUD-02 | **ROBUST** | F1 | 20 dbt; export; ml:features.py,flag_chance.py,schema.py; app:lap-waterfall,race-control,race-lost | 15g/19s | — (TX-30 g owns race_to_track 2026) | :156 joins_previous flag only; 15 generic + 19 singular tests |
| `int_lap_fuel_state` | AUD-02 | **ROBUST** | 0 | 11 dbt; ml:flag_chance.py | 5g/7s | — | no fill site; assert_fuel_curve_monotonicity, assert_fuel_load_matches_scheduled_distance |
| `int_stint_end_regime` | AUD-02 | **ROBUST** | K1 F6 | 3 dbt; ml:features.py,flag_chance.py; app:pit-strategy | 24g/4s | — | :117-118 -1 sentinel, :194-202 status labels, :272 censored defaults TRUE (conservative); assert_stint_end_cause_partition, assert_stint_censoring_partition |
| `int_microsector_crossings` | AUD-03 | **ROBUST** | 0 | 1 dbt | 7g/2s | — | no fill site in code |
| `int_corner_metrics` | AUD-03 | **ROBUST** | 0 | 2 dbt; export | 10g/2s | — | no fill site in code |
| `int_microsector_corner_class` | AUD-03 | **ROBUST** | Z1 F4 X1 | no dbt | 10g/2s | — (orphan) | :201 apex speed borrowed from neighbour and flagged apex_speed_borrowed (:285) |
| `fct_telemetry_deltas` | AUD-03 | **ROBUST** | X6 | no dbt; export; qv | 8g/2s | — | :82-98 FULL OUTER JOIN key coalesce only; assert_telemetry_deltas_null_when_side_missing |
| `int_corner_skill_residuals` | AUD-03 | **ROBUST** | 0 | 3 dbt; export; ml:features.py | 6g/4s | — | no fill site in code |
| `int_lap_air_state` | AUD-03 | **ROBUST** | Z6 SE1 C1 F2 | 9 dbt; export; app:cards,dirty-air-lap-map,pit-strategy | 5g/7s | — (AX-24 / DM-04 own the DriverAhead method; not a fill) | :343-366 0.0/free_air only for the leader or a measured lap; unmeasured = NULL (FD6); assert_air_state_unmeasured_is_null |
| `int_lap_physical_ahead` | AUD-03 | **ROBUST** | X3 | 1 dbt | 10g/6s | — | py :238 last-sample dt 0, :343 int counts; assert_physical_ahead_unknown_never_clear_air |
| `int_lap_proximity` | AUD-03 | **ROBUST** | Z7 K1 C6 X1 | 1 dbt; ml:schema.py; app:dirty-air-lap-map | 9g/5s | — | :455-495 0.0 only inside a MEASURED lap (proximity_bin_count NOT NULL); unmeasured = NULL (CO-21 comment :441-449); assert_proximity_train_subset_of_within1s |
| `int_microsector_proximity` | AUD-03 | **ROBUST** | F7 X1 | no dbt | 14g/5s | — (orphan) | :127 pit-out time fallback, :264-321 SC flags and timing-reason labels; assert_microsector_validity_rules |
| `int_corner_drift_from_early_stint` | AUD-03 | **ROBUST** | 0 | 1 dbt | 7g/0s | — | no fill site in code |
| `int_lap_corner_inputs` | AUD-03 | **ROBUST** | 0 | 1 dbt | 8g/1s | — | no fill site in code |
| `int_traffic_exposure_driver_race` | AUD-03 | **ROBUST** | 0 | 1 dbt | 3g/1s | — | no fill site in code |
| `int_lap_corner_drift` | AUD-03 | **ROBUST** | 0 | 1 dbt | 8g/0s | — | no fill site in code |
| `int_traffic_exposure_race` | AUD-03 | **ROBUST** | 0 | no dbt | 2g/0s | — (orphan) | no fill site |
| `fct_pit_stop_crosscheck` (not in manifest) | AUD-04 | **ROBUST** | Z2 F2 X3 | no dbt | 0g/0s | — (TX-27 owns the cross-check) | :57-59 key fallback, :79 n_stops compare; not in manifest; yml tests on crosscheck_id/status only |
| `fct_speed_traps` (not in manifest) | AUD-04 | **ROBUST** | 0 | no dbt | 0g/1s | — | no fill site; assert_speed_traps_missing_not_zero; not in manifest |
| `fct_speed_traps_season` (not in manifest) | AUD-04 | **ROBUST** | 0 | no dbt | 0g/1s | — | no fill site; assert_speed_traps_missing_not_zero; not in manifest |
| `fct_track_limits` (not in manifest) | AUD-04 | **ROBUST** | 0 | 1 dbt | 0g/1s | — | no fill site; assert_track_limits_reconcile; not in manifest |
| `fct_track_limits_driver_session` (not in manifest) | AUD-04 | **ROBUST** | C2 | no dbt | 0g/1s | — | :51-53 counts 0 only when has_deletion_data, else NULL; not in manifest |
| `int_compound_cliff_predicted` | AUD-05 | **FIX** | Z3 K4 | 8 dbt; export; ml:powerlaw.py,card.py,schema.py | 5g/9s | HD26 | :122-123 track_temp_c 30.0 and optimal_temp_low 20.0 defaults, unflagged, feed ambient_temp_delta -> expected_compound_pace_s (:232) -> compound_component_s, a term of the lap identity; compound-param fills (:136-141, :254) guarded by assert_compound_params_cover_mart |
| `int_synthetic_teammate` | AUD-05 | **CHECK** | K1 | 1 dbt; export; app:synthetic-teammate | 6g/1s | HD26 candidate | :161 pair-weight SD defaults to 0.5 on a pair's first lap; page synthetic-teammate reads pair_quality_weight; assert_synthetic_teammate_identity does not cover it |
| `int_field_pace_curve` | AUD-05 | **ROBUST** | C1 F8 | 6 dbt; export; ml:powerlaw.py,features.py; app:field-pace-curve | 8g/8s | — (TX-31 related: SC flags default FALSE) | :96-130 SC/VSC/red flags default FALSE, :149 count; assert_field_pace_honest_range and 7 more singular tests |
| `int_lap_thermal_proxy` | AUD-05 | **ROBUST** | Z11 | 3 dbt; ml:card.py,schema.py | 4g/3s | — | :146-162 prior-lap NULL push residual contributes 0 (declared window convention, comment :133-137); current-lap NULL stays NULL; assert_thermal_variance_positive |
| `int_track_evolution` | AUD-06 | **FIX** | Z2 | 7 dbt; export; app:cards,track-evolution | 5g/2s | HD25 (ambient), HD28 (rubber clamp); fix owned by DM-01 | :156-163 ambient_component_s and unexplained_residual_s COALESCE 0 (fires where slope or track_temp_c is NULL); rubber clamp at :80-90; published on track-evolution page |
| `int_driver_race_paired_laps` | AUD-06 | **ROBUST** | F1 X1 | 2 dbt | 8g/1s | — | :76-77 filter and flag only |
| `int_lap_normalized_pace` | AUD-06 | **ROBUST** | K1 F1 X1 | no dbt | 6g/0s | — (orphan: theta fallback 0.004 has no reader) | :155 theta_time fallback 0.004; no dbt, export, app or ml consumer |
| `mart_corner_skill_driver` | AUD-06 | **ROBUST** | Z3 F1 X1 | no dbt; export; app:cards,corner-phase-skill,query-lab | 25g/3s | — | :153-165 leave-one-out sum minus 0 when the driver has no row (correct arithmetic); SEs use NULLIF (:268-272); 25 generic tests |
| `int_constructor_structural_pace` | AUD-07 | **FIX** | SE1 F1 X3 | 4 dbt; export; app:constructor-structural-pace,degradation-simulator,party-mode | 17g/2s | HD25 (SE), HD27 (CI collapse), DM-02 all-wet ruling; fix owned by DM-02/DM-07 | :184-188 SE COALESCE 0 when SD is NULL (single obs); :189-198 CI falls back to the point estimate (zero-width CI) - not in DM-02 scope; published on constructor-structural-pace page (reads SE and CI) |
| `int_dirty_air_tax_component` | AUD-08 | **FIX** | F2 X1 | 6 dbt; export; ml:schema.py; app:cards,dirty-air-cost | 8g/10s | HD25 (SE); fix owned by DM-04 (held after AX-20) | SE = 0.15 x tax by convention (:354-359), so SE 0 on clean-air laps; assert_dirty_air_se_is_declared_convention PINS that convention and must change with DM-04; :308-309 filters, :394 flag |
| `int_lap_residual_decomposed` | AUD-09 | **FIX** | Z2 F2 | 14 dbt; ml:powerlaw_ceiling.py; app:lap-waterfall | 7g/16s | HD25; fix owned by DM-03 | :286 constructor_component_s COALESCE 0 (flagged constructor_pace_is_filled :290); :310-319 dirty_air_tax_s and its SE 0.0 where no dirty-air row (assert_dirty_air_fill_only_where_base_unmeasured); :316 tax confidence 0; rubber/ambient now NULL + reason in the working tree (TX-30 e) |
| `fct_lap_residuals` | AUD-09 | **CHECK** | 0 | 5 dbt; export; qv; ml:features.py; app:cards,constructor-team-averages,lap-waterfall,pit-strategy,race-lost | 22g/6s | inherits HD25 (DM-03) | no own fill; carries constructor_component_s without constructor_pace_is_filled (DM-03); assert_lap_7term_identity, assert_residual_decomposition_identity |
| `mart_metric_benchmark` | AUD-09 | **CHECK** | 0 | no dbt; export; app:cards | 9g/2s | inherits HD25 (DM-03) | no own fill; aggregates the constructor term (DM-03 cites :35) |
| `int_lap_anomaly_flags` | AUD-09 | **ROBUST** | Z2 F3 | 5 dbt; export; app:data-quality-audit | 9g/1s | — | :131,:143 z and MAD score 0 only when the spread is 0 (z is traceability only; assert_mad_floor keeps MAD > 0); :216-257 rain flags |
| `int_sector_residual_decomposed` | AUD-09 | **ROBUST** | 0 | no dbt; export; app:sector-decomposition | 8g/2s | — | fill site is in a comment only; assert_sector_residual_identity, assert_sector_aggregates_to_lap |
| `fct_driver_skill_features` | AUD-09 | **ROBUST** | Z1 F2 | no dbt; export; app:cards,driver-consistency,query-lab,wet-race-specialist | 6g/0s | — | :213 strategic_divergence_share 0 with teammate_available_flag (:212); no app page reads the share (grep) |
| `int_lap_telemetry_aggregates` | AUD-09 | **ROBUST** | C1 F8 | 2 dbt; ml:schema.py | 7g/0s | — | :93-163 per-sample 0/1 indicators and an AVG share |
| `mart_build_provenance` | AUD-09 | **ROBUST** | 0 | no dbt; export; app:cards | 15g/1s | — | no fill site; assert_build_provenance_one_row_matches_vars |
| `int_driver_circuit_affinity` | AUD-10 | **FIX** | C1 X1 | no dbt; export; app:driver-circuit-affinity | 19g/2s | HD27 | :111 same pooled-sigma2 fill; shrunk_affinity_se_s (:169) published on driver-circuit-affinity page |
| `int_driver_circuit_era_affinity` | AUD-10 | **FIX** | C1 X1 | no dbt; export; app:ghost-race-standings,hidden-performance | 20g/3s | HD27 | :141 same pooled-sigma2 fill; shrunk_affinity_se_s read by ghost-race-standings |
| `int_driver_season_ratings` | AUD-10 | **FIX** | C1 | 1 dbt | 12g/2s | HD27 | :66 AVG(POWER(COALESCE(residual_stddev_s,0),2)) puts 0 variance for single-race cells into the pooled sigma2 that sets the posterior SE (:121) |
| `int_era_normalized_driver_rating` | AUD-10 | **FIX** | SE1 C2 | 1 dbt; export; app:cards,era-ratings-timeline,era-translator,hidden-performance | 16g/3s | HD27; SE fill owned by DM-07 | :156 era_adjusted_rating_se_s COALESCE 0 (0 rows today, DM-07); inherits the sigma2 fill; published (era pages, mart_driver_season_summary.rating_se_s) |
| `mart_race_driver_summary` | AUD-10 | **CHECK** | C1 F1 | 1 dbt; export; qv; app:cards | 25g/7s | inherits HD25 (DM-03) | :189 has_dnf flag, :205 count; aggregates the constructor term (DM-03 cites :46) |
| `mart_driver_season_summary` | AUD-10 | **CHECK** | C2 | no dbt; export; app:cards | 25g/4s | inherits HD25, HD27 (DM-03, DM-07) | :173-174 counts; carries rating_se_s from the era rating (:88) |
| `int_driver_race_skill_loro` | AUD-10 | **ROBUST** | C1 F1 X1 | 5 dbt; export; ml:schema.py; app:ghost-race-standings | 9g/3s | — | :155-156 filters, :236 count |
| `mart_race_coverage` | AUD-10 | **ROBUST** | C9 F1 | 1 dbt; export; app:cards,data-quality-audit | 13g/1s | — | :60-86 coverage shares, :109-124 counts; 13 generic tests, assert_every_lap_race_rated_or_explained |
| `int_constructor_structural_pace_qualifying` | AUD-11 | **FIX** | SE1 X2 | 1 dbt; export; app:constructor-structural-pace,party-mode | 3g/0s | HD25 (SE), HD27 (CI collapse) | :139-142 SE COALESCE 0 unconditionally (not gated like the race model); :143-152 CI falls back to the point; published on constructor-structural-pace page; 3 generic tests, no SE test |
| `int_lap_residual_decomposed_qualifying` | AUD-11 | **FIX** | Z14 SE1 X2 | 1 dbt | 4g/0s | HD25 (DM-06 lists only the SE, as ML-only) | :122 constructor pace 0 with no flag, :124 SE 0, :131 compound wear 0; :166-180 total_explained and residual are sums of COALESCE(...,0) terms; feeds the exported int_qualifying_decomposed |
| `int_qualifying_decomposed` | AUD-11 | **FIX** | Z1 F1 | 1 dbt; export; ml:schema.py; app:quali-vs-race-skill | 4g/1s | HD25 | :146 quali_vs_race_skill_delta_s = quali - COALESCE(race skill, 0): no race skill reads as exactly field average; quali-vs-race-skill page averages it and derives race_skill_s from it |
| `int_qualifying_driver_summary` | AUD-11 | **CHECK** | 0 | 1 dbt; ml:schema.py | 7g/0s | inherits HD25 | fill site in comment only; aggregates the filled quali residual; ML reader (schema.py) |
| `int_qualifying_segments` | AUD-11 | **ROBUST** | X7 | 1 dbt | 9g/0s | — | :149-321 time-anchor fallbacks in joins; assert_quali_segment_matches_official |
| `int_qualifying_push_laps` | AUD-11 | **ROBUST** | F2 | 2 dbt | 9g/1s | — | :60 segment label 'Q' when unknown, :123 is_push_lap flag |
| `int_pit_strategy_cost_curve` | AUD-12 | **FIX** | Z3 K6 X1 | 1 dbt | 16g/2s | HD25 (sc hazard 0), HD26 (21 s, 30 C defaults) | :232,:257 pit loss 21.0 default, :262 sc_hazard 0 for 2018 (documented), :355-356 wear 0 where no curve row, :367-376 temp 30/20 defaults inside the compound offset |
| `int_pit_strategy_value` | AUD-12 | **FIX** | Z1 K4 C1 F3 X6 | 2 dbt; export; qv; app:cards,pit-strategy | 13g/2s | HD25 | :469-470,:490-491 opportunity_cost_s 0.0 where the optimum is unknown (graded as perfect), :475 confidence 0; :479-481 21 s pit loss is flagged pit_loss_imputed_flag; pit-strategy page and cards read both |
| `int_tyre_surface_vs_bulk_decoupling` | AUD-12 | **FIX** | Z3 K4 | no dbt; export; app:tyre-recovery-forecast | 9g/1s | HD26 | :78-79 push loads 0, :125-166 surface_bulk_ratio 0.5 default (steady push) feeds degradation_source, thermal_attribution_s and recovery_probability; tyre-recovery-forecast page reads all three |
| `fct_stint_features` | AUD-12 | **ROBUST** | C2 F1 | no dbt; export; qv; ml:features.py,evaluate.py,schema.py; app:blind-test-scoreboard,pit-strategy,query-lab | 23g/2s | — (TX-17 MEASURED: NULL + reason in the working tree) | :114 share, :248 count, :251 reason; assert_stint_dirty_air_null_when_unmeasured |
| `int_circuit_x_constructor_interaction` | AUD-13 | **FIX** | Z1 SE1 C1 X1 | 1 dbt; export; ml:card.py; app:constructor-circuit-interaction | 3g/0s | HD20 (value), HD25 (SE); fix owned by DM-05 | :155 interaction 0 and :157 SE 0 (DM-05: 545 of 1,634 filled, SE 0 on 885); published on constructor-circuit-interaction page; 3 generic tests, no SE test |
| `int_constructor_deg_sensitivity` | AUD-13 | **FIX** | Z9 SE1 C6 F4 | 1 dbt | 27g/3s | HD20 (slopes), HD25 (posterior SD); fix owned by DM-05 | :509-539 deg slope and hinge 0 for low-sample cells (flagged is_low_sample), :548 posterior SD 0 when tau2 <= 0, :568 cliff shift 0 (flagged is_low_sample_cliff) |
| `fct_ghost_car_pace` | AUD-13 | **FIX** | Z41 SE1 K4 C4 F1 X3 | 1 dbt; export; app:cards,duckdb | 23g/3s | HD20; owned by TX-18 / DM-05 | :210-244 pace, interaction and slope 0 (flagged *_is_prior), :298 cliff severity 0, :374-407 predicted lap time is a sum of COALESCE(...,0) terms; assert_ghost_se_never_zero_filled, assert_ghost_recombination |
| `fct_ghost_race_finish` | AUD-13 | **CHECK** | Z1 F1 | no dbt; export; qv; app:cards,counterfactual-championship,hidden-performance,query-lab | 14g/3s | inherits HD20 | own SE fill removed by TX-18 (NULL + reason); :164 DNF flag; inherits ghost-car prior fills |
| `int_driver_isolation_lap_panel` | AUD-14 | **ROBUST** | C2 F3 | 1 dbt; app:cards | 32g/5s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `int_driver_isolation_lap_pace` | AUD-14 | **ROBUST** | F1 | 2 dbt | 19g/0s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `int_driver_isolation_stint_tyre` | AUD-14 | **ROBUST** | C1 | 3 dbt | 15g/0s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `int_driver_isolation_lap_values` | AUD-14 | **ROBUST** | 0 | 2 dbt | 19g/0s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `fct_driver_isolation_pair_lap` | AUD-14 | **ROBUST** | 0 | 3 dbt | 25g/2s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `fct_driver_isolation_lap` | AUD-14 | **ROBUST** | C2 | 2 dbt | 27g/4s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `fct_driver_isolation_race` | AUD-14 | **ROBUST** | C3 | no dbt; export; app:cards | 19g/2s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `fct_driver_isolation_stint` | AUD-14 | **ROBUST** | C3 | no dbt; export; app:cards | 22g/2s | — | counts, coverage shares, labels and FALSE flags only; assert_isolation_small_sample_nulls and 13 more isolation tests |
| `int_lap_residual_stint_detrend` | AUD-15 | **FIX** | Z2 | 1 dbt | 3g/1s | HD25; fix owned by DM-06 (held, HD23) | :29-30 drift_s_per_lap 0 where the slope is undefined (580 of 7,989 stints per DM-06) |
| `mart_degradation_history_envelope` | AUD-15 | **FIX** | K3 X1 | no dbt; export; ml:powerlaw.py; app:degradation-simulator | 24g/1s | HD26; held behind TX-09 (XM) | :151-153 dirty_air_deg_mult 1.0, temp_headroom_c 8.0, temp_penalty 0.010 defaults where the isotonic fit has no cell; degradation-simulator page reads them; not built on TX-15 (no isotonic file) |
| `fct_cliff_prediction_features` | AUD-15 | **FIX** | Z8 K1 C1 F4 | 1 dbt; export; ml:intervals.py,features.py,holdout_config.py,schema.py; app:app/src/ml/verifyParity.ts,blind-test-scoreboard,cards,degradation-simulator,dirty-air-cost | 12g/7s | HD25; fix owned by DM-06 (held, HD23) | :552 copies drift 0; :439,:457 coverage 0 is a measured zero (comment); :564 survival weight 1.0 neutral (assert_survival_weight_neutral_without_prior_curve); exported, read by ML |
| `int_power_law_lap` | AUD-15 | **CHECK** | X1 | 3 dbt; ml:powerlaw_ceiling.py,powerlaw_fit.py | 12g/3s | inherits HD25 (DM-06) | :67 filter only; DM-06 says the power-law constructor_pace_s is 0 on 1,594 laps (filled in ml/src/powerlaw.py) |
| `fct_power_law_training` | AUD-15 | **CHECK** | 0 | no dbt; export; ml:powerlaw.py; app:degradation-simulator | 13g/1s | inherits HD25 (DM-06) | no own fill; joins the ML features above |
| `int_cell_power_law_fit` | AUD-15 | **ROBUST** | 0 | 1 dbt; ml:powerlaw_fit.py | 8g/2s | — | no fill site |
| `int_stint_power_law_fit` | AUD-15 | **ROBUST** | 0 | no dbt; ml:powerlaw_fit.py | 5g/2s | — | no fill site |
