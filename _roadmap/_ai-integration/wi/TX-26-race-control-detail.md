# TX-26 — Race-control detail: blue flags, investigations, sector yellows, tied to laps and circuit markers

**Group:** 1b new-data · **Depends on:** TX-15, TX-21 · **Model / cost:** `opus-5`, 1-2d

**Evidence:** data-use audit, read-only, 2026-11-16 (relayed to the board session; no evidence file on disk). References re-checked 2026-11-16.
**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread (rule 5). Never write `data/dev.duckdb`, `data/bronze/` or `data/fits/`. No data-writing make target without the owner. Nothing staged or committed by an agent.
**Class:** measured, transform class (rule 4: live since AX-07). Missing stays NULL with a reason, never 0. A card on this mart is AX-28, not this item.

## Why
Race control is only used for caution periods today. The clock that AX-22 / AX-25 were waiting for is now in Bronze: every R and Q race-control file in the 2026-11-16 ingest carries `session_time_corrected_s` (69 of 18,290 R rows null or NaN), and the fix and its test (`ingestion/tests/test_ingestion.py:472`) are in commit 8f23310.

## Method
1. First, AX-22's join check: race-control messages joined to laps on the corrected clock; report the join rate on Monza 2024, Silverstone 2024 and Austria 2022 (about 95% expected). If it fails, fall back to the `Lap` column for joins.
2. Classify messages (blue flag, investigation, penalty, sector yellow) by rules written in this doc before the build; unknown stays unclassified, never dropped.
3. Tie sector yellows to `circuit_markers` sectors where markers exist; NULL with a reason where they do not (one 2020 event and three 2026 events lack them; TX-22 names them).

## Done when
Join rate recorded; every message classified or marked unclassified; counts reconcile with Bronze per race.

## Sources
`transform/models/staging/stg_race_control.sql`, `transform/models/staging/src_formula1.yml`, `ingestion/src/ingest.py`, `transform/models/marts/fct_race_control_events.sql` (new).
