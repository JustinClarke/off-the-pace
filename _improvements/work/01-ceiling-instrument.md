# 01 — Ceiling instrument

**Group:** 01 · **Depends on:** `00a` (feature space), `01a` before `01b` · **Prices:** `02`, `05`

The programme cannot currently say how much headroom remains on four of its five models.
`ml/src/ceiling.py` reports `fraction_of_attainable` of 102× on the degradation trio and 1.04
on the cliff classifier — the instrument does not bind, and the gate says so and moves on.

Full diagnosis: `reference/ml_research_program.md` §1. Do not re-derive it.

---

## 01a — Learning curves

**Objective.** Answer "noise-limited or data-limited?" with an instrument that has no
estimator risk, before building one that does.

**Method.** Refit at 25 / 50 / 75 / 100% of training rows using `evaluate.py`'s existing
`_fit`/`_score` on the `cv_final_fold` split. Sample by **whole stints, not rows** — the
5-lap target's consecutive rows share 4 of their 5 terms, so row sampling leaks across the
split boundary. Plot eval loss against n and extrapolate.

Run a season-wise arm too (train on 2018–19, 2018–21, 2018–23), because the two arms answer
different questions: row count versus regime coverage. A flat row curve with a steep season
curve means the constraint is regulation-era drift, not data volume.

**Why it is first.** It costs half a day, uses only production code paths, has no circularity
concerns, and is the only independent check on `01b` — see defect 2 below.

**Acceptance.** A curve per family with the extrapolated intercept reported *alongside* the
curve, never instead of it, and the sampling unit stated.

**Definition of done.** The curves exist; the history entry states plainly whether each family
is still gaining from data at 100%, and whether the row and season arms agree.

### 01a — RESULT (2026-09-08), and one logged deviation

**Deviation from the method above, logged per the standing rule: a third arm was added.**
The two specified arms cannot separate the two readings of the season curve. Its final step
adds 2023 — simultaneously *the sixth season of coverage* and *the season adjacent to the 2024
eval*. The row arm cannot separate them either, because a uniform stint draw at 75% already
contains ~75% of 2023. So the same ladder was run from the other end — most-recent-*k* seasons,
growing backwards — and read against the expanding arm **at matched n**. If coverage binds, the
two ladders track each other at equal n; if recency binds, the recent-*k* ladder wins at equal n.
It wins, and that is the item's main finding.

Probe (throwaway, scratchpad only, nothing committed):
`scratchpad/{lc_probe,floors,lc_analyse,recency_arm,compare_arms}.py`, results in
`lc_results.json` / `floors.json` / `lc_summary.json` / `recency_results.json` /
`arm_comparison.json`, curves in `lc_<family>.png`.

**Gate 1 passed for all five families.** The 100% point of the row arm *is* the published refit,
and it reproduced the v11 headline bit-identically — absolute delta `0.000e+00` on every one of
p10 / p50 / p90 / cliff / stint life. 33 feature columns, `cv_final_fold`, train 2018–2023,
eval 2024.

#### The denominator, and why the obvious one is wrong

The reseed floor alone (`attribution.py::refit_noise_floor`, 5 seeds, `2*sqrt(2)*sd`) is the
**wrong** denominator for a last-leg gain. It is the sd of the headline under seed-only refits of
the *same rows*; the last leg differs in its rows too. The 100% point has no subsample variance —
it is every stint — but the 75% point is a mean over three draws and carries `sd_75/sqrt(3)`. So
the floor used here is `2 * sqrt(sd_75^2/3 + sd_reseed^2)`.

**This composite is local to 01a and must never be quoted as `refit_noise_floor`'s published
floor.** It matters: under the reseed floor alone, stint life's last leg reads as a real gain
(+0.00655 against 0.00281). Under the correct floor it does not (0.00887), because stint life has
the largest subsample sd of the five. The reseed floors themselves, first ever computed for p10
and p90: p10 0.00805 · p50 0.01332 · p90 0.00773 · cliff 0.00349 · stint life 0.00281.

#### Row arm — no family is still gaining at 100%

| family | 25% | 100% | last leg (75→100) | floor* | gain 25→100 | ×floor* |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| degradation p10 | 0.5472 | 0.5188 | +0.00242 | 0.00731 | +0.0284 | 3.9× |
| degradation p50 | 1.0587 | 1.0163 | +0.00450 | 0.00948 | +0.0424 | 4.5× |
| degradation p90 | 0.5733 | 0.5600 | −0.00090 | 0.00690 | +0.0132 | 1.9× |
| cliff (macro-F1) | 0.3800 | 0.3803 | +0.00127 | 0.00437 | +0.0002 | 0.05× |
| stint life | 1.9602 | 1.9487 | +0.00655 | 0.00887 | +0.0115 | 1.3× |

Signs are stated so positive is always *better*. `floor*` is the composite above.

**Every family's last leg is inside its floor.** The degradation trio did gain over the full 4×
range (1.9–4.5× floor), so the row curve is real and it is exhausted by 75%. The cliff classifier
gained **nothing at all** across the whole range — 0.05× its floor — so its row curve is flat end
to end, not merely flat at the top.

#### The extrapolated intercept does not bind, for any family

Reported alongside the curve as the acceptance requires, and reported as unusable. `y(n) = c +
a·n^(−b)` was fitted to all ten row-arm points, with `c` re-estimated leave-one-fraction-out.

| family | c | LOO range | LOO span | claimed headroom | why unusable |
| :--- | ---: | :--- | ---: | ---: | :--- |
| p10 | 0.4930 | 0.4402–0.5168 | 0.077 | 0.0258 | span 3.0× the headroom |
| p50 | 0.9638 | 0.8353–1.0106 | 0.175 | 0.0526 | span 3.3× the headroom |
| p90 | 0.5586 | 0.5584–0.5592 | 0.001 | 0.0014 | `b` pinned at bound 3.0, `a`≈7e10 |
| cliff | 0.3774 | 0.3761–0.3817 | 0.006 | −0.0028 | `b` pinned at bound 3.0; headroom negative |
| stint life | 1.6623 | 0.9722–1.7783 | 0.806 | 0.2865 | `b` pinned at bound 0.02 — `c` unidentifiable |

Two distinct degeneracies, both diagnostic rather than fixable by a better fitter. `b → 3` (p90,
cliff) means the fitter gave up and set `c` to the last observed point: a restatement of the
plateau, not an extrapolation. `b → 0.02` (stint life) leaves `c` unidentifiable — it trades off
freely against `a`, which is why its LOO range spans 0.81 nats against a claimed headroom of 0.29.
And where the fit is well-formed (p10, p50) the leave-one-out spread is three times the headroom
it claims.

