# TX-16 — 2018 Italian GP: carry out the owner's ruling (re-ingest, or a recorded gap shown as unavailable)

**Group:** 1a bronze-honesty · **Depends on:** TX-15 · **Blocker:** HD15 (owner) · **Model / cost:** `sonnet-5`, 0.5d

**Evidence:** data-use audit, read-only, 2026-11-16 (findings relayed to the board session; no evidence file on disk). File and line references below were re-checked on 2026-11-16 by the re-planning session.
**How to run:** every dbt run in your own scratch folder with the copy named `dev.duckdb`, 1 thread (rule 5; method as in `TX-03.md`). Never write `data/dev.duckdb`, `data/ci.duckdb`, `data/bronze/` or `data/fits/`. No `make ingest`, `bronze-lock`, `bronze-unlock`, `dbt build` on the real warehouse, `export` or `deg-iso-fit` without the owner. Nothing is staged or committed by an agent.

## Why
2018_14 is in the published Nov-8 export with 833 laps. In the new Bronze every run for 2018 R italian_grand_prix is status=error (10 runs, reason 'error'); qualifying is fine. `ingestion/known_gaps.txt` already lists it as a known gap, so the lock passes, and a rebuild silently drops the race from every page and card.

## Method (depends on HD15)
- **A (re-ingest):** owner runs `make bronze-unlock`, a single-race ingest for 2018 round 14 R, then `make bronze-lock` and `make bronze-verify`. If it loads, remove the line from `known_gaps.txt`. If it fails again, fall through to B.
- **B (recorded gap):** keep it in `known_gaps.txt`; the export writes a coverage row for the race with reason `SOURCE_UNAVAILABLE`; the data-quality page and every race picker show it as unavailable with that reason, never as a missing row. The next export withdraws the Nov-8 numbers for it; the owner sees that list first.
- **C (archived copy):** copy the 2018 Italian R partitions from `data/_archive-2026-11-14/bronze/` into Bronze, marked as an older ingest in the manifest. Only on the owner's say-so.

## Done when
A rebuild either carries 2018_14 or shows it as unavailable with a reason on every page that lists races, and a test fails if a race in the published export disappears without a coverage row.

## Sources
`ingestion/known_gaps.txt`, `scripts/export_app_data.py`, `app/src/features/data-quality-audit/`, `data/bronze/manifests/`.

## 2026-11-16 (fixall session), HD15 option B
- transform/models/marts/mart_race_coverage.sql: new n_bronze_lap_rows (stg_laps rows per race) and a first-match reason SOURCE_UNAVAILABLE when it is 0. This is derived from the data, not from a list. _coverage.yml documents it and its accepted_values.
- transform/tests/assert_every_lap_race_rated_or_explained.sql: new failure race_without_laps_unexplained (a race_to_track race with no laps whose reason is OK, or with no Bronze laps that is not SOURCE_UNAVAILABLE). race_to_track is the list every picker reads, so a published race cannot vanish without a coverage row.
- app data-quality page (app/src/features/data-quality-audit/): lists the season's SOURCE_UNAVAILABLE races under "Races not available" with the reason, never as zero laps (vitest 7 pass; tsc clean).
- Scratch check (/private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/fix): 2018_14 gives n_bronze_lap_rows 0, n_lap_rows 0, SOURCE_UNAVAILABLE; the coverage accepted_values test passes. The coverage test still fails on 1 row, 2021_12, which is a separate TX-15 finding.
- Not done: race pickers (shared useRaceOptions) still list 2018_14 from race_to_track with no "unavailable" label. Pages that pick it show their empty state. The assistant race.coverage card text (raceKinds.ts COVERAGE_TEXT) has no SOURCE_UNAVAILABLE entry: AX code, not touched. Nothing is exported until the owner exports.
