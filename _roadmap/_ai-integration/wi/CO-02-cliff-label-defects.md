# CO-02 — Cliff label defects

**Group:** D carry-over · **Depends on:** none · **Blocker:** none. `CD2` ruled C (2026-10-15): 2018 is fitted on its own data.

**Sources:** `transform/tasks/coefficients/survival.py`, `fit_compound_cliff.py`, `transform/macros/compound_cliff_wear.sql`, `transform/models/intermediate/int_compound_cliff_predicted.sql`, `transform/seeds/compound_cliff_params.csv`, `transform/dbt_project.yml`.

**Audit findings:** 1, 2, 9 (SQL and macro headers only), T1, T2; T6 as a check-run.

This changes the training label. The version bump is recorded once, in CO-03, together with CO-04's label changes. It is not a silent fix.

---

## What exists today (checked 2026-10-15)

1. **T1, wear subtracted twice.** `estimate_cliff_severity` (`survival.py:197-278`) evaluates the pre- and post-cliff regression lines at the same age (onset + 2.5), so its result already excludes wear. `cliff_plateau_s` in `compound_cliff_wear.sql` still subtracts `5.5 × wear_gradient`. The docstring at `survival.py:210-211` ("replicates the window-mean approach") is false: on linear data with a step, the window mean includes 5.5 laps of wear and the regression gap does not.
2. **T2, defaults replace real fits.** `fit_compound_cliff.py:406-409` replaces any severity under 0.1 s (or over 1.5 s) with a class default of 1.2–1.5 s. Severity source by season: 2018 62/62 class default; 2019 41/61; 2020 25/51; 2021 17/61; 2022 10/63; 2023 11/66; 2024 9/71.
3. **Finding 1, 2018 never refit.** All 62 2018 rows equal the 09-28 seed numerically and are class defaults for both onset and severity. The +0.37 s offset that compensated was removed (`dbt_project.yml:244` is `{}`), so 2018 ratings carry the over-correction again. Under FD3 (point-in-time), 2018 has no earlier season to fit from, hence `CD2`.
4. **Finding 2, 2025 rows stale.** 61 of 64 are `carried_forward`, and none equals the current 2024 values (Abu Dhabi MEDIUM: 0.97 in 2025, 0.31 in 2024). They match the 10-03 archive. The fitter's default `--seasons` is 2018–2024, so 2025 was never fitted.
5. **Finding 9 (code half).** The headers of `compound_cliff_wear.sql` and `int_compound_cliff_predicted.sql:7-22` describe the old window-mean severity.

## Method

1. **T6 check-run first.** Count detected-cliff stints dropped because onset < 5 leaves under 2 pre-cliff laps, and how much severity moves if the pre-line needs 3 laps. Material if more than 5% of cliff stints are dropped or any season's median severity moves more than 0.05 s. If material, fix it here; if not, record the numbers and stop.
2. Remove the double wear subtraction so the plateau uses the severity as fitted. Fix the docstring and both headers (finding 9, code half).
3. Keep fitted severities under 0.1 s (a measured "little or no cliff"). Fit 2018 on 2018's own data (`CD2` = C, a declared one-season exception to FD3) instead of the hand-set class default. Every other season, and 2025, stays fitted on earlier seasons only. Label the 2018 rows `data_window` as an in-sample fit.
   - **Consequence of CD2 = C:** 2018 labels use 2018's own laps, so 2018 is in-sample. Say so wherever 2018 appears (seed, docs, model card), and never use 2018 for any honest evaluation (validation folds, gates, headline metrics). Anything else with no usable fit still follows the class-level handling already in the fitter; do not widen the exception.
4. Fit 2025 point-in-time (on 2018–2024) rather than carrying rows forward. Write the right `data_window` label on refit rows.

## Acceptance

- Simulated stint: plateau equals the true step to within 0.05 s.
- No seed row says "carried forward" unless it equals its source row exactly (test).
- Severity source per season, before and after, is recorded.

## Output

Per season: mean cliff term before/after, cells by severity source, labels moved by more than 0.5 s; the T6 numbers.

## Definition of done

Seed refit and label rebuilt on dev; the numbers above are in the log. Retraining is CO-03. Do not commit.