**So the learning-curve instrument returns the same verdict `ceiling.py` already returns: it does
not bind.** That is the honest answer to "how much headroom", and it strengthens the case for
`01b` rather than weakening it — the difference-based floor is now the only remaining instrument,
not a third opinion.

#### The arms disagree, and the third arm says why: recency, not coverage

Expanding-from-oldest against growing-from-newest, at matched n, in units of each family's own
reseed floor. Positive means **the newer window wins**.

| k | n (approx) | p10 | p50 | p90 | cliff | stint life |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | ~12k | −0.86 | **+5.63** | +0.90 | **+9.33** | **+57.5** |
| 2 | ~23k | −0.10 | **+3.83** | **+3.03** | **+9.08** | **+27.0** |
| 3 | ~34k | −2.83 | **+1.95** | **+1.73** | **+8.98** | **+42.0** |
| 4 | ~46k | +0.26 | **+3.22** | +0.22 | **+7.59** | **+20.0** |
| 5 | ~57k | **+1.60** | **+1.62** | −0.96 | **+1.56** | **+13.8** |

The season arm's climb is **not** regime coverage. For p50, cliff and stint life the newer window
beats the older one at every matched n, and for stint life by 14–57× its floor. Only p10 is
indifferent, and p90 is mixed.

The blunt version of the same question — *is a proper subset of the seasons better than all of
them?*

| family | best window | rows dropped | value | vs full | ×floor | verdict |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| **cliff** | **2021–2023** | **44,206 (46%)** | **0.39318** | **+0.01291** | **+3.71×** | **subset beats full** |
| stint life | 2020–2023 | 32,832 | 1.94681 | +0.00191 | +0.68× | inside noise |
| p50 | 2019–2023 | 10,867 | 1.01539 | +0.00095 | +0.07× | inside noise |
| p10 | 2018–2023 | 0 | 0.51880 | — | — | full set is best |
| p90 | 2018–2023 | 0 | 0.56003 | — | — | full set is best |

**The cliff classifier is better trained on 2021–2023 than on 2018–2023: +0.01291 macro-F1,
3.71× its own reseed floor, obtained by deleting 46% of its training rows.** That is larger than
most feature-group deltas the programme has shipped on, and it is a change to what production
trains on. **It has not been acted on** — see `05-model-family.md` §`05d`.

#### Why 2018 is the season that hurts — mechanism, verified not assumed

`compound` is ordinal-encoded from sorted unique training values (`features.py::_build_encoders`).
The production encoder is
`{HARD:0, HYPERSOFT:1, INTERMEDIATE:2, MEDIUM:3, SOFT:4, SUPERSOFT:5, ULTRASOFT:6, WET:7}`.

**Three of those eight levels — HYPERSOFT, SUPERSOFT, ULTRASOFT — occur in 2018 and in no other
season**, and in none of the 2024 eval rows. They cover 8,777 of 2018's ~17,380 mart rows, over
half the season. 2018 is the last season before the C1–C5 naming, which is exactly the identity
`08d` exists to source, and `08a` has just backfilled those three labels into
`dim_compounds_season`. "2018 hurts the cliff classifier" and "2018's compound identity is on a
different scale from every other season" are plausibly the same fact.

**A caveat that bounds the finding.** `load_features` fits the encoder on the full 2018–2023
training frame *before* any split, and every arm here subsets rows of the already-encoded matrix —
so the encoding was held fixed across all three arms and none of them is confounded by it. But a
production change to a 2021–2023 window would also refit the encoder, dropping those three levels
and renumbering the rest. The measured +0.01291 is therefore **not** what a production window
change would return. `05d` must measure the window change with the encoder refit inside it.

#### Two limits of this item, stated

- Every recency-arm cell is a **single fit**, not a multi-seed mean, so each carries reseed noise
  that is not floored. The cliff result at 3.71× survives that comfortably; the p50 and stint-life
  subset gains at 0.07× and 0.68× plainly do not, and are reported as inside noise.
- The eval side is **one season**. A "recent seasons train better" result measured against 2024
  alone could be partly 2024-specific. Confirming it needs the same ladder against the other fold
  eval seasons, which was not run.

---

## 01b — Empirical noise floor

> **RESCOPED 2026-09-07 (research round R1). Build a difference-based estimator, not a k-NN
> sweep.** What this item is attempting — estimating irreducible noise without first estimating
> the regression function — is **variance estimation in nonparametric regression**, a solved
> problem with a forty-year literature (Rice 1984; Hall–Kay–Titterington 1990; and for random
> design, Shen, Gao, Witten & Ma, *Annals of Statistics* 48(6) 2020, a minimax-optimal
> U-statistic local-polynomial estimator requiring no smoothness assumption on the design
> density).
>
> **Three of the five defects below dissolve under that frame:**
>
> | defect | status |
> | :--- | :--- |
> | **1** — m-bias, `σ²(1−1/m)`, symmetric at m=2 | **Dissolved as a bug, kept as arithmetic.** The `(1−1/m)` factor is the *defining* property of the family and is corrected in closed form. The fix proposed below — model `d = y₁ − y₂` as `ε ⊛ (−ε)` — **is** the m=2 difference-based estimator, independently rederived. The literature supplies higher-order sequences and their exact constants, so m > 2 needs no bespoke correction. |
> | **2** — one-sided falsification gate | **Still real. Keep the fix below in full.** The bracket has no substitute. |
> | **3** — opposite-signed biases, only one removed | **Dissolved.** The mean-function bias is handled by smoothing the pairwise differences with local polynomial regression at a known rate. There is no `d → 0` step, so no surviving constant lands in an intercept. |
> | **4** — unspecified metric, wrong defaults | **Sharpened, and now binding.** See the dimension constraint below. |
> | **5** — `d → 0` may be unreachable | **Dissolved.** Nothing needs to reach zero. Measure the admissible-neighbour distribution anyway, as a diagnostic rather than a go/no-go. |
>
> **The constraint that does not go away is dimension.** Difference-based estimators are analysed
> in low dimension; this matrix is 33 columns. *Bayes Error Rate Estimation in Difficult
> Situations* (2025) found k-NN the most accurate non-parametric estimator by a wide margin but
> requiring **1,000 samples per class minimum and 2,500 at only four features**, with all
> estimators failing as dimension grows. **A k-NN floor over 33 scaled columns is outside the
> regime where the estimator has been shown to work, and defect 2's one-sided gate cannot detect
> that failure.**
>
> **So: do not estimate one global floor in 33-D.** Estimate **stratified floors in ≤ 3
> deliberately chosen dimensions** — `compound × lap-in-stint band × circuit`, all physically
> meaningful, all already in the mart — and report a floor per stratum with its n. Never pool
> them into one number. Stratifying is something this item already asks for on other grounds.
>
> **Bracket it against two other legs**, both of which fail in different directions:
> a distributional fit's closed-form expected pinball under perfect calibration (`09a`, the
> parametric end), and `05c`'s GPBoost fitted `σ²_residual` (a model-based estimate). Reporting
> the spread is more informative than any single leg, and it is the house style `ceiling.py`
> already uses for its in-sample vs cross-fitted oracle.
>
> **Cost drops from 2–3d to ~1–2d.** Evidence:
> [`../research/R1-instruments.md`](../research/R1-instruments.md) §1.

