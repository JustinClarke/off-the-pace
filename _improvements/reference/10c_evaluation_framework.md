# 10c Evaluation Framework — Cause-specific metrics without the mixture artefact

**Item:** 10c  
**Status:** MEASURED, and **every number below the § Result summary heading is SUPERSEDED** — see the correction block immediately following.  
**Objective:** Stop quoting AFT NLL on a mixture as though it were a headline. Evaluate the model with metrics that don't have the scoring-artefact problem.

> ## ⚠ Correction — 2026-09-10, by `10d`. The results in this document were measured in-sample.
>
> `evaluate_10c.py` loaded the shipped `ml/models/stint_life_regressor_v11.bst` and scored it on
> the `cv_final_fold` eval rows. `train.py` refits the shipped booster on **every** training
> season and `training_seasons` is 2018–2024; **the eval fold is 2024**. The eval set was inside
> the booster's own training data, so every metric in § Result summary measures memorisation.
>
> Reproduced exactly before anything was built on the repair: an all-seasons refit under the 10b
> label, scored on the 2024 rows, returns green-pit Brier **0.141216**, AUC **0.844167**, slope
> **1.231641** — this document's 0.1412159702194419 / 0.8441673881692147 / 1.2316409494909957 to
> six decimal places, with the 5-bin table matching row for row.
>
> | green-pit | published here (in-sample) | honest refit (2018–2023 → 2024) |
> |---|---:|---:|
> | time-dependent AUC | 0.844 | **0.691** |
> | IPCW-Brier | 0.141 | **0.206** |
> | calibration slope | 1.232 | **0.666**, 95% [0.463, 0.906] |
>
> **The slope does not merely shrink — it crosses 1.0, so this document reported the
> miscalibration with the wrong sign.** "The model over-predicts stint life" survives; "observed
> risk exceeds predicted and the gap widens *as risk rises*" does not — out of sample the gap is
> widest at the *low*-risk end and the risk score is over-dispersed, not compressed.
>
> **What survives.** The § Metric corrections are real repairs to `survival.py` and stand
> unchanged — the metrics were never the problem, the model being scored was, and their 26
> regression tests still pass. § Do not quote the overall row stands. The § Is the 1.23 slope a
> model defect, or an SC-selection artefact? conclusion stands on a re-run: out of sample,
> zero-SC races 0.6555 (n=7,588) vs SC races 0.7823 (n=1,682) vs all races 0.6664 — both strata
> well below 1.0, so selection still does not explain the defect. Only its sign changed.
>
> **What does not survive.** The headline (0.844 / 0.141 / 1.23), the per-horizon tables, the
> D-calibration table, the zero-SC/SC table's numbers, and the description of the artefact as
> "the 10b-trained model" — the `.bst` was rewritten by a `standard`-variant retrain
> (`stint_life_regressor_v11_20260910T092333.json`) after this ran, so re-running the script
> afterwards scored a different model again.
>
> **Repaired.** `evaluate_10c.py` now refits on the training side by default and keeps the
> shipped-booster path only as a labelled `in_sample` diagnostic, printed beside the headline as
> an optimism gap. Full working: [`../work/10-competing-risks.md`](../work/10-competing-risks.md)
> § 10d — Verdict.

## The problem

10b confirmed that separating causes moves NLL by -0.028 (Gate 1 passed). But NLL on an AFT model that mixes two processes (tyre-limit survival + exogenous interruptions) is biased as a headline:

- The mixture weights vary by cause
- NLL aggregates both processes' likelihoods equally
- Reporting a delta on a mixture metric obscures what we're actually measuring

## The solution: Cause-specific evaluation with dependence-aware metrics

### 1. Metrics that fit the framing

Instead of NLL (which conflates processes), measure survival discrimination directly:

- **IPCW-Brier**: Inverse Probability Censoring Weighted Brier score
  - Measures predicted vs observed event rates at specific time horizons
  - Accounts for censoring via Kaplan-Meier weighting
  - Lower is better; 0 is perfect

- **Time-dependent AUC**: Concordance at time horizons
  - Among pairs where one observed event by time t and one is at-risk, does the model rank them correctly?
  - Extends Harrell's C to multiple time points
  - Higher is better; 0.5 is random

- **D-calibration**: Observed vs expected event rates by predicted risk group
  - Splits population by predicted risk, compares KM estimate to AFT prediction
  - Calibration slope should be ≈1 (perfect agreement) or ≈0.9-1.1 (good)

