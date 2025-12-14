# Coefficient Fitting Pipeline

This module replaces the hand-edited placeholder values in `seeds/compound_cliff_params.csv`
with empirically fitted coefficients derived from the dbt-built warehouse (`data/dev.duckdb`).

## Why survival analysis?

The naive approach is to fit an OLS regression of `lap_time ~ age_in_stint` and find the
inflection point. This systematically **underestimates** cliff onset for one reason: F1
teams pit *before* the cliff. By the time the race engineer calls the pit, the tyre is
degrading badly but hasn't fully cliffed yet. Every voluntary pit is an "I stopped the
experiment early" event   in survival-analysis language, it is **right-censored**.

If you ignore censoring and treat voluntary pits as complete stints, your regression
sees "no cliff happened by lap X" and concludes X is a typical stint length. This is
wrong. The correct question is: "if drivers *had* stayed out, when would the cliff have
occurred?"   and that requires accounting for censoring.

### The model

We use the **Kaplan-Meier estimator** (nonparametric) to estimate the survival function
`S(t) = P(cliff has not occurred by lap t)`. The **median survival time**   the lap at
which S(t) crosses 0.5   is our estimate of `compound_cliff_onset_laps`.

**Event:** A lap where `lap_time > rolling_5_lap_median + 0.5s` for at least 2
consecutive laps. The continuation requirement filters out single-lap anomalies (track
limits, lock-ups).

**Censoring:** Any stint that ends without observing the event (voluntary pit, end of
race). These contribute information about the *minimum* cliff onset   we know the cliff
hadn't happened yet when the car pitted.

**Forced stops:** DNF, retirement, crash, safety-car pitting   these are treated as
*uncensored* because the team did not choose to pit at that moment. They provide the
cleanest observations of full tyre wear curves.

### Why KM rather than Cox PH?

The plan originally specified Cox PH (parametric hazard model), which would allow
covariates like `track_temp_c` and `compound_code`. KM was chosen for V1 because:

1. **Identifiability:** The dataset is grouped by `(circuit_key, compound_code, season)`,
   so covariates are already stratified. Cox PH would require a shared baseline hazard
   across groups, which doesn't hold across compounds.
2. **Interpretability:** The KM median has a direct physical interpretation
   ("half the stints would have cliffed by lap X"). Cox PH hazard ratios require
   more explanation for a portfolio audience.
3. **Data density:** Some groups have <20 stints   Cox PH with multiple covariates
   would be underpowered. KM is robust to small N.

When more seasons are added (2025+), switching to a stratified Cox PH model to
capture track-temperature effects within compound class would be the logical upgrade.

### Cliff severity

`compound_cliff_severity` is estimated from uncensored stints (observed cliff or
forced DNF) as the average lap-time delta between `[onset, onset+5]` vs
`[onset-5, onset-1]`. The 10th–90th percentile trim removes one-off crash outliers.

### Wear gradient

`compound_wear_gradient` (s/lap of steady-state degradation) uses OLS on the linear
region `[lap 3, cliff_onset-2]`, restricted to stints with R² > 0.10. Low R² stints
indicate variable track conditions or atypical strategies and are excluded.

## Promotion workflow

Running the fitter does **not** immediately update the live seeds. All output goes to
`seeds/_pending/` for human review. The promotion step is deliberate:

```bash
# 1. Fit (writes to seeds/_pending/)
make coefficients-fit

# 2. Inspect the output
open seeds/_pending/compound_cliff_params_pending.csv

# 3. Promote (archives old, installs new)
make coefficients-promote

# 4. Rebuild dbt models that depend on the seeds
make dbt-dev
```

Old seed versions are archived to `seeds/_archive/` with a date suffix so you can
roll back if a fit produces bad results.

## Freshness

The `check_freshness.py` module exits with code 1 if any managed seed's `fit_date`
is older than 365 days. The `dbt-dev-full` Makefile target calls this before `dbt run`
so stale coefficients are surfaced before baking into the warehouse.

A `dbt test` freshness check in `seeds/schema.yml` provides a second line of defence  
it warns (not errors) if `fit_date` in the live seed is old.

## Adding a new compound or circuit

1. Verify the new `compound_code` or `circuit_key` exists in `stg_laps` after ingestion.
2. Run `make coefficients-fit`. The fitter will pick up the new group automatically.
3. If it falls to class defaults (< 8 stints), it will log a warning. This is expected
   in the first season a new circuit or compound appears.
4. Promote and rebuild.
