# CO-30 — Isolation panel: price the dirty-air tax for thin field-base cells (W10 option 1a)

**Status:** SPEC (build log, item CO-30). Code and tests exist; the refits, CI fixture refresh and rebuilt dev are open. Build log: `status/build-log.json`.

**Group:** 1 data settled · **Depends on:** `CO-17` · **Blocker:** none for the code. Shipping waits on the v17 label version (CO-31, CO-32). Raised 2026-10-24 from watch W10 (owner ruling: option 1a).

**Sources:** `transform/models/intermediate/int_driver_isolation_lap_panel.sql`, `transform/dbt_project.yml` (`isolation_thin_min_air_measured_share`), `transform/models/intermediate/schema.yml` (`is_thin_cell_tax`), `transform/tests/assert_isolation_thin_cell_tax_matches_component.sql`, `transform/tasks/coefficients/fit_constructor_car_fe.py`, `data/fits/constructor_car_fe_isolation.parquet`, `transform/tests/fixtures/fits/`.

**Git state (2026-10-24):** the panel SQL and the `isolation_thin_min_air_measured_share` var are in commit `ac9e798`. The new test `assert_isolation_thin_cell_tax_matches_component.sql` is untracked.

---

## Why

CO-04 left 4,655 isolation laps out of `int_driver_isolation_lap_panel` (T18). They sit in thin field-base cells (fewer than 5 laps), so `int_dirty_air_tax_component` has no row for them and the panel had no tax to subtract. The owner did not accept this as debt (W10, 2026-10-23) and chose option 1a: keep the laps and price the tax inside the panel.

## Method (done in the working tree)

1. A lap with no `int_dirty_air_tax_component` row gets tax = `theta_air` x previous-lap dirty-air share, clamped to [0, 5] s, flagged `is_thin_cell_tax = true`.
2. Only in races where more than `isolation_thin_min_air_measured_share` (0.5) of laps have a measured air state. 2018_1 and 2018_2 (6% measured) stay out.
3. No label move. With `field_restart_adjacent_laps` held at 2, `fct_cliff_prediction_features` matches v16 dev to 1e-6 on every column.

Measured on a scratch copy (2026-10-24): panel 123,085 -> 127,478 rows (+4,393 laps, 3,503 of them followed a car, mean tax 0.264 s, 126 races). Isolation car-FE refit on scratch fits: 1,604 -> 1,619 isolation rows.

## Still open

1. Refit `data/fits/constructor_car_fe_isolation.parquet` (and `constructor_car_fe.parquet`) on the v17 substrate. Do this after the owner commits, not before.
2. Refresh the CI fits fixtures in `transform/tests/fixtures/fits/` from those refits (watch W4 shape; command in `transform/tests/README.md`).
3. Rebuild dev and ship in label version v17 together with CO-31 and CO-32 (D8: not in v16).

## Tests it relies on

- `assert_isolation_thin_cell_tax_matches_component` (new): the in-panel price matches the component's formula where both exist. Its vacuity guard is 1,000 repriced laps on full data and 50 on target `ci` (the fixture measures 91; at 1,000 it failed the fixture build and skipped 158 nodes, fixed 2026-10-24).
- T41 `assert_isolation_base_invariance`, `assert_isolation_field_centring`, `assert_isolation_phase_partition`, `assert_isolation_recovery_share`.
- Schema tests on `int_driver_isolation_lap_panel`, including `is_thin_cell_tax`.
- `pytest transform/tasks/coefficients/tests` (`test_fit_constructor_car_fe.py`, `test_no_vacuous_singular_tests.py`).

## Definition of done

On a rebuilt dev: the tests above pass, the panel row count and the thin-cell lap count are recorded, the isolation refit is in `data/fits/` and the CI fixture fits are refreshed, and the v17 label version records the change. W10 clears only when CO-30 and CO-31 both land and ship in v17 with W11 option C (CO-32). Do not commit; the owner commits.

Step up to `opus-5` if the refit moves a constructor's isolation number by more than its interval.