**Do not build `reference/ml_research_program.md` §3b as written.** Its §3a probe correctly
disproved the original hand-picked-key design. The replacement design it proposes carries five
defects, found 2026-09-07, and its own falsification gate cannot detect four of them.

### Defect 1 — pooled centred residuals are not the noise distribution

§3b fix 1 centres within each matched group and pools the centred residuals. With
`y_ij = f(x_i) + ε_ij`, centring gives `r_ij = ε_ij − ε̄_i`, so `Var(r) = σ²(1 − 1/m)`.

At the `m ≈ 2.2` the §3a probe actually found, that is roughly `σ²/2`. Worse, at m = 2 the
pooled set is exactly `±(ε₁ − ε₂)/2` — **symmetric by construction**.

Two consequences:
- The pinball floor read off that pool is biased **low**, so the instrument reports more
  headroom than exists.
- p10 and p90 floors come out identical, because the skew is gone. The target is plainly
  skewed — its three constant-predictor floors are 1.2512 / 1.9536 / 0.7859, which they could
  not be otherwise — and the asymmetry is the thing being measured.

**Fix — SUPERSEDED 2026-09-09 by `01b`'s result; kept so the correction is visible.** As
written it was: *do not centre-and-pool; for m = 2 the pairwise difference `d = y₁ − y₂` is
distributed as `ε ⊛ (−ε)`, so fit a skew-capable parametric family to `d` and back out ε's
quantiles.* **That cannot work.** `d` is exactly symmetric for every ε — if ε₁, ε₂ are i.i.d.
then `(ε₁,ε₂) =ᵈ (ε₂,ε₁)`, so `d =ᵈ −d` — and a skew-capable family fitted to it returns zero
skew by construction, reproducing the p10 = p90 collapse this defect exists to remove. The law
of `d` fixes `|φ_ε|²` and nothing about the phase; **odd information about ε is not identified
at m = 2 at all.**

