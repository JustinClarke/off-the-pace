# TX-22 — Ingest manifest: one latest status per session, circuit_info failures recorded, missing markers named

**Group:** 1a bronze-honesty · **Depends on:** none · **Model / cost:** `sonnet-5`, 0.5-1d

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
- Audit (g): `telemetry_full_status` looks blank for Q. Re-checked 2026-11-16: blank appears on skip-on-rerun rows (1,737 Q, 1,540 R rows); every one of the 193 Q sessions has a run with `ok`. The real gap is that no reader resolves "latest status per session" across the 10 runs, so coverage checks read skip rows as blank.
- Audit (h): the 8 empty 2018 rows are 2 sessions (2018 R Australia, pos_data empty; 2018 R Bahrain, both channels empty) over 4 runs each; circuit_info fails for both (KeyError '3' / '77').
- circuit_markers missing for one 2020 event; circuit_info and circuit_markers missing for three 2026 events (not yet named).

## Method
Offline code and test change only; no re-ingest. Add a latest-status-per-session view to `verify_bronze.py` (skip rows inherit the status of the run that wrote the session); name the 2020 and 2026 events missing markers or info; record the 2018 circuit_info failures in `known_gaps.txt` as information lines. Tests in `ingestion/tests/`.

## Done when
`verify_bronze.py` reports telemetry_full coverage per session for R and Q from the latest writing run, the missing-markers events are named, and `make test` passes offline.

## Sources
`ingestion/src/ingest.py`, `ingestion/verify_bronze.py`, `ingestion/known_gaps.txt`, `ingestion/tests/test_bronze_verification.py`.

## 2026-11-16 fix (fixall session): what changed and what was checked
- `ingestion/verify_bronze.py`: new `latest_session_status()` (one row per season, session type and race: status, `telemetry_full_status` and note from the latest **writing** run, so a later `skip` row inherits it; `circuit_info_status` from the latest non-blank value) and `manifest_findings()`, shown as a new section 5 "MANIFEST" (row counts are now section 6). The section is informational: it never fails a run on its own, because presence (section 1) already does.
- `ingestion/known_gaps.txt` (comment lines only, no gap line changed): the 2018 circuit_info failures (KeyError '3' for 2018 R australian_grand_prix, '77' for 2018 R bahrain_grand_prix), and the events with no circuit markers: 2020 R and Q sakhir_grand_prix (markers only); 2026 R monaco_grand_prix, 2026 R and Q spanish_grand_prix, 2026 Q bahrain_grand_prix (circuit_info and markers).
- `ingestion/tests/test_bronze_verification.py`: two tests (skip rows inherit the writing run; a session with only skip rows; circuit_info failure and missing markers named; no manifests).
- Checked: `make test` 160 passed offline (about 2.5 s). `verify_bronze.py` on data/bronze (read-only): Q is `ok` for all 193 sessions from the latest writing run; R has 2018 R australian and bahrain `empty`, 2018 R italian `error` (known gap) and 2026 R bahrain `thin` (known gap); no re-ingest.
