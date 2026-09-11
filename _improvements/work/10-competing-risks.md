# 10 — Competing risks in the stint-life target

**Group:** 10 · **Depends on:** `10a` before `10b` before `10c` · **Shares its label with `02d`**

Opened 2026-09-07 out of research round R1. The strongest finding of that round, and the only one
where a settled statistical framework maps onto a **measured** defect in a shipped model.

Full evidence: [`../research/R3-competing-risks.md`](../research/R3-competing-risks.md).
Do not re-derive it.

**The claim in one line.** `schema.py` frames remaining stint life as single-event right-censored
survival. But "uncensored" is not one event — a stint ends for several reasons, and only one of
them is a statement about the tyre.

**Verified.** Of 5,360 uncensored stints, **1,543 (28.8%) end under safety car, VSC or red flag.**
They run **11.14 / 17.04 / 5.34 laps** respectively against green's **19.44**. Present in every
season (19.2–38.9% non-green). The AFT fit is therefore a mixture of a tyre-wear process and an
exogenous-interruption process, with a circuit- and season-varying mixture weight.

**Corrected by `10a`:** 325 of those 5,360 are not stints at all but 2018 laps FastF1 never
assigned a stint number, and 127 of them are non-green. On real stints the share is **1,416 /
5,037 = 28.1%**, and 2018 drops from 26.0% to 17.4%. The claim stands; the 2018 row did not.
See `10a`'s correction table below.

**Corroboration, Assumed rather than Verified.** In `ml/model_card.yml`'s `dual_importance`,
`age_in_stint` is in **neither** top-5 for `stint_life_regressor`, while the two models predicting
pace and cliff state both carry it prominently. What sits at the top instead is `fuel_mass_kg` and
`lap_number` — near-collinear, i.e. the **race clock**. That is the fingerprint a mixture of
tyre-limit and deployment-timing events predicts. Importance rankings are not causal and
`lap_number` correlates with tyre age by construction; carry both caveats whenever it is quoted.

**And the input is not the problem.** `age_in_stint` is FastF1's `TyreLife` passed through
untouched, 0.21% missing, and every within-stint step is exactly +1 across 154,378 transitions.
See [`../notes/tyre-life-provenance.md`](../notes/tyre-life-provenance.md). This is a **target**
problem. Nobody should re-open the data question.

---

## 10a — The end-regime label — **LANDED 2026-09-08**

**Objective.** One column: why did this stint end?

**Method.** Classify each stint's final lap from `int_stint_geometry`'s `is_red_flag_lap` /
`is_safety_car_lap` / `is_vsc_lap`, crossed with `is_censored_stint`, into
{green-pit, sc-pit, vsc-pit, red, race-end, retirement}. Precedence must be declared, not
inherited from whatever order the CASE happens to be written in — red before SC before VSC is what
the R3 measurement used.

**`02d` needs the same label.** Build it once, use it twice; sequence the two together.

**Acceptance.** The label exists at stint grain, its precedence rule is written down, and its
distribution reproduces R3's table.

**Definition of done.** A later reader can tell, for any stint, why it ended and how confidently.

### What landed

`transform/models/intermediate/int_stint_end_regime.sql`, one row per `stint_id`, 8,333 rows.
`fct_stint_features` now carries `end_regime`, `stint_end_cause` and `end_cause_confidence`
alongside `is_censored_stint`, so `10b` is a change to label construction in `ml/src` and nothing
else. Guarded by 19 schema tests on the model and 5 on the mart's passthrough columns, plus
`transform/tests/assert_stint_end_cause_partition.sql`, which re-derives the label independently
of the model's own CTEs — a different route to the final lap, the censoring window and the
running-at-the-flag test rebuilt from staging — so it fails on drift rather than moving with it.

**Two facets, not one, and they are not redundant.**

- `end_regime` ∈ {green, safety_car, vsc, red_flag} — the track regime in force on the stint's
  final lap, emitted for **every** stint including censored ones. Crossed with
  `is_censored_stint` it reproduces R3's 2×4 table exactly, cell for cell, counts and mean
  lengths both.
- `stint_end_cause` — the six-class answer, which folds the regime into the censoring split.

Splitting them is what lets the cause label do the honest thing on a censored stint without
losing the measurement R3 rests on.

### The precedence rule, as declared

1. **Censoring outranks regime.** A censored stint is the driver's last of the race, so it did not
   end in a tyre change whatever was flying at the time; its causes are `race_end` and
   `retirement`. The regime is still recorded in `end_regime`, so nothing is lost. The 2021
   Belgian GP — stopped and abandoned under red flag, 20 drivers classified after 3 laps — comes
   out `race_end` with `end_regime = 'red_flag'`, which is the true pair of facts. This is what
   makes the taxonomy's own shape work: four uncensored causes, two censored ones, six.
2. **Within an uncensored stint, severity decides:** `red_flag` > `safety_car` > `vsc` > green.
   Not academic — `TrackStatus` is a concatenated digit string, and **346 final laps carry more
   than one code**: 276 red+SC, 53 SC+VSC, 17 red+VSC. Reorder the CASE and those 276 change
   class with nothing else failing, which is what the singular test exists to catch.
3. **Within a censored stint, the classified result decides.** Running at the flag →
   `race_end`, else `retirement`. The test is on `status` ('Finished', '+N Lap(s)', 'Lapped'),
   not on `is_classified`: 23 'Retired' rows *are* classified because the driver covered 90% of
   the distance, and they stopped. Disqualification is the one status that hides the answer — a
   post-race ruling, not a reason a stint ended, landing on drivers who ran to the flag and on
   drivers who did not — so it is resolved on distance instead, and marked `inferred`.

### How confidently — `end_cause_confidence`

| value | n | what it means |
| :--- | ---: | :--- |
| `observed` | 7,593 | every input read, nothing chosen |
| `inferred` | 415 | severity precedence had to choose (346), the pit marker is missing on an uncensored stint (328, overlapping), or disqualification hid the answer |
| `unassigned_stint` | 325 | not a stint — see below. `stint_end_cause` is NULL here |

### Correction to R3's numbers — the artefact stints

**Verified.** 325 of the 8,333 "stints" are built from the 343 laps FastF1 never assigned a stint
number, all in 2018, mean length 1.06 laps. `fct_stint_features` already sorted them below every
real stint so they come out *uncensored*, and R3 counted them: **127 of them are non-green**.
They are not stints and their ending has no cause, so `stint_end_cause` is NULL on them and they
are excluded from any share.

That moves two of R3's numbers and leaves the finding standing:

| | R3, as written | corrected | note |
| :--- | :--- | :--- | :--- |
| non-green share of uncensored | 1,543 / 5,360 = **28.8%** | 1,416 / 5,037 = **28.1%** | headline barely moves |
| 2018 non-green share | 818 stints, **26.0%** | 495 stints, **17.4%** | entirely artefact |
| 2018 mean length, green | 16.6 | **24.0** | 1-lap artefacts were dragging it |
| 2018 mean length, non-green | 6.9 | **15.5** | same |

No other season contains an unassigned-stint row, so 2019–2024 are unchanged and 2018 stops being
the outlier it appeared to be. R3's headline claim — that the AFT fit is a mixture of a tyre-wear
process and an exogenous-interruption process, present in every season — survives intact.

### Deviations from this doc, logged

- **The label is not built inside `fct_stint_features`.** The method above said "crossed with
  `fct_stint_features.is_censored_stint`". Instead `int_stint_end_regime` **owns**
  `is_censored_stint` — the definition moved down out of the mart, which now reads it back — and
  the mart's output is bit-identical on that column (8,333/8,333 against an independent
  recomputation; 2,973 censored, unchanged). "Build it once, use it twice" applied to the
  censoring window too, rather than leaving `02d` a second copy to drift from. This doc's method
  paragraph is corrected above.
- **Two extra columns beyond the six-class label**: `end_regime` (so R3's table stays
  reproducible) and `end_cause_confidence` (the "how confidently" the definition of done asks
  for). Plus provenance — `end_lap_id`, `end_lap_number`, `end_lap_in_stint`,
  `is_multi_regime_end`, `ended_on_pit_lap`, `was_running_at_flag`.
- **The family is `strategy`, not a new `survival` family.** `transform_docs_facts.py` fixes the
  intermediate vocabulary at five families, and `int_sc_hazard_history` — the model `02d` rebuilds
  — already sits in `strategy`.

