# TX-20 — Change the telemetry distance clip as ruled in HD16

**Group:** 1a bronze-honesty · **Depends on:** TX-19 · **Blocker:** HD16 (owner) · **Model / cost:** `opus-5`, 0.5-1d

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
See TX-19. Lifting the clip moves corner-skill numbers at Spa (and any other track TX-19 names), so it is a contract change and goes to the owner first.

## Method
As ruled: per-circuit bound from `circuit_info` (length plus a margin), or keep 6,500 m and label the affected corners thin. Rebuild in scratch; diff corner marts; owner re-takes baselines.

## Done when
The ruled bound is in `stg_telemetry.sql`, a test pins it, and the diff the owner approved matches the rebuild.

## Sources
`transform/models/staging/stg_telemetry.sql`, `transform/models/staging/stg_circuit_info.sql`, `transform/models/marts/mart_corner_skill_driver.sql`.
