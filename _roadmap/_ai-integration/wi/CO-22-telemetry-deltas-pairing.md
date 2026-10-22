# CO-22 — Telemetry deltas: every pair, and unmatched corners read as identical

**Status:** SPEC (nothing run). **Group:** 1 data settled · **Depends on:** none · **Blocker:** none. Raised 2026-10-22 from the transform audit.

**Sources:** `transform/models/marts/fct_telemetry_deltas.sql`, `scripts/export_app_data.py`.

## Problem

- Pairing (about lines 18-28): the `teammates` CTE pairs every driver with every other driver who ran the same lap number in the race. It is not limited to teammates, whatever the name says.
- Zero fill (about lines 37-42): `COALESCE(m_a.x - m_b.x, 0)` writes 0 where one driver has no measurement for a corner, so a missing corner reads as "identical".
- The mart is exported to the app (`scripts/export_app_data.py`, `export_telemetry_deltas`). The app export depends on this fix.

## Method

1. Decide (opus) what the mart is meant to pair: teammates only, or every pair with the pair type recorded. Write the reason here.
2. Keep a delta NULL where either side is missing.
3. Check the app page that reads the export handles NULL.

## Definition of done

Model changed in the working tree; grain and new not-zero-fill checks pass; the app export row count before and after recorded. Do not commit; do not export to the CDN.

## Decision and result (2026-10-23, opus)

**Pairing: teammates only.** A pair is the two drivers one constructor entered in that race (`stg_laps.constructor_id`, which is single-valued per driver per race on dev). Reason: a raw corner delta between two cars is mostly the car, so only a same-car delta measures the driver; the model's header, its schema description ("same-car teammates") and the column docs all already say teammates, so the every-pair join was the bug, not the intent. Every-pair-with-type would also keep ~19x the rows (31,812 pairs vs 1,719) in an export no page reads. 11 race-constructor entries have one driver (DNS/withdrawals) and so no pair.

**NULL, not 0.** The two teammates' `int_corner_metrics` are FULL OUTER joined on (corner, lap), so a corner either driver measured has a row (the old join kept only corners driver_a measured), and each delta is plain `a - b`: NULL where either side is missing or the metric is NULL on one side (no braking point on a flat corner, no full throttle).

**App.** No app page reads `fct_telemetry_deltas` (nothing in `app/src`; the schema says no consumer). `export_telemetry_deltas` does `SELECT *` and needed no change; parquet carries the NULLs.

**Checks.** `not_null` dropped from the three delta columns in `marts/schema.yml`; two singular tests added: `assert_telemetry_deltas_null_when_side_missing` (re-derives each delta from `int_corner_metrics`; the old build fails it on 2.1M rows for `v_min` alone) and `assert_telemetry_deltas_teammates_only`. Grain test (`unique_combination_of_columns`) passes.

**Export row count (scratch copy of dev, not app/public):** before 28,628,356 rows, 31,812 pairs, 8 partitions, 199.9 MB, 0 NULL deltas, 10,480,499 braking deltas exactly 0; after 1,623,427 rows, 1,679 pairs, 8 partitions, 7.8 MB, NULL deltas braking 652,991 / v_min 219,526 / throttle 885,219 (219,526 rows have one side unmeasured), 3,877 braking deltas exactly 0.
