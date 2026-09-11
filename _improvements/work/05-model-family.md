# 05 — Model family

**Group:** 05 · **`05a` depends on:** `01a`, `01b` · **Cost:** days to weeks · **Lowest EV on the ladder**

> **SPLIT 2026-09-07 (research round R1).** "Model family" is not one decision. `05a` — the
> *shipping* class change — stays blocked and stays lowest-EV. But two pieces that were sitting
> behind that block are **hours and days respectively, have no dependencies, and do not leave
> the existing pipeline.** They are now `05b` and `05c` at the bottom of this doc. Neither
> inherits `05a`'s block; `05b` in particular should never have been behind a "days-weeks" item.

> **OPEN QUESTION — decision `D8`, raised 2026-09-11. Do not close or start `05a` before it is
> resolved.** The three-leg pinball-loss/headroom bracket this section asks for (`01a`, `01b`,
> `05c`) is now complete and converges on "no material headroom": `01a`'s learning curves are
> flat end to end for all five families and its extrapolated intercept does not bind on any of
> them; `01b`'s difference-based floor comes back *above* achieved loss on p10 and p50 (no
> measurable headroom, per its own falsification gate) and separates from it by only ~10-12% on
> p90 — a signal that does not survive the arm-5 race-component correction and that
> [`01-ceiling-instrument.md`](01-ceiling-instrument.md)'s own reconciliation section routes to
> `11a`'s conformal recalibration, not to a model-class change; `05c` finds
> `degradation_regressor_p50` sitting at its model-based noise floor, with its final repair-pass
> conclusion (in `build-log.json`'s `05c` note, not yet folded into this doc's results section
> below) that no headroom percentage is quotable at all, direction only. **That evidence would
> close `05a` cleanly as this section currently scopes it** — a shipping-class change judged on
> predictive headroom against the incumbent.
>
> But `build-log.json`'s `05a` item note separately carries a 2026-09-07 proposal, explicitly
> marked "proposed, not yet written into the leaf doc": judge model families on whether they
> yield a **publishable coefficient with an interval**, not on pinball loss alone, because
> XGBoost cannot hand you a parameter with uncertainty. The same 2026-09-07 session's own history
> entry already flagged that this doc "should be corrected before `05a` is run," and no session
> since has done that or ruled the proposal out. The headroom bracket above answers a predictive
> question; it says nothing about an interpretability/publishability question, and nothing in
> `01a`, `01b` or `05c` was designed to. Closing this item on headroom grounds alone, or starting
> it as a days-weeks shipping-class build, would each resolve that open disagreement in one
> direction without the human ever having reconciled it. See `D8` in
> [`../status/build-log.json`](../status/build-log.json) for the two paths and what each would do
> to this item's scope and cost.

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

#### Stage

**`MEASURED`, not `GATED`.** Gate 1 passed (arm 0a bit-identical, plus synthetic recovery), gate
4 passed decisively (arm 2b), gate 6 was run in full, gates 2 and 5 are N/A by construction — and
**gate 3 did not deliver**, so the standing gate has not been passed end-to-end. Per
[`../status/BUILD-ORDER.md`](../status/BUILD-ORDER.md), a number that has not been through
`gates.md` is `MEASURED`, however good it looks.

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

## Definition of done — `05a`

Not "a GAM was fitted". A comparison against the incumbent under
[`../foundations/gates.md`](../foundations/gates.md) — same split, same scorer, delta against
the family's own reseed floor, with the permutation-null arm where a capacity/information
split is meaningful — plus a written verdict on whether the class change is worth the loss of
the existing tooling (ONNX export, parity verification, `behaviour_audit`, the calibration
gates), which is a real cost and not a footnote.

**This defines "done" purely in pinball-loss/headroom terms.** See the open-question callout at
the top of this doc and decision `D8` in `build-log.json`: a proposed 2026-09-07 reframe toward
"a publishable coefficient with an interval" would make this section's definition of done the
wrong one, and that proposal has never been reconciled into this doc. Do not treat the headroom
bracket below as having settled that question — it wasn't designed to.