**The replacement, which is centre-and-pool with exact per-`m` corrections.** `r_i = Σ_j c_j ε_j`
with `c_i = 1 − 1/m`, `c_j = −1/m`; cumulants add over independent terms, so `κ_k(r) = κ_k(ε)·Σc^k`
with `Σc² = 1 − 1/m` (this defect's own `σ²(1−1/m)`, now used as arithmetic), `Σc³ = 0` at m = 2 and
`2/9` at m = 3, and `Σc⁴ > 0` at every m. **Variance and tail weight come from every cell; skew
needs m ≥ 3.** The rest of the fix stands: stratify, per §3b's own caveat that one global noise
distribution is probably false — and `01b` measured that caveat to be right, at a floor/achieved
ratio running 0.7 to 1.8 across strata.

### Defect 2 — the falsification gate is one-sided

§3b's gate is "floor ≤ model's achieved loss". That catches the *old* estimator's upward bias
(the naive design fails it outright, 2.5138 vs 1.0121 at p50). Defect 1 fails **downward**, so
the gate passes trivially and nothing checks it.

**Fix, two parts.**
- Report a **bracket, not a point**: the bias-corrected floor as the lower end, and a
  leave-one-out k-NN quantile regressor's own pinball loss as the upper end — a real
  predictor's loss can never fall below the Bayes loss. This is the house style already:
  `ceiling.py` deliberately brackets the in-sample and cross-fitted oracle for exactly this
  reason.
- The synthetic recovery test must inject **skewed, heteroscedastic** noise at the same k and
  m used on real data, not the clean Gaussian case `ml/tests/test_ceiling.py::test_anova_recovers_a_known_icc`
  already covers, and it must run at every point on the sweep rather than once.
- `01a`'s learning curves are the third check: if the floor says 30% headroom and the learning
  curve is flat, one of them is wrong.

### Defect 3 — the two biases have opposite signs and only one is removed

§3b fix 3 extrapolates `d → 0` to remove the neighbourhood-variation bias, which is upward. The
m-bias from defect 1 is downward and, at fixed k, is **constant along the sweep** — so it
survives the extrapolation and lands intact in the reported intercept.

**Fix.** Apply the m-correction before extrapolating, and state the residual bias direction of
the intercept explicitly.

### Defect 4 — the metric is unspecified, and the defaults are wrong for this matrix

"k-NN over the scaled feature vector" hides three decisions that determine the answer:

- `compound` and `air_state_dominant` are **ordinal-encoded categoricals** (`schema.py`'s
  `CATEGORICAL_COLUMNS`). Euclidean distance over an ordinal code makes SOFT↔MEDIUM = 1 and
  SOFT↔WET = 4. Handle by exact-match constraint, one-hot with a stated weight, or Gower.
- Continuous features keep **native NaN** for XGBoost; k-NN has no NaN semantics. Count them
  and state the treatment.
- "Scaled" by equal-weight standardisation asserts every feature matters equally, which is
  what the tree ensemble does not assume. A neighbourhood tight in irrelevant features and
  loose in relevant ones inflates the floor. Feature weighting from a model is soft
  circularity and needs its own pre-registered rule — §3b's fix 2 correctly bars
  prediction-conditioned metrics, but weighting is the case it does not cover.

### Defect 5 — the independence constraint may make `d → 0` unreachable

Requiring neighbours from a different stint, preferably a different race, while matching in a
space containing stint-trajectory features (`cumulative_push_load_*`, `laps_past_cliff`,
`age_in_stint`, `ahead_identity_stability`) sets a hard lower bound on achievable mean
neighbour distance.

**Fix, and do it first because it is cheap.** Measure the distribution of nearest *admissible*
neighbour distances before committing to the extrapolation design. If the admissible range is
far from zero, extrapolating to zero is a long lever on a curve never observed near its
intercept.

### Scope note — the cliff label is promised and not designed

§3's objective says "the degradation target **and the cliff label**". §3b and its closing
command are entirely pinball-on-the-continuous-target. A noise floor for macro-F1 is a
different problem: macro-F1 is not a proper scoring rule, so a Bayes-error bound does not
convert into an F1 bound without fixing the decision rule. **Either scope the cliff label out
explicitly or design it** — do not leave it reading as covered.

### What `01a` hands `01b` — read before designing the strata

`01a` landed 2026-09-08. Three of its results change this item.

1. **Defect 2's third check has already fired, and it constrains the answer.** The fix above
   names `01a`'s learning curves as the third leg: *"if the floor says 30% headroom and the
   learning curve is flat, one of them is wrong."* **The row curve is flat** — every family's
   75→100% leg is inside its floor, and the cliff classifier's is flat across the entire 4×
   range. A floor that comes back claiming material headroom is not thereby wrong, but it now
   owes an explanation for why more of the same data cannot reach it. Say which, in the result.

2. **The `compound` leg of the stratification carries a live confound.** HYPERSOFT, SUPERSOFT and
   ULTRASOFT occur only in 2018 and in none of the 2024 eval rows (8,777 rows, over half that
   season). A stratum keyed on any of the three is a *2018-only* stratum with no eval-population
   counterpart, and its floor cannot be compared with the loss it is meant to bound. Either
   exclude those three levels from the stratification and say so, or key the compound leg on the
   C1–C5 identity `08d` is sourcing rather than on the mart's raw label.

3. **The population question `05c` flagged is now measured from a second direction.** `05c` found
   the trio trained on an IPW population whose residual variance is 62% above the population it is
   scored on; `01a` finds the training population is also *temporally* mismatched — for p50, cliff
   and stint life the newer window beats the older at every matched n. Both say the same thing:
   **`01b`'s floor must be estimated on the `cv_final_fold` EVAL rows**, not on the training pool,
   and the result must state which population each leg of the bracket describes.

### 01b — PRE-REGISTRATION 2026-09-09. Written before any fit, per `gates.md` step 6.

`01a` was marked down for adding a third arm after seeing the first two disagree. Everything
below is fixed before the estimator is run, including the falsification rules and the two
identification results that shape the design.

#### The population, and the one thing it makes impossible

The `cv_final_fold` **eval** rows: 2024, 13,896 rows for the quantile trio, per hand-off point
3. Measured on the cached split before designing anything, as the cheap diagnostic defect 5
asks for:

| | |
| :--- | :--- |
| races / circuits / stints / drivers | 24 / 24 / 1,027 / 24 |
| compounds present | HARD 8,295 · MEDIUM 4,292 · INTERMEDIATE 669 · SOFT 637 · WET 3 |
| `lap_in_stint` | 2 – 72, median 13 |
| target | mean −2.5200 · sd 5.7300 · skew −1.1343 · excess kurtosis 3.4341 |

**Every 2024 circuit hosts exactly one race, so "same circuit, different race" does not exist
inside the eval population.** Defect 5's independence constraint asked for neighbours from a
different stint and *preferably* a different race; the second half is unavailable at this
population and is dropped rather than faked. Consequence, stated now rather than discovered
later: the estimator conditions on the race, so any race-level component of the residual is
treated as signal and the floor is biased **down** by exactly that component. Arm 5 measures
it. Hand-off point 2's confound is absent by construction — HYPERSOFT, SUPERSOFT and ULTRASOFT
do not occur in 2024 at all — so the compound leg is keyed on the mart's raw label and the
`08d` dependency does not bind here.

#### Two identification results that change the design

**(1) Defect 1's proposed fix is not identified, and would return the failure it was written to
remove.** The defect is right that pooled centred residuals are symmetric at m = 2. Its fix —
"fit a skew-capable parametric family to `d = y₁ − y₂` and back out ε's quantiles" — cannot
work. If ε₁, ε₂ are i.i.d. then `(ε₁, ε₂) =ᵈ (ε₂, ε₁)`, so `d =ᵈ −d`: **the pairwise difference
is exactly symmetric for every ε, however skewed.** Its law fixes `|φ_ε|²` and nothing about the
phase, so a skew-capable family fitted to `d` returns zero skew by construction — the same
p10 = p90 collapse defect 1 objects to, arrived at one step later. Odd information about ε
cannot be recovered from m = 2 at all.

**(2) The construction defect 1 rejects is the one that works, once the corrections are exact
and per-`m`.** Centre within a cell of size `m` and the residual is `r_i = Σ_j c_j ε_j` with
`c_i = 1 − 1/m` and `c_j = −1/m`. Cumulants add over independent terms, so `κ_k(r) = κ_k(ε)·Σc^k`
with

    Σc² = 1 − 1/m
    Σc³ = (1 − 1/m)³ − (m − 1)/m³        = 0 at m = 2,  2/9 at m = 3,  → 1
    Σc⁴ = (1 − 1/m)⁴ + (m − 1)/m⁴        > 0 for every m ≥ 2

`Σc² = 1 − 1/m` **is** defect 1's `σ²(1 − 1/m)`, now used as the closed-form correction rather
than reported as a bug — R1's "dissolved as a bug, kept as arithmetic". `Σc³ = 0` at `m = 2` is
result (1) restated. `Σc⁴ > 0` everywhere says the **tail weight is identified from pairs even
though the skew is not**. So: variance and kurtosis from every cell, **skew only from cells with
m ≥ 3**, which is 1,152 of the 1,494 cells and 13,430 of the 13,896 rows.

#### The estimator

Difference-based / U-statistic variance estimation, in the matched-cell form. The matching space
is **three coordinates, all pre-chosen on physical grounds**, per R1's dimension constraint:

| coordinate | treatment | why this and not a distance |
| :--- | :--- | :--- |
| `compound` | **exact match** | defect 4 — Euclidean distance over an ordinal code makes SOFT↔MEDIUM = 1 and SOFT↔WET = 4 |
| `circuit_key` | **exact match** (≡ `race_id` at this population) | as above, and it removes track identity from the difference |
| `lap_in_stint` | **exact match** at the headline level, `|Δ|` as the graded sweep coordinate | the only one of the three with a meaningful metric |

Admissibility: the two rows of a pair must come from **different stints**. Nothing is scaled,
nothing is one-hot, no feature weighting is used, so defect 4's three sub-decisions are answered
by not making them. `compound` is never NULL at this population and `lap_in_stint` never NaN, so
defect 4's NaN question does not arise in the matching space; NaN counts in the *unmatched*
30 columns are reported as a diagnostic instead.

Per cell: `σ̂²_cell` from `Σᵢ rᵢ² / (m − 1)`, pooled within a stratum over its cells so the scale
is estimated on many degrees of freedom rather than on one cell's ~9 rows. Standardised shape
`(γ₁, γ₂)` from the pooled `κ̂₃`, `κ̂₄` with the exact per-`m` denominators above, fitted with a
Johnson **SU** (unbounded, four parameters, covers the skew/kurtosis region this target sits in,
`scipy.stats.johnsonsu`). The pinball floor follows in closed form: for `y = f(x) + σ(x)Z`,

    L*_α  =  E_x[σ(x)] · λ_α ,      λ_α = E[ ρ_α( Z − q_α(Z) ) ]

`λ_α` is computed by quadrature on the fitted `Z`, and reported beside the Gaussian value
(`λ_α = φ(z_α)`; 0.1755 / 0.3989 / 0.1755) so the shape correction stays visible — the same
posture `05c` took with its 0.70751-against-0.79788 shape factor.

#### Strata

`compound × lap-in-stint band × circuit`, exactly as R1 specifies. Bands: 2–5, 6–10, 11–15,
16–20, 21–30, 31+. **A floor is reported per stratum with its `n`, against that stratum's own
achieved pinball.** One `n`-weighted aggregate is also reported, and it exists for exactly one
purpose — reconciling against the published headline and against legs B and C, which are both
pooled numbers — and is labelled as an aggregate everywhere it appears. Strata below 30 rows are
reported with their `n` and excluded from the aggregate, never folded into a neighbour.

#### The arms

| arm | what | fixed in advance |
| :--- | :--- | :--- |
| **0** | Gate 1 instrument check: `evaluate.py::_fit`/`_score` at v11 params on `cv_final_fold` must reproduce the published p10/p50/p90 headline | 0.5188 / 1.0163 / 0.5600, abs delta < 1e-9 |
| **1** | Diagnostics: cell-size distribution, coverage, admissible-neighbour distance in the 30 *unmatched* columns, NaN counts | reported whatever they are; no go/no-go, per R1's demotion of defect 5 |
| **2** | The conditioning ladder — `σ̂²` at L0 `(race)`, L1 `+compound`, L2 `+lap band`, **L3 `+lap_in_stint` (the headline)**, L4 `+air_state_dominant`, L5 `+fuel bucket` | L3 is the reported floor. L4/L5 are **4- and 5-coordinate matches, outside the analysed regime**, and exist only to measure how much unmatched-feature bias survives at L3. Flat L3→L5 means the bias is small; a steep drop means the floor is badly biased up |
| **3** | The `|Δ lap_in_stint|` sweep, δ = 0…5 at fixed `(race, compound)` | the falsification gate is checked at **every** δ and every ladder level; a violating point is reported as an instrument failure and stays in the table |
| **4** | Shape: `κ̂₃` (m ≥ 3 only), `κ̂₄` (all m), Johnson SU fit, `λ_α`, and a per-compound sensitivity | `γ₁` is reported with its sign; if the SU region does not contain `(γ₁, γ₂)` the fit is reported as failed, not swapped for a family that fits |
| **5** | Bias direction, both ways: **up** = the L3→L5 drop from arm 2; **down** = the between-race variance component of the production model's own eval residuals (`ceiling.py::variance_components`, grouped on `race_id`) | a near-zero race component means race-conditioning removes nothing the model does not already have, and the downward bias is nil |
| **6** | Synthetic recovery, on the real X and the real cell structure: `y = f_synth(x) + σ_synth(x)·Z` with `Z` the **skewed, heavy-tailed** fitted shape and `σ_synth` heteroscedastic in `lap_in_stint`. Plus a null arm (`f` constant → the estimator must return σ exactly) and a pure-bias arm (`σ = 0` → whatever it returns is the mean-function bias, measured) | run **at every ladder level and every δ**, per defect 2. Recovery of `σ²`, `γ₁`, `γ₂` and `L*_α`; tolerance ±5% on `σ²`, and `γ₁`'s **sign** must be recovered or arm 4 is void |
| **7** | The bracket. Upper end: a **leave-one-out cell-quantile predictor's own pinball** — a real predictor, so its loss cannot fall below Bayes. Leg B (parametric): `L_α = E_x[s(x)]·λ_α` with `s(x)` from the *model's own* predicted `q90 − q10` spread — circular by construction and labelled so. Leg C: `05c`'s 1.0024, quoted, never re-derived | reported as a spread with each leg's population and bias direction named. **Legs are never differenced** (`epistemics.md`) |

#### Falsification, pre-committed

- **The gate is `floor_α ≤ achieved_α`, checked at every ladder level and every δ**, not once at the
  headline. Looser matching raises `σ̂²`, so L0/L1 are *expected* to violate; that is the
  instrument working. A violation at **L3** is an instrument failure and is reported as one.
- **Defect 2's third check has already fired.** `01a`'s row curve is flat for all five families.
  If L3 returns material headroom on the trio, the result must say why more of the same data
  cannot reach it — `01a`'s own answer, that the binding constraint is recency rather than
  volume, is the candidate, and it must be argued rather than assumed.
- If arm 6's null arm does not recover σ to ±5%, **the arithmetic is wrong and no floor is
  quoted from any arm.**
- If arm 6 fails to recover the sign of `γ₁`, arm 4 is void and the p10/p90 floors are withheld;
  p50 survives, because `λ_0.5` depends on the shape only through `E|Z − med Z|` and is far less
  sensitive to skew than the tail levels are.

#### Scoped out, explicitly

**The cliff label is scoped out, and this closes the scope note above rather than deferring it.**
Macro-F1 is not a proper scoring rule, so a Bayes-error bound on `laps_until_cliff_class` does not
convert into an F1 bound without also fixing the decision rule — and the decision rule is a
choice the programme has not made and should not make inside a measurement item. Nothing here
should be read as bounding the classifier. `09a`'s CRPS is the proper-score end of that question
and is where it belongs. Stint life is out for the same reason at one remove: the AFT NLL's floor
under a perfect prediction is already computed directly by `ceiling.py` and needs no difference
estimator.

---

### 01b — RESULT (2026-09-09). The instrument fails its own gate at the headline level, and that is the finding.

**The floor is not usable on `p10` or `p50`: at the three-coordinate headline level it comes back
*above* the loss it is meant to bound.** On `p90` it comes back below, by more than its own error
bar before one correction and by about its own error bar after it. Two rules were caught and
repaired mid-item by the pre-registered synthetic arm, and one identification result in the leaf
doc's own defect list turned out to be wrong in a way that would have produced a plausible number.

Probe (throwaway, scratchpad only, nothing committed): `cache_split.py`, `est.py`, `arm0.py`,
`arm1234.py`, `arm6.py`, `unit.py`, `arm6b.py`, `final.py`, `verify.py`, `p90.py`; results in
`arm0.json` / `arm1234.json` / `arm6.json` / `arm6b.json` / `final.json` / `verify.json` /
`p90.json` / `strata.csv`.

**Gate 1 passed.** `evaluate.py::_fit`/`_score` at v11 params on `cv_final_fold` reproduced the
published headline bit-identically on all three heads — absolute delta `0.000e+00` on
0.5187979725350818 / 1.0163386141079709 / 0.5600310001217083. 68,574 train, 13,896 eval, 33
feature columns.

#### Defect 1's fix would not have worked, and the construction it rejects does

Pre-registered as identification result (1), and it is worth restating as a result because the
leaf doc has carried the broken fix since 2026-09-07. **The pairwise difference `d = y₁ − y₂` is
exactly symmetric for every ε, however skewed** — if ε₁, ε₂ are i.i.d. then `(ε₁,ε₂) =ᵈ (ε₂,ε₁)`,
so `d =ᵈ −d`. Fitting "a skew-capable parametric family to `d`" therefore returns zero skew by
construction and hands back the p10 = p90 collapse defect 1 was written to remove, one step later
and harder to see.

Demonstrated numerically, not only derived (`unit.py`, 400k rows of clean synthetic cells with
arbitrary cell means and a known Johnson SU noise):

| m | σ̂² err | γ̂₁ err | γ̂₂ err |
| ---: | ---: | ---: | ---: |
| 2 | +0.30% | **undefined** — Σcentred cubes = −4.7e−12, denominator 0 | −1.6% |
| 3 | −0.18% | −4.4% | −1.6% |
| 5 | +0.36% | +3.6% | +5.5% |
| 10 | −0.23% | −2.2% | −6.4% |
| 20 | +0.44% | +0.1% | −1.4% |

So the m = 2 skew is not merely hard to estimate, it is **exactly zero information**. The
centre-and-pool construction defect 1 rejects is the one that works, once the per-`m` corrections
are exact: `Σc² = 1 − 1/m` (defect 1's own `σ²(1−1/m)`, used as arithmetic), `Σc³ = 0` at m = 2 and
`2/9` at m = 3, `Σc⁴ > 0` at every m. **Tail weight is identified from pairs; skew needs m ≥ 3.**

#### Arm 1 — the diagnostics, and what they say about extrapolating

L3 covers **13,678 of 13,896 eval rows (98.4%) in 1,276 cells**, median 10 members, max 36; 1,152
cells hold m ≥ 3 (13,430 rows) and carry the skew. Of the 30 unmatched columns only two carry any
NaN at all — `ahead_identity_stability` 28.4%, `surface_bulk_ratio` 10.8% — so defect 4's NaN
question is small and localised, and nothing in the matching space is ever missing.

The admissible-neighbour distance, standardised, over those 30 unmatched columns:

| | p05 | p25 | median | p75 | p95 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| admissible pairs (same race, compound, lap-in-stint; different stints) | 1.466 | 2.943 | **4.275** | 6.021 | 9.187 |
| random pairs from the same eval population | 3.477 | 5.316 | **6.829** | 8.640 | 12.166 |

**Matching on three coordinates buys a 37% reduction in the unmatched-feature distance and the
distribution does not approach zero.** That is defect 5's worry, measured: an extrapolation to
zero distance would be a long lever on a curve never observed near its intercept, so none was run.
The leaf doc's own instruction — *"if the admissible range is far from zero, extrapolating to zero
is a long lever"* — is the reason, decided by the diagnostic rather than after seeing a result.

#### Two rules the synthetic arm caught, before any floor was quoted

The pre-registered null arm (`f` constant, so the estimator must return σ exactly) **failed on the
first pass**, at −39.7% / −39.5% / −21.9% on L0 / L1 / L2. `unit.py` above then showed the algebra
was right to ±0.5%, which located the failure in the two rules wrapped around it. Both were real:

1. **The one-row-per-stint rule was selecting on the coordinate the noise is heteroscedastic in.**
   It took the lowest `lap_in_stint`, which wherever the rule binds — L0/L1/L2, where one stint
   contributes many rows to a cell — systematically selects early-stint rows, where σ is smaller.
   Repaired by drawing the row at random and averaging over 8 seeds. At L3 the rule binds on
   nothing (`lap_in_stint` is unique inside a stint) so the repair changes L3 by exactly zero, and
   the sd over the 8 repeats is 0.0000 there against 1.70 at L0.
2. **The shape standardisation was destroying the tails it existed to preserve.** Standardising on
   `circuit × compound × lap_band` — 259 strata, ~24 rows each — normalises every small group by a
   scale its own outlier inflated. Recovered excess kurtosis came back **−37.3%**; the
   unstandardised pooled version came back **+67.5%** on the scale mixture. The coarse
   `compound × lap_band` (22 strata) recovers it to **+0.5%**. Both of the obvious choices were
   wrong, in opposite directions.

After both repairs the null arm passes at every ladder level, worst +4.13%, scored against the
truth **on the rows each level actually uses** — which is the arithmetic question. Scored against
all eval rows L0/L1 still read −17%, and that is now correctly attributed: **L0 and L1 see only
7.4% of the eval rows**, because collapsing each stint to one row leaves a `(race)` cell with ~20
members drawn from 1,027 stints. Coverage, not bias.

Re-run at the shape actually claimed below (γ₂ ≈ 5.1, much heavier than the 2.2 the first pass
injected), 5 repetitions: null arm σ̂² **−1.98% ± 2.14%**, end-to-end `p50` floor **+3.4%**.
The floor pipeline recovers.

#### Arm 2 — the conditioning ladder, and the falsification gate at every rung

`σ̂²` and the floor `σ̂ · λ_α` at each level, with the gate `floor ≤ achieved` checked at all
eighteen points. Ratios are floor/achieved; **bold** marks a violation.

| level | matched on | σ̂² | σ̂ | cells | coverage | p10 | p50 | p90 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| L0 | race | 30.028 | 5.480 | 24 | 0.074 | **2.024** | **1.945** | **1.630** |
| L1 | + compound | 26.688 | 5.166 | 58 | 0.074 | **1.908** | **1.833** | **1.537** |
| L2 | + lap band | 14.848 | 3.853 | 259 | 0.250 | **1.423** | **1.368** | **1.146** |
| **L3** | **+ lap-in-stint (headline)** | **8.704** | **2.950** | **1,276** | **0.984** | **1.090** | **1.047** | 0.877 |
| L4 | + air state | 7.803 | 2.793 | 2,007 | 0.934 | **1.032** | 0.991 | 0.831 |
| L5 | + fuel bucket | 6.767 | 2.601 | 2,726 | 0.835 | 0.961 | 0.923 | 0.774 |

**L3 violates the gate on p10 and p50.** Pre-registered as an instrument failure, and reported as
one rather than dropped. The mechanism is visible in the same table: **the ladder is still falling
at L3** — −10.4% to L4 and a further −13.3% to L5 — so the residual mean-function bias at three
coordinates is larger than the headroom the floor is being asked to resolve. L4 and L5 are 4- and
5-coordinate matches, outside the regime R1's dimension constraint permits, and they are quoted
here only as that bias probe.

The upward bias is not a simulation artefact but a theorem: `Var(y | cell) = Var(f | cell) +
E[σ²|cell]`, so `σ̂²_L3 ≥ σ²_true` on the covered population for any `f` whatever. The synthetic
pure-bias arm puts a size on it — with `σ = 0` and a real `f`, the estimator returns 1.394 at L3
against 3.363 at L0 and 0.623 at L5 — and the full arm reads **+17.0% on σ̂² and +15.0% on the p50
floor**. That magnitude rests on an invented mean function and is **not** subtracted from anything;
only the direction is used, and the direction needs no calibration.

#### Arm 3 — the `|Δ lap-in-stint|` sweep

At fixed `(race, compound)`, cell-weighted to match the ladder's weighting:

| δ | 0 | 1 | 2 | 3 | 4 | 5 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| σ̂² | 8.779 | 11.116 | 14.232 | 17.745 | 22.207 | 26.968 |
| p10 ratio | **1.094** | **1.232** | **1.394** | **1.556** | **1.741** | **1.918** |
| p50 ratio | **1.052** | **1.183** | **1.339** | **1.495** | **1.672** | **1.843** |
| p90 ratio | 0.881 | 0.992 | **1.122** | **1.253** | **1.402** | **1.545** |

δ = 0 reproduces L3 to +0.87%, which is the consistency check between the pair form and the
centred form. The gradient is steep — σ̂² triples over five laps — which is why L2 (band matching)
sits at 14.8 against L3's 8.7, and it is a second reason not to extrapolate: the one coordinate
with a metric has a strong mean-function slope along it.

*A weighting correction, logged.* The first pass weighted the sweep by pairs, which weights a cell
by `m(m−1)/2` and over-represents large cells; it returned 7.510 at δ = 0 against L3's 8.704. The
table above weights each anchor row once. Row-weighting is the right choice for a population
average and it is what makes δ = 0 and L3 agree.

#### Arm 4 — the shape, and why it is not the Gaussian one

From 1,152 cells with m ≥ 3, standardised on the 22 coarse strata, df 12,402:
**γ̂₁ = −0.5935, γ̂₂ = +5.1086.** Johnson SU fitted on that pair gives

| | λ(0.10) | λ(0.50) | λ(0.90) |
| :--- | ---: | ---: | ---: |
| fitted shape | **0.19164** | **0.36070** | **0.16657** |
| Gaussian reference `φ(z_α)` | 0.17550 | 0.39894 | 0.17550 |

Using the Gaussian factor instead would inflate the p50 floor by 11% (1.177 against 1.064) and
deflate p10 by 8%. This is the same correction `05c` made with its 0.70751-against-0.79788 shape
factor, arrived at independently and pointing the same way.

**γ̂₁ and γ̂₂ are attenuated, and only their direction is used.** The synthetic full arm recovers
γ₁ at ×0.601 and γ₂ at ×0.514 of truth, because the mean-function bias carries its own near-Gaussian
shape and dilutes both. De-attenuating by those factors moves the floors by +1.8% / −4.0% / −3.5% —
the shape is not where the answer lives.

#### Arm 5 — the bias runs both ways, and the downward leg is small

Conditioning on the race treats any race-level component of the residual as signal, which biases
the floor **down**. `ceiling.py::variance_components` on the production p50 eval residuals grouped
by `race_id`: `σ_b² = 0.4738` against `σ_w² = 9.9969`, **ICC = 0.0452** over 24 races. Adding it
back gives σ̂² = 9.178, σ̂ = 3.030, and floors of 0.5806 / 1.0927 / 0.5046 — ratios 1.119 / 1.075 /
0.901. **The downward correction makes the p10 and p50 violations worse, not better.**

#### The answer, per head

Race-cluster bootstrap, 200 draws over the 24 races, on the L3 floor:

| head | L3 floor | 95% band | achieved | verdict |
| :--- | ---: | :--- | ---: | :--- |
| p10 | 0.5654 | 0.4988 – 0.6327 | 0.5188 | floor **above** achieved; band contains it. **No headroom measurable.** |
| p50 | 1.0641 | 0.9388 – 1.1909 | 1.0163 | floor **above** achieved; band contains it. **No headroom measurable.** |
| p90 | 0.4914 | 0.4336 – 0.5500 | 0.5600 | floor below achieved by **+12.3%**, and the band excludes it |

**p90 is the only head where the floor and the achieved loss separate at all**, and the separation
survives the correction that matters: the L3 floor is upward-biased by a theorem, so removing that
bias can only *increase* p90's headroom. It does not survive the arm-5 correction as cleanly —
adding the race component back gives 0.5046 with a band of 0.4485 – 0.5618, whose top edge just
covers the achieved 0.5600. **So p90 carries headroom of at least ~10%, on an instrument whose
error bar is about the same size. Directional, not established.**

#### Arm 7 — the bracket

Never differenced (`epistemics.md`); each leg's population and bias direction is named instead.

| leg | construction | p10 | p50 | p90 | bias |
| :--- | :--- | ---: | ---: | ---: | :--- |
| A (L3) | matched-cell, 3 coordinates, eval rows | 0.5654 | 1.0641 | 0.4914 | **up** (theorem); **down** by 4.5% race ICC |
| A (L5) | 5 coordinates — outside the regime, bias probe only | 0.4985 | 0.9383 | 0.4333 | up, smaller; coverage 0.835 |
| B | parametric: scale from the **model's own** predicted q90−q10 | 0.5549 | 1.0445 | 0.4823 | circular — assumes the model's conditional spread |
| C | `05c` GPBoost fitted σ²_residual, quoted not re-derived | — | 1.0024 | — | **down** (in-sample on both the tree and the stint effect) |
| — | leave-one-out cell quantile — a *real* predictor, 13,430 rows | 0.6090 | 1.0717 | 0.5350 | none; it is a loss, not an estimate |
| — | production, **same 13,430 rows** | 0.5149 | 1.0059 | 0.5555 | — |
| — | production, all 13,896 eval rows | 0.5188 | 1.0163 | 0.5600 | — |

Legs A and B agree to within 2% on all three heads from entirely different inputs — one from
within-cell dispersion of the data, one from the model's own predicted spread — which is the
strongest single piece of evidence that the arithmetic is sound. Leg C sits 5.8% below leg A on p50
and is a lower bound where leg A is an upper one, so **the p50 answer is `L* ∈ [1.0024, 1.0641]`
with the achieved 1.0163 inside it.**

**The leave-one-out cell predictor appears to beat the production p90 head and does not.** On the
identical 13,430 rows it scores 0.5350 against 0.5555. A reseed floor is the wrong instrument for
that comparison — it prices "same config, different seed", and this is two different predictors on
one row set — so a paired race-cluster bootstrap was run instead: **−0.02045, sd 0.04201, 95%
[−0.10688, +0.05342]**. It straddles zero comfortably and the finding is withdrawn. p10 and p50 go
the other way and also straddle (+0.09412 and +0.06575).

#### Per-stratum, as R1 requires

`compound × lap-in-stint band × circuit`: 259 strata, of which **172 hold n ≥ 30 and cover 12,560
of the 13,896 rows**. The remainder are reported in `strata.csv` with their `n` and excluded from
the aggregate rather than folded into a neighbour.

| head | aggregate floor | aggregate achieved | ratio | per-stratum ratio p10 / median / p90 | strata violating |
| :--- | ---: | ---: | ---: | :--- | :--- |
| p10 | 0.5201 | 0.4894 | 1.063 | 0.72 / 1.32 / 1.83 | 127 / 172 |
| p50 | 0.9789 | 0.9667 | 1.013 | 0.73 / 1.14 / 1.57 | 119 / 172 |
| p90 | 0.4521 | 0.5348 | 0.845 | 0.67 / 0.99 / 1.34 | 82 / 172 |

The aggregate exists only to reconcile against the headline and against legs B and C, all of which
are pooled numbers; it is an aggregate everywhere it appears. Note that its achieved column sits
below the published headline (0.4894 against 0.5188 on p10) because the 1,336 rows in sub-30 strata
are harder than average — that is a population difference, not a disagreement.

The per-stratum spread is the more informative half of the table: **the floor/achieved ratio runs
from about 0.7 to about 1.8 across strata on every head.** One global floor for this target would
have been false, exactly as §3b's own caveat guessed.

#### Reconciliation with `01a`, as the definition of done requires

`01a`'s row curve is flat for all five families and its extrapolated intercept does not bind.
`01b` was named as the third check on the case where a floor claims material headroom against a
flat learning curve. **On p10 and p50 that case does not arise** — the floor claims *negative*
headroom, so the two instruments agree that there is nothing more to get from more of the same
data, and `01a` already named the reason: the binding constraint is recency, not volume.

**On p90 the case does arise**, at ~10–12%, and it owes the explanation the leaf doc demands.
`01a`'s p90 row arm gained +0.0132 over the full 4× range — 1.9× its own reseed floor, the weakest
of the trio — and its recency arm is the only one of the five that is *mixed* rather than
one-signed (−0.96 to +3.03 across matched n). So the honest reading is that p90's headroom is not
a data-volume claim: more 2018–2023 rows do not reach it, and p90 is also the head where the
newer-window argument is weakest. **What it points at is the upper tail's conditional shape, not
its training set** — which is `11a`'s Mondrian-conformal recalibration, not `05a`'s model family.
Recorded, not acted on.

#### What this item does and does not establish

**Establishes.** The estimator's arithmetic (±0.5% on σ², exact m = 2 skew non-identification,
±5% end-to-end floor recovery under skewed heteroscedastic noise). That defect 1's proposed fix is
unusable and why. That the mean-function bias at three matched coordinates is larger than the
quantity being measured, so **R1's dimension constraint binds harder than it was stated to**: it is
not only that 33-D is outside the regime, it is that the ≤3-D fallback does not have enough
resolution to answer the question either. That p10 and p50 have no measurable headroom, from a
third independent direction after `01a` and `05c`.

**Does not establish.** Any headroom percentage on p10 or p50 — the instrument fails its gate
there and no number is quoted. p90's headroom beyond "at least ~10%, directional" — the arm-5
correction pulls its band back over the achieved loss. The magnitude of the mean-function bias —
+17% is a property of an invented `f`. The noise shape's true skew and kurtosis — γ̂₁ and γ̂₂ are
attenuated by a measured factor and only their sign and rough scale are used.

**Three instruments now agree** on the question `01` was opened to answer. `ceiling.py`'s
`fraction_of_attainable` does not bind; `01a`'s learning curves do not bind; `01b`'s difference-based
floor does not bind on two of three heads and binds weakly on the third. That is not three failures
— it is a consistent answer, and the consistent answer is that **the degradation trio's remaining
headroom is smaller than any instrument the programme has can resolve.**

---

### Definition of done

The synthetic recovery test (skewed, heteroscedastic, per-sweep-point) passes; the admissible
neighbour-distance distribution is measured and reported; the floor is published as a bracket
with the metric, NaN treatment and weighting rule stated; every point on the curve is checked
against the falsification gate and a violating point is **reported as an instrument failure,
not dropped from the plot**; and the result is reconciled against `01a`'s learning curves.
