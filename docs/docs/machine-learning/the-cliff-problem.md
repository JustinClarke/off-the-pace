---
sidebar_position: 2
title: The cliff problem
---

# The cliff problem

A tyre does not lose grip linearly. It holds a working window, then **falls off a cliff** a few laps where pace collapses by a second or more. Strategy lives and dies on calling that cliff: pit a lap early and you concede track position; pit a lap late and you bleed the race away on dead rubber.

---

## Why the statistical prior is not enough

The [methodology](/understand/methodology) layer fits a Kaplan-Meier survival curve per `(circuit, compound, season)` and stores the median cliff onset in `dim_compounds_season`. That is the right tool for a *population* question and it feeds the decomposition's compound term honestly.

But it answers the average case. The real cliff for a given stint shifts with:

- **thermal history**-how hard the tyre has been pushed (`push_residual`, cumulative surface/bulk load),
- **dirty air**-laps spent in another car's wake overheat the surface (`dirty_air_thermal_load_*`),
- **ambient and air density**-a hot, thin-air afternoon cliffs earlier,
- **fuel load**-a heavy car early in the stint loads the tyre differently,
- **compound generation**-2018 legacy compounds behave unlike the 2019+ range.

These interact. A linear correction per dimension cannot capture "Soft, lap 14, after six laps in dirty air, on a hot low-grip surface." Gradient-boosted trees can which is the entire reason for the machine layer.

## The three questions, three target families

The machine layer predicts three distinct things from the **same** per-lap feature row:

### 1. Next-lap degradation *how much pace, with what confidence*

`next_lap_degradation_jump_s`: the fuel-corrected pace change the **next** lap will show, in seconds. It is bounded to `[−10, 10]` and is legitimately **negative ~44%** of the time a tyre coming into its window, or recovering after an out-lap, genuinely *gains* pace. (An early spec assumed this target was strictly positive; the data disproved it see deviation D5 in the model card.)

Because a point estimate hides risk, this is modelled as a **quantile trio** `p10` / `p50` / `p90` so strategy sees a median *and* a calibrated `[p10, p90]` band.

### 2. Laps until the cliff *when*

`laps_until_cliff_class`, a 4-way bucket: `0_to_2`, `3_to_5`, `6_plus`, `none_in_stint`. The class balance (eligible, non-null) is roughly 58 / 15 / 15 / 12, so the classifier trains with **balanced class weights** to keep the rare imminent-cliff windows from being drowned out.

### 3. Remaining stint life *how long*

`remaining_stint_life_laps`: a synthesised, non-negative count of usable laps left in the stint. Useful for the strategy view's "this set is done in ~N laps" readout.

## Where the data comes from

Every target and feature is one row of [`fct_cliff_prediction_features`](/reference/models/fct/fct_cliff_prediction_features) the contracted, lap-grain feature mart. Ground truth is **137,373 laps across 2018–2024** (7 seasons); after eligibility filtering, **110,440 rows** carry both the degradation and cliff targets, and **116,957** carry stint-life.

The targets are *forward-looking by construction* (they describe future laps), which makes leakage the central risk of the whole exercise. How that risk is contained is the subject of [Validation & the leakage spine](/machine-learning/validation-and-leakage); what the model actually sees is [The feature pipeline](/machine-learning/feature-pipeline).