### What `10b` reads

`stint_end_cause = 'green_pit'` is the tyre-limit set: 3,621 stints, mean 20.44 laps. Everything
else uncensored — `sc_pit` (806, 12.48), `vsc_pit` (223, 18.47), `red` (387, 5.34) — is what
`10b` recodes to censored.

---

## 10b — The cause-specific arm

**Objective.** Test whether separating the causes buys anything, cheaply, before anything
expensive is built.

**Method.** Keep `survival:aft`. Refit with **non-green endings treated as censored** — the
interval label already supports it; this is a change to label construction, not to the model
class. That fit estimates the *tyre-limit* distribution, which is the quantity the app's gauge
claims to show. Compare against the incumbent under
[`../foundations/gates.md`](../foundations/gates.md), delta against the family's **own** reseed
floor.

**This is a genuine test, both ways.** If the recoded fit does not move NLL beyond the floor, the
reframing closes on a measurement and `10c` never runs.

**Declare the e-value construction before running** (`09b`).

**Acceptance.** Gate steps 1–3 run in full; the delta is quoted with its floor ratio.

**Definition of done.** A written verdict: does splitting the causes move the family, or not.

---

## 10c — Evaluation that fits the framing

**Objective.** Stop quoting AFT NLL on a mixture as though it were a headline.

**Method.** Cause-specific IPCW-Brier and time-dependent AUC, plus a calibration check
(D-calibration, or the 2025 A-calibration variant which handles censoring less conservatively).

**And state the dependent-censoring caveat rather than assuming it away.** SC arrival correlates
with race state, which correlates with tyre state, so censoring is **not** independent — under
which IPCW-weighted Brier and the concordance index are themselves biased. The literature's
recommended treatment is a copula-based sensitivity analysis: bracket it across a band of
dependence strengths rather than claiming to have fixed it. That is the same bracketing house
style `ceiling.py` already uses for its oracle.

**Acceptance.** Cause-specific metrics reported with the dependence band, never as a point.

**Definition of done.** The stint-life headline says which cause it is about.

### Verdict — MEASURED 2026-09-10

Full results and the per-horizon tables: [`../reference/10c_evaluation_framework.md`](../reference/10c_evaluation_framework.md).

**The headline, and it names its cause:** tyre-limit survival on green-pit endings is predicted
with **time-dependent AUC 0.844** and **IPCW-Brier 0.141** (9,270 eval-fold laps, 2024).

**The finding worth acting on is the calibration, not the discrimination.** Green-pit calibration
slope is **1.23** — observed risk exceeds predicted in 4 of 5 risk bins and the gap widens as risk
rises (at the top bin, predicted 0.78 against observed 0.95). The model **over-predicts stint
life, and is worst on the stints it already flags as fragile**. That is a live defect in the
quantity the app's gauge shows, and it is a better lead than 10b's -0.028 NLL.

**Three things this item did not deliver, stated plainly:**

1. **No per-cause comparison.** Under the 10b variant green-pit is the only uncensored cause, so
   the other five strata have no events to score and their metrics are undefined. 10c produced one
   clean stratum and five empty ones. Comparing survival *across* causes needs a cause-specific
   hazard treating each cause as its own event in turn — which 10b did not train.
2. **The dependence band is not quantified.** Only stated. An earlier draft's "dependence strength
   1.2×" is **withdrawn**: cause determines censoring status under 10b, so cause-specific censoring
   rates are 0/1 by construction and their spread measures the definition, not the dependence.
   Quantifying it needs an instrument for SC arrival — which is what `07a` is building.
3. **The `overall` row is not a headline and must not be quoted** (Brier 0.093, AUC 0.924). It
   scores green-pit events against an at-risk pool that is 54% non-green, and the causes differ in
   length by construction (`race_end` 26.4 laps mean, `green_pit` 20.4, `red` 5.3). A model scores
   well there by separating *cause membership* — the same mixture artefact this item exists to
   remove, in a new metric. It is kept as a diagnostic and labelled as one in the artefact.

**Metric repairs were needed first.** Three of the metrics did not measure what they claimed;
`d_calibration` was a tautology returning 0.5 for every row, `ipcw_brier` ignored the horizon in
its weights, and `time_dependent_auc` counted ties as discordant. All fixed in `ml/src/survival.py`
and the item re-run before any number was used downstream. Superseded figures: green-pit AUC 0.829,
overall Brier 0.116, overall AUC 0.916, and the unsupported "calibration slope ≈1 (unbiased)".
Detail in the reference doc's § Metric corrections.

---

---

## 10d — Fix the stint-life calibration defect

**Objective.** The model over-predicts how long tyres last. Fix that, in the model.

