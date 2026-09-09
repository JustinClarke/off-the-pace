# R2 — Model family: four candidate classes, ranked by what they cost the shipping pipeline

**Track:** T2 · **Prices:** `05a` · **Status:** DRAFTED

`work/05` frames the model-family question well and blocks it correctly — it is expensive and
unlikely to pay unless `01` shows headroom. This document does not argue with that ordering. It
argues that **"model family" is not one decision**, and that three of the four candidate moves
are far cheaper than `05a`'s "days to weeks" because they do not leave the XGBoost pipeline.

The ordering below is by **cost to the existing tooling** — the ONNX export, the parity gate,
`behaviour_audit`, the calibration gates — which `work/05` correctly names as a real cost.

---

## The two structural arguments, restated with a measurement

`work/05`'s two arguments are nesting and smooth monotone curves. A third is measurable:

**Verified — the degradation target is skewed and heavy-tailed.** `next_5_lap_cumulative_jump_s`,
training-eligible rows, `data/dev.duckdb` read-only:

| n | mean | sd | p01 | p10 | p50 | p90 | p99 | skewness | excess kurtosis |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 82,315 | −1.9777 | 6.0833 | −20.079 | −10.313 | −0.777 | 3.171 | 13.915 | **−0.829** | **5.218** |

Left-skewed, with a tail that runs to −20 s against a median of −0.78 s. Three independently
fitted conditional quantiles cannot share information about that shape; a model of location,
scale and shape can. This is the standard argument for **distributional regression**, and it
applies here on a measured basis rather than a stylistic one.

> **Negative result, recorded so it is not re-derived.** The usual first argument for
> distributional regression — quantile crossing — **is not available here.** `predict.py:53`
> row-sorts the trio before writing, so the parquet's 0 crossings in 137,447 rows say nothing
> about the models. See [R4](R4-conditional-coverage.md) §"what came back negative".

---

## Tier 1 — free, stays inside XGBoost, ships tomorrow

### Monotone constraints on the physically monotone coordinates

XGBoost has supported `monotone_constraints` for years. `work/05`'s second argument — that a
tree ensemble "spends capacity rediscovering" a monotone physical curve and can produce
non-monotone artefacts, which `behaviour_audit`'s monotonicity probe exists to catch — is an
argument for **turning the constraint on**, not for changing model class.

Candidates from the contract: `age_in_stint`, `lap_in_stint`, `laps_past_cliff`,
`cumulative_push_load_surface` / `_bulk`. Each is a coordinate where degradation is physically
expected to be monotone in one direction.

Cost: a hyperparameter. ONNX export unaffected. `behaviour_audit`'s monotonicity probe becomes a
**test of a guarantee** rather than a hope. This is the single cheapest item in this entire
research round, and it directly answers half of `work/05`'s structural case without any of
`05a`'s expense. It should not be blocked behind `01`.

Caveat: a hard constraint costs fit where the physics is wrong (warm-up, track evolution, fuel
effects at the start of a stint make early-stint pace non-monotone in age). Run it as a
`gates.md`-compliant add-ablation like anything else — the constraint may not clear its own
reseed floor, and that is a result.

---

## Tier 2 — cheap, keeps gradient boosting, changes the loss

### Distributional boosting (XGBoostLSS / NGBoost / CatBoostLSS)

