# compound-cliff-2a - Task 2A: price a cell-less lap as unknown, not as zero (DEFERRED)

**Status: DEFERRED.** Not completed and not abandoned. No Task 2A functional change is active in the repository. All functional changes were reverted to baseline `ac3fdd9`. The patch and tests here are kept for reference only. They were not applied, run against real data, or shown to work.

## What Task 2A was meant to change

- Price a lap whose compound-parameter cell is missing as unknown (NULL) instead of a numeric zero (a free tyre).
- Exclude such unpriced laps from `int_field_pace_curve` eligibility.

## Why the functional changes were reverted

NULL for cell-less laps changes values the ML models train on. The field-pace exclusion changes the baseline used in downstream residuals. The five existing ML models would need retraining.

## What would move

- `expected_compound_pace_s` and `expected_degradation_rate_s_per_lap` could become NULL (or change) where they are now numeric.
- Downstream: `int_field_pace_curve`, the lap residuals, `fct_cliff_prediction_features`, and the ML feature list in `ml/src/schema.py` (the `compound` and `cliff_prior` groups).
- That matters to `fct_cliff_prediction_features` and all five ML models: input values, training rows and the residual baseline would shift.

## Before any implementation

A deliberate feature and target impact analysis and an explicit retraining decision are required first.

## Archived files and sha256

```
94cef6f6b9dc06c681522488377c8ad9b844ef2ec9bc935e7e649648f9c98a7c  2a_deferred_tracked.patch
566a174299b9b50d0735017a3a6575ae015495662659616e4d0e94fd351b79d3  tests/assert_compound_cliff_predicted_grain.sql
6319443a266623eac420c5c2da031765d88e3486f0d0225d60af98a71600dfa9  tests/assert_compound_cliff_predicted_missing_cell_unpriced.sql
ba3dffec776b3686bd567af263f72626d552d6d23753045fe32d71013c0cedd8  tests/assert_compound_wear_missing_cell_is_null.sql
b23e55a819efce4c0d7c1a8861eba35120802512ad916a08857c40a17d200cf0  tests/assert_degradation_rate_unchanged_for_missing_cell.sql
5cbec9512f67ab73740107823b1f9443d185017639a6bd2d97e5e3ecb981bb27  tests/assert_field_pace_curve_excludes_unpriced_laps.sql
```

The tests were written for `transform/tests/`. They are not registered there.

## Provenance

Recovered on 2026-11-24 from Claude's temporary scratchpad (temporary, not permanent storage):
`/private/tmp/claude-501/-Users-justin-github-off-the-pace/cafa7cc8-3835-48c0-9a07-5706da459952/scratchpad/2a_deferred_tracked.patch` and `.../2a_deferred_files/transform/tests/`. This folder is now the permanent copy.
