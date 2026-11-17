# TX-15 — Rebuild on the 2026-11-16 Bronze in a scratch copy and diff it against the published Nov-8 export

**Group:** 1a bronze-honesty · **Depends on:** none · **Model / cost:** `sonnet-5`, 1d · **Blocker:** none (measurement only)

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
Every published number (`app/public/data/_manifest.json`, version e5b324bf3e6d07a6, generated 2026-11-08) was built from the OLD Bronze, now in `data/_archive-2026-11-14/`. Bronze was re-ingested 2018-2026 (R and Q, telemetry_full) and `make bronze-verify` passed on 2026-11-16. Nothing has been rebuilt on it. Before any fix is measured, we need to know what the rebuild alone moves, and what it drops.

## Method
1. Full `dbt build` of the current tree on the new Bronze, in a scratch folder (`bronze_base` var pointing at `data/bronze`), 1 thread.
2. Diff against the published export: race list per season, laps per race, rows per mart, and per-column hashes for the exported tables. Name every race present in one and absent in the other. Expected: 2018 Italian GP (2018_14, 833 laps in the Nov-8 export) disappears (every manifest run for 2018 R italian_grand_prix is status=error; it is listed in `ingestion/known_gaps.txt`).
3. Count, per mart, rows whose value moves by more than the TX-14 tolerance; list the top movers.
4. Record the counts behind TX-17, TX-18 and TX-19 on this build (zero-filled dirty-air stints, zero-filled ghost columns, Spa samples at or above 6,500 m), so those items measure against it.

## Done when
A parity report in `_evidence/tx-15-bronze-parity/` (new) lists dropped and added races, row deltas per mart and the top movers, and the owner has read it. No published file changes.

## Sources
`app/public/data/_manifest.json`, `data/bronze/MANIFEST.json`, `ingestion/known_gaps.txt`, `transform/dbt_project.yml`, `scripts/export_app_data.py` (its `--db` and `--out` flags, TX-12, for a scratch export).

## 2026-11-16 scratch rebuild (fixall session)
Scratch build of the tree as it stood before this session's edits: /private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/base/dev.duckdb (Bronze read-only, 1 thread). dbt run 98/98 OK; dbt test 1,360 pass, 54 fail (most fail because the 2026 races are in Bronze but not in the race_to_track seed). Car-FE fits were re-fitted into scratch with pyfixest 0.60 in a scratch venv; .venv has 0.70, which breaks fit_constructor_car_fe and 24 coefficient tests. Excluded: mart_degradation_history_envelope (no degradation_isotonic.parquet; TX-09/XM) and int_lap_physical_ahead+ (feeds no exported table; over 10 minutes single-threaded).
Diff against app/public/data (2018-2025): /private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/tx15_diff/ (README.md, summary.md, summary.json, movers_*.csv).
- 2018_14 dropped everywhere (833 laps, 19 driver-races, 8,150 ghost lap rows). The base reason is NO_RACING_LAPS, which is wrong; TX-16 fixes it.
- NEW: 2020_1 leaves the ghost marts, int_field_pace_curve and int_track_evolution. Its tyre QA is now quarantined_race (published: partial, OK).
- NEW: 2021_12 now has 20 valid laps (published: NO_RACING_LAPS) but no rating and reason OK, so assert_every_lap_race_rated_or_explained fails on 1 row.
- Row-level movement is broad: for example fct_lap_residuals changes on 84,806 of 160,215 rows, constructor_component_s up to 1.31 s; mart_driver_season_summary changes all 173 rows (ci max 0.115); mart_race_driver_summary changes 1,586 of 3,118 rows; int_corner_skill_residuals corner_residual_total_s up to 22.5 s.
- 2026 rows are built into every mart (no seed covers 2026).
- Counts for TX-17/18: 2,418 of 8,895 stints at 0 dirty air (1,134 with no measured lap); finish_pos_se = 0 on 4 of 30,054 rows; ghost car pace fills: host pace and its SE on 1,122 rows, deg-slope sd on 77,461 rows.
Not done: the evidence folder _evidence/tx-15-bronze-parity/ (the owner reads the scratch report first); per-column hashes; owner review.
