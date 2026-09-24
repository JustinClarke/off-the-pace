# 05 — Model family

**Group:** 05 · **`05a`:** CLOSED 2026-09-11, unstarted (see below) · depended on `01a`, `01b`

> **SPLIT 2026-09-07 (research round R1).** "Model family" is not one decision. `05a` — the
> *shipping* class change — stays blocked and stays lowest-EV. But two pieces that were sitting
> behind that block are **hours and days respectively, have no dependencies, and do not leave
> the existing pipeline.** They are now `05b` and `05c` at the bottom of this doc. Neither
> inherits `05a`'s block; `05b` in particular should never have been behind a "days-weeks" item.

> **CLOSED 2026-09-11 — decision `D8` ruled by the user.** `05a` is closed, unstarted. The
> reframe proposal described below (judge model families on a publishable coefficient with an
> interval, not pinball loss) was **rejected/deferred**, not adopted. Full ruling and reasoning
> in the `05a — CLOSED 2026-09-11` section after the Definition of done, and in `D8`'s
> `resolution` field in [`../status/build-log.json`](../status/build-log.json).

Twenty-two checkpoints of hyperparameter search inside **one model class**. Whether
gradient-boosted trees are the right class for this data has not been tested once.

**Blocked deliberately.** This is the most expensive item in the programme and the least
likely to pay unless `01` shows real headroom remains. If the degradation trio sits near a
trustworthy empirical floor, a model-class change cannot claim what is not there, and this
item closes unstarted. If `01` shows meaningful headroom, this moves up — a class change is
the kind of move that could actually claim it.

## The structural argument

- **Nesting.** Lap within stint within race within season, with driver and constructor
  crossing that hierarchy. A hierarchical / mixed-effects model represents this directly, and
  its per-level variance components are *themselves* an answer to `01`'s headroom question —
  which is the second reason to run `01` first, since the two items would otherwise measure
  the same thing twice by different means.
- **Smooth, monotone physical curves.** Degradation against tyre age is physically expected to
  be smooth and mostly monotone. A GAM encodes that as a prior; a tree ensemble spends capacity
  rediscovering it and can produce non-monotone artefacts — which `behaviour_audit`'s
  monotonicity probe already exists to catch, and which the right model class would make
  unnecessary.

## Connection to 03

`03c`'s AKM decomposition is a hierarchical model of the same panel, fitted for a different
purpose. If `03c` lands first, its variance components are evidence for or against this item
that costs nothing extra to read.

---

## 05b — Monotone constraints. Hours, no dependencies, stays inside XGBoost.

**Objective.** Test the smoothness prior directly, without a class change.

**The argument this item answers.** The section above says a tree ensemble "spends capacity
rediscovering" a monotone physical curve and can produce non-monotone artefacts, which
`behaviour_audit`'s monotonicity probe exists to catch. That is an argument for **turning the
constraint on**, not for changing model class. XGBoost has supported `monotone_constraints` for
years.

**Method.** Candidates from the contract, each a coordinate where degradation is physically
expected to be monotone in one direction: `age_in_stint`, `lap_in_stint`, `laps_past_cliff`,
`cumulative_push_load_surface`, `cumulative_push_load_bulk`. Run as a `gates.md`-compliant
add-ablation like anything else, delta against the family's own reseed floor.

**Cost:** a hyperparameter. ONNX export unaffected, parity gate unaffected. `behaviour_audit`'s
monotonicity probe becomes a **test of a guarantee** rather than a hope.

**The honest caveat.** A hard constraint costs fit wherever the physics is wrong — warm-up, track
evolution and fuel burn make early-stint pace non-monotone in tyre age. The constraint may not
clear its own floor, and that is a result, not a failure.

**Definition of done.** A measured verdict per family, and a statement on whether the
monotonicity probe can be retired or must stay.

---

### 05b — CLOSED 2026-09-08. Measured negative result on both testable families; the
monotonicity probe does not retire.

**Pre-registered arms** (written here before the fits below were run). Candidates and
direction, chosen from physical reasoning, not searched: `age_in_stint` +1, `lap_in_stint`
+1, `laps_past_cliff` +1, `cumulative_push_load_surface` +1, `cumulative_push_load_bulk` +1
for `degradation_regressor` (target increases with more/older tyre wear); all five flipped
to -1 for `stint_life_regressor` (remaining life decreases with the same wear). `params`
are each family's own `ml/models/<target>_best_params.json` (v11, unchanged). Split is
`cv_final_fold` via `evaluate.py::_evaluation_split` — train 2018-2023, eval 2024, same as
the production headline. `cliff_classifier` was pre-registered as **attempt-then-justify**:
run the mechanism check first (below) and only fit it on real data if the constraint could
mean what the physical argument claims.

**Gate 1 — instrument check.** Baseline (unconstrained, tuned params) refit via
`evaluate.py::_fit`/`_score` reproduced the published v11 headline to 6dp for both families:
`degradation_regressor_p50` 1.0163386141079709 (both), `stint_life_regressor`
1.9487233293052475 (both).

**Gate 2/3 — add-ablation vs the family's own reseed floor** (`AT.refit_noise_floor`, 5
reseeds at `S.RANDOM_STATE + i`, `2*sqrt(2)*sd`):

| Family | Metric | Baseline | Constrained | Δ (+ = constraint better) | 2σ√2 floor | Floor ratio | Verdict |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `degradation_regressor_p50` | pinball ↓ | 1.016339 | 1.104032 | -0.087693 | 0.013317 | 6.58x | CLEARS — worsens |
| `stint_life_regressor` | AFT NLL ↓ | 1.948723 | 1.961266 | -0.012542 | 0.002811 | 4.46x | CLEARS — worsens |

**Gate 4 (adapted) — capacity vs information.** No new column is added here, so the literal
"row-shuffle the new columns" arm doesn't apply. Adapted question: does forcing
monotonicity help via real signal, or would it buy the same thing on pure noise (a
regularization/capacity artifact)? Row-shuffled the 5 candidate columns independently in
train and eval (breaks their relationship to y, keeps capacity identical), refit both arms
on the shuffled matrix, and split `capacity = shuffled(constrained) - shuffled(baseline)`
from `information = real_delta - capacity`:

- `degradation_regressor_p50`: capacity -0.004043 (0.30x floor, inside noise), information
  -0.083650 (6.28x floor). The worsening is real information, not a capacity artifact.
- `stint_life_regressor`: capacity -0.000246 (0.09x floor, inside noise), information
  -0.012296 (4.37x floor). Same conclusion.

This is the honest caveat from the top of this section, measured rather than assumed: the
physics really is non-monotone across the eval window (warm-up, track evolution, early-stint
fuel burn), and the constraint pays for that with real fit, on both families where it can be
tested.

**Gate 5 — forward-window audit.** N/A. All five candidates are pre-existing contract
features that already cleared their own leakage/forward-window checks when admitted; nothing
label-adjacent is introduced by adding a hyperparameter.

**Mechanism check — does the constraint even deliver the guarantee?** Verified on synthetic
toys (not production data), because the headline deltas above say the constraint changes the
fit but say nothing about whether `behaviour_audit`'s monotonicity guarantee actually holds
afterward:

- `reg:squarederror` (a toy: `y = 2x + noise`, `monotone_constraints=(1,)`): 0 violations
  over a 200-point grid. The guarantee holds exactly, as documented.
- `reg:quantileerror` (what all three `degradation_regressor` quantile heads use) — same
  toy, same constraint: **2/199 violations, magnitude -0.139**, comparable to the signal
  itself. XGBoost 3.3.0 does not enforce `monotone_constraints` under this objective. So even
  setting the fit cost aside, adopting this constraint on `degradation_regressor` would not
  buy the guarantee the argument in this doc is built on.
- `multi:softprob` (`cliff_classifier`) — a toy 3-class problem built so `P(class 2) = x/10`
  exactly by construction, fit with `monotone_constraints=(1,)`: 32-54/199 violations **per
  class**. The constraint restricts each class's raw margin independently; it says nothing
  about the softmax-*normalized* class probability, which is the quantity the physical claim
  ("P(imminent-cliff class) rises with `laps_past_cliff`") is actually about. There is no way
  to express that claim as a single per-feature direction in `multi:softprob`. **Not run on
  real data** — a measured number here would carry no valid interpretation in either
  direction.

**Verdict.** Closed as a measured negative result. Do not adopt `monotone_constraints` on
any of the three families as currently built. `behaviour_audit`'s monotonicity probe **stays
— cannot be retired**: today's unconstrained production models already fail it
(`degradation_regressor_p50` 3/19 violations, `stint_life_regressor` 1/19), and neither
family has a clean path to fixing that — the quantile heads' constraint doesn't mechanically
work, and the survival head's does but costs real, floor-clearing fit.

**Landed alongside, found while running the audit both ways.**
`evaluate.py::behaviour_audit`'s monotonicity check applied one hardcoded direction
(non-decreasing) to every family in `ELEVATION_TARGETS`. That's right for
`degradation_regressor` (more wear ⇒ more predicted time loss) but backwards for
`stint_life_regressor` (more wear ⇒ *less* predicted remaining life): every prior run of
this probe scored `stint_life_regressor`'s correctly-decreasing predictions as violations,
and a model that wrongly held remaining life flat or rising past the cliff would have passed
it clean. Fixed: direction is now keyed off `spec.family`, and the output field is renamed
`monotone_non_decreasing` → `monotone_as_expected` with an explicit `expected_direction`
(grepped the repo for the old key name — no other reader depends on it). With the fix,
`stint_life_regressor`'s unconstrained baseline shows 1/19 real violations, not the inverted
reading it would have gotten before.

---

## 05c — GPBoost variance-components probe. Measurement only; ships nothing.

**Objective.** Get fitted per-level variance components, as a third leg of `01`'s bracket.

**Why this belongs inside `01`, not after it.** GPBoost fits `y = F(X) + Zb + ε` — a boosted tree
ensemble *plus* grouped random effects, learning trees and (co)variance parameters jointly. It
returns `σ²_stint`, `σ²_race`, `σ²_driver`, `σ²_residual` **as fitted parameters**. That residual
variance is a model-based estimate of irreducible noise, failing in different directions from
`01b`'s neighbourhood construction and from `09a`'s parametric one.

This doc already notices the connection ("its per-level variance components are *themselves* an
answer to `01`'s headroom question"). The consequence is that the dependency runs both ways:
a bounded GPBoost probe is **an instrument for `01`**, so it should not sit behind it.

**Method.** Fit at the production split. Read the variance components. **Ship nothing** — no
artefact, no contract change, no ONNX. The nesting is lap within stint within race within season,
with driver and constructor crossing it. MERF / REEMtree are the cheaper first try if GPBoost is
awkward to install.

**Cost:** 1–2 days, all of it measurement. Note that a *shipping* GPBoost model would cost the
ONNX path for the random-effects term — which is `05a`'s problem, not this item's.

**Definition of done.** Four variance components with their fit diagnostics, reconciled against
`01a`'s learning curves and `01b`'s bracket, with disagreements reported rather than averaged.

> **SUBSTRATE BANNER — read before quoting any number from the 2026-09-08 sections below.**
> Everything in the pre-registration and in results parts 1–2 was measured on the **v11**
> substrate: 33 feature columns and the **pre-`08m` target**. `08m` rebuilt
> `next_5_lap_cumulative_jump_s` and `08n` shipped the refit as **v12**, under the explicit
> ruling that v11 and v12 headlines are *different quantities and are not compared*. The v11
> target's variance is roughly twice v12's (40.11 against 19.64 on the training rows), so every
> component, every bridge and the `±1.5%` headline below describe a quantity production no
> longer predicts. They are kept as the record of what was measured, not retracted — but the
> live answer is in **`05c` — RERUN 2026-09-17** and **`05c` — RECONCILIATION**, after part 2.

---

### 05c — PRE-REGISTRATION 2026-09-08. Arms written before any of them were run.

`gates.md` step 6. Everything below was written before a single fit; the results section
follows it and does not edit it.

**Family and split.** `degradation_regressor_p50`'s target, `next_5_lap_cumulative_jump_s`,
on `evaluate.py::_evaluation_split`'s `cv_final_fold` — train 2018–2023 (68,574 rows, 5,173
stints, 123 races, 37 drivers, 16 constructors), eval 2024 (13,896 rows). The same split every
other number in the programme is quoted on.

