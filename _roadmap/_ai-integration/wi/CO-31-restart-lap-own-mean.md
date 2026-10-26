# CO-31 — Field pace curve: first four green laps after an SC or red flag take their own trimmed mean (W10 option 2b)

**Status:** MEASURED (build log, item CO-31, 2026-10-25). Code and tests are committed in `82796dc` and scratch numbers exist; the v16 baseline re-take, refits and rebuilt dev are open and are produced by the CO-33 seal. Build log: `status/build-log.json`.

**Group:** 1 data settled · **Depends on:** `CO-17` · **Blocker:** the v16 re-take of `label_stability_baseline.csv` is CO-33 step 4; it waits on the CO-33 rehearsal and the owner's approval, not on DA-05 (owner 2026-10-25: seal without dirty air). Raised 2026-10-24 from watch W10 (owner ruling: option 2b; keep `field_restart_adjacent_laps = 4`).

**Sources:** `transform/models/intermediate/int_field_pace_curve.sql`, `transform/dbt_project.yml` (`field_restart_adjacent_laps`), `transform/tests/assert_field_pace_restart_cells_own_mean.sql`, `transform/tests/assert_field_pace_honest_range.sql`, `transform/tests/assert_prior_season_labels_frozen.sql`, `transform/seeds/label_stability_baseline.csv`.

---

## Why

After an SC or red flag, the smoothed field base leaned on the third green lap by -0.185 s (100 cells) and on the fourth by -0.051 s against those cells' own trimmed mean (CO-17 dev build, D8's v16 bump). CO-04 left this as debt (T18, W10). The owner ruled option 2b.

## Method (done in the working tree)

1. `field_restart_adjacent_laps` 2 -> 4: the first four green laps after an SC or red flag use their own trimmed mean, not the smoothed curve. With the var at 2 the model reproduces the CO-17 dev build to 2.8e-14 s.
2. `assert_field_pace_restart_cells_own_mean` was rewritten to count restart depth on its own (not from the model's flag), and passes at 4.

Measured on a scratch copy (2026-10-24), smoothed minus own trimmed mean, CO-17 dev build -> window 4: lap 3 -0.185 -> 0.000, lap 4 -0.051 -> 0.000, lap 5 +0.077 -> -0.046, lap 6 +0.021 -> -0.030 (both under 0.05 s). 422 field-base cells change. `next_5_lap_cumulative_jump_s` changes on 20,646 of 161,040 laps, row counts unchanged; season means move by -0.024 to +0.007 s.

This moves the label. `assert_prior_season_labels_frozen` FAILS 7 rows on a full dev build until the baseline is re-taken for the sealed v16 (CO-33). That failure is expected; do not silence it, and do not set the var back to 2.

## Still open

1. Re-take `transform/seeds/label_stability_baseline.csv` for the sealed v16 (CO-33 step 4): one snapshot covering CO-30 and CO-31, not waiting on DA-05. Note it in `dbt_project.yml` beside the 2026-10-24 CO-17 re-take note (which also says v16; see D11).
2. Refit `data/fits/constructor_car_fe.parquet` and `constructor_car_fe_isolation.parquet` on the sealed v16 substrate, refresh the CI fixture fits (CO-33).
3. Rebuild dev on the committed code.
4. Owner option: widen to 6 if the lap 5 and lap 6 leans (-0.046, -0.030) matter.

## Tests it relies on

- `assert_field_pace_restart_cells_own_mean` (rewritten), `assert_field_pace_honest_range`, `assert_field_pace_smoothing_respects_boundaries`.
- `assert_prior_season_labels_frozen` (fails 7 rows until the v16 re-take in CO-33, then must pass).
- `pytest transform/tasks/coefficients/tests`.

## Definition of done

On a rebuilt dev: `dbt build` 0 errors after the v16 baseline re-take, the per-lap bias table above re-measured, label diff recorded per season, refits in `data/fits/`, CI fixtures refreshed. W10 clears when CO-30 and CO-31 both land and CO-33 seals v16 (no longer waits on W11 option C, owner 2026-10-25). Do not commit; the owner commits.