### 2. The dependent-censoring caveat

**SC arrival is not independent of tyre state.** Race state correlates with both:
- Tyre degradation determines safety-car likelihood (more degraded tyres → longer stints → more likely to be active when SC deployed)
- Safety-car arrival correlates with race state, which correlates with tyre state by construction

IPCW estimates are biased under dependent censoring. Standard approach: instead of claiming to have "fixed" it, **bracket the estimates across a band of dependence strengths**:

- Estimate dependence strength from censoring-rate variation across causes
- Use copula-based sensitivity analysis to bracket IPCW estimates
- Report the band, not a point estimate

This is the same bracketing house style `ceiling.py` already uses for its oracle.

## Definition of done

1. ✓ IPCW-Brier computed at multiple time horizons
2. ✓ Time-dependent AUC computed at the same horizons
3. ✓ D-calibration slope reported — green-pit only; **not assessable** for the other causes (no uncensored events under the 10b variant)
4. ~ Per-cause metrics reported separately — reported, but only green_pit is *computable*; see § What the per-cause rows can and cannot say
5. ~ Dependent-censoring sensitivity band **stated** as a caveat, not resolved — stated qualitatively; the band is **not quantified** (no copula analysis run)
6. ✓ The stint-life headline says **which cause** it is about — see § Headline

## Causes and their interpretation

From `10a`:

- **green_pit** (n=3,621): Stint ended in a tyre change under green. Tyre-limit distribution, no confounding.
- **sc_pit** (n=806): Stint ended in a tyre change under safety car. Tyre-limit, but truncated by deployment.
- **vsc_pit** (n=223): Stint ended in a tyre change under virtual safety car. Same as sc_pit.
- **red** (n=387): Stint ended under red flag (race stopped). Censored by race event, not pit decision.
- **race_end** (censored): Stint was the driver's last of the race (classified). No tyre change; uncensored → right-censored.
- **retirement** (censored): Driver retired. No tyre change; censored → right-censored.

**Green-pit is the cleanest signal** — it's the tyre-limit distribution without deployment confounding. SC/VSC endings are truncated (the pit wall stopped when the flag flew, not when the tyre was spent). Red flag is a race-level event. Censored endings are by definition right-censored.

## What this does NOT do

- **Resolve** dependent censoring. IPCW is still biased; we're making the bias visible.
- **Replace** the gates framework. 10c is an evaluation arm, not a feature test, so it does not run gates 1-7. But it declares its metrics and methodology in advance.
- **Gate the finding**. The -0.028 NLL delta from 10b is what it is; 10c reports it in a framework that fits the data structure.

## References

- `10-competing-risks.md` § 10c: Evaluation that fits the framing (the spec this document operationalizes)
- `10-competing-risks.md` § 10a: The end-regime label (the cause grouping)
- `10b_measurement_results.md`: The 10b measurement and its honest delta
- `R3-competing-risks.md`: The original measurement that opened this item

## Result summary

> **SUPERSEDED — read the correction block at the top of this file first.** Everything from here
> to § Metric corrections was measured with the 2024 eval rows inside the scored booster's
> training set. Kept as the record of what was published and how far off it was; **do not quote
> any figure below as a headline.** The honest replacements are in the correction block and in
> [`../work/10-competing-risks.md`](../work/10-competing-risks.md) § 10d.

Model `stint_life_regressor_v11`, `cv_final_fold` — the split says train 2018-2023, eval 2024, but the booster that was scored had been fitted on 2018-**2024**, which is the defect. Counts are **eval-fold laps**, not stints (the 10a stint counts in § Causes are all-seasons and are not the same denominator).

### Headline (in-sample — superseded)

> **Tyre-limit survival (green-pit endings) is predicted with time-dependent AUC 0.844 and IPCW-Brier 0.141**, on 9,270 eval-fold laps. Calibration slope is **1.23** — the model systematically over-predicts stint life, and does so more at the high-risk end.

| Metric | green_pit | race_end | sc_pit | vsc_pit | retirement | red | *overall* |
|---|---|---|---|---|---|---|---|
| n (laps) | 9,270 | 9,528 | 904 | 287 | 264 | 19 | *20,272* |
| Uncensored events | 9,270 | 0 | 0 | 0 | 0 | 0 | *9,270* |
| IPCW-Brier | **0.141** | n/a | n/a | n/a | n/a | — | *0.093* |
| Time-dep AUC | **0.844** | n/a | n/a | n/a | n/a | — | *0.924* |
| Cal slope | **1.23** | n/a | n/a | n/a | n/a | — | *1.24* |