**The likelihood is not the production loss, and that is a population difference, not a
disagreement.** GPBoost fits `y = F(X) + Zb + ε` under a **Gaussian** likelihood; production
scores **pinball** at α ∈ {0.10, 0.50, 0.90}. `σ²_residual` is therefore a variance about the
conditional *mean*, and it is never diffed against a pinball number. It reaches pinball only
through a declared shape assumption, written out in arm 4 below and labelled as such.

**Weighting.** Fitted **unweighted**, though production's quantile trio carries IPW
`survival_weight` (mean 1.713 on these rows). A variance component is a property of a
population; re-weighting the rows redefines that population, and REML under weights is a
different estimator. The weighted fit runs as a sensitivity arm, and if the two disagree the
unweighted one is the one quoted, with the gap reported.

**Grouping levels.** `race_id`, `stint_id`, `driver_id`, `constructor_id` as independent
grouped random effects. Stint is nested in race and in driver by construction, so this is the
standard variance-components decomposition rather than a claim about crossing. `driver_id` and
`constructor_id` are close to nested within season and their split may be weakly identified —
declared here in advance, so a clean-looking split between those two is not read as evidence.

#### Arm 0 — instrument check (gate 1, adapted)

Gate 1 asks for an N-column refit reproducing the v11 headline to 6dp. A different model class
cannot do that, so it is adapted into two parts, **both of which must pass before any real-data
GPBoost number is read**:

- **0a — the harness has not moved.** Refit `degradation_regressor_p50` through
  `evaluate.py::_fit`/`_score` on this split and require the published v11 headline
  **1.0163386141079709** to 6dp, exactly as `05b` did.
- **0b — GPBoost recovers components it is given.** Synthetic data at this design's real
  shape (123 races × 5,173 stints × 37 drivers × 16 constructors, ~68k rows) with known
  `σ²_race`, `σ²_stint`, `σ²_driver`, `σ²_constructor`, `σ²_residual` and a nonlinear `F(X)`.
  Pass condition, declared now: each component recovered within **±20% relative**, and
  `σ²_residual` within **±10%**. Failure means the probe stops and reports that, rather than
  reporting real-data components from an instrument that cannot recover known ones.

#### Arm 1 — the raw decomposition (no features)

Intercept-only `GPModel`: `y = μ + Zb + ε`. This is the target's variance split before the
contract explains anything.

**Declared cross-check against a production instrument.** A *single-level* (stint-only)
intercept-only fit must reproduce `ceiling.py::variance_components`' one-way ANOVA ICC **on the
identical rows** — not on the `attainable.variance` block's mart-scope rows (95,346 rows /
6,422 stints, `between_stint_share_overlapping` 0.1239), which are a different population and
are not diffed against. Agreement to ~2dp is expected; a larger gap is a finding about one of
the two instruments and is reported as that.

#### Arm 2 — the fitted decomposition (33 contract columns)

`gpb.train` with the contract's 33 columns, same four grouping levels, `regression_l2`.
Boosting rounds by GPBoost's own CV with early stopping on the train rows. The four components
after `F(X)` are the item's deliverable.

**Arm 2b — permutation null (gate 4, adapted).** No column is being added, so the literal
add-ablation shuffle does not apply. The adapted question: is `F(X)` absorbing real signal, or
is the drop in `σ²_residual` from arm 1 to arm 2 what any 33-column ensemble buys on noise?
Row-shuffle all 33 columns in train, refit, and require the components to return toward arm 1's.
The gap between shuffled and real is the information the contract actually carries.

#### Arm 3 — stability (gate 3, adapted)

Gate 3's `2*sqrt(2)*sd` over 5 reseeds, applied to **the components themselves** rather than to
a delta, at `S.RANDOM_STATE + i`. A component whose reseed scale is comparable to the component
is not reportable to the precision it prints at.

**Arm 3b — the overlap arm.** Adjacent rows of a 5-lap cumulative target share 4 of their 5
terms, so `ε` is serially correlated within stint (`ceiling.py` measures lag-1 0.604 against
0.8 from overlap alone). REML assumes independent `ε`. Refit on a **non-overlapping** subsample
— every 5th lap within each stint, the construction `ceiling.py`'s `non_overlapping` block
already uses — and report both. Declared now: **if they disagree materially, the
non-overlapping fit is the one quoted.**

#### Arm 4 — reconciliation, with the shape assumption stated

`σ_residual` is converted to the programme's two live scores under an explicit Gaussian shape,
and the converted numbers are reported as *implied floors*, never as measurements:

- implied pinball at α=0.5: `0.5 · σ · sqrt(2/π)` = `0.39894 · σ`, against achieved
  **1.0163386**;
- implied CRPS: `σ / sqrt(π)` = `0.56419 · σ`, against `09a`'s achieved **1.4603683** and its
  `unc` **2.7646751**.

Per `epistemics.md`, these sit **beside** `09a`'s numbers and are not differenced with them.

**What this item cannot close.** The definition of done asks for reconciliation against `01a`'s
learning curves and `01b`'s bracket, and neither has run. So `05c` delivers its own leg plus the
two reconciliations that exist today (`09a`, and `ceiling.py`'s ANOVA), and records the exact
quantity `01b` must return for the three-way bracket to close. It lands `MEASURED`, not `GATED`.

**Gates, declared in advance.** 1 adapted (arm 0); 2 **N/A** — nothing is added, no delta is
claimed; 3 adapted (arm 3); 4 adapted (arm 2b); 5 **N/A** — no new features, the 33 contract
columns cleared their own forward-window checks when admitted; 6 is this section.

---

### 05c — RESULTS 2026-09-08 (part 1: instrument, raw decomposition, two method findings)

Run under the pre-registration above. Where a result deviates from what was pre-registered,
the deviation is stated here and the pre-registration is left as written.

**Environment.** `gpboost` 1.7.4, installed to a scratchpad directory on `sys.path`, never into
the repo venv and never into `ml/requirements.txt` — this item ships nothing. Warehouse read
`read_only=True` through `features.py::load_features`. Split cached once and reused across arms
so every number below is on identical rows: **68,574 train rows (2018–2023) / 13,896 eval
(2024), 5,173 stints, 123 races, 37 drivers, 16 constructors.**

#### Arm 0a — PASSES, bit-identical

`evaluate.py::_fit`/`_score` at v11 params reproduces the published headline exactly:
`1.0163386141079709` against `1.0163386141079709`, absolute difference `0.000e+00`. The harness
has not moved since `05b`.

#### Arm 0b — 4 of 5 components recovered; `constructor` misses its declared tolerance

First attempt, at a **fixed 300 boosting rounds**, inflated *every* component by ~20%
(`Error_var` 9.456 against a true 8.000, `race` +21.9%, `stint` +22.6%). That is not noise: an
underfit `F(X)` has nowhere to go but the variance components. **Boosting-round count is part of
this instrument, not a convenience** — recorded because any future variance-components probe
that fixes rounds by hand will inherit the same bias.

Re-run under arm 2's declared protocol (race-grouped 80/20 hold-out, early stopping at 50,
stopped at 1,077 rounds):

| component | true | fitted | rel err | declared tolerance |
| :--- | ---: | ---: | ---: | :--- |
| `Error_var` | 8.000 | 7.773 | −2.8% | ±10% — **pass** |
| `race` | 1.500 | 1.534 | +2.3% | ±20% — pass |
| `stint` | 3.000 | 3.114 | +3.8% | ±20% — pass |
| `driver` | 0.400 | 0.410 | +2.5% | ±20% — pass |
| `constructor` | 0.250 | 0.165 | **−34.0%** | ±20% — **fail** |

#### Arm 0c — the `constructor` miss is sampling noise, and the pre-registered tolerance was unmeetable

**Deviation from the pre-registration, logged.** The pre-registration says a 0b failure stops the
probe. It was not relaxed; it was *diagnosed*, intercept-only (seconds per replicate rather than
minutes), over 40 replicates on the real group design — once with small-but-real `driver`/
`constructor` variance, once with both exactly zero:

| component | levels | true | mean | bias | rel sd | p05–p95 |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `Error_var` | — | 33.320 | 33.287 | −0.1% | **0.6%** | 33.01 – 33.53 |
| `stint` | 5,173 | 5.340 | 5.354 | +0.3% | 3.0% | 5.09 – 5.54 |
| `race` | 123 | 3.370 | 3.553 | +5.4% | 20.6% | 2.61 – 4.74 |
| `driver` | 37 | 0.400 | 0.365 | −8.8% | 31.8% | 0.18 – 0.56 |
| `constructor` | 16 | 0.250 | 0.563 | +125.3% | **215.6%** | 0.09 – 1.56 |

A variance estimated from `k` groups carries roughly `sqrt(2/(k-1))` relative sampling sd on its
own — 36.5% at `k=16`. **The ±20% tolerance was arithmetically unmeetable by any estimator on a
16-level design.** The defect was in the pre-registration, not in GPBoost: `0b`'s −34.0% is one
draw from a distribution whose 5th–95th percentiles span 0.09–1.56 for a true 0.25.

Under the null (arm b), the instrument does **not** manufacture components: `driver` returns
exactly 0.000 ± 0.000, `constructor` 0.009 ± 0.008.

**Consequence for how the components below are read.** `Error_var` and `stint` are reportable at
the precision they print. `race` carries ~21% relative sampling sd. **`driver` and `constructor`
are not estimable on this design and no claim rests on their point values** — only on the
upper bounds arm 1 supports. And note that the pre-registered arm-3 reseed floor (tree seeds
only) does **not** capture this: it measures numerical stability, not the sampling uncertainty
that dominates the small-`k` levels. Both are reported, separately.

#### Arm 1 — the raw decomposition (intercept-only, no features)

**A bug found and fixed mid-arm.** `GPModel.fit(y=...)` fits **no intercept** unless `X` is
passed. The first fit therefore decomposed `E[y²]` rather than `Var(y)`, absorbing
`mean(y)² = 4.372` into the components (fitted total 45.583 against `var(y)` 40.115). Refitted
with an explicit intercept (fitted at −2.071 against a sample mean of −2.091):

| component | variance | share | sd (s) |
| :--- | ---: | ---: | ---: |
| `race` | 3.3704 | 8.0% | 1.836 |
| `stint` | 5.3388 | 12.7% | 2.311 |
| `driver` | 0.0000 | 0.0% | 0.002 |
| `constructor` | 0.0052 | 0.0% | 0.072 |
| `Error_var` | 33.3190 | **79.3%** | 5.772 |
| total | 42.0334 | | 6.483 |

**Driver and constructor identity carry no measurable variance in this target.** Read against
arm 0c's null distribution (`driver` 0.000 ± 0.000, `constructor` 0.009 ± 0.008) these are
indistinguishable from exactly zero, and read against arm 0c's alternative they sit below the
5th percentile of what a true `driver` 0.40 / `constructor` 0.25 would produce — so those
magnitudes are excluded, not merely unresolved.

