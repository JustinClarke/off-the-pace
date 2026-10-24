# CO-27 baseline options probe (2026-10-24)

Warehouse: copy of data/dev.duckdb (CO-17 second build per the log: PASS=1443 ERROR=0 of 1446)
at scratchpad/co27/dev-probe.duckdb, hard-linked as scratchpad/co27/db/dev.duckdb so the catalog
is named `dev` (the byte oracle's SQL needs it). All access read-only.
data/dev.duckdb sha256 before and after: f068fed74d25dbe854aa06505b08889f0b1bd8aee0d7f400eb22069680d53ba4 (unchanged).
Manifest: copy of transform/target/manifest.json.

Note: CD15 and CD16 were both already RESOLVED (2026-10-23) when this ran, so this probe is
confirmation evidence, not input to an open ruling.

## CD15 (two baseline-gated tests) - ruled B then C

The two tests were removed from the tree in commit e87f728. Their logic was evaluated directly
in SQL on the copy, using CO-17's own build as the baseline (what option A would commit).

| Option | What changes | Pass / fail | Risks |
|---|---|---|---|
| A: baseline from CO-17's build | Commit a parquet of fct_lap_residuals | assert_residual_variance_shrinks: FAIL 1 row (ratio 1.0, band is [0.85, 0.99]). assert_constructor_pace_propagates: FAIL 1 row (current var 1.3201 = baseline var, test needs strictly lower). Both fail by construction, every build. | A self-baseline can never pass; the tests compare against a pre-decomposition build that no longer exists. |
| B: remove (ruled, done) | 2 tests gone (e87f728) | 0 tests, 0 fails | Lost coverage: no check that constructor variance > 0 (today 0.628, > 0) and no residual-variance regression check. Planned C replaces both without a baseline. |

Values: driver_skill_residual_s var_pop 1.32009 over 148,622 laps; constructor_structural_pace_s var_pop 0.62807.

## CD16 (pipeline real-data gates) - ruled B

| Option | What changes | Pass / fail | Risks |
|---|---|---|---|
| A: re-baseline on CO-17's build | Rewrite model_hashes.baseline.json and data_profile.baseline.json | Today, before re-baseline: byte oracle FAIL, 12 fct_* drifted (audit said 11; fct_driver_isolation_* x4, fct_power_law_training, fct_stint_features 9,374 -> 8,945, fct_telemetry_deltas 28,628,356 -> 1,623,427, fct_ghost_car_pace, fct_ghost_race_finish, fct_lap_residuals, fct_driver_skill_features, fct_cliff_prediction_features), 4 new models, 53 non-fct warnings. Data profile FAIL, 211 drifts (audit said 187), incl. 10 new tables and 1 missing column (fct_driver_skill_features.constructor_aero_pace_index_final). After re-baseline both would pass by definition. | Not done: every drift must first be traced to a reviewed change; not traced in this probe. Some trace plainly (stint_features to CO-09, telemetry_deltas to CO-22), the rest are untraced. |
| B: leave baselines, pipeline off (ruled) | Nothing | Pipeline gated off by vars.PIPELINE_ENABLED (pipeline.yml line 43); both checks would fail if it were turned on. | Real-data path unguarded by byte oracle and profile diff until reviewed; W18 (is PIPELINE_ENABLED set?) still unknown. |

Baselines untouched: model_hashes.baseline.json e2fcc4e8...926d5c, data_profile.baseline.json 35d0ec25...6eab (sha256 same before and after). No candidate baseline regenerated, since neither ruling adopts one.

Raw output: scratchpad/co27/hash_check.txt, profile_check.txt, cd15_probe.txt.
