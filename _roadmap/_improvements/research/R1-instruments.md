# R1 — Instruments: the noise floor, the multiplicity audit, and what the headline score should be

**Track:** T1 + T5 + scoring · **Prices:** `01a`, `01b`, `04a`, `04b`, `04c`, `05a`
**Status:** DRAFTED

Three instrument questions the programme has open, and what the literature says about each.
Taken together they change what `01b` and `04` should be built as — in `01b`'s case, into
something cheaper and better-founded than the design `work/01` is currently defending against.

---

## 1. The noise floor: this is a solved problem in the statistics literature, under a different name

`work/01` 01b is trying to estimate the irreducible noise of a regression function without
first estimating the regression function — because estimating it with the incumbent model is
circular. That is, exactly, **variance estimation in nonparametric regression**, and it has a
forty-year literature the programme has not touched.

### The relevant family: difference-based estimators

`y_i = f(x_i) + σ(x_i)ε_i`. Difference-based estimators form squared differences of
*near-neighbour observations* and exploit the fact that `f` nearly cancels between neighbours,
so the difference is nearly pure noise. Rice (1984) is the origin; Gasser–Sroka–Jennen-Steinmetz
and Hall–Kay–Titterington (Biometrika 1990) give the optimal difference sequences.
[A recent review](https://link.springer.com/chapter/10.1007/978-3-032-07178-1_19) covers the
family. The modern reference point for random design is
[Shen, Gao, Witten & Ma, *Optimal estimation of variance in nonparametric regression with random
design*, Annals of Statistics 48(6), 2020](https://arxiv.org/abs/1902.10822): a **U-statistic-based
local polynomial estimator**, minimax optimal at rate
`n^(−8αβ/(4αβ+2α+β)) ∨ n^(−2β/(2β+1))` for `α`-Hölder mean and `β`-Hölder variance, and — the
part that matters here — **requiring no smoothness assumption on the design density.**

### What that does to `work/01`'s five defects

`work/01` 01b lists five defects in the §3b design. Adopting the difference-based frame
**dissolves three of them and sharpens the other two**:

| defect | status under a difference-based estimator |
| :--- | :--- |
| **1 — pooled centred residuals are `σ²(1−1/m)`, biased low, and symmetric at m=2** | **Dissolved as a bug, kept as arithmetic.** The `(1−1/m)` factor is the *defining* property of the family and is corrected in closed form. `work/01`'s own proposed fix — model the pairwise difference `d = y₁ − y₂` as `ε ⊛ (−ε)` — is the m=2 difference-based estimator, independently rederived. The literature supplies the higher-order sequences and their exact constants so `m > 2` groups need no bespoke correction. |
| **2 — the falsification gate is one-sided** | **Still real, still needs `work/01`'s fix.** The bracket (bias-corrected floor below, a real leave-one-out predictor's loss above) is the right construction and has no substitute. |
| **3 — the two biases have opposite signs; extrapolation removes only one** | **Dissolved.** The mean-function bias is handled by *smoothing the pairwise differences with local polynomial regression* at a known rate, not by extrapolating a sweep to `d → 0`. There is no `d → 0` step, so there is no surviving constant to land in an intercept. |
| **4 — the metric is unspecified and the defaults are wrong for this matrix** | **Sharpened, and it becomes the binding constraint.** See below. |
| **5 — the independence constraint may make `d → 0` unreachable** | **Dissolved.** Nothing needs to reach zero. The admissible-neighbour-distance measurement `work/01` calls for is still worth running, but as a diagnostic rather than a go/no-go on the design. |

### The constraint that does *not* go away: dimension

Difference-based estimators are analysed in low dimension. This feature matrix is 33 columns.
Nonparametric variance estimation in 33 dimensions is cursed, and the applied Bayes-error
literature puts a number on how cursed: [Bayes Error Rate Estimation in Difficult Situations
(2025)](https://arxiv.org/abs/2506.03159) ran 2,500 Monte Carlo simulations per scenario across
kNN, Generalized Henze–Penrose and KDE estimators, and found kNN the most accurate
non-parametric estimator by a wide margin — but requiring **1,000 samples per class minimum, and
2,500 per class at only four features**, with all estimators failing the target confidence range
as dimension grows.

**That is a direct, citable warning against `01b` as scoped.** A kNN floor over a scaled 33-column
space on 82,315 rows is outside the regime where the estimator has been shown to work, and the
falsification gate in `01b` cannot detect that failure because it is one-sided.

**Recommendation.** Do not estimate one global floor in 33-D. Estimate **stratified floors in a
deliberately low-dimensional space** — `compound × lap-in-stint band × circuit` is three
coordinates, all of them physically meaningful, all of them already in the mart, and stratifying
is something `work/01` already asks for on other grounds ("one global noise distribution is
probably false"). Report a floor per stratum with its n, and never pool them into one number.
That is both defensible and cheaper than the sweep.

### The alternative instrument, which is cheaper still

A **distributional fit is itself a noise-floor estimate.** If you fit conditional scale and shape
rather than three separate conditional quantiles (see [R2](R2-model-family.md)), the fitted
conditional distribution `F(·|x)` gives the expected pinball loss of a *perfectly calibrated*
predictor in closed form, per row. Averaged, that is a floor — under the model's distributional
assumption, which is the circularity, stated plainly.

This is not a replacement for the difference-based estimate. It is the **other end of the
bracket**: a parametric floor that is too optimistic where the family is misspecified, against a
nonparametric floor that is too pessimistic where neighbourhoods are loose. Reporting both, and
the gap, is more informative than either — and it is the construction `ceiling.py` already uses
for the in-sample vs cross-fitted oracle, so it is in the house style rather than new.

### And `01a` stands unchanged

Learning curves remain the right first move and the only estimator-risk-free check. Nothing in
the literature argues against them, and everything above increases their value, because a
stratified floor needs a second opinion more than a single global one did.

---

## 2. Multiplicity: `04` as specified is a descriptive audit, not a valid FDR statement

`work/04` proposes: enumerate the test family across 22 checkpoints, convert floor-ratios to
p-values, apply Benjamini–Hochberg. Two problems, one fatal to the interpretation.

**BH assumes a fixed family, chosen in advance.** This campaign's family was chosen adaptively —
each checkpoint's arms were picked knowing the previous checkpoint's results, and the campaign
stopped when it stopped for reasons related to what it found. Retrospective BH over an
adaptively-selected sequence does not control FDR; it produces a number shaped like an FDR
statement. `gates.md` step 6 already knows this ("pre-registration costs nothing"), but
pre-registration cannot be applied backwards.

**And `04b` — the floor-ratio-to-p-value conversion — is a hard problem the programme has
correctly flagged and should not have to solve.** `2*sqrt(2)*sd` over five reseeds is a noise
*scale*; converting it to a p-value needs a distributional assumption and a defensible df on
n = 5.

### The modern answer: e-values

An **e-value** is a non-negative statistic with expectation ≤ 1 under the null. It is the
betting-theoretic analogue of a p-value, and it has two properties that fit this campaign
exactly:

- **e-values compose under arbitrary dependence and optional stopping.** The
  [e-BH procedure](https://arxiv.org/pdf/2311.06412) (Wang & Ramdas) rejects the hypotheses with
  the *k\** largest e-values and **controls FDR at α under arbitrary dependence between the
  e-values** — no independence, no PRDS, no assumption about how the family was assembled.
- **Anytime-validity.** [Anytime-valid FDR control with the stopped e-BH procedure
  (2025)](https://arxiv.org/abs/2502.08539) extends this to data collected adaptively: e-BH
  applied to stopped e-processes controls FDR **at any data-dependent stopping time.** That is
  precisely the shape of a 22-checkpoint research campaign that stopped when it stopped.
- Related: [admissible online closed testing must employ e-values](https://arxiv.org/pdf/2407.15733),
  and the [game-theoretic statistics / safe anytime-valid inference survey](https://arxiv.org/pdf/2210.01948)
  (Ramdas et al.) for the framing.

**And it answers `04b` by dissolving it.** An e-value can be constructed directly from a betting
or likelihood-ratio construction on the reseed distribution — no p-value, no df on n=5, no
distributional assumption smuggled in to make a conversion work. The open decision `04b` names
stops being a decision.

### Recommendation, in two parts

1. **Run `04a` and `04c` as specified, and label the output honestly** — a descriptive audit of
   how many CLEARS would survive a correction, useful for calibrating the programme's own
   confidence, explicitly **not** an FDR-controlled statement. `04b` becomes "state why a valid
   retrospective conversion is not available", which is a one-paragraph result rather than a
   half-day of work.
2. **Install an e-value protocol for everything after this round.** Each new arm declares its
   e-value construction in its leaf doc before it runs (`gates.md` step 6 already requires
   pre-registration; this makes the pre-registration mechanically useful), and the campaign
   carries a running e-BH decision that is valid however many arms get added and whenever it
   stops. This is a change to `gates.md`, and it is the single highest-leverage change to the
   programme's own epistemics available.

---

## 3. The headline score: the trio is three numbers where one proper score exists

The degradation family reports pinball at α ∈ {0.10, 0.50, 0.90}. Pinball is a strictly proper
scoring rule *for a single quantile* — that part is sound. But three pinball losses are three
headlines, none of which scores the predictive distribution as an object, and the programme
routinely has to reason about "p50 clears but p90 does not" without a rule for combining them.

**Averaged quantile loss over a grid converges to the CRPS as the grid refines** — CRPS is the
strictly proper scoring rule for the whole predictive distribution, in the units of the target,
and it reduces to MAE for a point forecast, so it is directly comparable to the existing
baselines. [scoringRules](https://arxiv.org/pdf/1709.04743) is the standard reference.

Two things this buys immediately:

- **One number to gate on**, instead of an ad hoc rule for disagreeing quantiles. It also makes
  a distributional model ([R2](R2-model-family.md)) and the incumbent trio directly comparable,
  which they currently are not.
- **A decomposition.** The [Murphy / calibration–resolution decomposition](https://arxiv.org/pdf/2005.01835)
  and the [CRPS decompositions](https://arxiv.org/pdf/2311.14122) split a proper score into
  **calibration loss + resolution (discrimination) + uncertainty (the data's own entropy)**. The
  third term is an *empirical* irreducible-difficulty term — an independent read on the same
  quantity `01b` is trying to estimate, from a completely different direction, at the cost of
  arithmetic on scores you already compute.

Gneiting's framing is the one the repo should adopt for what a band claims: **maximise sharpness
subject to calibration.** [R4](R4-conditional-coverage.md) measures the calibration half; CRPS
scores both at once.

---

## Proposed promotions

- **`01b` is rescoped**, not blocked: difference-based / U-statistic variance estimation,
  stratified in ≤ 3 dimensions, bracketed against a distributional fit's closed-form floor. The
  five defects in `work/01` are answered above; three of them stop existing.
- **`04b` is closed** with a written reason rather than solved.
- **A new item in `gates.md`**: e-value pre-registration per arm, e-BH at campaign level.
- **A new item**: report CRPS alongside the trio, and publish the calibration/resolution/uncertainty
  decomposition. Cheap — it is arithmetic over predictions that already exist.
