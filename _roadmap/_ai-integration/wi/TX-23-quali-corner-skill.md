# TX-23 — Qualifying telemetry into corner skill (a qualifying corner-skill mart)

**Group:** 1b new-data · **Depends on:** TX-15, TX-19 · **Model / cost:** `opus-5`, 2-3d

**Evidence:** data-use audit, read-only, 2026-11-16 (relayed to the board session; no evidence file on disk). References re-checked 2026-11-16.
**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread (rule 5). Never write `data/dev.duckdb`, `data/bronze/` or `data/fits/`. No data-writing make target without the owner. Nothing staged or committed by an agent.
**Class:** measured, transform class (rule 4: live since AX-07). Missing stays NULL with a reason, never 0. A card on this mart is AX-28, not this item.

## Why
193 Q telemetry files exist in Bronze (`telemetry/season=*/race=*/session=Q/`), but the `raw_telemetry` source glob (`src_formula1.yml:525`, `telemetry/*/*/*.parquet`) only reaches race files. Corner skill is race-only today.

## Method
1. New source and staging model for Q telemetry (same columns and clip as `stg_telemetry.sql`; follow the HD16 ruling if it has landed).
2. Qualifying corner metrics on the push laps only (definition to rule in the doc before building: deleted laps out, in/out laps out), with n per driver-corner and an interval.
3. A separate mart (not mixed with race corner skill), its own `schema.yml` entry and tests. Shown as "qualifying" everywhere; never merged into a race rating.

## Done when
The mart builds in scratch for 2018-2025, every row has n and an interval, and a test fails if a race lap reaches it.

## Sources
`transform/models/staging/src_formula1.yml`, `transform/models/staging/stg_telemetry.sql`, `transform/models/intermediate/int_corner_metrics.sql`, `transform/models/marts/mart_corner_skill_driver.sql`, `transform/models/staging/stg_telemetry_qualifying.sql` (new).