**Depends on** [`10c`](#10c--evaluation-that-fits-the-framing) for the finding, and
[`08k`](08-foundations-repair.md#08k--rebuild-the-model-artefacts-against-the-post-08j-32-feature-contract)
because this item retrains and re-exports `stint_life_regressor` and that cannot be validated
against a red ONNX-parity and manifest-contract suite.

**The finding.** Green-pit calibration slope **1.232**. Observed risk exceeds predicted in 4 of 5
risk bins and the gap widens as risk rises:

| model says stint is this likely to be over | it actually is, this often |
| ---: | ---: |
| 0.110 | 0.169 |
| 0.282 | 0.237 |
| 0.442 | 0.490 |
| 0.603 | 0.737 |
| **0.781** | **0.946** |

The bottom row is the problem. On stints the model has already flagged as fragile it is wrong in
the dangerous direction — it reports life left in a tyre that is essentially finished. This is the
quantity the app's gauge shows, so the defect is user-visible.

**It is the model's, not the sample's.** This had to be settled first, because green-pit is a
*filtered* stratum — a stint only becomes green-pit if no safety car diverted it — and
recalibrating a model to match a filtered sample would bake that filter's bias in permanently.
Races with **zero SC/VSC endings** had no diversion, so green-pit within them is unfiltered. The
slope does not move:

| stratum | n (laps) | slope | AUC |
| :--- | ---: | ---: | ---: |
| Zero-SC races (no diversion possible) | 6,822 | **1.224** | 0.845 |
| SC races (diversion occurred) | 2,448 | 1.267 | 0.844 |
| All races | 9,270 | 1.232 | 0.844 |

Race-level cluster bootstrap on the zero-SC stratum (200 draws, per `05c`'s gate-3 substitute):
mean 1.222, sd 0.0714, 95% interval **[1.098, 1.363]**, 0 of 200 draws below 1.0. That stratum
holds only **14 races** and cluster bootstraps on so few clusters run anti-conservative, so treat
the interval as indicative — the finding rests on the point estimate being unmoved across a split
that would have to move it if selection were the cause.

**Method — the constraint, not the recipe.** Fix the fit. Do **not** post-hoc recalibrate against
the green-pit evaluation sample, for the reason above. Candidate directions, none of them ruled on
yet: the AFT scale parameter, the label construction 10b introduced, or a distributional
assumption that does not fit a target with skewness −0.829 and excess kurtosis 5.218 (`R2`).
Re-measure with `ml/src/evaluate_10c.py`, whose metrics are now under regression test.

**Acceptance.** Gates 1–7 per [`../foundations/gates.md`](../foundations/gates.md). The 1.23 is a
**measurement** and has not been gated; the fix that follows from it must be. Report the slope with
its bootstrap interval, not as a point.

**Definition of done.** A written verdict on whether the slope moves toward 1.0 without costing
discrimination (AUC 0.844 is the incumbent), and either a landed fix or a recorded reason the
defect is not addressable at this model class.

**Note for [`02b`](02-feature-expansion.md).** Its pre-flight requires 5-reseed noise floors for
`stint_life_regressor`. Those must be measured **after** this lands, or they are measured against a
model that is about to change.

### Pre-registration — arms and e-value (gates 6 and 7)

Written 2026-09-10, before any arm was scored on the 2024 eval fold.

**The instrument, first (gate 1).** `evaluate_10c.py` as written loads the *shipped*
`stint_life_regressor_v11.bst`, which `train.py` refits on **every** training season — 2018–2024 —
and scores it on the `cv_final_fold` eval rows, which are 2024. The eval fold is inside that
booster's training set, so every 10c number is in-sample. The honest instrument refits on the
training side of the split only (`EV._evaluation_split` → `EV._fit` on `split.X_tr`, exactly as
`evaluate.py::evaluate_target` already does) and scores 2024 out of sample. Both are measured below;
the honest one is the baseline every arm is compared against.

**Headline for this item.** Green-pit calibration slope on the 2024 eval fold, out of sample, with a
200-draw race-level cluster bootstrap interval (`05c`'s gate-3 substitute). Secondary: green-pit
time-dependent AUC and IPCW-Brier. "Toward 1.0" is scored as a decrease in `|slope − 1|`.

**Arms.** Every arm is selected on the **training side only** — expanding season folds inside
2018–2023. Nothing is selected on the 2024 rows; that is the constraint the method section sets, and
it is what keeps this a fit change rather than a post-hoc recalibration against the eval sample.

| arm | what moves | selection signal (train-side inner CV) |
| :--- | :--- | :--- |
| **A0** | nothing — the incumbent, refit honestly | — (baseline) |
| **A1** | `aft_loss_distribution_scale` ∈ [0.30, 1.40] | inner-fold green-pit \|slope − 1\|, ties broken on inner-fold AFT NLL |
| **A2** | `aft_loss_distribution` ∈ {normal, logistic, extreme} | XGBoost's own `aft-nloglik` on the inner folds, each distribution at its own A1 scale |
| **A3** | label construction ∈ {standard, 10b} | inner-fold green-pit \|slope − 1\| |
| **A4** | capacity: `max_depth` ∈ {3,4,5,6,8} × `n_estimators` ∈ {200,400} | inner-fold green-pit \|slope − 1\| |

**Gate 4 is inapplicable in its literal form and the substitute is stated rather than skipped.** The
permutation null row-shuffles *new columns*. No arm here adds a column: A1, A2 and A4 change how the
same feature matrix is fitted, and A3 changes only the label bounds. Capacity is therefore identical
between every arm and A0 — the nuisance parameter gate 4 exists to remove is exactly zero by
construction, not by assumption. The substitute null is the **reseed null**: arm and incumbent refit
at the same five seeds, under H₀ ("the change carries no information about calibration") the paired
delta is mean-zero.

**Gate 3 floor.** Five seeds, 20260528–20260532, varying XGBoost's `seed` (which drives `subsample`
and `colsample_bytree`, so the refits genuinely differ — 10b's zero-variance reseed table came from
not varying it). Floor = `2*sqrt(2)*sd` of the green-pit calibration slope across those five,
measured on the incumbent family, per `attribution.py::refit_noise_floor`.

**E-value — Construction A, declared now.** From
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) §3.

- **Null.** H₀: the arm's change carries no information about green-pit calibration, so the paired
  reseed delta below is mean-zero.
- **Delta, oriented so positive is improvement.**
  `delta = |slope(A0) − 1| − |slope(arm) − 1|`, both measured on the 2024 green-pit stratum.
- **Scale.** `s = c * sqrt(2) * sd` with **`c = 1.5`**, `sd` the gate-3 reseed sd above. `c = 1.5`
  and not 1.0 because `sd` is a five-seed plug-in and §3's stated hole applies: validity is
  **conditional on σ ≤ s** and that condition is stated here rather than hidden.
- **Betting fraction.** `lambda = 2 / c = 1.333`, growth-rate optimal against `delta* = F`.
- **Result.** `E = exp((2 / c^2) * (z − 1))` with `z = delta / (sqrt(2) * sd)`, i.e.
  `E = exp(0.8889 * (z − 1))`.
- **Family.** Four declared arms (A1–A4). All four are counted in the campaign family and reported
  with their `E`, `E < 1` included. Campaign-level decisions run e-BH per gate 7.

**Seeds.** 20260528, 20260529, 20260530, 20260531, 20260532. Bootstrap seed 20260910, 200 draws,
races as the resampling unit.

### Verdict — MEASURED 2026-09-10

**The defect this item was created to fix does not exist as described. The 1.232 is an in-sample
number, and out of sample the slope is 0.666 — on the other side of 1.0.** The instrument was
scoring a booster on rows that were inside its own training set. Gate 1 caught it, which is what
gate 1 is for.

#### 1. Gate 1 — the instrument, and what it was actually measuring

`evaluate_10c.py` loaded `ml/models/stint_life_regressor_v11.bst` and scored it on the
`cv_final_fold` eval rows. `train.py` refits the shipped booster on **every** training season and
`training_seasons` is 2018–2024; the eval fold **is** 2024. Every 10c number was in-sample.

Reproduced exactly, which is how the provenance was settled. Refitting on all seasons under the 10b
label and scoring the 2024 rows returns green-pit **Brier 0.141216, AUC 0.844167, slope 1.231641**
against 10c's published 0.1412159702194419 / 0.8441673881692147 / 1.2316409494909957 — six decimal
places, and the 5-bin table lands on 10c's `0.110 0.282 0.442 0.603 0.781` → `0.169 0.237 0.490
0.737 0.946` row for row.

Two further facts fell out of that check:

- **`evaluate_10c.py` no longer scored the model 10c reported.** The `.bst` was rewritten by a
  `standard`-variant retrain (training log `stint_life_regressor_v11_20260910T092333.json`,
  `censoring_variant: "standard"`) *after* 10c ran, so re-running the script today returned
  0.834378 / 1.234564 — the *standard*-variant in-sample refit, to six decimals. 10c's own
  description of the artefact as "the 10b-trained model" was already false by the time it was read.
- **The hyperparameters were never fitted for this problem.** `tune.py` calls
  `F.load_features(target=target)` with the default `censoring_variant="standard"`, and folds over
  `bundle.training_seasons` = 2018–2024, so `max_depth: 8` and `aft_loss_distribution_scale: 0.8`
  were selected against the *other* label construction, on the mixture NLL 10c said not to use as a
  headline, with 2024 in the validation set.

The honest instrument refits on the training side only (`EV._evaluation_split` → `EV._fit` on
`split.X_tr`, the path `evaluate.py::evaluate_target` already uses) and scores 2024 out of sample.
The optimism it was hiding, on identical eval rows, is not a rounding error:

| green-pit | honest | in-sample | optimism |
| :--- | ---: | ---: | ---: |
| time-dependent AUC | **0.6914** | 0.8344 | +0.1429 |
| IPCW-Brier | **0.2059** | 0.1407 | −0.0652 |
| calibration slope | **0.6664** | 1.2346 | +0.5682 |

The slope does not merely shrink across that gap — it **crosses 1.0**, so the in-sample run reported
the miscalibration with the wrong sign. Every downstream statement built on it inherits that.
**`AUC 0.844` is not the incumbent. `0.691` is.**

**10c's selection check has to be re-run, and it survives.** The zero-SC / SC split was the evidence
that the miscalibration was the model's and not the sample's, and it was measured in-sample like
everything else. Out of sample it still holds, in the new direction: zero-SC races slope 0.6555
(n=7,588, 16 races), SC races 0.7823 (n=1,682, 8 races), all races 0.6664. Both strata sit well
below 1.0. Selection does not explain the defect — that conclusion of 10c's is unaffected, only its
sign is.

#### 2. The honest baseline, with its interval

Refit 2018–2023, scored on 2024, 10b labels, tuned v11 params. Race-level cluster bootstrap, 200
draws, 24 eval races:

> **Green-pit calibration slope 0.666, 95% [0.463, 0.906]** — 99.5% of draws below 1.0.
> Time-dependent AUC 0.691. IPCW-Brier 0.206.

Gate-3 reseed floor, five seeds with XGBoost's `seed` genuinely varied (10b's zero-variance reseed
table came from not varying it, so `subsample` and `colsample_bytree` drew identically every time):
slope sd **0.006208**, floor `2*sqrt(2)*sd` = **0.017559**; AUC sd 0.001256, floor 0.003554.

#### 3. The arms

Every arm selected on the training side only. `delta = |slope(A0) − 1| − |slope(arm) − 1|`.

| arm | slope | boot 95% | delta | × floor | AUC | ΔAUC | × AUC floor | Brier |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **A0** incumbent | 0.6664 | [0.463, 0.906] | — | — | 0.6914 | — | — | 0.2059 |
| **A1** scale 0.90 | 0.6883 | [0.465, 0.947] | +0.0219 | 1.25× | 0.6843 | −0.0071 | 1.99× | 0.2084 |
| **A2** normal | *selected the incumbent* | | 0 | 0 | | | | |
| **A3** standard labels | 0.7000 | [0.444, 0.933] | +0.0336 | 1.91× | 0.6935 | +0.0021 | 0.60× | **0.1903** |
| **A4** depth 3 / 200 | 0.8791 | [0.584, 1.220] | +0.2127 | 12.11× | 0.6871 | −0.0043 | 1.21× | 0.2100 |
| A4x depth 2 / 200 † | **1.0735** | [0.704, 1.446] | +0.2601 | 14.81× | 0.6826 | −0.0088 | 2.47× | 0.2150 |
| C2 standard + depth 2 † | 1.0476 | [0.669, 1.448] | +0.2860 | 16.29× | 0.6739 | −0.0175 | 4.94× | 0.1993 |

† **Undeclared.** The pre-registered A4 grid was `max_depth ∈ {3,4,5,6,8}`; depth 2 and the
cross with the `standard` label are extensions added after seeing the monotone trend, logged here
rather than folded into the declared arm. They are counted in the family and reported, but the
declared A4 winner is depth 3.

**A1 — the AFT scale is not the lever, and this is the clearest negative of the four.** Across
0.30→1.40, a 4.6× range, the train-side inner-fold green-pit slope moves only 0.537→0.622 and never
reaches 0.63. On 2024 the best scale buys +0.022 of slope for −0.007 of AUC (2.0× the AUC floor) —
it pays more in discrimination than it returns in calibration. The inner-CV NLL optimum under the
10b label is 0.90, not the shipped 0.80, so the scale *is* mis-set; it just does not matter here.

**A2 — the distributional assumption is not the lever either, and R2's skew statistic was measured
on the wrong quantity.** Screened on XGBoost's own `aft-nloglik` over the inner folds, each
distribution at its own swept scale: **normal 1.8364** (scale 0.90) beats extreme 1.8650 (0.90) and
logistic 1.8876 (0.70). The arm selects the incumbent, so nothing needs plumbing through
`laps_from_margin`, the ONNX export and `app/src/ml/survival.ts` — which is worth knowing, because
`extreme` would have needed all three (its standardised median is `log(log 2) = −0.3665`, not 0, so
`exp(margin)` stops being the median). The reason the direction fails: skewness −0.829 and excess
kurtosis 5.218 are properties of the **target in laps**, and the AFT does not assume that quantity is
normal — it assumes the *log-scale residual* is. Measured, that residual has skew **−0.443** and
excess kurtosis **−0.063**. It is already close to normal on the scale the model actually uses.

**A3 — the label construction is worth revisiting, but not for the slope.** `standard` and `10b` are
indistinguishable on slope (0.700 vs 0.666, delta 1.9× floor, paired interval straddling zero), but
`standard` is **better on green-pit Brier, 0.190 vs 0.206**, better on the level bias (mean log
residual −0.285 vs −0.434) and costs no AUC. 10b's label change, whose original +0.179 NLL was
already withdrawn as a 92.6% scoring artefact and restated as −0.028, makes green-pit *worse* out of
sample on the metric 10c chose as its headline. That is a finding about 10b, not about 10d, and it
is recorded here for whoever rules on 10b.

**A4 — capacity is the lever, and the relationship is monotone.** Train-side inner CV, 10b labels,
scale 0.90:

| max_depth | 2 | 3 | 4 | 5 | 6 | 8 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| inner-fold slope | 0.794 | 0.708 | 0.680 | 0.669 | 0.656 | 0.622 |
| inner-fold NLL | 1.8171 | 1.8090 | 1.8078 | 1.8130 | 1.8188 | 1.8364 |

The slope rises as depth falls, and inner-CV NLL **also** improves — the shipped `max_depth: 8` is
worse on the training folds' own headline metric, which is what you expect from hyperparameters
selected under a different label construction. The mechanism is visible in the fit: the standard
deviation of the margin over the green-pit eval rows falls 0.642 → 0.509 → 0.418 as depth goes
8 → 3 → 2. The incumbent's risk score was over-dispersed relative to its real skill, which is
exactly what a slope below 1.0 means.

#### 4. Gate 7 — the e-values, and why they should not be believed at face value

Construction A as declared, `c = 1.5`, `lambda = 4/3`, `sd = 0.006208`, `E = exp(0.8889*(z−1))`:

| arm | delta | z | E |
| :--- | ---: | ---: | ---: |
| A1 scale 0.90 | +0.0219 | 2.50 | 3.78 |
| A2 normal | 0 | 0.00 | **0.41** |
| A3 standard | +0.0336 | 3.83 | 12.4 |
| A4 depth 3 | +0.2127 | 24.2 | 9.3 × 10⁸ |
| A4x depth 2 † | +0.2601 | 29.6 | 1.1 × 10¹¹ |
| C2 standard + depth 2 † | +0.2860 | 32.6 | 1.5 × 10¹² |

**Those last three are not evidence at that strength and the construction is what is wrong, not the
arithmetic.** The pre-registered scale is the reseed sd, which measures **refit** noise — how much
the slope moves when only XGBoost's seed changes. The uncertainty that actually governs a slope
estimated from 24 races is **sampling** noise, and the cluster bootstrap puts that at sd ≈ 0.10–0.19,
**16–30× larger**. Feeding a scale 25× too small into `exp()` is how you get 10¹¹. Reported as
declared, per gate 7, and then read correctly: on the instrument that matches the estimand, the
paired race-cluster bootstrap — both arms scored on the *same* resampled races, so the shared
race-draw noise cancels — the deltas straddle zero:

| arm | paired delta | 95% | P(improves) |
| :--- | ---: | :--- | ---: |
| A1 scale 0.90 | +0.0211 | [−0.0101, +0.0549] | 0.870 |
| A3 standard | +0.0212 | [−0.0721, +0.1334] | 0.630 |
| A4 depth 3 | +0.1726 | [−0.1389, +0.3103] | **0.945** |
| A4x depth 2 † | +0.1695 | [−0.3081, +0.4029] | 0.855 |

`gates.md` already says the floor and the e-value are two instruments and must be allowed to
disagree in public. Here a third disagrees with both, and it is the one to believe: **the capacity
fix clears the reseed floor by 12×, returns E ≈ 10⁹, and still cannot be established at 95% on 24
races.** The floor is not wrong about refit noise; it is being asked a question it does not answer.

#### 5. Gate 4 — inapplicable, and stated rather than skipped

No arm adds a column. A1, A2 and A4 change how the same 32-feature matrix is fitted; A3 moves only
the label bounds. Capacity is identical between every arm and A0, so the nuisance parameter the
permutation null exists to remove is exactly zero **by construction**, not by assumption. The
substitute declared in the pre-registration — the five-seed reseed null — was run and is §2's floor.

#### 6. The trade-off that was not anticipated: the slope moves, the bias does not

This is the part that matters for the gauge, and it is the reason this item does not close as a win.

| | predicted risk → observed risk, 5 bins | mean log bias | intercept |
| :--- | :--- | ---: | ---: |
| A0 depth 8 | 0.058→0.330 · 0.186→0.386 · 0.345→0.492 · 0.512→0.590 · 0.732→0.780 | −0.434 | +0.271 |
| A4 depth 3 | 0.096→0.303 · 0.210→0.407 · 0.320→0.523 · 0.434→0.588 · 0.604→0.757 | −0.524 | +0.192 |
| A4x depth 2 | 0.115→0.279 · 0.218→0.447 · 0.301→0.509 · 0.397→0.595 · 0.533→0.749 | −0.560 | +0.180 |

Reducing capacity fixes the **dispersion** of the risk score and leaves the **level** where it was —
the calibration intercept only moves +0.271 → +0.180, and the mean log-scale bias gets *worse*,
−0.434 → −0.560. Observed risk still exceeds predicted in all five bins at every depth. Restated in
the brief's own terms: the original complaint was "the model says 0.781 and the tyre is finished
0.946 of the time". Honestly measured that reads "the model says **0.533** and the tyre is finished
**0.749** of the time" — a ~22-point gap in the same dangerous direction, and **none of the four
declared arms closes it.**

That residual bias is not obviously a defect at all. Under the 10b label the model estimates the
**latent tyre limit**, and green-pit endings are realisations that stopped at or before it, so a
median above the observed green-pit ending is what the framing *predicts*. The app's gauge reads
that latent quantity to a user who interprets it as a realised stint — which is precisely the
product question the closing section of this doc raises and does not settle. It is also why A3's
Brier is better: `standard` targets the realised ending, which is what the gauge claims to show.

#### 7. Answering the item's definition of done

**Does the slope move toward 1.0?** Yes, and materially: 0.666 → **1.074** at depth 2 (declared
winner depth 3: **0.879**), a 78% reduction in `|slope − 1|`, and both bootstrap intervals now
contain 1.0 where the incumbent's excluded it in 99.5% of draws.

**Without costing discrimination?** Nearly. Against the honest incumbent AUC of 0.691 — not the
in-sample 0.844 — depth 3 costs 0.0043 (1.2× the AUC reseed floor) and depth 2 costs 0.0088 (2.5×).
Small, real, and priced.

**Landed?** No, deliberately, and this is a judgment call that should be reviewed:

1. The paired bootstrap cannot establish the improvement at 95% on 24 eval races. Overwriting the
   shipped booster on a 0.945-probability result is exactly the kind of move `04a`'s multiplicity
   finding exists to discourage.
2. The right fix is not a hand-picked `max_depth`. §1 shows the whole tuned parameter set was
   searched under the `standard` label, on the mixture NLL, with 2024 in the validation folds. Depth
   is the symptom the calibration slope happened to expose; a re-search under the honest split and a
   metric that is not the mixture NLL is the actual repair, and it is a separate item.
3. §6 says the level bias — the part that is dangerous for the gauge — survives every arm. Shipping
   a slope fix while that stands would move a number the app shows without fixing what it shows.

**Landed instead:** the instrument. `ml/src/evaluate_10c.py` now refits on the training side by
default and keeps the shipped-booster path only as an explicitly labelled `in_sample` diagnostic,
printed beside the headline as an optimism gap so the failure cannot recur silently. The 26
`ml/tests/test_survival.py` regression tests are untouched and pass — the metrics were never the
problem, the model being scored was.

**Follow-ups this opens.** (a) Re-run `tune.py` for `stint_life_regressor` under the honest split
and the chosen label, on a metric that is not the mixture NLL. (b) Rule on 10b with A3's numbers in
hand: `standard` beats `10b` on green-pit Brier out of sample. (c) Settle the product question in
§6 before any recalibration of the level — it is a question about what the gauge should mean, not a
statistical one. (d) `02b`'s note still stands and is now sharper: its `stint_life_regressor` noise
floors must not be measured until (a) resolves.

**Recorded 2026-09-10, on close-out.** Follow-up (a) is now item [`10e`](#10e--re-tune-stint_life_regressor-under-the-honest-split) below, and `02b` waits on it in the log. (b) is appended to `10b`'s note in `build-log.json`, where whoever rules on that item will read it. (c) is decision **D5**; whether to ship the depth fix in the meantime is decision **D4**. 10d is staged `MEASURED`, not `GATED` — gate 4 was substituted rather than run, and `gates.md` is explicit that an item which skips a step is `MEASURED`, never `GATED`.

---

## 10e — Re-tune `stint_life_regressor` under the honest split

**Objective.** The hyperparameters were never fitted for this problem. Fit them.

**Depends on** [`10d`](#10d--fix-the-stint-life-calibration-defect) for the finding and for the
repaired instrument. **Blocks** [`02b`](02-feature-expansion.md)'s noise-floor pre-flight.

**The defect in the search, as `10d` established it.** `tune.py` calls
`F.load_features(target=target)` with the default `censoring_variant="standard"` and folds over
`bundle.training_seasons` = 2018–2024. So the shipped `max_depth: 8` and
`aft_loss_distribution_scale: 0.8` were selected

1. under the **other** label construction,
2. on the **mixture AFT NLL** that `10c` ruled out as a headline, and
3. with **2024 inside the validation folds** — the season everything downstream evaluates on.

All three are wrong for the quantity the app's gauge shows. This is the repair `10d`'s verdict
names as the real one; depth was only the symptom its calibration slope happened to expose.

**What the search will find, already measured.** Capacity is the lever and the relationship is
monotone — and the shipped setting loses on the training folds' *own* metric, which is the
signature of a search run under the wrong label:

| `max_depth` | 2 | 3 | 4 | 5 | 6 | 8 (shipped) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| inner-fold green-pit slope | 0.794 | 0.708 | 0.680 | 0.669 | 0.656 | 0.622 |
| inner-fold NLL | 1.8171 | 1.8090 | 1.8078 | 1.8130 | 1.8188 | **1.8364** |

The AFT scale is mis-set too (inner-CV optimum 0.90 under the 10b label against the shipped 0.80),
though `10d` priced that as not mattering for calibration.

**Method — the constraint, not the recipe.** Re-run `tune.py` for `stint_life_regressor` with the
folds confined to the **training side** of `cv_final_fold` so 2024 stays out, the censoring variant
chosen deliberately rather than by default, and a selection metric that is **not** the mixture NLL —
green-pit IPCW-Brier and `|calibration slope − 1|` are the two `10d` used. Re-measure with
`ml/src/evaluate_10c.py`, whose honest mode is now the default and whose metrics carry 26
regression tests.

**Do not hand-pick a depth.** That is exactly what `10d` declined to land, and for the reason in its
§7: a single parameter chosen by eye on 24 eval races is not a repair to a search that was run
wrongly. If the re-search lands on depth 3 by itself, that is a result; asserting it is not.

**Settle [D5](../status/build-log.json) first if you can.** It decides which label this tunes
against, and it is a product question, not a statistical one. `10d`'s A3 arm is the evidence in
hand: out of sample `standard` beats `10b` on green-pit Brier, **0.190 vs 0.206**, with no AUC cost.

**Watch the level bias.** `10d` §6 found that capacity fixes the **dispersion** of the risk score
and leaves the **level** — intercept +0.271 → +0.180, mean log bias *worsening* −0.434 → −0.560,
observed risk above predicted in all five bins at every depth. A re-search that optimises the slope
alone will reproduce that, and the level is the half that is dangerous for the gauge.

**Acceptance.** Gates 1–7 per [`../foundations/gates.md`](../foundations/gates.md). Report the slope
with its race-level cluster bootstrap interval, never as a point — and note the standing limit:
24 eval races could not establish `10d`'s 0.17 slope improvement at 95%, so a result resting on the
same 24 races inherits the same ceiling.

**Definition of done.** A tuned parameter set selected under a split and a metric that both match
the estimand, with a written verdict on what it costs and buys against the honest incumbent
(green-pit slope 0.666, AUC 0.691, Brier 0.206) — or a recorded reason the search does not move it.

### D5 is settled, and it sets the label — recorded 2026-09-10

**The realised stint ending**, i.e. the `standard` censoring/label construction, not `10b`'s latent
tyre limit. The gauge says "remaining stint life: N laps" and a user reads that as the realised
answer, deployments included; that is also the pit wall's own decision quantity. It is the side the
numbers already favour — `10d`'s A3 arm scored `standard` better than `10b` on out-of-sample
green-pit Brier (0.190 vs 0.206) at no AUC cost, and the latent framing's level bias *worsens*
as the slope is fixed (−0.434 → −0.560). "Show both" was considered and set aside: it roughly
doubles this item and adds app work. **10e tunes against `standard`.**

One consequence for the numbers below. The incumbent named in the definition of done — slope 0.666,
AUC 0.691, Brier 0.206 — is the incumbent *under the `10b` label*. The like-for-like baseline for a
`standard`-label re-search is `10d`'s A3 row, reproduced here as **A0**: slope 0.700, AUC 0.694,
Brier 0.190. Both are reported; A0 is the one the arms are scored against.

### Pre-registration — arms, space and e-value (gates 6 and 7)

Written 2026-09-10, **before any trial ran**. Everything below is selected on the training side of
`cv_final_fold` (seasons 2018–2023); nothing is selected on 2024.

**The split, exactly.** `EV._evaluation_split` puts train on 2018–2023 and eval on 2024. The
re-search's inner CV is `train._season_folds` over the **training side only**, `n_splits=4` on six
seasons — expanding whole-season windows, first train 2018–2019 validating 2020, last train
2018–2022 validating 2023. Four folds and not five because five over six seasons opens with a fold
trained on 2018 alone; four reproduces production's own shape (first train = two seasons) inside the
shorter window. The eval season never enters a fold. This is the defect `10d` named: today's
`tune.py` folds over `bundle.training_seasons`, which is 2018–**2024**.

**The label, explicitly.** `censoring_variant="standard"`, passed rather than defaulted. It happens
to equal `load_features`' current default; the point is that it is now a stated choice and appears in
the run's own record, because `10d` showed the default is what made the shipped search wrong for
`10b` and right for `standard` by accident rather than by decision.

**The space.** `tune.SEARCH_SPACE ∪ tune.SURVIVAL_SPACE` as widened for open item 21, with **one
declared change: `max_depth` low bound 3 → 2.** `10d` measured inner-fold slope rising monotonically
as depth falls and its best arm sat at depth 2, outside the shipped space — a search that cannot
propose the value its own predecessor found best is a search stopped on its edge before it starts.
The bound moves in `tune.py` (the same file the item 21 widening moved) rather than being patched per
run. Every other range is untouched.

**Arms.** Two searches, differing only in what they select on. Both run 60 TPE trials seeded with
`S.RANDOM_STATE`, MedianPruner as production, over the identical folds.

| arm | selection objective (mean over the four inner folds) | why it is declared |
| :--- | :--- | :--- |
| **A0** | — (baseline: shipped v11 params, refit honestly under `standard`) | the incumbent |
| **S1** | green-pit **IPCW-Brier** ↓ | a proper scoring rule; scores level *and* dispersion, and it is the metric on which `standard` already beat `10b` |
| **S2** | green-pit **\|calibration slope − 1\|** ↓ | the metric `10d`'s winning arm used — declared separately precisely to test this doc's own warning that optimising the slope alone leaves the level where it is |

Neither objective is the mixture AFT NLL. It is reported per selected config as a diagnostic only,
so the shipped `max_depth: 8` can be checked against the training folds' own former headline.

**Boundary handling, declared in advance.** `tune.boundary_params` names any parameter that comes back
on an edge. If either search stops on one, the probe past that bound is run and reported **as a
declared extension of that arm**, not folded into it — `10d`'s A4x/C2 were added after seeing the
trend and had to be marked undeclared, and this is the cheap way not to repeat that.

**What is reported for every arm.** Green-pit calibration slope with a 200-draw **race-level cluster
bootstrap** interval (seed 20260910, races the resampling unit, 24 eval races), time-dependent AUC,
IPCW-Brier, and — because this is the half `10d` found survives every fix — the **level**
diagnostics: calibration intercept, mean log-scale bias, the 5-bin predicted→observed table, and the
sd of the log-scale prediction. A slope that improves while the mean log bias worsens is reported as
exactly that.

**Gate 3 floor.** Five seeds, 20260528–20260532, varying XGBoost's `seed` (which drives `subsample`
and `colsample_bytree`, so the refits genuinely differ), measured on **this family's own** label
construction — `standard`, not `10b`. `10d`'s floor was measured under `10b` and `gates.md` is
explicit that a floor is not borrowed across families. Floor = `2*sqrt(2)*sd` per
`attribution.py::refit_noise_floor`.

**Gate 4, and an honest correction to how `10d` stated it.** The permutation null row-shuffles *new
columns*; no arm here adds one, so it is inapplicable in its literal form and the declared substitute
is the paired reseed null. But `10d` also wrote that "capacity is identical between every arm and A0
… by construction". For a hyperparameter re-search that is **false**: `max_depth` and `n_estimators`
*are* capacity, and capacity is the entire content of the arm. So there is no information/capacity
decomposition to run here, and the e-value's null below is stated as what it actually is — "no
difference beyond refit noise" — rather than as an information null it cannot be.

**E-value — Construction B, declared now.** From
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) §4, which that
document calls the default and which removes the plug-in-scale hole that `10d` fell into (its
Construction A fed a refit-noise sd into `exp()` and returned 10¹¹).

- **Null.** H₀: the re-searched parameter set performs no better than the incumbent beyond refit
  noise, so the five paired reseed deltas are mean-zero.
- **Deltas, oriented so positive is improvement,** both pre-registered:
  `d_B(i) = Brier(A0, seed_i) − Brier(arm, seed_i)` and
  `d_S(i) = |slope(A0, seed_i) − 1| − |slope(arm, seed_i) − 1|`, all on the 2024 green-pit stratum,
  arm and incumbent refit at the **same** five seeds so the shared seed noise cancels.
- **Statistic.** `t = sqrt(5) * mean(d) / sd(d)` (ddof=1), `g = 1`,
  `E = (1+5g)^(-1/2) * [(1 + t²/4) / (1 + t²/(4(1+5g)))]^(5/2)`.
- **Verified before use**, as §4 requires: 100k simulated draws of five i.i.d. `N(0, σ)` deltas at
  several σ, mean `E` = 1 to Monte Carlo error.
- **Reported alongside:** Construction A at `c = 1.5` on the same deltas, purely so this item's
  numbers sit beside `10d`'s table on the same scale, and **the paired race-cluster bootstrap**,
  which is the instrument that matches the estimand. `10d` §4 already ruled that where the three
  disagree the bootstrap is the one to believe, and this item does not get to re-litigate that
  after seeing its own numbers.
- **Family.** Both declared searches (S1, S2) plus any declared boundary extension. All are counted
  and reported with their `E`, `E < 1` included. Campaign-level decisions run e-BH per gate 7.

**The standing limit, restated before the numbers exist.** 24 eval races could not establish `10d`'s
0.17 slope improvement at 95%. Anything measured here rests on the same 24 races and inherits the
same ceiling; a result inside it is reported as inside it.

### Verdict — MEASURED 2026-09-10

**The search moves the numbers, and it moves the half `10d` said would not move.** Re-run under the
`standard` label, on the training side only, selecting on green-pit IPCW-Brier, the search returns a
parameter set that is better than the incumbent on **calibration slope, on Brier, on AUC, and on the
level bias at the same time** — no trade. That was not the expected shape and the reason it happened
is not the one this doc predicted.

#### 1. Gate 1 — the instrument

Every honest baseline `10d` published was reproduced before anything was built on it, to every digit
`10d` printed, through `evaluate_10c.evaluate_mode` and again through this item's own harness:

| | reproduced | `10d` published |
| :--- | :--- | :--- |
| `10b` honest — Brier / AUC / slope | 0.205929 / 0.691432 / 0.666397 | 0.2059 / 0.6914 / 0.6664 |
| `standard` honest (`10d`'s A3) | 0.190290 / 0.693548 / 0.700013 | 0.190 / 0.6935 / 0.700 |
| `standard` in-sample (the shipped `.bst`) | 0.834378 AUC / 1.234564 slope | 0.834378 / 1.234564 |
| `10b` level diagnostics | intercept +0.2713, mean log bias −0.4342 | +0.271, −0.434 |
| `10b` 5-bin table | 0.058→0.330 · 0.186→0.386 · 0.345→0.492 · 0.512→0.590 · 0.732→0.780 | row for row |

**And one of `10d`'s own arms turned out to be under-described.** Its `C2` row —
"standard + depth 2", slope 1.0476 / AUC 0.6739 / Brier 0.1993 — does not reproduce from the shipped
params with `max_depth` set to 2, which return **1.0295 / 0.6833 / 0.1975**. It reproduces exactly at
`aft_loss_distribution_scale = 0.90`, A1's inner-CV optimum: **1.0476 / 0.6739 / 0.1993**. So `10d`'s
capacity arms were run at scale 0.90 and its table says only "depth 2". Recorded here because
[D4](../status/build-log.json) is a decision about that exact configuration.

The eval fold is unchanged: 20,272 laps, **9,270 green-pit**, **24 races**, no censoring inside the
green-pit stratum under either label construction.

#### 2. What the search did, including where it stopped

**Both declared searches stopped on `n_estimators = 200 (low)`** — with `learning_rate` at 0.0205
against a bound of 0.02. Those two axes multiply, so a search pinned on both is asking for a weaker
fit than the space can express. Per the pre-registration the bound was probed rather than read: the
low bound moved 200 → 50 (step 100 → 50, a strict superset of the old grid) and both searches re-ran
as **S1x** and **S2x**. It mattered — inner-fold Brier 0.1981 → **0.1764**, inner-fold `|slope − 1|`
0.3454 → **0.0915**.

| arm | space | selected | inner-fold value | boundary |
| :--- | :--- | :--- | ---: | :--- |
| S1 | as shipped | depth 10, 200 trees, lr 0.0205, scale 0.552, heavy `gamma`/`reg_lambda` | Brier 0.1981 | **pinned** `n_estimators` low |
| **S1x** | widened | **depth 8, 100 trees, lr 0.0219, scale 0.754, `reg_alpha` 2.64, `min_child_weight` 3, subsample 0.674, colsample 0.702** | **Brier 0.1764** | **interior on every axis** |
| S2 | as shipped | depth 3, 200 trees, lr 0.0255, scale 0.839 | \|slope−1\| 0.3454 | **pinned** `n_estimators` low |
| S2x | widened | depth 7, 50 trees, lr 0.0314, scale 0.953 | \|slope−1\| 0.0915 | **pinned again**, at 50 |

**S1x in full**, so the result outlives the scratchpad it was written to:

```json
{"aft_loss_distribution_scale": 0.7537929016487691, "colsample_bytree": 0.7022777269179408,
 "gamma": 0.00526088099298953, "learning_rate": 0.021917329940077092, "max_depth": 8,
 "min_child_weight": 3, "n_estimators": 100, "reg_alpha": 2.6396744208969904,
 "reg_lambda": 0.016254068532870026, "subsample": 0.6740434973007393}
```

Reproduce with:
`python -m ml.src.tune --target stint_life_regressor --trials 50 --folds 4 --honest-split
--censoring-variant standard --objective green_pit_brier --no-refit --version 10e_S1x
--studies-dir <scratch>/studies --best-params-out <scratch>/S1x_best_params.json`

**`10d` predicted the search would land on low depth. It did not.** S1x chose `max_depth` **8** — the
shipped value — and bought its fit reduction on the *shrinkage* axis instead: `n_estimators ×
learning_rate` falls **5.26 → 2.19**. Depth was the axis `10d` happened to be holding when it found
the effect; it is not the axis the search picks when allowed to choose freely. S2's declared winner
*was* depth 3, independently reproducing `10d`'s A4 pick from a different objective — so the depth
finding is real, it is just not the cheapest route to the same place.

**S2x pinned twice, so the pin was probed rather than reported.** A coordinate ladder in
`n_estimators` at S2x's other parameters, on the same inner folds and through the same
`tune._green_pit_objective`:

| `n_estimators` | 10 | 25 | **50** | 100 | 200 | 400 | 800 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective \|slope−1\| | 40.80 | 2.37 | **0.09** | 0.33 | 0.38 | 0.44 | 0.48 |
| slope | 41.80 | 3.37 | 1.016 | 0.672 | 0.619 | 0.563 | 0.521 |
| green-pit AUC | 0.684 | 0.679 | 0.668 | 0.655 | 0.652 | 0.647 | 0.640 |
| green-pit Brier | 0.427 | 0.296 | 0.186 | 0.194 | 0.210 | 0.216 | 0.223 |
| margin sd | 0.111 | 0.242 | 0.386 | 0.545 | 0.658 | 0.741 | 0.821 |

The optimum is **genuinely interior and happens to sit on the bound**: one step further down and the
objective is 26× worse, because the risk score becomes *under*-dispersed and the slope overshoots to
3.37 and then 41.8. That is `boundary_params`' own distinction — "the learner wants more" versus "the
optimum lives at the edge" — settled by the probe it says is the only way to settle it. It is a
**coordinate** probe and cannot see a joint move ([`epistemics.md`](../foundations/epistemics.md)); it
is used only to read one axis, which is the question the pin asks.

#### 3. The arms, on the 2024 eval fold

Green-pit stratum, n = 9,270, 24 races. Every configuration refit on 2018–2023 through
`evaluate._fit` on the identical split; only the hyperparameters differ. Bootstrap = 200 draws,
races the resampling unit, seed 20260910.

| arm | slope | boot 95% | AUC | Brier | mean log bias | intercept |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: |
| **A0** incumbent v11 | 0.7000 | [0.444, 0.933] | 0.6935 | 0.1903 | −0.2848 | +0.2234 |
| S1 brier (pinned) | 0.5803 | [0.394, 0.772] | 0.7071 | 0.1892 | −0.2087 | +0.2663 |
| **S1x brier** | **0.9034** | **[0.643, 1.190]** | **0.7154** | **0.1674** | **+0.0681** | **+0.0068** |
| S2 slope (pinned) | 0.8667 | [0.562, 1.266] | 0.6836 | 0.1934 | −0.3570 | +0.1835 |
| S2x slope | 1.2877 | [0.927, 1.720] | 0.7032 | 0.1803 | +0.3203 | −0.3206 |
| *ref:* `10d` C2 depth 2 | 1.0295 | [0.677, 1.420] | 0.6833 | 0.1975 | −0.3966 | +0.1489 |

Against A0's **own** gate-3 floor — measured under `standard`, this family's own label, five seeds
20260528–20260532 with XGBoost's `seed` varied: slope sd 0.011786 (floor 0.033337), AUC sd 0.001855
(floor 0.005247), Brier sd 0.000731 (floor 0.002066). **Note it is nearly twice `10d`'s 0.006208**,
which was measured under `10b` — `gates.md`'s rule against borrowing a floor across families earns
its keep here.

| arm | Δ\|slope−1\| | × floor | ΔBrier | × floor | ΔAUC | × floor |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| S1 | −0.1197 | −3.59× | +0.0011 | 0.54× | +0.0135 | 2.58× |
| **S1x** | **+0.2034** | **6.10×** | **+0.0229** | **11.06×** | **+0.0219** | **4.17×** |
| S2 | +0.1667 | 5.00× | −0.0031 | −1.49× | −0.0099 | −1.89× |
| S2x | +0.0123 | 0.37× | +0.0100 | 4.85× | +0.0096 | 1.83× |
| *ref:* C2 depth 2 | +0.2705 | 8.12× | −0.0072 | −3.50× | −0.0103 | −1.96× |

**Paired race-cluster bootstrap** — both arms scored on the same resampled races, which is the
instrument `10d` §4 ruled is the one to believe:

| arm | Δ\|slope−1\| | 95% | P | ΔBrier | 95% | P |
| :--- | ---: | :--- | ---: | ---: | :--- | ---: |
| S1 | −0.1144 | [−0.176, −0.038] | 0.005 | +0.0007 | [−0.005, +0.006] | 0.610 |
| **S1x** | +0.1731 | [−0.117, +0.273] | 0.930 | **+0.0237** | **[+0.0067, +0.0368]** | **1.000** |
| S2 | +0.1414 | [−0.177, +0.266] | 0.930 | −0.0027 | [−0.010, +0.004] | 0.265 |
| S2x | −0.0039 | [−0.636, +0.495] | 0.465 | +0.0119 | [−0.010, +0.034] | 0.830 |
| *ref:* C2 | +0.1492 | [−0.326, +0.378] | 0.835 | −0.0067 | [−0.016, +0.001] | 0.070 |

**The slope improvement inherits exactly the ceiling this doc warned it would**: +0.173 at P = 0.930,
an interval straddling zero, indistinguishable from `10d`'s +0.173 at P = 0.945. Twenty-four races
could not establish that then and cannot now.

**The Brier improvement does not.** +0.0237, 95% [+0.0067, +0.0368], **200 of 200 draws improve**. A
proper score evaluated per row has far less sampling variance than a slope fitted through five binned
points, so the same 24 races *can* resolve it. That is the one number in this item that clears its
own instrument at 95%, and it is the number the selection metric was.

#### 4. The level bias — the prediction, and where it broke

This doc predicted that a re-search optimising the slope would leave the level where it was. **For
the slope-selected arm that is exactly what happened**, and the reproduction is close to literal:
S2's mean log bias is **−0.3570** against A0's −0.2848, i.e. *worse*, matching `10d`'s
−0.434 → −0.560 on the `10b` label. Optimising `|slope − 1|` alone buys dispersion and pays for it in
level, twice, under both label constructions.

**The Brier-selected arm breaks the pattern, and the mechanism is that Brier prices the level and
`|slope − 1|` does not.**

| | 5 bins, predicted risk → observed risk | mean log bias | intercept |
| :--- | :--- | ---: | ---: |
| A0 | 0.105→0.296 · 0.249→0.403 · 0.409→0.513 · 0.566→0.603 · 0.759→0.763 | −0.2848 | +0.2234 |
| S2 | 0.136→0.299 · 0.272→0.403 · 0.377→0.539 · 0.484→0.597 · 0.647→0.739 | −0.3570 | +0.1835 |
| **S1x** | 0.274→0.238 · 0.431→0.423 · 0.576→0.526 · 0.700→0.627 · 0.836→0.764 | **+0.0681** | **+0.0068** |

A0 predicts **below** observed risk in all five bins; S1x predicts **above** it in all five. The bias
is not removed — it is **reduced 76% in magnitude and flipped in sign**, and the sign it flips to is
the conservative one: the gauge now says a tyre is slightly closer to finished than it turns out to
be, where the incumbent said it had life it did not have. For a number a pit wall reads as safe laps
remaining, those two errors are not equivalent, and this item does not get to call the flip a free
win — it is a smaller error in a better direction, which is a product judgment as much as a
statistical one.

Two-thirds of that came from the label, not the search: `10d` already measured the level bias at
−0.434 under `10b` against −0.285 under `standard`. D5 bought most of it before this item ran.

#### 5. Gates 2 and 4 — inapplicable in their literal form, and stated rather than skipped

**Gate 2** is an add-ablation. Nothing is added here: every arm is the same 32-column matrix under the
same label, fitted differently. The substituted requirement — "same split for every family in the
comparison", through `evaluate.py`'s own `_fit` — is met exactly; all six configurations share one
`_evaluation_split` and one set of eval rows.

**Gate 4** row-shuffles new columns, and there are none. `10d` declared the reseed null as the
substitute and it was run again here (§3's floor). But `10d` also wrote that "capacity is identical
between every arm and A0 … by construction", and **for a hyperparameter re-search that is false**:
`max_depth`, `n_estimators` and `learning_rate` *are* capacity, and capacity is the whole content of
the arm. There is therefore no information-versus-capacity decomposition available here, and the
e-value's null below is stated as what it is — "no difference beyond refit noise" — not as an
information null it cannot be. This is a correction to how `10d` phrased its own gate-4 substitution,
not a new hole.

#### 6. Gate 7 — the e-values, and the family they belong to

Construction B as declared, on five paired reseed deltas, `g = 1`. **Verified before use** per §4 of
the reference: 100k simulated draws of five i.i.d. `N(0, σ)` deltas return mean `E` = **0.999–1.000**
two-sided at every σ, and **0.70** with the one-sided truncation this item declared (a delta in the
wrong direction pays the minimum). `E[E] ≤ 1` holds; the construction is conservative by ~30%, which
is the price of orienting it. The reference's own worked example returns **17.05** against its
published 17.0.

| arm | Δ\|slope−1\| | `E_B` (slope) | ΔBrier | `E_B` (Brier) | `E_A` (slope, c = 1.5) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| S1 | −0.1197 | 0.408 | +0.0011 | 14.22 | 0.0007 |
| S1x | +0.2034 | 34.28 | +0.0229 | **35.88** | 2.1 × 10⁴ |
| S2 | +0.1667 | 34.31 | −0.0031 | 0.408 | 3.0 × 10³ |
| S2x | +0.0123 | 5.57 | +0.0100 | 34.64 | 0.79 |

**e-BH at α = 0.05 over the four declared arms rejects nothing.** The threshold for a lone rejection
in a family of four is `n/(αk)` = **80**, and the largest `E` is 35.9. Reported as declared, and it is
the right answer: an item that re-searched a parameter set on two objectives, then probed a boundary
and re-ran both, has spent four hypotheses and does not get to bank the best one at face value.

Construction A is again inflated — 2.1 × 10⁴ for S1x — for exactly the reason `10d` diagnosed: the
reseed sd measures refit noise, the cluster bootstrap puts sampling noise 8–16× higher. It is
reported because gate 7 says report what you declared, and it is not believed. **Three instruments,
and they disagree in public: S1x clears the reseed floor 6–11×, returns `E_B` ≈ 35, fails e-BH, and
is significant at 95% on Brier but not on slope.** All four statements are true and they are about
different questions.

#### 7. The metric the incumbent was tuned on, for completeness

`aft_nloglik` on the eval fold — the objective `tune.py` used to select the shipped params:

| | A0 | S1x | S2 | S2x | C2 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| all eval rows (the mixture) | **1.9878** | 2.1512 | 1.9783 | 2.3045 | 1.9966 |
| green-pit rows only | 3.4356 | **3.2837** | 3.4318 | 3.4163 | 3.4360 |

The incumbent is at or near the top on the mixture and last on the stratum. That is the cleanest
statement of what `10c` ruled and this item acted on: the two metrics rank the models differently, and
the mixture is the one the app does not care about.

#### 8. Answering the definition of done

**A tuned parameter set selected under a split and a metric that both match the estimand:** yes —
**S1x**, `censoring_variant=standard` (D5's realised stint ending), folds confined to 2018–2023, and
green-pit IPCW-Brier as the objective. Interior on every axis of the space that produced it.

**What it costs and buys against the honest incumbent:** it buys, and does not appear to cost.
Against A0 under the same label (slope 0.700 / AUC 0.694 / Brier 0.190): slope → **0.903**
(|slope−1| −68%, 6.1× floor), Brier → **0.167** (11.1× floor, and the only 95%-significant result
here), AUC → **0.715** (+0.022, 4.2× floor — an *increase*), mean log bias −0.285 → **+0.068**. Against
the definition-of-done's `10b`-label incumbent (0.666 / 0.691 / 0.206) the gaps are larger, but that
is not the like-for-like comparison and is not claimed as one.

**Landed? No — and unlike `10d`, not because the result is weak.** Three reasons, and only the third
is about the numbers:

1. **Landing is not this item's call.** `10e` is staged `SPEC` and the build order puts overwriting a
   shipped artefact behind a human decision. Nothing in `ml/models/` was touched: the search ran with
   `--no-refit` and wrote its params to the scratchpad.
2. **e-BH rejects nothing at α = 0.05.** The strongest arm returns `E` = 35.9 against a threshold of
   80. `04a`'s multiplicity finding exists to stop exactly the move of banking the best of four
   declared arms.
3. **The level bias flipped sign rather than closing**, and which side of zero a stint-life gauge
   should err on is the product question D5 answered for the *label* and did not answer for the
   *level*. A model that tells a pit wall the tyre is more finished than it is will be wrong in a way
   users notice differently from the incumbent's error, and that is worth a decision rather than a
   default.

**What this item does close.** The search defect `10d` named is fixed in the production path, not
worked around: `tune.py` now takes `--censoring-variant`, `--objective` and `--honest-split`, warns
when a survival search runs with the eval season inside its folds, and `--no-refit` lets a search be
read without republishing an artefact. The two bounds that were truncating this problem — `max_depth`
low and `n_estimators` low — are widened with the pins that moved them recorded in
`test_search_space.py`. `02b`'s noise floors can now be measured, and §3 already carries them for
both the incumbent and S1x.

#### 9. Deviations from the method above, logged

- **The pre-registered space was widened mid-item, once, under the declared boundary rule.**
  `n_estimators` low 200 → 50. The rule was written before any trial ran and the probe is reported as
  the extension it is (S1x/S2x), not folded into S1/S2. `max_depth` low 3 → 2 was declared up front.
- **Four arms, not two.** The boundary extensions are counted in the e-value family, which is why the
  e-BH threshold is 80 rather than 40.
- **The shrinkage ladder in §2 is post-hoc**, added after S2x pinned a second time, to answer a
  question the pre-registration named ("probe past the bound") but could not have specified a shape
  for in advance. It is a coordinate probe and is read as one.
- **`ml/models/encoders.json` was rewritten** by running gate 5 through its production entry point
  (`python -m ml.src.features --check` calls `load_features(persist_encoders=True)`). The content is
  byte-identical to `HEAD` — `git diff` is empty — but the ad-hoc-probe rule says not to touch
  `ml/models/*.json` and this is disclosed rather than buried.
- **Not run: a second widening below `n_estimators = 50`.** The ladder shows the objective 26× worse
  one step down, so the bound is no longer binding on the optimum and a third search would be
  chasing a question already answered.

---

## The product question this does not settle

From the app's point of view the pit wall's decision *is* arguably the thing to predict — a user
reading "remaining stint life: 11 laps" may want the realised answer, deployments included. That
is a genuine product call and it is the user's, not a statistical one.

It does not rescue the incumbent, because the incumbent answers **neither** question cleanly. It
answers the marginal mixture: a tyre limit contaminated by a deployment process it cannot see
coming, and a deployment process degraded by tyre variation. Splitting the causes lets the app
choose — and lets it show both. `int_sc_hazard_history` is exactly the term that recombines them.