**Assumed, not verified:** that this is the differencing, not the absence of driver skill.
`next_5_lap_cumulative_jump_s` is a within-stint *change*, so a driver's persistent pace level
is differenced out by construction and only a driver-constant difference in *degradation rate*
could appear here. `03` should not read this as "no driver effect exists"; it is evidence about
this target's construction. Nothing was run to separate the two.

#### Method finding — the pre-registered ANOVA cross-check failed, and the cause is window overlap

Declared expectation: a stint-only REML fit reproduces `ceiling.py::variance_components`' one-way
ANOVA ICC on identical rows to ~2dp. Measured on the same 68,574 rows: **ANOVA 0.174836 against
REML 0.199020, gap +0.024183** — outside the declared tolerance.

Chased on simulated data using the *real* stint design with a known ICC of 0.195122:

| noise injected | ANOVA ICC | REML ICC | gap |
| :--- | ---: | ---: | ---: |
| gaussian | 0.195136 | 0.194639 | −0.000497 |
| target-shaped (skew −0.81, excess kurtosis 5.02) | 0.200693 | 0.201004 | +0.000312 |
| heteroscedastic across stints | 0.198769 | 0.197222 | −0.001547 |
| **AR(1), ρ = 0.60 within stint** | **0.326886** | **0.345472** | **+0.018586** |

Neither estimator is at fault — they agree to <0.002 wherever the one-way model holds, including
under the target's own heavy tails. **Only serial correlation splits them**, and ρ=0.60 is not a
hypothetical: it is the lag-1 autocorrelation `ceiling.py` already measures within stint
(`within_stint_lag1_autocorr` 0.6044), produced by the 5-lap target's overlapping window.

The more important half: under AR(1) **both estimators inflate badly** — a true ICC of 0.195 is
read as 0.327 (ANOVA) and 0.345 (REML), a ~70% overstatement of the between-stint share. This
corroborates with a mechanism what `ceiling.py`'s `non_overlapping` block already does by
construction, and it is why the pre-registration's arm 3b (non-overlapping rows) is the fit that
gets quoted.

#### Population and shape, measured before any bridging

Two facts that govern arm 4 and were checked rather than assumed:

- **The target's variance falls monotonically by season** — 2018 47.94, 2019 40.75, 2020 42.26,
  2021 39.64, 2022 36.74, 2023 33.46, 2024 32.83. Train (2018–23) pools at **40.115**; eval
  (2024) is **32.831**, a ratio of 0.818. A component fitted on train describes a *more variable
  population* than the one the headline is scored on. Per `epistemics.md` the two are reported as
  separate legs and never differenced.
- **The Gaussian shape assumption is wrong in a knowable direction.** The bridge from `σ` to
  pinball assumes `E|z − median(z)| = sqrt(2/π) = 0.79788`. Measured on within-stint deviations:
  **0.688 (train), 0.711 (eval)** — so a Gaussian bridge overstates the implied floor by ~14%.
  `ceiling.py`'s `analytic_from_icc` denominator rests on the same Gaussian shape and inherits
  the same overstatement; that is a note for `01`, not a defect fixed here.

---

### 05c — RESULTS 2026-09-08 (part 2: the fitted decomposition, and what it says about `01` and `05a`)

#### Arm 2 — the fitted decomposition (33 contract columns, 1,499 early-stopped rounds)

| component | intercept-only (arm 1) | + 33 columns (arm 2) | share of arm 2 |
| :--- | ---: | ---: | ---: |
| `race` | 3.3704 | 1.0106 | 7.5% |
| `stint` | 5.3388 | 2.7022 | 20.0% |
| `driver` | 0.0000 | 0.0000 | 0.0% |
| `constructor` | 0.0052 | 0.0112 | 0.1% |
| `Error_var` | 33.3190 | **9.8103** | 72.5% |
| total | 42.0334 | 13.5343 | |

#### Arm 2b — gate 4 (permutation null): PASSES, and by a wide margin

All 33 columns row-shuffled under one joint permutation (preserving feature–feature structure
and therefore capacity exactly), refit at the identical 1,499 rounds:

`race` 3.3937 · `stint` 5.3444 · `driver` 0.0000 · `constructor` 0.0014 · **`Error_var` 32.7428**

- **capacity** (what the ensemble buys on destroyed signal): `33.3190 − 32.7428 = 0.5762`, 1.7% of
  the intercept-only residual.
- **information** (what the columns actually carry): `32.7428 − 9.8103 = 22.9325`.

An information-to-capacity ratio of ~40:1. The drop in residual variance is real signal, not the
capacity artefact `gates.md` step 4 exists to catch. This arm also does double duty as the
in-sample optimism bound, which arm 4 uses.

#### Arm 3 — gate 3 as pre-registered is DEGENERATE. No reseed floor was obtained.

All five reseeds returned **byte-identical** components (`Error_var` 9.8103 at every one of
`S.RANDOM_STATE + 0..4`), so `2*sqrt(2)*sd = 0.0000` exactly and every floor ratio is infinite.

**Verified cause, not inferred:** the parameter dict carries no `bagging_fraction`,
`feature_fraction`, `bagging_freq` or `subsample`, so the GPBoost fit has **no stochastic
component at all** and `seed` cannot move it. The reseed-floor construction that `gates.md`
step 3 specifies measures sampling variation across seeds; transplanted onto a deterministic
fit it measures nothing, and a floor of 0.0000 must never be read as "extremely stable".

**Deviation logged.** The pre-registration named arm 3 as the adapted gate 3 and it did not
deliver. The uncertainty that actually governs these components is arm 0c's **sampling**
distribution, which is where every precision claim in this section is anchored instead. Adding
bagging to manufacture a non-degenerate seed floor was **not** done: it would return a number
far smaller than the sampling uncertainty already measured, at the cost of changing the fit.

#### Arm 3b — the tree-fitted non-overlapping arm is NOT quotable

Reported for completeness: on 15,897 non-overlapping rows at 1,057 rounds — `race` 1.3645 ·
`stint` 0.0000 · `Error_var` 17.3058. **It is not used for anything**, for two reasons found
after the fact:

- 1,057 boosting rounds against 12,985 training rows is a far higher capacity-per-row than
  arm 2's, and **no matching permutation null was run at that ratio**, so its optimism is
  unmeasured and its `Error_var` is not comparable to arm 2's.
- the subsample is **position-locked, not random**: "every 5th lap from the first" always keeps
  stint position 0, so it over-represents early-stint rows. `var(y)` on it is **51.2947** against
  40.1149 on all rows — a materially different population. `ceiling.py`'s `non_overlapping` block
  uses the same construction and inherits the same bias.

#### Arm 3c — the overlap question answered cleanly, with no trees involved

Added after arm 3b proved unusable. Intercept-only on both row sets, so there is no tree fit to
confound it — the like-for-like comparison against arm 1:

| | all rows | non-overlapping | 
| :--- | ---: | ---: |
| n / rows per stint | 68,574 / 13.26 | 15,897 / 3.07 |
| `race` | 3.3704 | 3.8351 |
| **`stint`** | **5.3388** | **0.0004** |
| `Error_var` | 33.3190 | 48.5072 |
| `ceiling.py` one-way ANOVA stint ICC | 0.174836 | 0.021334 |

**The between-stint variance in this target is almost entirely an artefact of the overlapping
5-lap window.** Two independent estimators collapse together — REML's `stint` component from
5.3388 to 0.0004, and `ceiling.py`'s ANOVA ICC from 0.1748 to 0.0213 — and the second lands in
the same neighbourhood as the `attainable.variance` block's own mart-scope non-overlapping
figure of 0.00806. Race structure, by contrast, is stable across the two row sets (3.37 → 3.84)
and is therefore real.

**Assumed:** that `stint ≈ 0` is absence rather than low power. At 3.07 rows per stint the design
is weak, though arm 0c's null arm shows the estimator returns exactly 0.000 rather than noise
when a component is truly absent, and the ANOVA agrees at 0.0213. Not separately powered.

#### Arm 4 — reconciliation, and the falsification pattern

`σ_residual` bridged to the programme's live scores. Measured inputs, not assumed:
population ratio `var(eval)/var(train) = 32.8307/40.1149 = 0.81841`; shape factor
`E|z − median(z)|` = **0.68605 (train)**, **0.70751 (eval)**, against the Gaussian 0.79788.

A leg landing **above** the achieved 1.0163386 is not a floor — no predictor can beat an
irreducible floor — so it falsifies its own assumptions and is marked as such:

| σ²_resid source | train pop / gaussian | train pop / train shape | **eval pop / eval shape** |
| :--- | ---: | ---: | ---: |
| arm 1, no features (33.3190) | 2.3028 ✗ | 1.9800 ✗ | 1.8473 ✗ |
| **arm 2, 33 columns (9.8103)** | 1.2495 ✗ | 1.0744 ✗ | **1.0024 → 1.4% headroom** |
| arm 2c, optimism-corrected (10.3865) | 1.2857 ✗ | 1.1055 ✗ | 1.0314 ✗ (−1.5%) |

**Only one leg in the whole table is self-consistent**, and the falsifications are informative:
they say the Gaussian shape assumption and the train-population anchoring each break the bridge
on their own. The two legs that survive or nearly survive straddle the achieved loss by ±1.5%.

**The finding.** By this instrument, `degradation_regressor_p50` is sitting **at its model-based
noise floor to within ±1.5%**. The honest statement is a bracket, not a point: **between 0% and
~1.4% of the headline pinball remains available**, and the optimism-corrected leg cannot resolve
even that much.

**Also falsified: the "unseen race" floor.** `resid + race + stint` = 13.5231 implies 1.1769 on
the surviving leg, comfortably above the achieved 1.0163 — so the production model beats a floor
built on the assumption that residual race- and stint-level structure is unrecoverable. Two
candidate causes, neither tested here: 2024's race/stint effects are not draws from the
train-fitted distribution (the season-variance decline), and in-sample RE fitting inflates those
two components by absorbing what the trees leave. Recorded as open.

#### Sensitivity — the IPW-weighted fit, and why the unweighted one is still the one quoted

Production's quantile trio trains under IPW `survival_weight` (mean 1.7126, range 1.0266–4.0000).
Refit at the identical 1,499 rounds with those weights:

`race` 1.1829 · `stint` 3.0553 · `driver` 0.0000 · `constructor` 0.0153 · **`Error_var` 15.8951**

A **62% higher residual** than the unweighted 9.8103 — the two disagree materially, and the
pre-registration's tie-break applies: the unweighted fit is quoted, the gap reported. But there
is a stronger reason than the declared preference, found by running it: **the production headline
is *scored* unweighted on the eval fold** (`evaluate.py::_score` applies no weights), so the
population the 1.0163386 describes is the unweighted one, and only the unweighted component
bridges to it. The weighted fit describes the IPW-reweighted training population instead.

Recorded as a fact about the models rather than about this probe: **the population the degradation
trio is trained on is substantially noisier than the population it is scored on.** IPW up-weights
exactly the late-stint, long-stint rows where the 5-lap target is most variable. Nothing here
tests what that does to the headline; it is flagged for `01` and `09`.

#### Two GPBoost library findings, recorded so the next probe does not rediscover them

- **`GPModel.fit(y=...)` fits no intercept** unless `X` is passed. Silent: it decomposes `E[y²]`,
  not `Var(y)`.
- **Sample weights must go to the `GPModel()` constructor, not `Dataset(weight=)`** — and passing
  them to both is rejected by the C++ layer with `Weights need to be provided to the 'GPModel()'
  constructor`. The Python constructor accepts a `weights` kwarg either way, so the failure only
  appears at `train()`.

