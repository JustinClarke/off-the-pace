# TX-30 — Transform honesty sweep: one scratch rebuild, one diff review

**Group:** 0a-bronze-honesty · **Depends on:** TX-15, TX-16, TX-17, TX-18, TX-19, TX-20, TX-21, TX-22 (the items it absorbs) · **Model / cost:** `opus-5`, about 3d in all (absorbed items included) · **Blocker:** none of its own; it lands only after HD16 is confirmed, through TX-20

**Why one item:** the owner, 2026-11-16: "place them into items after we fix the transform layer but before ai work". Every honesty fix below moves published numbers, and each one was going to be built, diffed and reviewed on its own. TX-30 makes them one sweep: one scratch rebuild on the 2026-11-16 Bronze as the baseline, every fix measured against it, and ONE owner diff review of all mart-level changes with ONE re-export decision at the end.

**Where it sits:** after the transform layer is fixed and before any new-data or AI work. TX-23..TX-28 (new-data marts and raw channels), AP-09 and AX-28 (new-data pages and cards) and the assistant items AX-10, AX-12, AX-13, AX-14 all wait on TX-30. TX-29 (holdout 2025) and TX-09 (degradation refit, blocked on XM) stay separate; see the end.

**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/`, `data/fits/` or `app/public/data/`. No ingest, `bronze-lock`/`bronze-unlock`, real-warehouse build or export without the owner. Agents never stage or commit.

**How the board tracks it:** the absorbed items keep their own ids, docs and stages; TX-30 depends on all of them, so it becomes runnable only when they are done, and it then carries the three new steps (e, g, i) and the closing review (k). The pointer goes to step a (TX-15).

## Sub-steps, in order

| Step | Item | What | Model, cost | State on 2026-11-16 |
| :--- | :--- | :--- | :--- | :--- |
| a | TX-15 | Scratch rebuild on the 2026-11-16 Bronze; diff against the Nov-8 export (manifest e5b324bf3e6d07a6). This is the baseline every later step measures against. | sonnet-5, 1d | SPEC, runnable now |
| b | TX-16 | 2018 Italian GP (2018_14): recorded gap, shown as unavailable with the reason (HD15 resolved as B; the re-ingest failed). | sonnet-5, 0.5d | SPEC |
| c | TX-17 | `fct_stint_features.sql:226`: unmeasured stint dirty-air tax becomes NULL with a reason, not 0. | opus-5, 1d | SPEC |
| d | TX-18 | Ghost marts (`fct_ghost_car_pace.sql:206-221`, `fct_ghost_race_finish.sql:334`): a declared field-average prior is flagged, a missing value is NULL; no SE is filled with 0. | opus-5, 1d | SPEC |
| e | (new, in TX-30) | Lap-residual zero-fills in `int_lap_residual_decomposed.sql` (see below). | opus-5, 0.5d | not started |
| f | TX-19, TX-20 | Spa clip: per-circuit bound. The fix is already in the working tree; the sweep VERIFIES it, it does not redo it. | sonnet-5 / opus-5, verify only | MEASURED; TX-20 waits on HD16 |
| g | (new, in TX-30) | 2026 missing from `race_to_track` (see below). | sonnet-5, 0.25d | not started |
| h | TX-21 | Doc fixes (track-status codes, 2018 R Bahrain, 2024 race-control clock). Done; re-verified below. | sonnet-5, 0.25d | MEASURED |
| i | (new, in TX-30) | Stale docs and baselines (see below). | sonnet-5, 0.25d | not started |
| j | TX-22 | Ingest manifest coverage. Ingest-side, offline code and tests; can run at any time inside the sweep. | sonnet-5, 0.5-1d | SPEC, runnable now |
| k | (TX-30 close) | ONE owner diff review of every mart-level change against the step-a baseline, and ONE re-export decision (watch AXW14). | owner | not started |

### e. Lap-residual zero-fills (new)
`transform/models/intermediate/int_lap_residual_decomposed.sql`:
- lines 254-255: `COALESCE(e.rubber_component_s, 0.0)` and `COALESCE(e.ambient_component_s, 0.0)` ("NULL for low-sample laps, filled 0 to preserve row");
- lines 278-281: `COALESCE(cs.constructor_structural_pace_s, 0.0)` and `COALESCE(cs.constructor_structural_pace_se_s, 0.0)` (all-wet races and constructors with no dry clean lap; the comment explains the term cancels from ML labels but not from residual levels).

Numbers, re-checked read-only on 2026-11-16 against the published Nov-8 `app/public/data/facts/fct_lap_residuals` (161,040 laps): rubber = 0 on 47,558 (29.5%), ambient = 0 on 11,605, constructor pace and SE both 0 on 7,757 (4.8%). These match the audit. An exact 0 can also be a genuine value, so the first job of this step is to re-count on the step-a build and split filled from genuine (join to `int_track_evolution` and `int_constructor_structural_pace` row presence).

Decide per column and record the ruling in this doc: (1) NULL with a reason column, or (2) a declared prior (0 or field value) with a `*_filled` flag. An SE is never filled with 0 under either choice. Check every consumer before choosing NULL: `ml/src/powerlaw_ceiling.py:281` already COALESCEs rubber to 0, and the residual identity must still sum. Recommendation (not a ruling): rubber and ambient keep 0 as a declared prior with a flag (the identity needs a value; the track-evolution term is small on low-sample laps); constructor pace keeps 0 with a flag; constructor SE becomes NULL.

### f. Spa clip (verify, do not redo)
Working tree: `transform/models/staging/stg_telemetry.sql` (circuit_bound CTE: published lap length x 1.10, floored at 6,500 m) and the new test `transform/tests/assert_stg_telemetry_distance_bound.sql`. Verify on the step-a build: the test passes, rows move only in the 9 Spa race_ids (+10 to +11%), runaway laps stay excluded, and the downstream corner marts (`int_corner_metrics`, `int_lap_telemetry_aggregates`, `mart_corner_skill_driver`) are in the step-k diff. Also check `int_microsector_corner_class.sql:23`, which still describes the 6,500 m clip.

HD16: the owner's instruction on 2026-11-16 was "fix all the spa laps" (as relayed by the orchestrator), read as option A, the per-circuit bound. This is the owner's instruction, not a formal ruling. HD16 stays OPEN until the owner confirms A at the step-k review.

### g. 2026 and race_to_track (new)
In the TX-20 scratch build the relationships test `stg_telemetry.race_id -> race_to_track` failed for 14,625,196 rows: all 19 2026 race_ids are missing. `race_to_track` is a seed (`transform/seeds/race_to_track.csv`, 173 rows, 2018-2025). Finding to verify: **the seed is wrong, not the test.** 2026 is in Bronze and staging, and `int_stint_geometry.sql:56` and `int_lap_fuel_state.sql:52` join the seed, so 2026 laps silently lose their track. Fix: add the 2026 rows to the seed (track ids from the Bronze schedule). This does not make 2026 usable: HD17 says 2026 is not yet defined for use (no pages, no fits), and TX-29's guard test keeps it out of fits. If the owner would rather keep 2026 out of the transform entirely, the alternative is a season filter in staging, and the test stays as it is either way.

### h. TX-21 doc fixes, re-verified 2026-11-16 (read-only)
- `transform/models/staging/src_formula1.yml:82` and `ingestion/SCHEMA.md:92`: 5=red, 6=VSC deployed, 7=VSC ending, matching `stg_laps.sql:121-126`. Correct.
- `ingestion/known_gaps.txt:8-12`: names 2018 R australian_grand_prix (pos data) and 2018 R bahrain_grand_prix (car and pos data). Correct.
- `ingestion/SCHEMA.md:217` and `:248`: session_time_s is time of day (UTC), filled for 2024; use session_time_corrected_s (null only for 69 rows, 2018 Bahrain R). Consistent with the TX-21 note.
TX-21 can be promoted to LANDED by the orchestrator once the owner has seen the diff.

### i. Stale docs and baselines (new)
- `docs/reference/models/stg/stg_telemetry.mdx` lines 11 and 42 still say samples are filtered to 0-6,500 m. Update after step f is verified.
- `transform/tests/model_hashes.baseline.json` and `transform/tests/model_hashes.ci.baseline.json`: re-take ONLY after the owner accepts the step-k diff (as in TX-14), never before, so the baseline records the accepted state.

### k. Close
One evidence folder, `_evidence/tx-30-honesty-sweep/`, holding: the step-a parity report, then per step the rows and columns that move against it, then one combined mart-level diff (rows per mart, columns changed, top movers, races dropped or added). The owner reads it once and rules: accept or not, HD16 confirmed or not, and whether to re-export (AXW14). No re-export, CDN publish or commit happens inside TX-30.

## Done when
All absorbed items are LANDED (or recorded as verified), steps e, g and i are done in the working tree with their rulings written here, the combined diff is in `_evidence/tx-30-honesty-sweep/`, and the owner has recorded the step-k review. Model hash baselines are re-taken after that review.

## Stays separate
- **TX-29** (holdout 2025, HD17): a ruling-driven change, not part of the sweep. It does not wait on TX-30: the sweep changes no fit code and no fit window, and the transform fits TX-29 edits read `int_stint_geometry`, `int_lap_fuel_state`, `int_track_evolution`, `int_field_pace_curve` and `int_microsector_proximity`, none of which the sweep changes except the 2026 seed rows that TX-29's 2018-2024 window excludes. ML refits stay owner steps (PK1/XM).
- **TX-09** (degradation isotonic refit, BLOCKED on XM): does not block the sweep. Whether it blocks the assistant is an open question for the owner (HD19).

## Sources
`transform/models/intermediate/int_lap_residual_decomposed.sql`, `transform/models/marts/fct_stint_features.sql`, `transform/models/marts/fct_ghost_car_pace.sql`, `transform/models/marts/fct_ghost_race_finish.sql`, `transform/models/staging/stg_telemetry.sql`, `transform/tests/assert_stg_telemetry_distance_bound.sql`, `transform/seeds/race_to_track.csv`, `docs/reference/models/stg/stg_telemetry.mdx`, `transform/tests/model_hashes.baseline.json`, `app/public/data/_manifest.json`.


## Dependency-map fix steps (DM-01 to DM-07)

Board items DM-01..DM-07 (status/build-log.json) track the zero-fill fixes from the dependency report. They run after this sweep, in order, except DM-04 and DM-06 which are held after AX-20 (HD23). Each item below: problem, fix, test, whether published numbers change, dependency. DM-04 and DM-06 are also referenced from wi/AX-24-car-ahead-off-published.md and wi/ML-01-retrain-2018-2024.md.

### DM-01 — int_track_evolution: drop the ambient fill, flag or NULL the clamped rubber

#### Problem
int_track_evolution writes a hidden zero in two places. The ambient component is COALESCEd to 0 where the weather slope is missing (1 row). The rubber slope is clamped to <= 0 (the clamp at about :80-90), so 36 of 166 races have rubber exactly 0 (1,989 rows) and the track-evolution page plots that as a measurement. Its methodology does not say so.

#### File and line
transform/models/intermediate/int_track_evolution.sql:156-163 (ambient COALESCE) and :80-90 (rubber clamp). Page: app/src/features/track-evolution (queries.ts:28, transform.ts:16-30).

#### Fix
Remove the ambient COALESCE so a missing slope gives NULL. Keep the clamp for the fit but add a flag (rubber_is_clamped) and publish the rubber value as NULL where clamped, or carry both a raw and a clamped column. Pick one in the build; state it in the page methodology.

#### Test
An expression test: rubber is NULL iff the clamp fired. Keep the existing monotone tests. A dbt test that no ambient value is 0 by fill.

#### Do published numbers change
Yes: the track-evolution page for 36 races. Rubber also sits outside the residual identity, so lap residuals do not move.

#### Dependency
Waits on TX-30 so it runs on the post-sweep build. DM-02 waits on this. Not run: no dbt, nothing under data/ or app/public/data/.

### DM-02 — int_constructor_structural_pace: no-estimate row with a reason for all-wet races, fix the unweighted centring, remove the SE fill

#### Problem
73 of 1,655 (race, constructor) pairs in 15 races have no structural-pace row (all-wet races, or a constructor with no dry clean lap). Downstream, int_lap_residual_decomposed writes 0.0 for them. The re-centring (from :150) subtracts an unweighted race-level average, so the zero-sum does not hold on the weighted field. The SE is COALESCEd to 0 (:184-194; 0 rows hit today).

#### File and line
transform/models/intermediate/int_constructor_structural_pace.sql:150-176 (centring) and :184-194 (SE fill).

#### Fix
Emit a no-estimate row for each missing pair with a reason (all_wet_race, no_dry_clean_lap), NULL estimate and NULL SE. Centre with weights (lap count). Remove the SE COALESCE.

#### Test
No SE of 0; per-race weighted zero-sum; the 73 missing pairs each carry a reason.

#### Do published numbers change
Yes, for the centring (constructor pace shifts slightly). The reason rows change coverage, not existing numbers.

#### Dependency
Waits on DM-01. DM-03 and DM-07 wait on this. Owner ruling on all-wet races is assumed to be "no estimate with a reason"; confirm.

### DM-03 — Carry constructor_pace_is_filled through fct_lap_residuals, the marts and the export; pages filter on it

#### Problem
int_lap_residual_decomposed.sql:286 writes 0.0 constructor pace on 8,494 laps and sets constructor_pace_is_filled at :290, but no mart, int_power_law_lap or the export carries the flag. 5,153 filled laps are ml_eligible (fct_lap_residuals.sql:115). The car term reads 0 and driver_skill_residual_s is shifted by the same amount.

#### File and line
int_lap_residual_decomposed.sql:286-290; fct_lap_residuals.sql; mart_race_driver_summary:46, mart_driver_season_summary:74, mart_metric_benchmark:35; pages race-lost (queries.ts:83,89), lap-waterfall (queries.ts:78,84), constructor-team-averages (queries.ts:35).

#### Fix
Select the flag in fct_lap_residuals, aggregate it (share of filled laps) in the three marts, add it to the export and the schema. Pages exclude filled laps from the car-term averages or show them as no estimate.

#### Test
Flag present in the schema.yml of each model; a vitest per page that a filled lap is not averaged as a measured zero.

#### Do published numbers change
Yes: about 4.4% of constructor-races on the three pages and the marts.

#### Dependency
Waits on DM-02 (no-estimate rows decide which laps are filled). DM-05 waits on this. Needs a re-export, which is the owner's decision (AXW14).

### DM-04 — Dirty air: rebuild air state on proximity crossings (AX-24), then propagate theta's interval into the tax SE

#### Problem
int_lap_air_state still reads FastF1 DriverAhead (assert_car_ahead_field_internal_only says so). int_dirty_air_tax_component multiplies a frozen theta 0.331 by the lagged share, with SE set to 0.15 times the tax by convention (:354), so SE is 0 on 102,059 of 147,931 clean-air laps. The chain feeds lap residuals, dirty-air-cost (MAX of cumulative understates on 6 driver-races) and ML labels.

#### File and line
int_lap_air_state.sql; int_dirty_air_tax_component.sql:306-316 (fill) and :354 (SE convention); test assert_dirty_air_se_is_declared_convention.

#### Fix
1. AX-24: rebuild air state on int_lap_proximity crossings. 2. Propagate theta's interval into the SE (delta method or draws), remove the 0 SE, and fix the NULL cumulative.

#### Test
SE greater than 0 wherever share is greater than 0; a theta-sensitivity test; the car-ahead guard test stays green.

#### Do published numbers change
Yes, and the ML labels move (version bump, see DM-06).

#### Dependency
HELD. Waits on AX-20, AX-24 and DM-03. Stays waiting on AX-20 per HD23; do not make runnable earlier.

### DM-05 — Ghost chain: interaction and deg-sensitivity NULL not 0, with a true flag

#### Problem
78,377 of 1,372,651 ghost laps (5.7%) carry a prior fill (host_deg_slope 77,430, ego_deg_slope 77,151, host_constructor_pace 1,122). circuit_interaction_is_prior is 0 on every row although int_circuit_x_constructor_interaction.sql:155-157 filled 545 of 1,634 rows (SE 0 on 885). The flag cannot see upstream fills. 18 non-self scenarios mix a filled and an estimated slope.

#### File and line
int_circuit_x_constructor_interaction.sql:155-157; int_constructor_deg_sensitivity.sql; fct_ghost_car_pace.sql:210-244 and :298; fct_ghost_race_finish.sql. Pages: counterfactual-championship (queries.ts:60-66), hidden-performance (queries.ts:52-94).

#### Fix
Interaction and deg-sensitivity become NULL where unestimated; the is_prior flag is set from the true source. Then the two pages use n_laps_prior_filled. Depends on HD20: A keep 0 as a flagged declared prior, B treat as missing.

#### Test
Extend assert_ghost_se_never_zero_filled; flag count equals fill count.

#### Do published numbers change
Yes if HD20 is B (NULL). Under A only the flags and notes change.

#### Dependency
Waits on DM-03 and on decision HD20 (OPEN, owner). TX-18 already added the *_is_prior flags.

### DM-06 — ML-only zeros: drift_s_per_lap, quali SE, power-law constructor_pace_s, the powerlaw_ceiling COALESCE; version bump

#### Problem
Zeros that reach only ML: int_lap_residual_stint_detrend:29-31 fills drift_s_per_lap with 0 on 580 of 7,989 stints (copied at fct_cliff_prediction_features.sql:552); int_lap_residual_decomposed_qualifying.sql:124 fills the SE with 0 on 38 laps (436 training rows, schema.py:258); the power-law constructor_pace_s is 0 on 1,594 of 139,933 laps (powerlaw.py:90,97); ml/src/powerlaw_ceiling.py:281,286 re-applies COALESCE(...,0).

#### Fix
NULL (or an explicit flag) in place of each fill; ML code accepts NaN where meant. Bump the label or feature version.

#### Test
A NaN-allowed schema test and a label-stability baseline.

#### Do published numbers change
ML outputs only. No page or card number moves before the retrain.

#### Dependency
Waits on AX-20 (HD23: ML after launch) and TX-29 (holdout move). Do it with or just before ML-01 so one retrain covers it.

### DM-07 — Inert SE fills (era rating, structural pace): tidy, no number change

#### Problem
int_era_normalized_driver_rating.sql:156 and int_constructor_structural_pace.sql:184-188 coalesce the SE to 0. Neither fires today (0 rows) but either would publish a false certainty if it did.

#### Fix
Remove the COALESCE so an absent SE stays NULL. The structural-pace half is done inside DM-02; this item covers the era rating and confirms the second.

#### Test
Assert SE is NULL or greater than 0 on both models.

#### Do published numbers change
No.

#### Dependency
Waits on DM-02.
