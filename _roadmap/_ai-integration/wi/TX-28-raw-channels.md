# TX-28 — Raw pos_data and car_data channels (telemetry_full) into staging

**Group:** 1b new-data · **Depends on:** TX-15, AX-24 · **Model / cost:** `opus-5`, 2d+

**Evidence:** data-use audit, read-only, 2026-11-16 (relayed to the board session; no evidence file on disk). References re-checked 2026-11-16.
**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread (rule 5). Never write `data/dev.duckdb`, `data/bronze/` or `data/fits/`. No data-writing make target without the owner. Nothing staged or committed by an agent.
**Class:** measured, transform class (rule 4: live since AX-07). Missing stays NULL with a reason, never 0. A card on this mart is AX-28, not this item.

## Why
`data/bronze/telemetry_full/` (car_data per driver) and `data/bronze/pos_data/` carry about 65% more samples than merged telemetry and cover 2018 R Australia where merged data is thin. Position status is always OnTrack, so they give no track-limits signal. Any car-ahead use touches AX-24 (no published number from DriverAhead), so this waits for AX-24.

## Method
Staging models for both channels; a coverage table per session; no published mart until a consumer is named and ruled. Any proximity measure built on pos_data is a new measure and goes through AX-24's reader check.

## Done when
Staging models build in scratch, coverage per session is published in the evidence, and no mart reads them without a named consumer.

## Sources
`transform/models/staging/stg_telemetry_position.sql`, `transform/models/intermediate/int_lap_proximity.sql`, `data/bronze/telemetry_full/`, `data/bronze/pos_data/`.