#### What this says about `05a`, and what it does not

`05a`'s block is written as: it moves up only if `01` shows real headroom, and closes unstarted
if the trio sits near a trustworthy floor. **This leg says the floor is where the model already
is.** That is evidence toward closing `05a`, and it is deliberately *not* acted on here — `05c`
is one leg of a three-leg bracket and the other two (`01a`'s learning curves, `01b`'s
difference-based floor) have not run. A single model-based estimate, resting on a Gaussian-shape
bridge and a proportional population rescale, is not grounds to close the most expensive item in
the programme.

**What `01b` must return for the bracket to close:** an irreducible-noise estimate on the
`cv_final_fold` **eval** population, expressed as either a residual sd in seconds or directly as
a p50 pinball floor. This leg's value is **σ = 2.8335 s → pinball 1.0024**, and the leg is
already known to be a *lower* bound (both the 1,499-round tree fit and the 5,173-level stint
random effect are fitted on the rows the components are read from). Report the spread; do not
average it.

#### Stage (as recorded 2026-09-08 — superseded, see the end of this item)

**`MEASURED`, not `GATED`.** Gate 1 passed (arm 0a bit-identical, plus synthetic recovery), gate
4 passed decisively (arm 2b), gate 6 was run in full, gates 2 and 5 are N/A by construction — and
**gate 3 did not deliver**, so the standing gate has not been passed end-to-end. Per
[`../status/BUILD-ORDER.md`](../status/BUILD-ORDER.md), a number that has not been through
`gates.md` is `MEASURED`, however good it looks.

---

### 05c — RESULTS 2026-09-08 (part 3: the repair pass, written into this doc 2026-09-17)

This session ran after part 2 and its findings reached `build-log.json`'s `05c` note but never
this doc, which is the divergence the standing rule forbids. Recorded here as the record has it,
and marked where this session's own re-derivation disagrees with the arithmetic in that note.

**The IPW sensitivity arm was re-run, because part 2's version of it was not interpretable.** The
original script passed sample weights to `gpb.Dataset(weight=)`, which `gpboost` 1.7.4 rejects —
they belong on `GPModel(weights=)` — and it died there before its `json.dump`, losing arms
2/2b/3/3b to the log. Re-run with the weights
**normalised to mean 1** (raw `survival_weight` averaged 1.7126 and gpboost divides the nugget by
`weights[i]`, so raw weights would have rescaled `Error_var` against arm 2 for reasons unrelated
to the reweighting): `race` 1.1826 · `stint` 3.0516 · `driver` 0.0004 · `constructor` 0.0154 ·
**`Error_var` 9.2769**, total 13.5269 against arm 2's 13.5343. **The total is invariant; the
composition is not** — reweighting moves ~0.53 out of `Error_var` into `race` and `stint`, so the
floor leg is weight-sensitive: 0.9747 (4.1%) against arm 2's 1.0024 (1.4%).