`n/a` = no uncensored events, so the metric is not defined. `—` = below the n≥20 floor. *Overall is diagnostic only — see below.*

Green-pit per-horizon (deciles 10-90 of observed event times):

| | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 |
|---|---|---|---|---|---|---|---|---|---|
| IPCW-Brier | 0.093 | 0.140 | 0.154 | 0.169 | 0.171 | 0.166 | 0.152 | 0.132 | 0.096 |
| Time-dep AUC | 0.807 | 0.819 | 0.825 | 0.833 | 0.842 | 0.851 | 0.858 | 0.867 | 0.894 |

Green-pit D-calibration (5 risk bins, shared horizon = median observed time):

| Predicted risk | 0.110 | 0.282 | 0.442 | 0.603 | 0.781 |
|---|---|---|---|---|---|
| Observed (KM) | 0.169 | 0.237 | 0.490 | 0.737 | 0.946 |

Observed risk exceeds predicted in 4 of 5 bins and the gap widens with risk — consistent with slope 1.23. **This is a real miscalibration, not noise**, and it is the most actionable thing 10c produced: the model is too optimistic about how long stints last, worst for the stints it already flags as fragile.

*Why 1.23 is trustworthy rather than an artefact of the repaired estimator* — **the reasoning below is sound and the conclusion drawn from it was still wrong.** The estimator is unbiased where it is applied, so the 1.23 is not the metric's. It is the *scoring set's*: the rows were in the booster's training data. An unbiased estimator applied to an in-sample prediction returns an honest measurement of memorisation. This paragraph ruled out the metric and then read that as having ruled in the model, which does not follow. Original text follows: fed data drawn from the lognormal AFT the metric assumes — so calibration is correct by construction — the fixed `d_calibration` returns slope **1.03** at 0% censoring, 0.98 at 20%, 0.93 at 40% (`ml/tests/test_survival.py::test_d_calibration_recovers_a_slope_near_one_when_well_specified`). The green-pit stratum has **no censoring within it**, which is the 1.03 case. The estimator is unbiased where it is being applied, so the 1.23 is the model's, not the metric's.

### Do not quote the overall row

Under the 10b variant, `green_pit` is the **only** uncensored cause — all 9,270 uncensored events are green-pit, and every other cause is 100% censored by definition. So the overall row scores green-pit events against an at-risk pool that is 54% non-green, and those causes differ in length *by construction*:

| cause | mean stint length (laps) |
|---|---|
| race_end | 26.4 |
| green_pit | 20.4 |
| vsc_pit | 18.5 |
| sc_pit | 12.5 |
| retirement | 12.3 |
| red | 5.3 |

`race_end` stints are long because they ran to the flag; `red` stints are short because the race stopped. A model can score well on the overall row by separating *cause membership*, which is available from race state, without understanding tyre limits at all. That is the same mixture artefact 10c was created to remove, wearing a different metric — which is why overall (0.924) sits well above green-pit (0.844). **The 0.844 is the defensible number.**

### What the per-cause rows can and cannot say

Only green-pit yields metrics. For every other cause the 10b variant sets all endings to censored, so there are no events to score and IPCW-Brier / AUC / calibration are undefined — the evaluation script records this rather than emitting a number. This is correct behaviour but it does mean **10c did not deliver per-cause comparison**; it delivered one clean stratum and five empty ones. Comparing tyre-limit survival *across* causes needs a cause-specific hazard that treats each cause as its own event in turn, which is not what 10b trained.

### Is the 1.23 slope a model defect, or an SC-selection artefact?

**A model defect.** This was the open question the dependence caveat left hanging, and it had to be answered before "fix the calibration" could mean anything — recalibrating the model to match a filtered sample would bake the filter's bias into the gauge permanently.

A stint only *becomes* green-pit if no safety car diverted it first, so the green-pit stratum is a filtered sample and the filter is plausibly related to tyre wear. But **races in which no stint ended under SC or VSC had no diversion at all**, so within them green-pit is an unfiltered sample of the tyre-limit distribution. If the miscalibration is a selection artefact it must weaken there. It does not:

