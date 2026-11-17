# TX-19 — Measure what the 6,500 m telemetry clip removes (Spa first) before anyone rules on lifting it

**Group:** 1a bronze-honesty · **Depends on:** none · **Model / cost:** `sonnet-5`, 0.5d · **Feeds:** HD16

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
`transform/models/staging/stg_telemetry.sql:70-71` keeps only `distance_m > 0 AND distance_m < 6500`. Spa is about 7 km, so the audit finds about 10% of Spa samples clipped, and Turns 17-19 thin. Other long tracks may be affected too.

## Method
Read-only on Bronze (or the TX-15 scratch build): per circuit, the share of samples at or above 6,500 m, the corners from `dim_corners` whose window crosses 6,500 m, and the corner-skill rows that would gain samples. Report what moves in `int_corner_metrics` and `mart_corner_skill_driver` if the bound becomes circuit length plus a margin (from `circuit_info`).

## Done when
A table per affected circuit (share clipped, corners affected, rows that move, size of the move) goes to the owner with HD16.

## Sources
`transform/models/staging/stg_telemetry.sql`, `transform/models/reference/dim_corners.sql`, `transform/models/intermediate/int_corner_metrics.sql`, `transform/models/marts/mart_corner_skill_driver.sql`.