*Why part 2's 15.8951 must not be read, verified rather than asserted.* `15.8951 / 9.2769 =
1.7134`, which is the mean raw `survival_weight` (**1.7126**) to within 0.05%. gpboost divides the
nugget by `weights[i]`, so part 2's number is the *same fit* with `Error_var` rescaled by the
weight mean — an artefact of not normalising, not a second result. It is not comparable to arm 2's
9.8103 and the 62%-higher-residual reading in part 2 is withdrawn.

**A 2024 sanity check, also never run in part 2.** rmse 3.4726 and `0.5*MAE` of the conditional
*mean* 1.1428 on the 13,896 eval rows against the achieved 1.0163386 — the probe's mean fit is
~12% worse than production at α=0.5, as expected for a mean fit on a skewed target. It confirms
these components come from a **weaker model** than the one whose headroom they bound.

**A thin-2 arm did not rescue arm 3b.** Every 2nd lap is position-locked exactly as arm 3b
documents, `var(y)` 43.4841 against 40.1149, and `Error_var` 12.8627 implies 1.1478 — above the
achieved 1.0163 and therefore self-falsifying. Thinning is monotone across 1/2/5 (`stint`
2.7022/1.2714/0.0000, `Error_var` 9.8103/12.8627/17.3058, floor 1.0024/1.1478/1.3313), which adds
nothing to arm 3c. **No tree-fitted thinned arm is quotable at any thinning level.**

#### Gate 3, the real substitute: a cluster bootstrap over races — and it FAILS

Arm 0c measures estimator noise at a fixed synthetic truth. The gate-3 question is different:
what if the races actually observed had been different ones. Five draws, races resampled with
replacement, `race` and `stint` ids re-labelled per draw so a duplicated race acts as an
independent draw, rounds fixed at 1,499.

`Error_var` draws **7.3782 / 7.8434 / 9.0440 / 7.2143 / 8.6362**, sd **0.7938**.

- The 1.4% headroom is **0.0140** in absolute pinball. Against a floor sd of ≈0.041 that is
  **0.34× one sd**, and ≈0.12× a gate-style `2*sqrt(2)*sd` threshold.
- The floor's ±1.96 sd interval, ≈**0.923 – 1.082**, **contains the achieved 1.0163386**.
- The IPW variant's larger 4.1% headroom (0.0416) is still only ≈1.0× the sd, so the
  1.4%-vs-4.1% modelling-choice spread is itself inside the noise and is not a real disagreement.

*Arithmetic note, logged 2026-09-17.* `build-log.json` records the floor sd as 0.0446 and the
gate threshold as 0.1263, giving 0.31× and 0.11×. Re-deriving from the same recorded inputs
(`sd(Error_var)` 0.7938, `Error_var` 9.8103, shape 0.70751, population ratio 0.81841) gives
**0.0406 / 0.1147** and 0.34× / 0.12× — the note's propagation omitted the `sqrt(population
ratio)` factor that its own floor includes. **The verdict is identical either way** and nothing
downstream changes; it is recorded so the numbers reconcile.

**Use the bootstrap's sd, never its mean.** Draws come back biased low (a draw holds only ~63%
distinct races while rounds stay fixed at 1,499, so capacity per distinct row rises above arm 2's).

**Consequence, and it is the headline.** `degradation_regressor_p50`'s achieved loss is
**indistinguishable from its model-based noise floor**, and **no headroom percentage — not 1.4%,
not ±1.5% — is quotable from this probe.** Direction only. Part 2's `±1.5%` phrasing is retracted
by this section.

---

### 05c — RERUN 2026-09-17 on the v12 substrate. The probe no longer binds, and the reason is measurable.

Part 2's answer describes a target that `08m` has since rebuilt. This section re-runs the same
instrument against what production predicts today, adds the three arms the 2026-09-08 run did not
have, and closes the definition of done's reconciliation clause in the section after it.

**Environment.** `gpboost` 1.7.4, installed to a scratchpad directory appended to `sys.path`
(*after* the repo's own entries, so the repo's `numpy`/`pandas` win) — never into the repo venv,
never into `ml/requirements.txt`. Warehouse read `read_only=True` through
`features.py::load_features`. Split cached once and reused so every arm below runs on identical
rows. Probe throwaway, scratchpad only; nothing committed, no model artefact, no warehouse write,
no git state touched.

**A footgun found on the first run, worth more than the arm that found it.**
`evaluate.py`'s `MODELS_DIR` and `ARTEFACTS_DIR` are **relative** (`Path("ml/models")`). Run a
probe from anywhere but the repo root and `_params_for` finds no `*_best_params.json`, **silently
returns `train.SMOKE_DEFAULTS`, and fits a completely different model with no warning.** Arm 0a
failed at `5.258e-03` against the published headline until the probe was made to `chdir` to the
repo root, after which it is bit-identical. Any probe that reports a near-miss on gate 1 should
check its working directory before it checks its arithmetic.

#### The substrate, measured rather than assumed

| | v11 (2026-09-08) | v12 (2026-09-17) |
| :--- | ---: | ---: |
| train rows / eval rows | 68,574 / 13,896 | 67,907 / 13,712 |
| feature columns | 33 | 32 |
| races / stints / drivers / constructors | 123 / 5,173 / 37 / 16 | 123 / 5,176 / 37 / 16 |
| `var(y)` train / eval | 40.1149 / 32.8307 | 19.6415 / 12.9192 |
| population ratio `var(ev)/var(tr)` | 0.81841 | **0.65775** |
| achieved p50 pinball | 1.0163386141079709 | **0.9823587335698977** |
| mean IPW `survival_weight` | 1.7126 | 1.9704 |
| within-stint lag-1 autocorrelation | 0.6044 | **0.3501** (train) / 0.4000 (eval) |
| shape factor, eval (Gaussian = 0.79788) | 0.70751 | 0.59308 |

**Arm 0a passes bit-identically**: `evaluate.py::_fit`/`_score` at v12 params on `cv_final_fold`
returns `0.9823587335698977` against the published `0.9823587335698977`, absolute difference
`0.000e+00`.

#### Arm 1 — the raw decomposition, and arm 2 — the fitted one

Intercept-only fitted with an explicit `X` column, per the library trap recorded in part 1.
Arm 2 uses the 32 contract columns at **630 rounds**, chosen by early stopping (50) on a
race-grouped 80/20 hold-out of the training rows, because part 1 established that the round count
is part of this instrument. Booster params declared before fitting: `regression_l2`, lr 0.05,
`max_depth` 6, `num_leaves` 31, `min_data_in_leaf` 20, **no bagging or feature subsampling**.

| component | arm 1 (no features) | share | arm 2 (32 columns) | share | v11 arm 2, for contrast |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `race` | 0.6490 | 3.3% | 0.4998 | 3.7% | 1.0106 |
| `stint` | 1.4109 | 7.1% | 1.9618 | 14.5% | 2.7022 |
| `driver` | 0.0000 | 0.0% | 0.0006 | 0.0% | 0.0000 |
| `constructor` | 0.0014 | 0.0% | 0.0169 | 0.1% | 0.0112 |
| **`Error_var`** | **17.8914** | **89.7%** | **11.0308** | **81.7%** | 9.8103 |
| total | 19.9527 | | 13.5098 | | 13.5343 |

**The residual share rose from v11's 79.3% to 89.7% before features and from 72.5% to 81.7%
after them.** Consistent with — though not independently established by — `08m`'s own measurement
that the target's seed-echo share fell from 88.6/92.6/89.0% to 39.69/49.90/23.54%: what the repair
removed was structured, so what is left is proportionally more noise. Read that as a corroboration
of `08m`, not as a second measurement of it.

**Driver and constructor identity again carry no measurable variance**, and the same caveat
applies unchanged: `next_5_lap_cumulative_jump_s` is a within-stint *change*, so a driver's
persistent pace level is differenced out by construction. `03` must not read this as "no driver
effect exists".

#### Arm 2b — gate 4 (permutation null): PASSES

All 32 columns row-shuffled under one joint permutation (capacity preserved exactly), refit at the
identical 630 rounds: `race` 0.6285 · `stint` 1.3946 · `driver` 0.0000 · `constructor` 0.0003 ·
**`Error_var` 17.7058**.

- **capacity** `17.8914 − 17.7058 = 0.1857`, 1.0% of the intercept-only residual;
- **information** `17.7058 − 11.0308 = 6.6750`.

A ratio of **36:1**, against v11's ~40:1. The drop in residual variance is real signal.

#### Arm 0c — the instrument does not manufacture components, at the v12 scale

The sampling result from 2026-09-08 is a property of the *design* (a variance from `k` groups
carries ≈`sqrt(2/(k-1))` relative sd on its own — 12.8% at `k=123`, 2.0% at 5,176, 23.6% at 37,
**36.5% at 16**) and the design is unchanged, so it carries without re-measurement. The null arm
does not, because the residual it sits against has halved. Re-run at the v12 scale, 8 replicates
each, truth for `race`/`stint`/`Error` taken from arm 1's own fit:

| condition | `driver` fitted | `constructor` fitted |
| :--- | :--- | :--- |
| null (`driver` = `constructor` = 0) | **0.0000 ± 0.0000** | **0.0026 ± 0.0018** |
| alt (`driver` 0.200, `constructor` 0.125 — the same *share* the v11 arm's 0.400/0.250 were) | 0.1514, p05–p95 0.113–0.181 | 0.1262, p05–p95 0.051–0.255 |

Arm 1's fitted `driver` 0.0000 and `constructor` 0.0014 sit **inside the null distribution and
below the 5th percentile of the alternative**, so those magnitudes are *excluded*, not merely
unresolved. Recovery of the other three under the null: `Error_var` 17.8911 against a true
17.8914 (sd 0.6%), `stint` 1.4088 against 1.4109 (sd 5.0%), `race` 0.5898 against 0.6490
(−9.1%, sd 11.3% — the analytic 12.8%).

#### The ANOVA cross-check now PASSES, which corroborates part 1's mechanism finding

Part 1 declared that a stint-only REML fit should reproduce `ceiling.py::variance_components`'
one-way ANOVA ICC on identical rows, found a gap of **+0.024183** on v11, and traced it — on
simulated data — to serial correlation from the overlapping 5-lap window, showing the two
estimators agree to <0.002 under every other departure and split only under AR(1).

On v12, with the same rows and the same two estimators: **ANOVA 0.098616 against REML 0.093663,
gap −0.004953** — five times smaller and the other sign. And the lag-1 autocorrelation that the
mechanism blamed has fallen from **0.6044 to 0.3501**. The 2026-09-08 diagnosis predicted exactly
this, on a substrate that did not exist when it was written.

#### Arm 3c — the overlap finding replicates

Intercept-only on both row sets, no trees to confound it:

| | all rows | non-overlapping (every 5th lap in stint) |
| :--- | ---: | ---: |
| n / rows per stint | 67,907 / 13.12 | 15,775 / 3.05 |
| `race` | 0.6490 | 1.7012 |
| **`stint`** | **1.4109** | **0.0004** |
| `Error_var` | 17.8914 | 29.7644 |
| `ceiling.py` one-way ANOVA stint ICC | 0.098616 | 0.055711 |

The `stint` component again collapses to ~0 on non-overlapping rows, so **the between-stint
variance in this target remains largely an artefact of the overlapping window** even after `08m`.
The position-lock caveat from part 2 not only survives but is *worse* on v12: `var(y)` on the
thinned rows is 30.9557 against 19.6415 on all rows, a ratio of 1.58 against v11's 1.28. Race
structure is again the stable one across the two row sets.

#### Sensitivity — the IPW-weighted fit

Weights normalised to mean 1, identical 630 rounds: `race` 0.5333 · `stint` 2.3039 · `driver`
0.0003 · `constructor` 0.0184 · **`Error_var` 10.4003**, total 13.2562. Reweighting takes 0.6305
out of `Error_var`, of which 0.3771 reappears in `stint` and `race` and 0.2536 leaves the total —
the same direction as v11's ~0.53, on a target of half the variance. Unlike v11, where the total
was invariant (13.5269 against 13.5343), here the total moves by 1.9%, so the v12 reweighting is
not a pure reallocation. The unweighted fit stays the quoted one for the reason
part 2 found by running it: **the production headline is scored unweighted** (`_score` applies no
weights), so only the unweighted component bridges to it.

#### Arm 6 — the out-of-sample check part 2 never ran

Every component in arms 1 and 2 is fitted *in sample*, which part 2 correctly flagged as the
reason its floor is a lower bound. This arm puts a number on that from the other side. The
**production v12 p50 model's own residuals on the 2024 eval rows** are a genuinely out-of-sample
read on the same unexplained variance, and `ceiling.py::variance_components` decomposes them with
a second, independent estimator. Extraction verified: `0.5·E|r|` on those residuals is
**0.982359**, the published headline to 6dp.

| | `var(resid)` | `race` σ²_b (ICC) | `stint` σ²_b (ICC) | `driver` ICC | `constructor` ICC |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 2024 eval, **out of sample** | **9.1686** | 0.4524 (0.0492) | 1.2974 (0.1415) | 0.0069 | 0.0036 |
| 2018–23 train, in sample | 9.1995 | 0.0856 (0.0093) | 0.9068 (0.0986) | 0.0033 | 0.0022 |

Two cross-instrument agreements fall out, neither of them arranged:

- **`01b`'s arm 5 measured the race ICC of the v11 production eval residuals at 0.0452.** The same
  quantity on v12 is **0.0492**. Two substrates, two sessions, the same number to within its own
  sampling error at `k=24`.
- **Arm 2's `stint` component, rescaled to the eval population, is 1.9618 × 0.65775 = 1.2905
  against this arm's 1.2974** — a REML variance component and a one-way ANOVA on a different
  model's residuals, agreeing to **0.5%**. `race` agrees less well (0.3288 against 0.4524, 27%
  apart) which is exactly where the sampling sd is largest.

The generalisation gap is the finding, though. The same `F(X)` leaves 47% of the target's variance
unexplained in sample on the training rows and **71% out of sample on 2024**.

#### Arm 7 — the eval population measured directly, instead of rescaled

Arm 4's bridge carries one assumption that is not about shape: that `σ²_residual` transfers from
the 2018–2023 population to 2024 in proportion to `var(y)`. On v11 that rescale was 0.818 and
forgiving. On v12 it is **0.658 and it decides the answer.** So it was removed rather than
defended — the same decomposition fitted **directly on the 13,712 eval rows**, no transfer.

| | `race` | `stint` | `Error_var` | total |
| :--- | ---: | ---: | ---: | ---: |
| 7a intercept-only, on 2024 | 0.4327 | 0.6519 | 11.9144 | 12.9996 |
| 7b + 32 columns @ 71 rounds | 0.3846 | 0.7533 | **9.6674** | 10.8054 |
| 7b-null, permutation null @ 71 rounds | 0.4405 | 0.6547 | 11.7923 | 12.8876 |

capacity 0.1221, information 2.1250 — a 17:1 ratio, so gate 4 passes on this row set too. The
derived optimism-corrected leg (`7c` in arm 4's table) is `9.6674 + 0.1221 = 9.7895`.
The cost is stated: 13,712 rows and 1,027 stints against
67,907 and 5,176, fitted in sample on the very rows the headline is scored on, so **this leg is a
lower bound by more than arm 2 is, not less.**

**The obvious objection, and why it does not carry the conclusion.** 71 rounds against arm 2's 630
is a much weaker `F(X)`, and part 1 established that an underfit `F(X)` has nowhere to put its
error but the variance components — so arm 7b's 9.6674 is plausibly inflated by underfitting
rather than by the population. That objection is real, and it is why **arm 6 rather than arm 7
carries the argument**: arm 6's `F(X)` is the fully-trained production booster, 630-equivalent on
all 67,907 rows, and applied out of sample to 2024 it still leaves **9.1686**. A strong `F(X)` and
a weak one land 5% apart, and both land far above the 7.2555 the rescale predicts.

#### Arm 8 — is the rescale true? Half of it is, and it is the wrong half

The intercept-only four-level decomposition, refitted season by season. No trees, so nothing is
confounded by capacity-per-row.

| season | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `var(y)` | 22.832 | 21.711 | 24.655 | 22.158 | 15.207 | 11.774 | 12.919 |
| `Error_var` | 19.351 | 19.737 | 23.558 | 21.320 | 12.894 | 10.713 | 11.914 |
| **residual share** | 0.848 | 0.909 | 0.956 | 0.962 | 0.848 | 0.910 | **0.922** |

**The raw rescale is supported**: the residual share is 0.908 ± 0.046 across seven seasons and
2024's 0.922 sits well inside that. Note also that the season-variance decline part 1 reported as
monotone on v11 is **not monotone on v12** — 2023 (11.77) is lower than 2024 (12.92).

**What is not supported is the rescale of the *fitted* residual**, which is what arm 4 actually
transports. Arm 2's `Error_var` rescaled to the eval population is `11.0308 × 0.65775 = 7.2555`.
Arm 6 measures the production model's genuine out-of-sample residual variance on those same rows
at **9.1686** — **26.4% higher than the rescaled leg, and that 9.1686 already contains model
error**, so the true noise is below it. The transfer assumes `F(X)` removes the same *share* of
variance on both populations; arm 6 measures that it removes 53% in sample and 29% out of sample.

**The sharpest version, and the one to quote.** Arm 6 gives the fitted residual on both
populations for the same `F(X)`: **9.1995 on the training rows (in sample) against 9.1686 on 2024
(out of sample), a ratio of 0.997.** The *fitted* residual is very nearly invariant across the two
populations, while `var(y)` falls by 34%. Arm 4 transports it by 0.658. Solving for the transfer
ratio at which arm 2's leg would exactly equal the achieved loss gives **`r* = 0.832`**:

| transfer ratio | source | implied p50 floor | |
| ---: | :--- | ---: | :--- |
| 0.658 | `var(y_eval)/var(y_train)` — what arm 4 assumes | 0.8736 | survives |
| **0.997** | **measured, production's own fitted residual on both** | **1.0754** | **falsifies** |
| 1.000 | no transfer at all | 1.0772 | falsifies |

**The surviving leg requires the fitted residual to shrink by more than 17% between the two
populations. The only direct measurement of that shrinkage says it shrinks by 0.3%.** The caveat
that keeps this from being conclusive is stated: 9.1995 is in sample on the training rows and is
therefore optimistically low, so the true ratio is below 0.997 — but it would have to fall past
0.832 to rescue the leg, and nothing here suggests in-sample optimism of that size.

#### Arm 4 — the bridge, and what it now says

`σ_residual` converted to the p50 pinball under an explicit shape, reported as an *implied floor*
and never as a measurement. Three shapes, because the choice matters more than it did on v11:
the Gaussian `sqrt(2/π)` = 0.79788; the within-stint `y`-deviation shape 0.59308 that part 2 used;
and — new here, and the best anchored of the three — **0.64868, the shape of production's own 2024
residuals**, which is the distribution the published pinball is actually computed over. Legs on
the training population are rescaled by 0.65775; legs already on the eval population are not.

| `σ²_resid` source | value | gaussian | `y`-shape | **residual shape** |
| :--- | ---: | ---: | ---: | ---: |
| arm 1, no features *(train pop)* | 17.8914 | 1.3686 ✗ | 1.0173 ✗ | 1.1126 ✗ |
| **arm 2, 32 columns** *(train pop)* | 11.0308 | 1.0746 ✗ | 0.7988 | **0.8736** |
| arm 2c, optimism-corrected *(train pop)* | 11.2164 | 1.0836 ✗ | 0.8055 | 0.8810 |
| IPW sensitivity *(train pop)* | 10.4003 | 1.0434 ✗ | 0.7756 | 0.8483 |
| unseen-race, resid+race+stint *(train pop)* | 13.4923 | 1.1885 ✗ | 0.8834 | 0.9662 |
| arm 7a, intercept-only **on 2024** | 11.9144 | 1.3770 ✗ | 1.0236 ✗ | 1.1195 ✗ |
| **arm 7b, 32 columns on 2024** | 9.6674 | 1.2404 ✗ | 0.9220 | **1.0084 ✗** |
| arm 7c, optimism-corrected **on 2024** | 9.7895 | 1.2482 ✗ | 0.9278 | 1.0148 ✗ |
| arm 6, production OOS residual **on 2024** | 9.1686 | 1.2080 ✗ | 0.8979 | 0.9821 |

✗ marks a leg landing **above** the achieved 0.9823587 — no predictor can beat an irreducible
floor, so such a leg falsifies its own assumptions rather than bounding anything.

**Read the table by what each leg assumes, not by which number is smallest.**

- **Every leg measured directly on the eval population falsifies** under the best-anchored shape.
  Arm 7b's 1.0084 is the sharp one: the probe's own estimate of irreducible noise on 2024
  (`σ²` 9.6674) is **larger than the production model's actual out-of-sample residual variance on
  the same rows** (9.1686). A real predictor beats it, so it is not a floor. The comparison is
  doubly unfavourable to production and it still wins: production is a **median** fit, and the
  conditional mean is what minimises squared error, so a median predictor's residual variance can
  only be larger than a mean fit's on the same conditional distribution — and production is also
  the one being scored **out of sample**, where the probe is in sample.
- **The only legs that survive are the rescaled training-population ones** — and arm 8 measures
  that this is the rescale that does not hold.
- **Arm 6's 0.9821 is circular** and is printed only as a consistency check: it uses the very
  residuals the shape factor is taken from, so it reproduces the achieved loss by construction.
- **The CRPS leg falsifies everywhere**, at every source: implied CRPS runs 1.4756–1.9474 against
  `09a`'s achieved 1.3795 (and its `unc` 1.6850). The CRPS bridge `σ/sqrt(π)` has no
  empirical-shape correction available, and at a measured shape 19–26% below Gaussian it is simply
  not usable on this target. Recorded so the next probe does not spend a day on it.

**So the v12 answer is not part 2's answer.** On v11 one leg survived and read 1.4% headroom; here
the surviving legs and the falsifying legs **straddle the achieved loss**, and the spread across
the table under a single shape — 0.7988 to 1.1195 — is about **33% of the headline**, an order of
magnitude larger than any headroom anyone would want to claim from it.

#### Gate 3 on v12 — degenerate as pre-registered, and the substitute fails it by a hair

**As pre-registered it is degenerate again, and this was verified rather than assumed.** Five
reseeds at `S.RANDOM_STATE + i` return **byte-identical** components — `Error_var`
`11.030768189898309` at every one of the five — so `2*sqrt(2)*sd` is exactly **0.0000000000** and
every floor ratio is infinite. The cause is the same one part 2 diagnosed: the parameter dict
carries no `bagging_fraction`, `feature_fraction` or `subsample`, so the fit has **no stochastic
component** and `seed` cannot move it. A floor of 0.0000 must never be read as "extremely stable".
Bagging was again **not** added to manufacture a non-degenerate seed floor.

**The substitute, run at ten draws rather than the 2026-09-08 pass's five.** Races resampled with
replacement; `race` and `stint` ids re-labelled per draw so a duplicated race acts as an
independent draw; `driver` and `constructor` labels left alone because they are the crossing
levels; rounds fixed at arm 2's 630.

`Error_var` draws **8.9603 · 11.0062 · 11.9382 · 9.9973 · 9.4785 · 11.6573 · 11.0976 · 10.5993 ·
9.5268 · 11.3305** — mean 10.5592, **sd 1.0165**. Draws hold 73–84 of the 123 races distinct, and
the mean comes back 4.3% below the full-data 11.0308 exactly as the construction predicts, so the
**sd is the error bar and the mean is not a point estimate** — the same caveat as v11, at a fifth
of the v11 pass's bias.

| | value |
| :--- | ---: |
| arm 2 rescaled leg, implied floor | 0.8736 |
| floor sd, propagated from `sd(Error_var)` = 1.0165 | 0.0403 |
| gate-style `2*sqrt(2)*sd` threshold | 0.1139 |
| headroom against the achieved 0.9823587 | **+0.1087** |
| headroom in sd | 2.70× |
| **headroom against the gate threshold** | **0.95× — FAILS, narrowly** |
| floor ±1.96 sd | 0.7947 – 0.9525 (does **not** contain achieved) |

**Gate 3 fails, and the near-miss is the least interesting thing in this table.** On v11 the same
construction put the headroom at 0.12× the threshold — deep inside noise. On v12 it is 0.95×,
*just* short. A reader could be forgiven for thinking one more draw would settle it. It would not,
because **this gate prices only sampling variability, and sampling variability is not the dominant
error on this leg.** Arm 8 measures the other one: moving the transfer ratio from the assumed
0.658 to the measured 0.997 moves this same leg from 0.8736 to 1.0754, a shift of **0.2018 — 5.0×
the floor sd and 1.77× the gate threshold**, and it moves it from "10.9% headroom" to "falsified".

**So the gate-3 verdict and the arm-8 verdict point the same way for different reasons**, and the
larger of the two errors is the one the gate cannot see. `gates.md` step 3 is the right instrument
for a delta between two fits on one population; it has nothing to say about a leg that transports a
quantity between two populations, and that is where this leg's uncertainty actually lives.

---

### 05c — RECONCILIATION 2026-09-17. The definition of done's last clause, closed.

The definition of done asks for the four components **reconciled against `01a`'s learning curves
and `01b`'s bracket, with disagreements reported rather than averaged.** Part 2 could not do it —
neither had run. Both have since finished (`01a` `LANDED` 2026-09-08, `01b` `CLOSED` 2026-09-09).
This section is that reconciliation. Per [`../foundations/epistemics.md`](../foundations/epistemics.md)
the legs sit beside each other and are never differenced or averaged.

#### The three-leg bracket exists on v11, and only on v11

`01a` and `01b` were both measured against the **pre-`08m` target**, and neither has been re-run
since. `08n`'s ruling is that v11 and v12 headlines are different quantities, so the bracket is
stated where its legs actually live.

| leg | construction | p50 value | own error bar | bias direction |
| :--- | :--- | ---: | :--- | :--- |
| `01a` learning curves | extrapolated intercept of `y(n) = c + a·n^(−b)` over ten row fractions | 0.9638 | LOO 0.8353 – 1.0106 | not identified |
| `01b` difference-based floor (L3) | matched-cell on 3 coordinates, eval rows | 1.0641 | 0.9388 – 1.1909 | **up** by theorem; **down** by a 4.5% race ICC |
| `05c` GPBoost (this item) | model-based `σ²_residual`, shape bridge, proportional rescale | 1.0024 | ≈0.9229 – 1.0819 | **down** — in sample on both the tree and the 5,173-level stint effect |
| — | **achieved** | **1.0163386** | | |

**The disagreement is larger than the quantity.** The three point estimates span **0.9638 to
1.0641 — 0.1003, or 9.9% of the headline** — against the largest headroom any of them claims
(`01a`'s 5.2%). Every leg's own interval contains the achieved loss, or its spread exceeds its own
claim. Averaging them would manufacture a precision that none of them has.

**They agree on direction, and on nothing finer.** `01a`'s intercept is the only leg whose point
estimate suggests material headroom, and `01a` itself declares it unusable — the leave-one-out
span is 3.3× the 0.0526 it claims. `01b`'s floor comes back *above* achieved, which is its own
pre-registered falsification condition. `05c`'s comes back below by 1.4%, which its own cluster
bootstrap then shows is 0.34× one sd. **Three instruments, three different failure modes, one
answer: no headroom that any of them can resolve.**

**The pairing `01b` already drew is confirmed.** `01b`'s arm 7 recorded leg C (this item) at 5.8%
below leg A (its own L3) and, since C is a lower bound where A is an upper one, read the p50 answer
as `L* ∈ [1.0024, 1.0641]` with the achieved 1.0163 inside it. Re-derived here from the two
published numbers: `1.0024 / 1.0641 = 0.94202`, i.e. 5.8%. That bracket stands as `01b` stated it.

#### Two reconciliations that are not with `01`, and both moved

- **`ceiling.py`'s one-way ANOVA.** Part 1's declared cross-check *failed* on v11 (ANOVA 0.174836
  against REML 0.199020) and part 1 traced the gap to serial correlation from the overlapping
  window. On v12 the same check **passes** — 0.098616 against 0.093663, gap −0.004953 — and the
  lag-1 autocorrelation it blamed has fallen from 0.6044 to 0.3501. A prediction made on one
  substrate, confirmed on another.
- **`09a`'s CRPS.** Part 2 bridged `σ` to CRPS as `σ/sqrt(π)` and reported it beside `09a`'s
  achieved. On v12 that bridge **falsifies at every source** (1.4756–1.9474 against an achieved
  1.3795), because it has no empirical-shape correction and the measured shape is 19–26% below
  Gaussian. The CRPS leg is withdrawn rather than quoted.

#### There is no three-leg bracket on the substrate production actually runs

This is the part worth carrying forward. **The bracket that `05a`'s closure rests on is entirely
on a retired target.** `01a`'s curves, `01b`'s floor and `05c`'s v11 components all describe
`next_5_lap_cumulative_jump_s` as it was before `08m` repaired it. On the live v12 target only
this item has a leg, and **this item's v12 leg does not bind.**

**What `01b` would have to return for a v12 bracket to exist:** an irreducible-noise estimate on
the `cv_final_fold` **2024 eval population of the v12 target**, as a residual sd in seconds or
directly as a p50 pinball floor. This item's v12 values for that comparison, with the spread
reported rather than collapsed:

| leg | `σ²` | `σ` | implied p50 floor | what it rests on |
| :--- | ---: | ---: | ---: | :--- |
| arm 2, rescaled to eval | 7.2555 | 2.6936 | 0.8736 | a fitted-residual rescale **arm 8 contradicts** |
| arm 7b, fitted on eval | 9.6674 | 3.1093 | 1.0084 ✗ | no transfer assumption at all — but a real predictor beats it, so it is not a floor |
| arm 6, production OOS residual | 9.1686 | 3.0280 | 0.9821 | circular; an upper bound only |

**Do not average these.** The honest statement of this item's v12 leg is a direction and a
refusal: **the achieved 0.9823587 cannot be separated from the model-based noise floor by this
instrument, and no headroom percentage is quotable in either direction.**

#### What this does and does not do to `05a`

`05a` was closed unstarted on 2026-09-11 under decision `D8`, and one of the three planks was this
item's v11 finding. **That closure is not disturbed and is deliberately not revisited here.** Its
own do-not-reopen clause requires *evidence that changes the headroom bracket itself — a ceiling
instrument finding real headroom that `01a`/`01b`/`05c` missed.* This rerun finds no such thing:
it finds that the instrument **cannot resolve** headroom on the repaired target, which is the same
direction as before and a weaker claim, not a contrary one. The closure also already rested on the
repair pass's *"no percentage is quotable, direction only, and the direction is none"* rather than
on the retracted `±1.5%`.

**What is flagged, and left for `01` and `11` rather than acted on here:** the statement *"the
floor is where the model already is"* was a v11 statement and **does not reproduce on v12**. On
the repaired target the model explains materially less of the target (arm 6: 29% of the eval
variance, against 53% in sample on train), and the instrument that used to pin it to its floor no
longer resolves the question.

**And there is a conflict here that this item cannot settle and should not paper over.** The
natural next move — re-run `01b` against the v12 target so the bracket has a second live leg —
runs into `01b`'s own do-not-reopen clause, which admits exactly three triggers: an eval population
with repeated circuits inside a season, `08d`'s C1–C5 identity, or a lower-dimensional target.
**A target rebuild is none of the three**, because the clause was written before `08m` existed and
could not contemplate it. Whether that counts as new evidence is a judgement about `01b`'s scope,
not a measurement, so it is **raised here and left for the orchestrating session or a human call**
rather than assumed either way. What this item can say is the factual half: `01a` and `01b` both
describe a target that production no longer predicts.

#### Stage — this item's verdict, 2026-09-17

**`CLOSED`**, as a completed measurement whose answer is a refusal rather than a number — which is
the programme working, not failing. *The stage change in [`../status/build-log.json`](../status/build-log.json)
is the orchestrating session's to make; this section records the item's own verdict against its own
definition of done.*

**Every clause of the definition of done is delivered.** Four variance components — on the retired
v11 target (parts 1–3) and on the live v12 target (this rerun). Their fit diagnostics: an
instrument check that reproduces the published headline bit-identically, a null/alternative
recovery study that shows the estimator neither manufactures nor resolves the small-`k` levels, a
permutation null on two independent row sets, a ten-draw cluster bootstrap over races, an
out-of-sample cross-check against the production model's own residuals, a direct fit on the eval
population, and a season-by-season test of the one assumption the bridge cannot avoid. Reconciled
against `01a`'s learning curves and `01b`'s bracket in the section above, **with the disagreement
quantified (a 9.9%-of-headline spread against a largest claim of 5.2%) and explicitly not
averaged**. And it **shipped nothing**, as specified — no artefact, no contract change, no ONNX,
no entry in `ml/requirements.txt`.

**Gates.**

| gate | verdict |
| :--- | :--- |
| 1 | **PASSED** — arm 0a reproduces `0.9823587335698977` bit-identically (`0.000e+00`), once the relative-path footgun was found |
| 2 | **N/A** — nothing is added and no delta is claimed |
| 3 | **FAILS** — degenerate as pre-registered (five reseeds byte-identical, `2*sqrt(2)*sd` exactly 0.0000), and the cluster-bootstrap substitute puts the surviving leg's headroom at 0.95× the threshold |
| 4 | **PASSED twice** — 36:1 on the training rows (arm 2b), 17:1 on the eval rows (arm 7b-null) |
| 5 | **N/A** — no new features; the 32 contract columns cleared their own forward-window checks when admitted |
| 6 | **HONOURED** — the 2026-09-08 pre-registration above is unedited, and every deviation from it is logged beside the arm that deviated |

There is no candidate change for `gates.md` to price end-to-end, because **the item ships nothing
by construction** — the same structure under which `05d` closed. `CLOSED` here means the question
was answered, not that a number passed a gate.

**Deviations from the pre-registration, logged.** (i) Arm 3 as written is degenerate on both
substrates and was replaced by the cluster bootstrap, as the 2026-09-08 pass first did. (ii) Arms
6, 7 and 8 are **new** and were not pre-registered — they were added after arm 4's v12 legs
disagreed, to test the bridge's population assumption rather than to produce a headline, and each
is reported with what it can and cannot support. (iii) The CRPS bridge declared in the
pre-registration's arm 4 is **withdrawn**, not merely reported, because it falsifies at every
source. (iv) Arm 0c's ±20% / ±10% tolerances were already shown unmeetable on a 16-level design by
the 2026-09-08 pass; this rerun does not re-apply them and uses the null/alternative comparison
instead.

**What would reopen this item.** Not a better fitter, and not more bootstrap draws — the dominant
error is the population transfer, not the estimator. It reopens on either: **(a)** a defensible
measurement of how the *fitted* residual transfers between the training and eval populations
(arm 8 measures the raw residual's transfer at 0.908 ± 0.046 and the fitted residual's at ~0.997,
and the bridge needs below 0.832 to survive); or **(b)** a second live leg on the v12 target from a
different construction, at which point the three-leg bracket this item's definition of done is
built around would exist on the substrate production actually runs. Neither is in this item's gift.

**Reusable findings, so the next probe does not rediscover them.** In addition to part 2's two
gpboost traps (`GPModel.fit(y=...)` fits no intercept unless `X` is passed; sample weights go to
the `GPModel()` constructor, not `Dataset(weight=)`), this rerun adds three:

- **`evaluate.MODELS_DIR` and `ARTEFACTS_DIR` are relative paths.** A probe run outside the repo
  root silently fits `SMOKE_DEFAULTS`. Check the working directory before the arithmetic.
- **`gpboost` 1.7.4 rejects `params={"std_dev": ...}`** — standard errors moved onto `summary()`,
  `get_cov_pars()` and `get_coef()` as a `std_err` argument.
- **Sample weights must be normalised to mean 1** before they are compared against an unweighted
  fit, because gpboost divides the nugget by `weights[i]`; the un-normalised `Error_var` differs
  from the normalised one by exactly the weight mean, as part 3 verifies to 0.05%.

---

## 05d — The training window. Raised by `01a`, not acted on.

**Objective.** `01a` found that the cliff classifier is **better trained on 2021–2023 than on the
full 2018–2023**: macro-F1 0.39318 against 0.38027, `+0.01291`, **3.71× its own reseed floor**
(0.00349) — obtained by deleting 44,206 rows, 46% of its training data. Full result and the two
other arms are in [`01-ceiling-instrument.md`](01-ceiling-instrument.md) §`01a — RESULT`.

That is a larger delta than most feature-group results the programme has shipped on, and it is a
change to what production trains on. It sits here rather than in `01` because "which rows the
model is fitted on" is a model-design choice of the same kind as "which model class", and it is
priced by the same ladder.

**It has deliberately NOT been acted on.** `01a` was a ceiling measurement; changing production
training on the back of it, in the same session, without the gate, is exactly the move
`foundations/gates.md` exists to prevent.

**The confound this item must close, which `01a` could not.** `features.py::load_features` fits
the ordinal encoder on the full 2018–2023 training frame *before* any split, and `01a` subset rows
of the already-encoded matrix — so the encoding was held fixed and `01a`'s arms are internally
clean. A real window change is not a row filter: it would refit the encoder, and HYPERSOFT /
SUPERSOFT / ULTRASOFT — three of the eight `compound` levels, present only in 2018 and in no 2024
eval row — would disappear from it, renumbering every remaining level. **So `01a`'s `+0.01291` is
not the number a production window change would return, and this item must measure the window
change with the encoder refit inside it.**

**Arms, to be pre-registered in full before running (gate 6).**

- **Window sweep with the encoder refit inside each fit**, not outside it, over the same
  most-recent-*k* ladder, for all five families rather than just the cliff classifier.
- **Multi-seed.** `01a`'s recency cells are single fits. Each window gets the same 5-seed
  treatment `attribution.py::refit_noise_floor` uses, so the delta has a floor rather than a
  point estimate under it.
- **More than one eval season.** `01a`'s eval side is 2024 alone, so "recent trains better" could
  be partly 2024-specific. Run the ladder against the other fold eval seasons.
- **Separate the two mechanisms.** Dropping 2018 removes *rows*, *compound levels* and *a
  regulation era* in one move. A compound-level-only arm (2018 kept, its three unique levels
  folded to a shared code) separates the encoding effect from the regime effect. Without it the
  finding cannot say which lever to pull, and "drop the season" and "fix the compound identity"
  are very different production changes — the second is `08d`.
- **Check it against `08d`.** If the mechanism is compound identity, `08d`'s real Pirelli C1–C5
  mapping may recover the dropped rows' value rather than confirming they should be dropped. That
  ordering matters: `08d` before a production window change, not after.

**Definition of done.** A window recommendation per family, each with its delta against that
family's own reseed floor, measured with the encoder refit inside the fit and on more than one
eval season; and a stated verdict on whether the effect is regime, encoding, or both. A window
change to production is a separate human call and is not in this item's scope.

### `05d` — RESULT (2026-09-15). The recommendation is the full window, for every family.

> **SUBSTRATE BANNER, added 2026-09-19 by the build-order audit.** This result ran on
> **2026-09-15, the day before `08m`**. Every one of its 900 fits is on the **pre-`08m` target**,
> and its gate-1 anchors are the **v11** headlines — `p10 0.5320213273637161`,
> `p50 1.0467899119026969`, `p90 0.578513617807211`, `cliff 0.37186552717207966`. Today's published
> headlines are v12's `0.47646 / 0.98237 / 0.51285 / 0.35247`
> (`ml/artefacts/evaluation_metrics.json`). The phrase *"`05d` (current substrate…)"* in the
> `01a`-reconciliation table below was true on 2026-09-15 and is not true now.
>
> A second drift on the stint-life row: its `S1x` arm used the parameter set `D4` had ruled to
> ship, on the pre-`08m` warehouse. `10e` landed `S1x` on **2026-09-19** after re-running it on
> v12 — same parameters, different substrate and a different eval fold (19,973 laps / 9,149
> green-pit).
>
> **The verdict is not retracted.** "Full window for every family" rests on within-run subset-vs-
> full comparisons that shared one target, across five eval seasons; the mechanism findings
> (encoding ruled out, 2018 ruled out, family-specific window saturation) are relative throughout.
> **The numbers have not been re-measured** and the ×-reseed-floor ratios in the tables below are
> against floors that `02b`'s 2026-09-19 re-run found moved by up to **3.2×** across `08m`
> (p10 0.004311 → 0.00136797). The near-miss cells — cliff `k=4` at **1.06×** and the `01a`
> replication at **2.57×** — are the ones where that matters; neither is shipping-grade either way
> on this item's own convention.
>
> `08m`'s §7 staleness table lists `08e`/`08f`/`08h`/`08i`, `02`, `11a`, `11b` and the production
> artefacts. **It does not list `05d`**, whose result landed one day earlier — which is why this
> banner did not exist until now. `08m`'s definition of done ("every number the fix invalidated is
> either re-measured or explicitly marked stale in its own leaf doc") is not met for this section
> or for [`01-ceiling-instrument.md`](01-ceiling-instrument.md).

Arms pre-registered in `scripts/arms_05d_training_window.py`'s docstring before any of them ran
(gate 6); every fit's headline, per seed, is in `ml/artefacts/05d_training_window_arms.json`.
900 fits, 59 minutes. **Gate 1 passed on all four unbarred families** — the full-window cell at
the canonical seed reproduced the published headline bit-identically (p10 `0.5320213273637161`,
p50 `1.0467899119026969`, p90 `0.578513617807211`, cliff `0.37186552717207966`).

**The confound `01a` could not close is closed, and it was not the problem.** Every arm here
refits the encoder on its own window's rows. One piece of luck made the comparison exact: 2024
introduces no categorical level that 2018–2023 does not already carry, so `encoder(2018–2023)`
and the production `encoder(2018–2024)` are the same map, and the full-window cell is directly
comparable to the published number rather than merely close to it.

#### The recommendation, per family

Read as a production rule — *train on the most recent k seasons* against the incumbent *train on
all of them* — aggregated over the five season-fold eval seasons where that rule is a proper
subset. Positive is improvement on every metric.

| family | best rule | eval seasons it wins | mean delta | × reseed floor | recommendation |
| :--- | :--- | ---: | ---: | ---: | :--- |
| degradation p10 | — | 0 / 15 cells | — | — | **full window** |
| degradation p50 | k=5 | 1 / 15 cells | +0.00707 | 0.68× | **full window** |
| degradation p90 | k=4 | 3 / 15 cells | −0.00123 | — | **full window** |
| **cliff** | **k=4** | **2 / 2** | **+0.00593** | **1.06×** | **full window** (see below) |
| stint life (shipped) | none stable | 2 / 5 at k=3 | — | — | barred, see below |
| **stint life (`S1x`)** | — | **0 / 15 cells** | — | — | **full window** |

For p10 and for stint life under `10e`'s `S1x` the result is not merely negative, it is monotone:
every season you delete costs you, at every rung, on every eval season. Those two families want
all the data there is.

#### `01a`'s cell replicates. `01a`'s rule does not.

The exact cell `01a` reported — eval 2024, train 2021–2023 — comes back **larger**, with the
encoder refit inside the fit and five seeds under it:

| | delta | floor | × floor |
| :--- | ---: | ---: | ---: |
| `01a` (pre-`08e`/`08f` substrate, encoder held fixed, single fit) | +0.01291 | 0.00349 | 3.71× |
| `05d` (current substrate, encoder refit inside, 5 seeds) | **+0.01484** | 0.00577 | **2.57×** |

t-interval on the five paired deltas `[+0.0114, +0.0183]`, p=0.0003. So the finding is real and it
is not an encoding artefact. **It is, however, an eval-season artefact.** The same k=3 rule applied
to the other eval seasons where it is a proper subset:

| eval season | delta at k=3 | × reseed floor | p |
| ---: | ---: | ---: | ---: |
| 2022 | −0.00219 | −0.45× | 0.111 |
| 2023 | **−0.00307** | −0.60× | **0.013** |
| 2024 | **+0.01484** | +2.57× | **0.0003** |

On 2023 the rule is significantly *worse*. That is precisely the limit `01a` stated it could not
test — "a 'recent seasons train better' result measured against 2024 alone could be partly
2024-specific" — and under test it does not survive.

The most defensible cliff rule is **k=4**, which wins on both eval seasons where it is a proper
subset (2023 +0.00329 p=0.022; 2024 +0.00858 p=0.0025). Its aggregate is **+0.00593, about 1.06×
the family's own reseed floor.** Consistent in sign, and at one floor it is not a shipping-grade
delta by this programme's own convention. **It does not move production.**

#### The verdict the item asks for: neither regime nor encoding, as `01a` framed them

**Encoding is ruled out.** Arm B keeps 2018's rows and 2018's regime and removes only its compound
identity — HYPERSOFT / SUPERSOFT / ULTRASOFT (7,880 rows, 55% of 2018) collapsed to one shared
code. In the cell where the entire finding lives, cliff on eval 2024, arm B moves the headline by
**−0.00004, −0.03× its own floor.** Arm C, the renumbering null — same levels, encoder integers
permuted per seed — moves it *more* (+0.00028). Folding the compound identity buys nothing, and
what little it does is indistinguishable from the integers being reshuffled. Arm B clears its floor
nowhere that matters, on any family.

**2018 is ruled out as the season that hurts.** Dropping 2018 alone (k = pool−1) gives cliff on
2024 only **+0.00240, 0.42× the reseed floor, p=0.106, CI straddling zero** — against +0.01484 for
k=3. And on the three earliest eval seasons dropping 2018 is strongly *harmful*: −8.35×, −3.95×,
−1.02× its paired floor on 2020, 2021, 2022. `01a`'s "why 2018 is the season that hurts" section
described a mechanism that the multi-season ladder does not support.

**What is actually there is family-specific window saturation.** Best window *size* against pool
size, `*` marking a best-k pinned at the pool (so the true optimum may be larger):

| family | E=2020 | E=2021 | E=2022 | E=2023 | E=2024 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| p10 | 2/2* | 3/3* | 4/4* | 5/5* | 6/6* |
| p50 | 2/2* | 3/3* | 4/4* | 5/5* | 5/6 |
| p90 | 2/2* | 3/3* | 4/4* | 4/5 | 3/6 |
| cliff | 2/2* | 3/3* | 4/4* | 4/5 | 3/6 |
| stint life `S1x` | 2/2* | 3/3* | 4/4* | 5/5* | 6/6* |

p10 and `S1x` are pinned at the pool at every rung — they never saturate. p90 and cliff come off the
pin the moment the pool exceeds four seasons. The honest description is **"cliff and p90 stop
gaining past roughly four seasons," not "2018 is bad"** — and a saturation that costs about one
reseed floor to exploit is not worth a production change.

#### Stint life: `01a`'s strongest recency finding was a hyperparameter artefact

`01a` reported stint life as the most recency-driven family of the five, the newer window beating
the older at matched n by **14–57× its floor**. `02b` bars the family until `10e` lands, so it was
run twice here rather than dropped: under the shipped params, and under `10e`'s declared winner
`S1x` (which `D4` has since ruled to ship).

Under the shipped params the ladder is incoherent — best k = 1, 3, 2, 1, 4 across the five eval
seasons, with subset gains up to 9.5× the paired floor for one- and two-season windows. Under
`S1x` **the full window wins on all five eval seasons, 0 wins for any subset rule at any rung, and
the ladder is monotone.** The window effect was the mis-tuned booster, exactly the defect `10d`
diagnosed and `10e` fixed. Nothing here asks for a stint-life window change.

#### Two mechanisms this item was sent to check, both void

- **`08d` is not on this path, and could not be.** `stg_tyre_allocations` holds 2019–2024 (384 rows,
  6 seasons). The C1–C5 scale did not exist in 2018. So the ordering worry in the spec above —
  "`08d` before a production window change, not after" — is **moot for the one season the question
  is about**: the real Pirelli mapping structurally cannot recover 2018's compound identity. Arm B
  makes it doubly moot by showing compound identity is not the mechanism anyway.
- **The `08f-2` mechanism in `build-log.json`'s item note is void.** It argued 2018 should be excluded
  because `circuit_constructor_interaction_s` is identically 0 across 2018's panel rows. That column
  reaches a model only through `cliff_candidate_flag`, which **`08j` pruned**. On the live 32-feature
  contract every feature has non-zero sd in 2018 and none has an anomalous 2018 null rate. The
  mechanism died with the flag; the note predates the prune.

#### Limits of this result, stated

- The paired floor is `2·sd/√5` over five seeds. With 4 df that is a touch optimistic against a
  t-interval, so every headline claim above is quoted with the t-interval and p-value beside it,
  and the verdict rests on the **reseed floor**, which is the programme's standard and is the
  denominator `01a` used.
- Arm B collapses three levels to one arbitrary code string, whose sort position sets its ordinal.
  Arm C is the control for exactly that, and it bounds the sensitivity: the numbering moving is worth
  under half a floor. A finding resting on arm B alone would need the code string varied.
- The eval seasons are the five season-grouped fold seasons. 2020 is a shortened, calendar-scrambled
  season and its ladder is only two rungs deep; it carries the least weight of the five.

#### Stage

**`CLOSED`.** Every clause of the definition of done is delivered — a window recommendation per
family with its delta against that family's own reseed floor, the encoder refit inside the fit, five
eval seasons rather than one, and a stated verdict on mechanism. The answer is **no window change,
for any family**, so there is no candidate for `gates.md` to run end-to-end and nothing is left for
the human call the spec reserved. Gate 1 passed; gate 6 was honoured; the renumbering null is the
gate-4-shaped arm for the encoding hypothesis. **Do not reopen** on a fresh single-eval-season
recency result — that is the shape this item falsified. Reopening needs a *multi-eval-season* subset
gain clearing its family's reseed floor.

## Definition of done — `05a`

Not "a GAM was fitted". A comparison against the incumbent under
[`../foundations/gates.md`](../foundations/gates.md) — same split, same scorer, delta against
the family's own reseed floor, with the permutation-null arm where a capacity/information
split is meaningful — plus a written verdict on whether the class change is worth the loss of
the existing tooling (ONNX export, parity verification, `behaviour_audit`, the calibration
gates), which is a real cost and not a footnote.

**This defines "done" purely in pinball-loss/headroom terms.** See the closure callout at
the top of this doc and decision `D8` in `build-log.json`: a proposed 2026-09-07 reframe toward
"a publishable coefficient with an interval" would have made this section's definition of done
the wrong one. It was ruled out — see below.

---

## 05a — CLOSED 2026-09-11. Unstarted, per its own pre-written exit condition. `D8` ruled:
reframe rejected/deferred.

**The ruling.** Decision `D8` (raised 2026-09-11, same day) asked whether `05a` should be judged
on predictive headroom, as this doc has always scoped it, or reframed around producing a
publishable coefficient with an interval — a proposal that had sat unreconciled in
`build-log.json`'s `05a` item note since 2026-09-07, flagged there as needing correction into
this doc "before `05a` is run," and never actioned across four intervening sessions. **The user
ruled: reject/defer the reframe.** `05a` stays exactly as this doc scopes it above — a
shipping-class model change, judged on predictive headroom against the incumbent under
[`../foundations/gates.md`](../foundations/gates.md).

**Why the evidence was already decisive on that scoping.** The three-leg bracket this section's
"Blocked deliberately" note asked for — `01a`, `01b`, `05c` — completed and converged before `D8`
was even raised, verified independently rather than taken on a prior summary's word:

- `01a`'s row-arm learning curves are flat end to end for all five families (last-leg gains
  0.05×–4.5× the reseed floor) and its extrapolated intercept does not bind for any of them (LOO
  spreads 3.0–3.3× the claimed headroom on p10/p50; `b` pinned at its fit bound on p90 and cliff;
  `c` unidentifiable for stint life). No family shows real, actionable headroom.
- `01b`'s difference-based floor comes back **above** achieved loss on p10 (0.5654 vs 0.5188) and
  p50 (1.0641 vs 1.0163) — "no headroom measurable," per its own pre-registered falsification
  gate — and separates from achieved by only ~10–12% on p90, a signal that does not survive the
  arm-5 race-component correction (corrected band top 0.5618 just covers the achieved 0.5600) and
  that [`01-ceiling-instrument.md`](01-ceiling-instrument.md)'s own reconciliation section routes
  to `11a`'s Mondrian-conformal recalibration, explicitly **not** to a model-class change.
- `05c` finds `degradation_regressor_p50` at its model-based noise floor to within ±1.5%, and its
  later repair-pass finding (cluster bootstrap over races, `build-log.json`'s `05c` note) goes
  further: no headroom percentage is quotable at all — direction only, and the direction is
  "none." *(Annotated 2026-09-17, not rewritten: the `±1.5%` in the first clause is **retracted**
  — see `05c` results part 3. The plank this ruling actually stands on is the second clause, and
  that one is unchanged. `05c`'s v12 rerun does not disturb it; see "What this does and does not
  do to `05a`".)*

Three independent instruments, three different failure modes, one answer: **no material headroom
remains for a model-class change to claim.** That is precisely the condition this doc's own
"Blocked deliberately" note named in advance as the one under which "this item closes unstarted."

**What happens to the reframe.** It is not discarded. It is **shelved**: a future session or the
user may open it as a new item under group `06` (publication track), where it belongs alongside
`06a`/`06b`/`06c`'s other publishable-finding work — a hierarchical/GAM fit whose purpose is a
coefficient with an interval, not a pinball-loss delta against the incumbent. `05c`'s own fitted
variance components (`σ²_race`, `σ²_stint`, `σ²_driver`, `σ²_constructor`, with arm 0c's
sampling-uncertainty distribution around each) already come closest to what the reframe was
reaching for, at the 1–2 days of measurement-only cost already spent — so a group-06 item
building on that footing would likely cost far less than `05a`'s original days-weeks,
shipping-class estimate. **This is a new item, not a reopening of `05a`**: `05a`'s definition of
done, as scoped above, is fully answered and spent by this closure.

**Do not reopen `05a`** without evidence that changes the headroom bracket itself (e.g. a new
ceiling instrument finding real headroom `01a`/`01b`/`05c` missed). A desire for a publishable
coefficient is not such evidence — it is a different question, and it has a home in group `06`.

Full ruling text: `D8` in [`../status/build-log.json`](../status/build-log.json)'s `decisions`
array. Full closure bookkeeping: the `05a` item in the same file's `items` array.
