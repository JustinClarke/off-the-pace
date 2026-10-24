# CO-15 — Monaco 2024 field pace: stop extrapolating the tyre-wear term

**Status:** LANDED in the working tree 2026-10-24 (numbers reproduced on the CO-17 build; commit held for the owner). Build log: `status/build-log.json`, item CO-15.

**Group:** 1 data settled · **Depends on:** `CO-09` (same label version) · **Blocker:** none. `CD9` ruled A (2026-10-22).

**Sources:** `transform/macros/compound_cliff_wear.sql`, `transform/dbt_project.yml`, `transform/models/intermediate/int_compound_cliff_predicted.sql`, `transform/models/intermediate/int_field_pace_curve.sql`, `transform/tests/assert_field_pace_honest_range.sql`, `transform/tasks/coefficients/survival.py`.

---

## Problem

`assert_field_pace_honest_range` fails 15 rows, all race `2024_8` (Monaco), laps 63–77. The field-pace base sits 5–10% below the race's fastest lap for the whole race. Cause (read-only probe, 2026-10-22): `compound_cliff_wear_s` charges `wear_gradient × age` at any tyre age. The slope is fitted on ages 3 to onset−2 and the cliff step is measured by onset+5 (`survival.py`), so past onset+5 the curve was never measured. Monaco 2024 ran one stint after a lap-1 red flag, with tyre ages up to 78. It is charged the full 10 s cap against an observed weight-corrected drift of −1.8 s.

## Method

1. Add dbt var `compound_wear_hold_after_onset_laps: 5.0`, with a comment saying it moves the label.
2. In the macro, hold the linear term's age at onset + hold: replace `age` with `age − GREATEST(laps_past_cliff − hold, 0)`. That equals `LEAST(age, onset + hold)` past the onset and `age` before it, so no call site changes. This is the same "hold, don't extrapolate" rule the cliff plateau already uses.
3. Add two tests (CD9):
   - `assert_compound_wear_not_extrapolated`: no valid lap's wear exceeds its cell's held value.
   - `assert_field_base_drift_tracks_observed` (error): per dry race, wear drift (last-quarter median minus laps 3 to first-quarter median) may not exceed the observed weight-corrected drift by more than 7 s.
4. Keep `assert_field_pace_honest_range`'s 0.920 floor. Do not loosen it.
5. Record the change in the label-version record (`ml/README.md`) as part of CO-09's label version. Do not bump twice.

A proposed diff exists from the probe, **not applied**. Treat it as a draft. The method above is what counts.

- **Copy (use this):** [`_evidence/co-15-2026-10-22/proposed_fix_wear_hold.diff`](../_evidence/co-15-2026-10-22/proposed_fix_wear_hold.diff), with [`PROVENANCE.txt`](../_evidence/co-15-2026-10-22/PROVENANCE.txt). It touches `transform/dbt_project.yml` and `transform/macros/compound_cliff_wear.sql`, and adds the two tests in step 3. sha256 `ce786784…af3d2a`.
- **Original (session scratch, may be gone; if it still exists the copy is redundant):** `/private/tmp/claude-501/-Users-justin-github-off-the-pace/e7074a22-d03f-4724-882d-5fb7a35a514d/scratchpad/proposed_fix_wear_hold.diff`.

## Acceptance (probe numbers, to be reproduced on CO-17's build)

- Honest-range failures: 15 → 0.
- `2024_8` lap 77 field-base ratio to fastest lap: 0.905 → about 0.972.
- Laps on the 10 s wear cap: 323 → 0.
- About 23,973 of 161,040 `int_compound_cliff_predicted` rows change (about 15%, max about 6.3 s). List the per-season counts.
- Both new tests pass. Drift excess: `2024_8` about 4.6 s; the largest is `2020_4` about 6.5 s (watch W8).

## Definition of done

Macro, var and the two tests above in the working tree. Also in the tree, found after the probe, and recorded in the build log: (a) the CO-17 audit made `expected_degradation_rate_s_per_lap` follow the hold, with a third error test `assert_degradation_rate_follows_wear_hold`; (b) the same macro feeds `int_pit_strategy_cost_curve`, whose optimum picks tied, so cost is rounded to 6 dp with an earliest-lap tie rule (2 of 13,045 optima changed). The tests pass on the touched models. The numbers above are reproduced within rounding, and any difference is explained. The label version is recorded jointly with CO-09. Retrain is CO-18; promotion is CD10. Do not commit.
