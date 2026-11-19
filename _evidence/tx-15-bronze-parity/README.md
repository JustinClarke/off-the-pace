# TX-15 bronze rebuild parity: how it was run

Measurement only. Written 2026-11-18 by an agent session. The owner has not read it. Nothing in the repo outside this folder was changed, nothing was staged or committed by the agent, and none of data/dev.duckdb, data/ci.duckdb, data/bronze/, data/fits/, app/public/data/ or data/_archive-2026-11-14/ was written (data/dev.duckdb and data/ci.duckdb do not exist in the repo checkout at the moment; data/fits/ holds only .gitkeep).

Files here: summary.md (the report), summary.json (the same numbers plus per-column hashes, per-table key, per-column moved counts, the test list, the scratch warehouse row counts), movers_<table>.csv (top 40 single-cell moves per table that moves), bronze_telemetry_distance_by_race.csv (Bronze telemetry samples at or above 6,500 m per race).

## Inputs

- Tree: HEAD 4320460 plus the uncommitted edits present at the start (int_lap_residual_decomposed, fct_ghost_car_pace, fct_ghost_race_finish, stg_laps, schema.yml files, seeds README and seed_manual_lap_exceptions.csv, a new test assert_car_ahead_field_internal_only.sql, and app/doc/roadmap files). Those edits were committed as e496682 while the build was running; no file under transform/ changed after the build started (checked by modification time).
- Bronze: data/bronze, MANIFEST.json file_count 19,505. `ingestion/src/bronze_lock.py verify data/bronze` (the command behind make bronze-verify, read-only) was run at the start: "OK", exit 0. 2018_14 (Italian GP race) has no Bronze files, as listed in KNOWN_GAPS.txt.
- Published side: app/public/data, manifest e5b324bf3e6d07a6.

## Commands (all in the scratch folder, 1 thread)

Scratch folder: /private/tmp/claude-501/-Users-justin-github-off-the-pace/9e7d79f2-3431-473d-ae21-4ffad6685e9c/scratchpad/tx15/ . The dbt copy is dev.duckdb there; profiles.yml (type duckdb, threads 1, settings threads 1, memory_limit 6GB) points at it. Wrapper dbt.sh runs the repo's .venv/bin/dbt (dbt-core 1.12.6, dbt-duckdb 1.11.0, duckdb 1.5.6) from transform/ with `--profiles-dir`, `--target-path` and `--log-path` in the scratch folder and `--vars '{bronze_base: /Users/justin/github/off-the-pace/data/bronze, fits_base: <scratch>/fits}'`.

1. `dbt seed` (19 seeds OK).
2. `dbt run --select +int_lap_fuel_state +int_field_pace_curve +int_event_corrections +int_track_evolution +stg_laps` (16 models), then `python -m tasks.coefficients.fit_constructor_car_fe --db <scratch>/dev.duckdb --out <scratch>/fits/constructor_car_fe.parquet` (1,687 rows).
3. `dbt run --select +int_driver_isolation_lap_panel` (21 models), then the same fit with `--panel isolation` (1,611 rows).
4. `dbt run --exclude mart_degradation_history_envelope "int_lap_physical_ahead+"`: 104 of 104 OK.
5. `dbt test --exclude mart_degradation_history_envelope "int_lap_physical_ahead+"`: 1,449 tests, 1,395 pass, 54 fail or error. (Run and test are separate on purpose: dbt build would skip every model below a failing test.)
6. Export: `scripts/export_app_data.py --db <scratch>/exportdb/export_copy.duckdb --out <scratch>/export`. The exporter exits on the first missing non-optional table, and mart_degradation_history_envelope is one, so the export ran on a copy of dev.duckdb with an empty table of that name (columns taken from the published parquet) added. The dbt-built dev.duckdb does not have that table. Result: 55 tables, 240 MB, in <scratch>/export (not copied into the repo). The manifest in that folder is the full-export one; an earlier per-table export attempt is in export_pertable_partial/ and should be ignored.
7. Diff: Python/duckdb scripts in the scratch folder (diff2.py, diff3.py, counts_e.py, counts_spa.py, rel.py, classify.py, build_report.py, build_md.py). Published and scratch parquet are read directly and joined on the grain key found by search (unique on both sides); per-column hash is sum(hash(col)) per table, so row order does not matter.

## Exclusions and caveats

- Excluded, as in the earlier attempt: mart_degradation_history_envelope (no degradation_isotonic.parquet; waits on TX-09/XM) and int_lap_physical_ahead with everything downstream (over 10 minutes single-threaded). Consequences: 12 dbt source tests on degradation_isotonic error; int_coast_tax_component is absent from the scratch export; the envelope table in the scratch export is empty.
- Car-FE fits: data/fits is empty in the repo and the repo .venv has pyfixest 0.70.0, which breaks fit_constructor_car_fe. A scratch venv (<scratch>/venv, Python 3.14, pyfixest 0.60.0, duckdb 1.5.6, pandas 2.3.3, pyarrow 26.0.0) ran both fits into <scratch>/fits. The repo .venv and data/fits were not touched. No published fit files exist on disk, so the fits themselves are not diffed.
- The ML outputs (driver_network_rating, mart_degradation_predictions) and the assistant cards were not rebuilt; they are not in the scratch export.
- The comparison mixes three causes (new Bronze, tree changes since Nov 8, scratch fit) and does not separate them. The tree already contains the TX-17, TX-18 and TX-20 edits, so section 5 of the report gives the published value, the scratch value, and the old-rule equivalent.
- Tolerance: float |delta| > 1e-9 (TX-14's ROUND(x, 9) oracle). TX-14 states no other numeric tolerance. Counts above 1e-6 and 1e-3 are in summary.json.
- The export and the Python imports wrote __pycache__ folders under the repo (scripts/, ml/ or transform/); they are untracked/ignored and were left.
