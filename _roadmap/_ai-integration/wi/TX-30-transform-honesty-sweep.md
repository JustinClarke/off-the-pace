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
