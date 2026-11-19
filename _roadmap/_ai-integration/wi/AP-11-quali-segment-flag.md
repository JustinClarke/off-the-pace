# AP-11 — Flag races with no qualifying segment data in the app

**Group:** 2-app-fixes · **Depends on:** TX-30 · **Model / cost:** `sonnet-5`, 0.5d

**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread. Never write `data/dev.duckdb`, `data/bronze/` or `app/public/data/` without the owner. Nothing staged or committed by an agent.

## Why
The results feed has no Q1/Q2/Q3 times for 2025 Miami: all 20 drivers have a position and timed laps, but every segment column is null. The staging model reported those drivers as `none`, which reads as "eliminated in Q1". That is false. The transform side is done: `stg_results_qualifying.segment_source` is `missing_from_feed` for that race (derived per race_id, and only that race today), and `official` for the other 192.

## Method
1. Audit page (`app/src/features/data-quality-audit/`): show "Qualifying segments not available: the feed carried no segment times for this race" for any race whose qualifying coverage is missing.
2. Source the flag from `mart_race_coverage` with a new qualifying column. That changes the mart's model hash and the CI hash baseline (`transform/tests/model_hashes*.json`), so it needs the owner's ruling first.
3. Re-export `app/public/data` (owner only) so the page reads the new column.
4. Any future qualifying-segment view reads `segment_source` and skips `missing_from_feed` races.

## Done when
The audit page shows the message for 2025 Miami and nothing else. A test fails if an `official` race shows the message.

## Sources
`transform/models/staging/stg_results_qualifying.sql`, `transform/models/staging/schema.yml`, `transform/models/marts/mart_race_coverage.sql`, `app/src/features/data-quality-audit/queries.ts`, `app/src/features/data-quality-audit/transform.ts`.
