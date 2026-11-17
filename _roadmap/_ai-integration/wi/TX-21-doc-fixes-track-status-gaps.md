# TX-21 — Doc fixes: track-status codes, the 2018 Bahrain gap note, the 2024 race-control clock note

**Group:** 1a bronze-honesty · **Depends on:** none · **Model / cost:** `sonnet-5`, 0.25d

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
- `transform/models/staging/src_formula1.yml:82` and `ingestion/SCHEMA.md:92` say 5=VSC, 6=SC ending, 7=red. The code (`stg_laps.sql:121-126`, ground-truthed against the Message column) decodes 5=red, 6=VSC deployed, 7=VSC ending. The docs are wrong; the code is right.
- `ingestion/known_gaps.txt:10` says the empty car and pos data is 2018 **Q** Bahrain. The manifests say 2018 **R** Bahrain (car_data and pos_data: no samples), and 2018 R Australia (pos_data). Both also fail circuit_info (KeyError '3' and '77').
- `ingestion/SCHEMA.md:217` says `session_time_s` is null for 2024. In the new Bronze the 2024 race-control files carry it and `session_time_corrected_s` (checked on one file, 2024 Abu Dhabi: 0 nulls). Re-check across 2024 and fix the note.

## Done when
The three docs match the code and the manifests; no code changes.

## Sources
`transform/models/staging/src_formula1.yml`, `ingestion/SCHEMA.md`, `ingestion/known_gaps.txt`, `transform/models/staging/stg_laps.sql`.
