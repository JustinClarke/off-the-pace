---
sidebar_position: 3
title: Methodology
---

# Methodology

How the decomposition is built in practice: the dirty-air attribution, the Kaplan-Meier tyre cliff, and the identification strategy that makes the physics terms separable.

---

## The identification challenge

Each physics term is estimated from lap time data that already contains all the other terms. Fuel, tyre degradation, rubber evolution, weather, constructor pace, and dirty air are all active simultaneously on every lap. Estimating any one term requires holding the others constant; however, you cannot hold them constant without estimates of the others.

The solution is **sequential residualisation**: estimate terms in order of decreasing identifiability, subtract them, and estimate the next term on the residual.

1. **Fuel** first, physically the most constrained. Fuel mass is computable from lap number and circuit length. The weight penalty is calibrated per circuit from clean stints (no safety car, no pit in/out) where tyre age is low enough that the compound term is minimal.

2. **Compound + rubber + ambient** jointly, from the fuel-adjusted residual panel. Compound is identified by stint-level within-driver variation (the same driver on the same tyre compound, same circuit, different age). Rubber and ambient are identified by their time-series signatures: rubber is monotone-increasing over the race, ambient can move either direction.

3. **Constructor** from the compound+rubber+ambient residual, using the panel structure. A constructor's pace is identified by cross-driver variation within the same team in the same race.

4. **Dirty air** from the constructor-adjusted residual, regressed against `dirty_air_share`. The dirty air share is computed from position gaps via `int_lap_air_state`.

5. **Driver residual**: the closure. Everything that remains.

## Tyre cliff: Kaplan-Meier survival analysis

The tyre cliff, the lap at which a compound's grip deteriorates sharply, is not a fixed number. It varies by circuit, compound, ambient temperature, driver weight, and stint history. A Hard compound at Suzuka cliffs much later than a Soft at Bahrain.

The cliff onset $\tau$ is estimated using **Kaplan-Meier survival analysis** on stint populations. Each stint is an "observation" that either reaches the cliff (event) or ends before the cliff (censored). The KM estimator gives the survival function, which is the probability a tyre survives to each lap, and the cliff onset estimate is the median survival time.

This is the same estimator used in clinical drug trials for time-to-event outcomes. The key property: it handles censoring correctly. A stint that pits on lap 18 is not a "missed cliff at lap 18"; it is a censored observation at lap 17. Ignoring censoring would systematically underestimate cliff onset.

The cliff parameters are stored in `dim_compounds_season`, with one row per `(circuit, compound, season)`. The fitter is in `transform/tasks/coefficients/fit_compound_cliff.py`. 401 circuit-compound groups in the current seeds.

## Clean lap filter

Not all laps are usable for coefficient estimation. The `clean_lap_filter` macro excludes:

- Pit-in and pit-out laps (tyre age jump, outlap grip anomaly)
- Safety car laps (artificial pace reduction)
- Virtual safety car laps
- Laps with rain (identified from `stg_weather`)
- Lap 1 (grid effects, multicar incidents)
- Laps flagged in `int_lap_anomaly_flags` (crashes, FCY, etc.)

The `correction_weight` column in `int_lap_residual_decomposed` reflects how clean a lap is. A weight of 1.0 means the lap is fully clean and should be used for training. Partial weights indicate laps with partial interference.

## The teammate baseline

The purest identification of driver skill is within-team: two drivers in the same car, same race, same conditions. The `int_synthetic_teammate` model constructs a synthetic teammate residual by comparing each driver's residual to their teammate's on equivalent laps (same lap number, same compound, same correction weight). This isolates the human contribution more cleanly than the full-panel estimate.

The synthetic teammate signal is exposed in `fct_driver_skill_features` for use in ML.

## What is *not* causal

The decomposition is **attributive**, not causal in the strict do-calculus sense. It says "X seconds of the pace deficit is attributable to dirty air," rather than "if the car had not been in dirty air, it would have been X seconds faster." The counterfactual claim requires additional assumptions about race dynamics that the model does not make.

This is intentional. Attribution is more defensible than counterfactual prediction and is sufficient for the stated purpose: ranking the causes of a pace deficit by magnitude.
