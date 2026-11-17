# TX-17 — fct_stint_features: unmeasured dirty air becomes NULL with a reason, not 0

**Group:** 1a bronze-honesty · **Depends on:** TX-15 · **Model / cost:** `opus-5`, 1d · **Blocks:** any card on dirty air (AX-15b)

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
`transform/models/marts/fct_stint_features.sql:226` is `COALESCE(da.cumulative_dirty_air_tax_s, 0.0)`. The audit counts 2,393 of 8,945 stints at 0 in the published table, including every stint of 2018_1, 2018_2 and 2018_3 (2018_1 and 2018_2 are NO_TELEMETRY). A measured 0 (clean air) is real, so 0 cannot tell measured from unmeasured. TX-03 fixed the same fault in the aggregates and left this mart.

## Method
1. Replace the fill with NULL where no dirty-air row exists, plus `dirty_air_unavailable_reason` (e.g. `NO_TELEMETRY`, `NO_AIR_STATE`).
2. Readers: `scripts/assistant_query_views.py` deny-lists the column (keep it denied); no file under `ml/src/` reads it (checked 2026-11-16); check app features and `schema.yml` tests, and list each reader in the hand-back.
3. Hash and data-profile baselines move for this mart: the owner re-takes them, as in TX-14.

## Done when
On the TX-15 build, the number of stints with NULL equals the number with no dirty-air row, a test fails if a stint without a dirty-air row carries 0, and the owner has seen the diff.

## Sources
`transform/models/marts/fct_stint_features.sql`, `transform/models/marts/schema.yml`, `scripts/assistant_query_views.py`.

## 2026-11-16 (fixall session)
- fct_stint_features.sql: the COALESCE(...,0.0) is gone. cumulative_dirty_air_tax_s is NULL when no lap has a measured tax. New columns n_dirty_air_measured_laps and dirty_air_unavailable_reason (NO_TELEMETRY when the race's air-measured share is at or below the coverage var, else NO_AIR_STATE). schema.yml documents both. New test assert_stint_dirty_air_null_when_unmeasured.
- Scratch diff against TX-15 base (/private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/fix_diff): 2018-2025, 1,134 of 8,895 stints go from 0 to NULL (NO_AIR_STATE 1,043, NO_TELEMETRY 91; 2018 223 ... 2025 138). 1,284 measured zeros stay 0. No other value moves (2,241 with 2026). The test passes on the fix build and would fail on the base build (2,241 unmeasured stints carry a value).
- Readers: scripts/assistant_query_views.py deny-lists the column (still denied; the new columns match the dirty_air pattern); docs/reference/models/fct/fct_stint_features.mdx (prose, not updated); transform/tests/data_profile.baseline.json (moves; the owner re-takes). No app feature and no ml/src file reads it.
- Caveat: a partly measured stint still sums only its measured laps (see n_dirty_air_measured_laps).