| green-pit stratum | n (laps) | cal slope | AUC | IPCW-Brier |
|---|---|---|---|---|
| **Zero-SC races (no diversion possible)** | 6,822 | **1.224** | 0.845 | 0.139 |
| SC races (diversion occurred) | 2,448 | 1.267 | 0.844 | 0.146 |
| All races (headline) | 9,270 | 1.232 | 0.844 | 0.141 |

**The conclusion of this section survives; the numbers in the table above do not.** Re-run out of
sample by 10d, the same argument still goes through — both strata sit far below 1.0, so a filter
that was supposed to explain the miscalibration does not:

| green-pit stratum | n (laps) | races | cal slope (honest) | AUC (honest) |
|---|---:|---:|---:|---:|
| **Zero-SC races (no diversion possible)** | 7,588 | 16 | **0.6555** | 0.6917 |
| SC races (diversion occurred) | 1,682 | 8 | 0.7823 | 0.6902 |
| All races | 9,270 | 24 | 0.6664 | 0.6914 |

The slope is flat across the split, and discrimination is identical to three decimals. Cluster bootstrap over races on the zero-SC stratum (races as the resampling unit, 200 draws, per 05c's gate-3 substitute): **mean 1.222, sd 0.071, 95% interval [1.098, 1.363], 0 of 200 draws below 1.0.** The interval excludes 1.0.

*Caveat on that interval:* the zero-SC stratum holds only **14 races**, and cluster bootstraps on so few clusters run anti-conservative, so read the interval as indicative rather than exact. The finding does not rest on it — it rests on the point estimate being unmoved (1.224 vs 1.267) across a split that would have to move it if selection were the cause.

**Consequence:** the model genuinely over-predicts stint life, and the fix belongs in the model rather than in the evaluation. This does *not* dispose of the dependence caveat for the IPCW-Brier and AUC figures — it answers one specific question the caveat raised.

### Dependence band: not quantified

Stated, not resolved — and deliberately not given a number. An earlier draft of this run reported "dependence strength 1.2×" derived from the spread in cause-specific censoring rates. That figure was withdrawn: under the 10b variant cause *determines* censoring status, so those rates are 0/1 by construction and their spread measures the censoring definition, not the dependence between censoring and tyre state. It also fed a band of `τ ∈ [0, min(0.5, ·)]`, which returns `[0, 0.5]` for any input.

The caveat that remains is qualitative and real: SC/VSC arrival is not independent of tyre state, so the green-pit IPCW estimates carry an unmeasured bias. Green-pit is the *least* exposed stratum (it has no censoring within it), but "least exposed" is not "unbiased". Quantifying the band needs an instrument for SC arrival and is outstanding work — see 07a, which is building exactly that first stage.

## Metric corrections (2026-09-10, post-measurement)

The first run of this item produced metrics that did not measure what they claimed. Found and fixed before the numbers went anywhere:

1. **D-calibration was a tautology.** `d_calibration` evaluated each row's survival curve at *its own* predicted median, so `z = (log(pred+shift) − log(pred+shift))/scale ≡ 0` and predicted risk was exactly 0.5 for every row, regardless of prediction. All five risk bins collapsed into one and the slope came back `null`. The observed side had the matching flaw — KM evaluated at each bin's own median, which pins every bin near 0.5 and flattens the observed axis. Both now use a shared horizon. *This is why the original note's "calibration slope ≈1 (unbiased)" was unsupported: there was no slope, only one degenerate point at the median. The true slope is 1.23, i.e. meaningfully miscalibrated.*
2. **IPCW-Brier was not IPCW.** Both branches of its `if censored / else` were byte-identical, and weights depended only on a row's own time, never on the horizon. Rows censored before `t` were scored as though they had failed by `t`. Now weighted per Graf et al. — `1/G(T_i)` for events before `t`, `1/G(t)` for rows still at risk, censored-before-`t` rows dropped.
3. **Time-dependent AUC counted ties as discordant** (`pred[e] < pred[r]` only, ties still in the denominator), and `y == t` put a row in both the event and at-risk sets. Ties now take half credit; at-risk is strictly `y > t`. Also vectorised — the O(n²) Python double loop was ~750M iterations.
4. **`dependence_strength` withdrawn** — see above.

Corrected green-pit AUC 0.844 vs 0.829 before; Brier unchanged at 0.141; overall Brier moved 0.116 → 0.093 on the weighting fix.
