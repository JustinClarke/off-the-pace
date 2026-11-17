# TX-27 — Jolpica pit_stops as an independent cross-check of stg_pits

**Group:** 1b new-data · **Depends on:** TX-15 · **Model / cost:** `sonnet-5`, 1d

**Evidence:** data-use audit, read-only, 2026-11-16 (relayed to the board session; no evidence file on disk). References re-checked 2026-11-16.
**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread (rule 5). Never write `data/dev.duckdb`, `data/bronze/` or `data/fits/`. No data-writing make target without the owner. Nothing staged or committed by an agent.
**Class:** measured, transform class (rule 4: live since AX-07). Missing stays NULL with a reason, never 0. A card on this mart is AX-28, not this item.

## Why
`data/bronze/reference/jolpica/pit_stops` is ingested and only used inside a lap-tyre QA model. A cross-check gives a measured second source for stop counts and laps.

## Method
Staging model over the Jolpica pit stops; a mart that sets Jolpica beside `stg_pits` per driver-race (stops, laps, Jolpica duration) with an agreement flag. Shown as a separate measured source; neither overwrites the other.

## Done when
Agreement rate per season recorded; every disagreement listed with both values.

## Sources
`transform/models/staging/stg_pits.sql`, `transform/models/staging/stg_lap_tyre_qa.sql`, `ingestion/src/jolpica_client.py`, `transform/models/marts/fct_pit_stop_crosscheck.sql` (new).

## 2026-11-16 (fixall session), scratch only, not exported
New source models/staging/src_jolpica.yml, stg_jolpica_pit_stops.sql, and mart models/marts/new_data/fct_pit_stop_crosscheck.sql (per driver-race: FastF1 and Jolpica stop counts and laps side by side; Ergast id mapped to the FastF1 abbreviation through Bronze results; crosscheck_status). Agreement per season (AGREE share of driver-races): 2018 342/392, 2019 386/413, 2020 282/321, 2021 374/422 (20 JOLPICA_RACE_MISSING), 2022 386/417, 2023 393/424, 2024 438/462, 2025 439/459. Every disagreement is a row with both values. Caveat: 39 Jolpica rows do not map to a FastF1 driver (id mismatch), which inflates COUNT_DIFFERS. The map needs a check before any page uses it. Output: /private/tmp/claude-501/-Users-justin-github-off-the-pace/2a4fcfbe-da29-45d9-a8d3-1e4bbaaf446a/scratchpad/fixall/new_marts_check.txt.
