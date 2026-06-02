---
sidebar_position: 4
title: Out-of-Sample Validation
---

# Out-of-Sample Validation

## Originally conceived as a blind test

The model was trained on 2018–2024 data and all coefficients were frozen before the 2025 season. The intent was a prospective out-of-sample test: freeze, observe, compare.

It is now 2026. The 2025 season is over. OpenF1 has published the data. There is no sealed envelope; it is just a reproducible validation against now-public data that anyone can run and get the same numbers.

The reframe matters: "blind test" was always a framing device to signal statistical discipline. The substance is the same (coefficients trained on 2018–2024 and evaluated on 2025 data the model never saw), but the honest label is **out-of-sample validation**.

## Why out-of-sample discipline matters

Most F1 analytics models are retrospective. They fit 2018–2024 data and describe 2018–2024 outcomes. That is useful but it is compression, not prediction. A model that achieves excellent fit on its training set has not proven it captures the underlying physics; instead, it has proven it has enough parameters to describe the data it trained on.

The test of a generalisable model is prospective: does it forecast outcomes it has not seen? The only way to demonstrate this is to commit to a coefficient freeze before new data arrives, observe new data, and report how far off you were, including when you are far off.

## What was frozen

Before the 2025 season:

- **Compound cliff parameters.** For every `(circuit, compound, season)`, the KM cliff onset estimate, compound severity coefficient, and wear gradient are locked in `transform/seeds/compound_cliff_params.csv`. Not refitted on 2025 data.
- **Constructor structural pace priors.** Panel fixed-effects from 2018–2024. New 2025 data flows through ingestion but the regression does not refit until after Abu Dhabi 2025.
- **Dirty air θ coefficient.** Calibrated on 2018–2024 partial residual panel. Fixed for the validation window.

## The committed evaluation targets

Three targets were committed before the 2025 season.

**Degradation rate accuracy.** Target: RMSE < 0.015 s/lap on `expected_degradation_rate_s_per_lap` across all compound-circuit combinations with ≥ 8 qualifying stints in 2025.

**Cliff onset accuracy.** Target: 70% of circuit-compound combinations within ±3 laps of the 2025 observed median cliff onset.

**Driver residual sign-consistency.** A driver's `driver_skill_residual_s` distribution in 2025 should be sign-consistent with 2024 unless there is a documented car change, team change, or known mechanical explanation.

## Current status

**The 2025 validation run has not been executed yet.** 2025 data is available on OpenF1 but has not been ingested into the Bronze layer. The validation run is planned after the ML component is complete, so that degradation rate predictions use the full model, not just the baseline decomposition.

When the validation is run, the numbers will be published here. The evaluation will report all three targets, including misses.

## How to run it yourself

Once 2025 data is ingested:

```bash
# Ingest 2025 season from OpenF1
python ingestion/src/ingest.py --start-season 2025 --end-season 2025 --sessions R

# Rebuild transform layer (coefficients stay frozen because they are already in seeds)
make dbt-dev

# The 2025 laps appear in fct_lap_residuals alongside 2018-2024
# Evaluation scripts will be in transform/tasks/validation/ (planned)
```

The coefficient seeds are version-controlled. The pre-2025 coefficient state is `git log`-auditable.