[XGBoostLSS](https://arxiv.org/pdf/2210.06831) (März) connects gradient boosting to the
**GAMLSS** framework: model every parameter of a chosen distribution — location, scale, shape —
rather than a conditional mean or a single quantile. NGBoost (Duan et al.) does the same via
natural gradients on a proper scoring rule. Both give the full predictive distribution, from
which p10/p50/p90 fall out by construction, coherent and non-crossing by definition.

For a target with skew −0.83 and excess kurtosis 5.2, the family choice matters and is the
whole risk: [recent work](https://arxiv.org/pdf/2410.03535) finds non-parametric alternatives
beating NGBoost on CRPS precisely because parametric families need domain expertise to avoid a
poor fit. A skew-t or two-piece normal is the honest starting family here, not a Gaussian.

**What it buys this repo specifically, beyond the trio:**

- **One proper score** (CRPS) instead of three pinball headlines — see [R1](R1-instruments.md) §3.
- **A closed-form noise-floor estimate**, because a fitted conditional distribution gives the
  expected pinball loss of a perfectly calibrated predictor per row — the parametric end of the
  bracket [R1](R1-instruments.md) §1 proposes.
- **Three artefacts become one.** The p10/p50/p90 trio is three boosters, three tunes, three sets
  of reseed floors. A distributional fit is one.

**Cost:** the loss and the artefact shape change, so the manifest, the predictions schema and the
ONNX post-transform all move. XGBoostLSS is XGBoost underneath, so the export path is
recoverable, but it is not free. Days.

### Non-parametric distributional forests

[Distributional Random Forests](https://arxiv.org/pdf/2206.04140) (Ćevid et al.) and quantile
regression forests avoid the family-choice risk entirely by producing a weighted empirical
conditional distribution. Cheaper to reason about, no family misspecification, but no ONNX story
and a much larger artefact. Worth a probe as a **reference distribution to score the parametric
fit against**, not as a shipping candidate.

---

## Tier 3 — the honest answer to `work/05`'s nesting argument

### GPBoost — tree boosting *with* grouped random effects

[GPBoost](https://github.com/fabsig/GPBoost) (Sigrist, JMLR 2022 / TPAMI 2023) fits
`y = F(X) + Zb + ε` where `F` is a boosted tree ensemble and `Zb` are grouped random effects,
learning the tree ensemble and the **(co)variance parameters** jointly — trees via LightGBM,
variance components via gradient descent or Fisher scoring.

This is the model `work/05` describes and then rejects as expensive. It is not as expensive as
described, because **it does not abandon the tree ensemble** — it adds a random-effects layer
on top of it. The nesting the repo has is exactly its use case: lap within stint within race
within season, with driver and constructor crossing.

**And its output *is* the answer to `01`'s question.** `work/05` already notices this
("its per-level variance components are themselves an answer to `01`'s headroom question"). It
is worth being blunt about the consequence: a GPBoost fit returns `σ²_stint`, `σ²_race`,
`σ²_driver`, `σ²_residual` **as fitted parameters**. That residual variance is a model-based
estimate of the irreducible noise — the third leg of the bracket in [R1](R1-instruments.md) §1,
obtained from a fit rather than from a neighbourhood construction, and therefore failing in
different directions from the difference-based estimate.

**This inverts `work/05`'s dependency.** `05a` is blocked on `01a`/`01b` because a class change
cannot claim headroom that has not been shown to exist. But a GPBoost fit is *also an instrument*
for `01`. The two items measure the same thing by different means — which `work/05` names as a
reason to run `01` first, and which is equally a reason to run a bounded GPBoost probe as part of
`01` rather than after it.

**Cost:** real. New dependency, no ONNX path for the random-effects part (the tree part exports;
the `Zb` term is a lookup the app would have to carry), and the parity gate would need extending.
But a **measurement-only probe** — fit, read the variance components, never ship — costs a day or
two and touches nothing. That probe is the recommendation, not the class change.

Related and cheaper to try first: MERF / REEMtree (mixed-effects random forests) are the same
idea with less machinery.

---

## Tier 4 — worth knowing about, not worth doing yet

### Tabular foundation models

[TabPFN v2](https://www.nature.com/articles/s41586-024-08328-6) (Nature, 2025) is a transformer
pre-trained on synthetic tabular tasks that does in-context learning — no fitting. Its successors
[TabPFN-2.5](https://arxiv.org/abs/2511.08667) and TabICLv2 report large win rates over tuned
XGBoost, including **an 85% win rate for regression on larger datasets** for TabPFN-2.5, and
[strong out-of-distribution behaviour](https://arxiv.org/pdf/2502.17361).

Three reasons this is Tier 4 for this repo and not Tier 1:

1. **The benchmark population is not this population.** Those win rates are over benchmark suites
   of i.i.d. tabular tasks. This is a panel with temporal structure, season-grouped CV, and a
   target whose consecutive rows share four of five terms. Nothing in those results speaks to it.
2. **It costs the entire shipping pipeline.** No ONNX, no `.bst`, inference is a forward pass
   through a large model. `app/public/models/` cannot carry it.
3. **But it is a superb ceiling probe.** Run it *only* as an instrument: if a foundation model
   with no feature engineering and no tuning cannot beat v11 on the `cv_final_fold` split, that
   is meaningful evidence about how much the 33-column contract is leaving on the table. If it
   beats it substantially, that is a headroom measurement worth more than the sweep in `01b`.
   Note [Tabular Foundation Models Can Do Survival Analysis](https://arxiv.org/pdf/2601.22259)
   covers the stint-life family too.

### Neural additive models and shape-constrained GAMs

[scam / mono-GAM](https://arxiv.org/pdf/2403.09438) gives shape-constrained additive modelling
with monotonicity *and* convexity/concavity constraints and automatic smoothing-parameter
selection; NAM/NODE-GAM are the neural equivalents;
[constrained monotonic neural networks](https://link.springer.com/article/10.1007/s11222-025-10791-8)
give universal approximation of monotone functions. These are the "right prior" answer to
`work/05`'s smoothness argument — but Tier 1's monotone constraints get most of the benefit for
none of the cost, and should be measured first.

---

## Recommended sequence

1. **Monotone constraints** (Tier 1). Hours. Unblock immediately; do not wait on `01`.
2. **GPBoost variance-components probe** (Tier 3, measurement only). 1–2 days. Fold into `01`
   as a third bracket leg rather than leaving it behind `01b`.
3. **CRPS reporting** (from [R1](R1-instruments.md) §3). Hours. Prerequisite for comparing any
   distributional fit to the incumbent trio at all.
4. **Distributional boosting** (Tier 2). Days. Only after 3, because without CRPS there is no
   comparable headline.
5. **TabPFN-2.5 as a ceiling instrument** (Tier 4). Bounded, measurement-only, never shipped.

`05a` stays blocked as a *shipping* decision. Steps 1–3 are not that decision and should not
inherit its block.
