# CO-31 — Field pace curve: first four green laps after an SC or red flag take their own trimmed mean (W10 option 2b)

**Status:** SPEC (build log, item CO-31). Code and tests exist in the working tree, uncommitted; the v17 baseline re-take, refits and rebuilt dev are open. Build log: `status/build-log.json`.

**Group:** 1 data settled · **Depends on:** `CO-17` · **Blocker:** the v17 re-take of `label_stability_baseline.csv` waits on the owner's commit and the DA-05 label decision (one bump, one snapshot for all of v17). Raised 2026-10-24 from watch W10 (owner ruling: option 2b; keep `field_restart_adjacent_laps = 4`).

**Sources:** `transform/models/intermediate/int_field_pace_curve.sql`, `transform/dbt_project.yml` (`field_restart_adjacent_laps`), `transform/tests/assert_field_pace_restart_cells_own_mean.sql`, `transform/tests/assert_field_pace_honest_range.sql`, `transform/tests/assert_prior_season_labels_frozen.sql`, `transform/seeds/label_stability_baseline.csv`.

---

## Why

After an SC or red flag, the smoothed field base leaned on the third green lap by -0.185 s (100 cells) and on the fourth by -0.051 s against those cells' own trimmed mean (v16 dev). CO-04 left this as debt (T18, W10). The owner ruled option 2b.

## Method (done in the working tree)

1. `field_restart_adjacent_laps` 2 -> 4: the first four green laps after an SC or red flag use their own trimmed mean, not the smoothed curve. With the var at 2 the model reproduces v16 dev to 2.8e-14 s.
2. `assert_field_pace_restart_cells_own_mean` was rewritten to count restart depth on its own (not from the model's flag), and passes at 4.

Measured on a scratch copy (2026-10-24), smoothed minus own trimmed mean, v16 -> v17: lap 3 -0.185 -> 0.000, lap 4 -0.051 -> 0.000, lap 5 +0.077 -> -0.046, lap 6 +0.021 -> -0.030 (both under 0.05 s). 422 field-base cells change. `next_5_lap_cumulative_jump_s` changes on 20,646 of 161,040 laps, row counts unchanged; season means move by -0.024 to +0.007 s.

This moves the label. `assert_prior_season_labels_frozen` FAILS 7 rows on a full dev build until the baseline is re-taken for v17. That failure is expected; do not silence it, and do not set the var back to 2.

## Still open

1. Re-take `transform/seeds/label_stability_baseline.csv` for v17: one label-version bump and one snapshot covering CO-30, CO-31 and CO-32, after the DA-05 label decision. Note it in `dbt_project.yml` beside the v16 re-take note.
2. Refit `data/fits/constructor_car_fe.parquet` and `constructor_car_fe_isolation.parquet` on the v17 substrate, refresh the CI fixture fits.
3. Rebuild dev on the committed code.
4. Owner option: widen to 6 if the lap 5 and lap 6 leans (-0.046, -0.030) matter.

## Tests it relies on

- `assert_field_pace_restart_cells_own_mean` (rewritten), `assert_field_pace_honest_range`, `assert_field_pace_smoothing_respects_boundaries`.
- `assert_prior_season_labels_frozen` (fails 7 rows until the v17 re-take, then must pass).
- `pytest transform/tasks/coefficients/tests`.

## Definition of done

On a rebuilt dev: `dbt build` 0 errors after the v17 baseline re-take, the per-lap bias table above re-measured, label diff recorded per season, refits in `data/fits/`, CI fixtures refreshed. W10 clears only when CO-30 and CO-31 both land and ship in v17 with W11 option C (CO-32). Do not commit; the owner commits.
