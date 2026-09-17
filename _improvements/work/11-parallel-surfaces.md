# 11 — Parallel surfaces

**Group:** 11 · **Depends on:** nothing · **`parallel`** — nothing on the ML ladder waits for these

Two items from research round R1 that touch no model and block nothing, so they can run at any
time. Both convert work that already exists into something a user can read.

---

## 11a — Mondrian-conformal recalibration of the degradation band

**Objective.** Give the p10–p90 band a coverage guarantee that holds **per circuit**, not just on
average.

**The defect, verified but in-sample.** Pooled coverage is 80.38% against a nominal 80, with
symmetric tails — marginally the band is excellent. Conditionally it is not:

| conditioning variable | groups | coverage range | spread |
| :--- | ---: | :--- | ---: |
| lap-in-stint band | 5 | 79.9–81.2% | 1.3 pts |
| `cliff_onset_passed` | 2 | 80.3–80.8% | 0.5 pts |
| **circuit** (n ≥ 300) | **36** | **72.4–85.6%** | **13.2 pts** |

The band is right along the axes the model was built to reason about, and wrong along circuit
identity. Full evidence, including the compound spread being a small-n artefact:
[`../research/R4-conditional-coverage.md`](../research/R4-conditional-coverage.md).

> **Protocol anchor.** Production v11 trains on every season (`holdout_season` = 2025, unpopulated)
> and `load_scoring_frame` scores every lap, so those figures are **in-sample**. They are the
> motivation, never the baseline. An in-sample conditional spread is a *lower bound* on the
> out-of-sample one.

**Method.** Split-conformal over the CQR score `max(q_lo − y, y − q_hi)`, with a **Mondrian
taxonomy keyed on `circuit_key`** — a separate conformal quantile per circuit. 36 groups at
n ≥ 300 is comfortably above what a 90% quantile needs. Hold out a calibration split **by season,
or by race within season, stated explicitly**.

**It does not touch the model.** No refit, no contract change, no re-tune, no ONNX re-export. It
is a post-hoc layer over outputs that already exist, so it cannot regress the headline and does
not need `gates.md` step 1.

**Exchangeability is the real risk and must be stated.** Seasons are not exchangeable — regulation
eras, compound allocations and calendars all move. If the out-of-sample check degrades, the
weighted-conformal and adaptive-conformal literature bounds the coverage gap by the drift rather
than assuming it away.

**Acceptance.** Coverage reported marginally and per circuit, **before and after, out of sample**,
with **interval width alongside** — a fix that buys Mexico's coverage by doubling its band width
is a real cost the app pays.

**Definition of done.** A per-circuit offset the app can apply, and an honest statement of what
the guarantee does and does not cover.

**Pre-registered caution.** 36 groups were scanned and the two worst reported. That is a
garden-of-forking-paths problem; the out-of-sample re-measurement is the test, and R4's table is
the hypothesis. Declare the e-value construction per `09b`.

---

### `11a` — PRE-REGISTRATION (2026-09-16, written before the test half was read)

Frozen from the calibration seasons alone. Machine-readable copy:
[`../implementations/11a/s1_prereg.json`](../implementations/11a/s1_prereg.json).

**The split, and why it is 3 / 2 / 2 rather than the "by season or by race within season"
the spec offered.** Both halves of a conformal layer must be out of sample — a conformal
quantile computed on rows the model trained on is optimistically tight — so fit, calibrate and
test have to be three *disjoint* blocks of seasons. Production v11 fits on all seven, so a
shadow fit is unavoidable; it writes nothing to `ml/models/` and touches no production artefact.

- **fit** 2018–2020 (32,695 rows) · **calibrate** 2021–2022 (23,551) · **test** 2023–2024 (26,224)

Two *test* seasons, not one, for a structural reason 01b already hit: **every 2024 circuit hosts
exactly one race.** With a single test season "per-circuit coverage" *is* "per-race coverage" —
circuit and race are perfectly confounded and nothing separates "Mexico is miscalibrated" from
"the 2024 Mexico race was unusual". Two test seasons give 22 of 24 circuits a within-circuit
replicate. Two *calibration* seasons for the mirror reason: one season is ~1 race per circuit,
and a per-circuit quantile off a single race inherits that race's idiosyncrasy wholesale.

The price is a three-season fit against production's seven, so the shadow model is weaker:
**calibration-half pooled coverage 77.06%**, against production's in-sample 80.38%. That is a
caveat on the *level* this study can transfer, not on the mechanism it tests.

```
### E-value pre-registration — 11a

H0                : (E1) race-level coverage at the named circuit has mean mu0 = 0.80
                    (E2) circuit identity carries no information about race-level coverage
Statistic         : p10-p90 band coverage indicator, shadow fit 2018-2020,
                    calibrate 2021-2022, test 2023-2024, training-eligible rows with a
                    non-null next_5_lap_cumulative_jump_s (R4's population)
Delta orientation : one-sided, under-coverage only; positive = coverage below nominal
Construction      : E1 betting e-value on bounded per-race coverage rates (A-family)
                    E2 shuffle-rank e-value over circuit labels (C), capped at K+1
Seeds             : n/a - no reseed arm; RANDOM_STATE 20260528 for the shadow fit
Parameters        : E1: mu0 = 0.80, mu1 = 0.75, sigma^2 = 0.005621 (per-race coverage
                        variance on CALIB races only), lambda_GRO = 6.157, hard cap
                        1/(1-mu0) = 5, capital fraction 0.5 -> lambda = 2.5
                    E2: K = 999, cap = 1000
Formula           : E1 = prod_r [1 + 2.5 * (0.80 - c_r)]  over test races r at the circuit
                    E2 = (K+1) / (1 + #{permuted stat >= observed stat})
Declared alt      : mu1 = 0.75 - a five-point shortfall on an 80% band, the smallest
                    miscalibration worth shipping a per-circuit correction for
Hypothesis count  : this adds 4 hypotheses to the campaign family
                    (E1 Mexico, E1 Qatar, E1 the two pooled, E2 the scan)
Reported          : E, whatever its value, including E < 1
```

**Why the betting unit is the race and not the lap.** Laps within a race are strongly dependent;
a lap-level product martingale over ~570 correlated indicators would be wildly anti-conservative.
Aggregating to the per-race coverage rate absorbs that dependence into the statistic. The residual
assumption — that races are independent — is stated, not assumed away, and E2 does not need it.

**Declared power, before the run.** Each pre-registered circuit hosts **2** test races, so E1 is a
product of two bounded factors. At the declared alternative its maximum attainable value is
**1.27 per circuit and 1.60 pooled**, against the `E >= 600` that
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) records as the
price of a lone rejection in a family of 30. **E1 therefore cannot clear e-BH by construction and
is declared in advance as a directional reading only.** E2 is the instrument carrying power. This
is a property of the design, recorded here so it cannot later be reported as a disappointment.

**Why `lambda` is truncated.** The GRO bet for this alternative is 6.157, above the hard
non-negativity cap of 5. Betting at the cap is degenerate — a single race covering at 100% drives
a factor to exactly 0 and annihilates the e-value permanently — so the Waudby-Smith–Ramdas
capital-preserving truncation at half the cap binds instead. Fixed before any test row was read.

**A third reading, declared as an effect size and not a test.** R4 screened circuits at
**n ≥ 300 laps**. Laps within a race are not independent, so the effective sample size per circuit
is the number of *races*, not the number of laps. `ceiling.py::variance_components` on per-race
coverage rates grouped by circuit asks how much of R4's 13.2-point spread is a circuit component
at all. If that component is near zero, a Mondrian scheme keyed on circuit is calibrating against
race-to-race noise and will not transfer. Declared here because it is the reading most likely to
overturn the item's own premise.

---

### `11a` — RESULT (2026-09-16)

**The recommendation is to ship no per-circuit offset.** Every conformal variant tested is either
neutral or actively harmful out of sample, and the defect they were built to fix is mostly a
measurement artefact. The deliverable is therefore a negative one, plus the data-volume threshold
at which the question could be reopened.

Scripts and artefacts: [`../implementations/11a/`](../implementations/11a/).

> **STALE AS OF `08m` (2026-09-16).** This result's band, coverage and pinball numbers are all
> computed on `next_5_lap_cumulative_jump_s` as it stood **before** `08m` fixed the compound
> seed's consumption and rebuilt the warehouse. The target is now a different quantity (mean
> −1.8793 s → −0.3946 s; population 82,470 → 81,619 rows), so the n = 82,470 population this
> section names no longer exists and every absolute number below is on the superseded target.
> The **negative recommendation survives** — it rests on out-of-sample behaviour of the conformal
> variants relative to each other on a common target, not on the target's absolute scale — but
> the coverage table would have to be rebuilt before any of its figures are quoted again, and the
> "mostly a measurement artefact" diagnosis should be re-checked, since `08m` removed a genuine
> systematic distortion from the very band this item was recalibrating. `08m` did not re-run it.

#### R4's table reproduces — once the predictions are not read from the stale parquet

Re-scoring the current v11 boosters on the current mart, on R4's exact population
(`is_in_envelope` + non-null target, n = 82,470):

| | this run | R4 |
| :--- | ---: | ---: |
| pooled coverage | **80.49%** | 80.38% |
| below p10 | 9.73% | 9.75% |
| above p90 | 9.78% | 9.88% |
| per-circuit spread, n ≥ 300, 36 circuits | **13.4 pts** | 13.2 pts |

R4 is **verified**. But note how that number had to be obtained.

> **`data/marts/mart_degradation_predictions.parquet` is stale.** It was written 2026-09-05 and
> the mart has been rebuilt since. Reading the *stored* predictions against the *current* target
> gives pooled coverage **78.77%** and a lower-edge rate of 11.25% — a 1.7-point error against the
> 80.49% the same boosters produce when re-scored now. Anything downstream reading that parquet is
> reading stale predictions. Found incidentally; not fixed here, and not this item's to fix.

#### The per-circuit spread is mostly race-to-race noise, not circuit identity

`ceiling.py::variance_components` on per-race coverage rates grouped by circuit. The naive column
is what a per-circuit coverage table computes structurally, and is the estimator R4's table is:

| population | circuit ICC | naive (biased up) | sd(circuit effect) | sd(race noise) |
| :--- | ---: | ---: | ---: | ---: |
| production v11, in-sample (R4's rows) | **0.024** | 0.313 | **0.74 pts** | 4.65 pts |
| production v11, out-of-sample (ineligible rows) | 0.285 | 0.468 | 7.01 pts | 11.10 pts |
| shadow fit, out-of-sample (2023–24) | 0.221 | 0.649 | 3.85 pts | 7.21 pts |

On R4's own rows the between-circuit coverage sd is **0.74 points** against 4.65 points of
race-to-race noise — the naive share overstates the circuit component **13×**. With 147 races over
36 circuits (~4.1 each), the standard error of a per-circuit coverage estimate is
4.65/√4.1 ≈ 2.3 points, and the max-minus-min of 36 such estimates is ~9–10 points from noise
alone. That accounts for most of the observed 13.4. **R4's `n ≥ 300` screen counts laps, and laps
within a race are not independent; the effective unit is the race.**

R4's own one-directional claim — that an in-sample spread is a lower bound on the out-of-sample
one — is separately **confirmed**: out of sample the spread is 28.9 pts and the circuit component
is larger (ICC 0.22–0.29, sd 3.9–7.0 pts). So a circuit effect does exist. It is simply far too
small relative to race noise to estimate from the races available.

#### The fix is strictly dominated, under both splits

Out of sample, shadow fit 2018–2020 / calibrate 2021–2022 / test 2023–2024 (26,224 rows, 46 races,
24 circuits). Coverage CIs are race-clustered bootstrap, n = 2000.

| scheme | coverage | 95% CI | below p10 | above p90 | mean width | per-circuit RMSE about 0.80 | spread |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: |
| raw (no conformal) | 81.11% | 78.0–83.5 | 11.03% | 7.87% | **7.507 s** | **6.63 pts** | **28.9 pts** |
| pooled CQR, symmetric | 83.72% | 80.6–86.0 | 9.52% | 6.77% | 7.957 s | 7.41 pts | 27.0 pts |
| pooled CQR, per edge | 83.77% | 80.8–86.0 | 9.24% | 6.99% | 7.962 s | 7.42 pts | 27.2 pts |
| **Mondrian, symmetric** | 84.22% | 81.2–86.7 | 9.15% | 6.63% | 8.493 s | **8.98 pts** | **37.8 pts** |
| **Mondrian, per edge** | 82.91% | 79.8–85.5 | 9.15% | 7.94% | 8.440 s | 8.39 pts | 37.5 pts |

**The Mondrian layer makes conditional coverage worse while costing 13% more band width.** It is
not a drift artefact: over 200 race-randomised splits — the near-exchangeable design where
conformal's own assumptions hold best — raw per-circuit spread is 29.6 ± 8.5 pts and Mondrian is
**40.4 ± 12.7**. It is overfitting, and the per-circuit offsets show it directly: the pooled
conformal offset is **+0.225 s**, while the per-circuit offsets run **−0.263 s to +6.605 s**, a
29× spread fitted from 43 calibration races.

The clearest single illustration lands on a pre-registered circuit. **Qatar's Mondrian band
inflates to 19.37 s against 7.51 s raw — 2.6× — and covers 99.87%.** That is precisely the failure
the acceptance criterion named in advance: a fix that buys coverage by doubling the band width.

Per stratum (`compound × lap-in-stint band × circuit`, 01b's stratification, 237 strata at n ≥ 30)
the ordering is the same: raw 11.96 pts RMSE about nominal, pooled 11.81, Mondrian 12.88.

#### Shrinkage rescues it as far as doing nothing, and no further

Partial pooling of the per-circuit quantile toward the pooled one, at the BLUP weight implied by a
variance decomposition of per-race conformal quantiles on calibration data
(w̄ = 0.72). Mean per-circuit RMSE about nominal, as a penalty **relative to doing nothing**:

| calibration races per circuit | Mondrian − raw | shrunk Mondrian − raw |
| ---: | ---: | ---: |
| 0.76 | +2.45 | +0.89 |
| 1.24 | +2.66 | +0.59 |
| 1.52 | +2.57 | +0.54 |
| 2.00 | +2.43 | +0.42 |
| 2.45 | +1.82 | +0.24 |

Shrinkage closes most of the penalty, and the penalty shrinks with volume — but the shrunk scheme
**converges to doing nothing from above and never beats it** at any volume the data can supply.
Note also that the shrunk scheme is a heuristic recalibration, **not** a conformal one: the shrunk
value is not an order statistic of the calibration scores, so the finite-sample distribution-free
guarantee does not apply to it. That is most of the reason to prefer the pooled offset, which
keeps its guarantee, to a shrunk per-circuit one that does not.

**What it would take.** The per-circuit estimate has SE = σ_race/√n_races, so a per-circuit offset
is only informative once that is small against σ_circuit:

| threshold | shadow OOS | production OOS |
| :--- | ---: | ---: |
| SE = the circuit effect | 3.5 races | 2.5 races |
| SE = half the effect | **14.1 races** | **10.0 races** |
| SE = a third of the effect | 31.7 races | 22.6 races |

A circuit hosts ~1 race per season, so races-per-circuit **is** seasons-of-history-per-circuit. The
warehouse holds 7 seasons and yields ~4 races per circuit. **The requirement is roughly 10–14, so
this is short by a factor of 2–3.** Reopen when the history reaches it, or if a taxonomy coarser
than circuit (circuit *archetype* — abrasiveness, lap length, downforce class) can pool races
without pooling away the effect. That is the natural next design and was not tested here.

#### The pre-registered e-values, reported whatever their value

| hypothesis | out-of-sample coverage | R4 in-sample | E |
| :--- | ---: | ---: | ---: |
| E1 Mexico | **85.88%** | 72.4% | **0.728** |
| E1 Qatar | **81.81%** | 72.7% | **0.949** |
| E1 both pooled | 84.51% | — | **0.690** |
| E2 scan, 36-circuit max under-coverage | observed 15.19 pts | — | **1.04** |

**Both pre-registered circuits reverse sign** — R4's two worst under-coverers are its two best
over-coverers out of sample. All three E1 values sit below 1, i.e. evidence *against* the declared
alternative, exactly as declared they would be reported. E2 at **1.04** says the worst observed
under-coverage is entirely typical of shuffled circuit labels: **no evidence that circuit identity
carries information about coverage.** E1's weakness was declared in advance (ceiling 1.27 per
circuit) and it is a directional reading only; **E2 is the result that carries weight**, and it is
null. This is what a garden-of-forking-paths artefact looks like when it is re-measured properly,
which is what the pre-registered caution existed to catch.

Four hypotheses join the campaign e-BH family. None is a rejection.

#### The exchangeability cost, quantified rather than assumed

Pooled conformal reaches **80.02% ± 2.03%** marginal coverage under the race-randomised split — the
textbook guarantee, delivered. Under the temporal split it overshoots to **83.72%**. The
**3.7-point gap is the cost of seasons not being exchangeable**, and it is a cost the weighted- and
adaptive-conformal literature would bound rather than remove.

The edges make it concrete, and 01b was right that they are in different states. On calibration
(2021–22) 10.99% of rows exceeded p90, so the conformal layer bought a **+0.173 s widening** of the
upper edge. On test (2023–24) only **7.87%** exceeded it — the upper edge had become conservative
and needed *tightening*. **The correction was applied in the wrong direction because the edge
changed state between calibration and test.** Meanwhile the lower edge ran hot in both halves
(11.9% then 11.0%), so p10 is the edge with a persistent problem and p90 is not — the opposite of
where a symmetric scheme would spend its width, and the reason the per-edge split 01b asked for was
worth carrying.

#### What the guarantee does and does not cover

**Does:** split conformal over the CQR score gives finite-sample, distribution-free **marginal**
coverage, and this run delivers it — 80.02% ± 2.03% against a nominal 80 under a race-randomised
split. It needs no assumption about the model, the features, or the shape of the residual.

**Does not:**
1. **Conditional coverage of any kind.** The marginal guarantee says nothing about any circuit,
   compound or stint phase. Mondrian would buy per-group coverage *if* the per-group quantiles were
   estimable; here they are not, and the attempt costs 13% of band width to make conditional
   coverage worse.
2. **Anything under season drift.** Exchangeability is assumed and is false across seasons; the
   measured price is 3.7 points of marginal coverage, and it moved the p90 correction the wrong way.
3. **Circuits with no calibration history.** China and Las Vegas appear in test with no calibration
   races — 1,184 test rows, 4.5% — and any per-circuit scheme must serve them from a pooled
   fallback with no per-group guarantee. Each new calendar addition is this case.
4. **The shrunk variant, at all.** Not an order statistic, so not conformal.
5. **The level, transferred from this study to production.** The shadow fit trains on three seasons
   against production's seven and covers at 77.06% on the calibration half where production covers
   at 80.49% in-sample. The *mechanism* transfers; the *level* does not.

#### Incidental verifications

- **Raw quantile-crossing rate: 0.093%** (shadow fit, pre-sort), under `predict.py`'s 1% warn
  threshold. R4 recorded this as structurally unmeasurable from the parquet because `predict.py:53`
  row-sorts before writing. It is measurable at fit time, and it is small.
- **The 3/2/2 split design.** Every 2024 circuit hosts exactly one race, so a single test season
  confounds circuit with race completely — the constraint 01b hit. Two test seasons give 22 of 24
  circuits a within-circuit replicate. Any future re-run of this item needs the same structure.

#### Definition of done

- **Per-circuit offset the app can apply** — [`../implementations/11a/offsets.csv`](../implementations/11a/offsets.csv),
  carrying `q_sym`, `q_lo`, `q_hi` per circuit plus the `__POOLED__` fallback row. **Shipped with a
  recommendation against applying the per-circuit rows.** If a correction is wanted, the pooled row
  (+0.225 s symmetric) is the only one that keeps its guarantee — and production's marginal coverage
  is already 80.49%, so it is not needed either.
- **Honest statement of what the guarantee covers** — the section above.

---

### What `01b` hands `11a` — read before choosing the conditioning variable

`01b` landed 2026-09-09 and produced one directional result, deliberately not acted on there
because it is a recalibration question rather than a model-family one.

**`p90` is the only head of the degradation trio where the empirical noise floor and the achieved
loss separate.** Its L3 matched-cell floor is 0.4914 against an achieved 0.5600 — about +12%
headroom — and the floor is upward-biased by a theorem (`Var(y|cell) = Var(f|cell) + E[σ²|cell]`),
so removing that bias can only widen the gap. `p10` and `p90` are not symmetric here: p10's floor
comes back *above* its achieved loss (0.5654 vs 0.5188) and p50's does too (1.0641 vs 1.0163).
**Whatever is available on this trio is in the upper tail specifically.**

Two caveats that bound it, both from `01b`'s own arms. Adding back the 4.5% between-race component
of the production residual (`ceiling.py::variance_components` on the p50 eval residuals) moves the
p90 floor to 0.5046 with a race-cluster band of 0.4485–0.5618, whose top edge just covers the
achieved 0.5600 — so the separation is about the size of its own error bar. And `01a`'s p90 row arm
was the weakest of the trio (1.9× its reseed floor over the full 4× range) with the only *mixed*
recency signal of the five families, so this is **not** a data-volume claim and a training-window
change is not the lever.

**Consequence for `11a`.** The per-circuit conditional coverage defect this item exists to fix is
measured on the p10–p90 band as a whole. `01b` says the two edges are not in the same state, so a
Mondrian scheme that recalibrates the band symmetrically would be correcting the edge that has
nothing to give alongside the edge that does. Consider keying the recalibration per edge, and
report the two tails separately whatever is chosen. `01b`'s per-stratum table
(`compound × lap-in-stint band × circuit`, 172 strata at n ≥ 30) is the same stratification this
item needs and is in `work/01-ceiling-instrument.md`.

---

## 11b — Assemble the stochastic DP over pit timing

**Objective.** Convert five predictive models into one decision surface, and get a headroom metric
**in seconds of race time**.

**Everything needed already exists.** `int_pit_strategy_cost_curve` (386,036 rows),
`int_pit_strategy_value` (7,129), `int_pit_loss_circuit`, `int_sc_hazard_history` — whose own
header says it exists *"so a Monte Carlo race simulator could draw an interruption on each
simulated lap"* and which `ml_headroom.md` records as **consumed by nothing** — plus the five
models. Those are the transition costs, the stochastic event process and the state dynamics of a
published dynamic-programming formulation (Carrasco Heine & Thraves, CEJOR 2022, including its
yellow-flag stochastic extension).

> **CORRECTION (2026-09-16, from the `11b` run below — three of the four table claims in the
> paragraph above are stale, and the `Method` block names two state dimensions that do not
> exist).** `int_pit_strategy_cost_curve` holds **414,289** rows, not 386,036.
> `int_sc_hazard_history` holds **149** rows, not 36, is keyed on **(circuit_slug, season)** since
> `02d`'s point-in-time rebuild, has **no lap axis** (it is a flat per-racing-lap rate, not a
> lap-varying profile), and is **not unconsumed** —
> [`int_pit_strategy_cost_curve.sql`](../../transform/models/intermediate/int_pit_strategy_cost_curve.sql)
> reads it as `pit_discount_factor`. `next_compound` is fixed to the realised choice (max 1
> distinct value per stint × scope), so *"compound on stop"* is **not enumerable**; track position
> has **no transition kernel**. And the cost curve's running cost is **not a model prediction** —
> it is `dim_compounds_season`, a lift of the 438-row `compound_cliff_params` seed. Read the
> `11b` RESULT below, not this paragraph. The seed finding is now its own item,
> [`08l`](08-foundations-repair.md).

**Why it matters beyond being a feature.** A DP is what converts a predictive distribution into a
decision, and it changes what the models are *scored on*. A degradation quantile is currently
scored by pinball loss — a statistician's question. Under a DP the same model is scored by **the
expected race time of the policy it induces**, which a strategist can read. The gap between the
DP's policy under the model and under an oracle is then a headroom estimate in seconds, sitting
alongside `ceiling.py`'s statistical one.

**Method.** State: lap, compound, tyre age, track position. Actions: stop / stay, and compound on
stop. Costs: `int_pit_loss_circuit` for the stop, the degradation forecast for the running cost.
Stochastic arm: draw interruptions per lap from `int_sc_hazard_history`'s shrunk per-lap hazard.

**Acceptance.** The DP reproduces known-good historical strategy calls at a rate stated with an
interval, and the model-vs-oracle policy gap is reported in seconds.

**Definition of done.** Assembly, not research — the hard parts are built. A verdict on whether
the induced-policy metric is worth adopting as a headline beside pinball/CRPS.

**Full context:** [`../research/R6-causal-decision-and-the-field.md`](../research/R6-causal-decision-and-the-field.md) Part 3.

---

### `11b` — PRE-REGISTRATION (2026-09-16, written before the test half was read)

Frozen from the dev seasons alone. Machine-readable copy:
[`../implementations/11b/s3_prereg.json`](../implementations/11b/s3_prereg.json).

**The split.** **dev** 2018–2022 (2,649 stints, 101 races, 35 circuits) · **test** 2023–2024
(1,391 stints, 46 races, 24 circuits). Two test seasons for 11a's reason — every 2024 circuit
hosts exactly one race. The DP arms are not fitted objects, but one forecast arm is: 11a's shadow
booster trains on 2018–2020, so 2023–24 is genuinely out of sample for it. **The production v11
arm is in-sample on every row** (v11 trains on every season) and is reported as such throughout.

**The betting unit is the RACE.** Stints within a race share a car, a driver, a track state and a
caution path. 11a measured a 13× overstatement from treating the lap as the unit; every interval
and every betting factor below clusters on the race.

```
### E-value pre-registration — 11b

H0                : (E1) the policy induced by the v11 degradation forecast is no better
                         than the policy induced by the seed-only production surface;
                         P(a race's mean regret is lower under model than under seed) = 0.50
                    (E2) the DP's chosen pit lap carries no information about the realised
                         pit lap
                    (E3) as E1, for the OUT-OF-SAMPLE shadow forecast
Statistic         : E1/E3  W_r = 1{ mean race regret(model) < mean race regret(seed) }
                            on the held-out half-sample truth surface
                    E2     fraction of stints with |L_dp - L_actual| <= 2 valid laps
Delta orientation : one-sided; W_r = 1 and a high reproduction rate count for the model
Construction      : E1/E3 betting e-value on bounded per-race indicators (A-family)
                    E2     Construction C, shuffle-rank, assumption-free
Seeds             : RANDOM_STATE 20260916 for the bootstrap and the permutation
Parameters        : E1/E3 mu0 = 0.50, mu1 = 0.65 (dev: 66/101 races = 0.6535),
                          sigma^2 = 0.228713, lambda_GRO = 0.6559, hard cap 2.0,
                          WSR capital-preserving truncation 1.0 -> lambda = 0.6559
                    E2     K = 999, k = 1, cap = 1000; L_actual permuted among stints
                          sharing a horizon-length bucket (H rounded to nearest 5)
Formula           : E1 = prod_r [1 + 0.6559 * (W_r - 0.50)]
                    E2 = (K+1) / (1 + #{permuted rate >= observed rate})
Declared alt      : mu1 = 0.65 - a two-in-three race win rate, the smallest edge worth
                    rewiring a production surface for
Hypothesis count  : this adds 3 hypotheses to the campaign family
Reported          : E, whatever its value, including E < 1
```

**Declared power, before the run.** 46 test races at mu1 = 0.65 gives expected log-growth
0.0452/race, so **E1 ≈ exp(2.08) ≈ 8.0** against the `E >= 600` a lone rejection in a family of 30
costs. E1 and E3 were therefore **declared in advance as directional readings that cannot clear
e-BH by construction**; E2 carries the power, capped at 1000.

**Two risks declared in advance, because both are the kind that overturn the item's own premise.**

1. **The oracle term may not be identified.** An oracle chosen by minimising the realised cost
   surface mines that surface's lap-to-lap noise — the minimum of ~50 noisy candidates is biased
   low, so "regret against the oracle" is inflated by something that has nothing to do with
   strategy. The pre-declared remedy is a half-sample split: build the oracle from a stint's
   odd laps, score every arm on its even laps, same systematic degradation, independent noise.
   **If the oracle's held-out regret is not the lowest of the arms, the oracle half of the
   acceptance criterion is declared UNIDENTIFIED rather than reported as a headroom number.**
2. **Extrapolation policy `flat` is the pre-declared default** — beyond the age a tyre actually
   reached, the unmodelled-degradation path is held constant and the seed curve carries the
   extrapolation alone. `persist` (hold the last observed slope) is a declared sensitivity, never
   a headline.

**One correction inside the pre-registration window, recorded.** After the block above was frozen,
the caution path was found to be sourced from `fct_lap_residuals`, whose SC/VSC/red-flag columns
are FALSE on all 137,447 rows because that mart is already filtered to green racing laps. It was
repointed at `int_stint_geometry` (162,729 rows; 8,927 SC, 2,980 VSC, 426 red-flag) and every arm
re-run. `lambda` was **not** re-derived from the corrected dev half — re-fitting the alternative to
the data after the fact is the thing pre-registration exists to stop — so it stays at 0.6559, which
the corrected dev win rate (0.6337) makes slightly conservative rather than slightly generous.

---

### `11b` — RESULT (2026-09-16)

**The DP assembles, and the induced-policy metric should NOT be adopted as a headline.** The
seconds-gap the item exists to produce has no identifiable reference point, is dominated by a
modelling choice inside the harness rather than by the models, and returns the verdict that every
professional strategy call in 2023–24 is 4.1 s/stint better than the best policy the warehouse can
induce. One piece of it *is* worth keeping, and it is not the seconds: the **reproduction rate**,
which the ML forecast moves from 33.9% to 53.0% out of sample.

Scripts and artefacts: [`../implementations/11b/`](../implementations/11b/).

#### The "everything needed already exists" claim: three of the four tables are not what the spec says

Read-only audit, [`../implementations/11b/s0_substrate.json`](../implementations/11b/s0_substrate.json).

| table | spec says | warehouse holds | |
| :--- | ---: | ---: | :--- |
| `int_pit_strategy_cost_curve` | 386,036 | **414,289** | 160,540 rows / 4,257 stints at `window` scope; 253,749 / 7,089 at `race` |
| `int_pit_strategy_value` | 7,129 | 7,129 ✓ | unique on `stint_id`; 4,137 rows carry a non-null `actual_pit_lap` |
| `int_pit_loss_circuit` | — | 36 | `pit_loss_s_shrunk` 19.30–29.61 s, median 23.34 |
| `int_sc_hazard_history` | **36** | **149** | grain is **(circuit_slug, season)** since `02d`'s point-in-time rebuild |

Four things follow, and each is a finding rather than a workaround.

1. **`int_sc_hazard_history` is not unconsumed.** `ml_headroom.md` finding #6 and R6 Part 3's table
   both record it as a leaf with no dbt consumer. `int_pit_strategy_cost_curve.sql` reads it and
   turns it into `pit_discount_factor`. Both documents are stale.
2. **It has no lap axis.** "Per-lap SC/VSC hazard per circuit" reads as a lap-varying profile; it is
   a flat per-racing-lap *rate* per (circuit, season) — 0.0243/lap on the test seasons. Every 2018
   row is NULL on every rate (no prior season), and consumers must join on both keys.
3. **The cost curve reads no ML prediction at all.** Its running cost is
   `dim_compounds_season`, which is a typed lift of the 438-row `compound_cliff_params` **seed**.
   So the existing decision surface is not "five predictive models"; it is a hand-seeded
   polynomial, and the item's objective needs the models wired into it, which is work, not
   assembly.
4. **Two of the four declared state dimensions do not exist in the substrate.**
   `next_compound` is fixed to the realised choice — max 1 distinct value per (stint, scope) over
   all 414,289 rows — so **the "compound on stop" action is not enumerable**. And **track position
   has no transition kernel**: `position` is recorded per lap in `fct_lap_residuals`, but nothing
   maps *stop at lap L* → *position after the stop*. That needs the whole field's pace and an
   overtaking model, and neither exists.

**And exactly one candidate per stint is observable.** For a horizon of H valid laps with the
realised stop after `n_old`, candidate L needs old-tyre pace at ages up to L and new-tyre pace at
ages up to H−L. The old set ran `n_old` laps and the new set ran H−n_old. So **L = n_old is the
only candidate with both arms on laps that were actually driven**; every counterfactual extrapolates
one arm past the age that tyre reached. That is the structural reason the incumbent surface uses an
extrapolatable polynomial, and the reason extrapolation policy turns out to dominate this study.

#### What the ML models actually predict is the seed's error, not tyre degradation

`int_lap_residual_decomposed` subtracts `int_compound_cliff_predicted.expected_compound_pace_s` —
the seeded polynomial, `grip_peak + LEAST(gradient·a + 0.002a² + severity·laps_past_cliff, 10.0) +
0.005·Δtemp` — before forming `driver_skill_residual_s`. So `next_5_lap_cumulative_jump_s`, the ML
target, is **the residual of the seed**. A per-lap running cost is `seed(age) + ρ(age)`, and the
models supply a correction to the first term rather than the term itself.

The correction is not small and it has a sign. On the 82,470 training-eligible rows the mean target
is **−2.163 s per 5 laps**, i.e. the seed over-charges degradation by about **0.14 s/lap**. The
cross-section shows the same thing directly: across tyre-age bands 0–5 → 40+, `compound_component_s`
climbs 1.165 → 7.141 s while `driver_skill_residual_s` falls −2.559 → −6.963 s, an almost exact
mirror. **Most of what the degradation trio has learned is how to undo the seed.**

**Why the answer is in seconds of race time, derived rather than asserted.** Across candidates the
horizon spans the same lap numbers, so `base_track_pace_s`, `fuel_component_s`, `rubber_component_s`,
`ambient_component_s` and `constructor_component_s` are identical for every candidate and cancel out
of the argmin. Only the compound term, ρ, and the pit term move. The differences are therefore
differences in that driver's own elapsed race time over the horizon — **minus `dirty_air_tax_s`,
which does depend on the decision and is exactly the missing track-position state.**

The cost function actually solved, with δ(u) = ρ(u) − ρ(1) so the common driver/car level cancels:

```
Cost(L) = A_old[L] + B_new[L] + baseline_delta·(H−L)        <- verbatim from the cost curve
        + Σ_{a≤L} δ_old(a) + Σ_{u≤H−L} δ_new(u)             <- the arm's degradation path
        + P · (m if a caution is available at L else 1)      <- int_pit_loss_circuit, m = 0.5
```

Four arms differ **only** in δ: `seed` (δ ≡ 0, which *is* the incumbent), `model` (v11, in-sample),
`shadow` (11a's 2018–2020 booster, out of sample), `oracle` (the realised ρ path). The model arms
telescope the forecast: J(t) = Σ_{j=1..5}(ρ(t+j) − ρ(t)) − 15·drift, so the predicted local slope is
J(t)/15 + drift. Backward induction over (candidate lap, caution indicator) is the yellow-flag
extension of Carrasco Heine & Thraves; every policy is then executed against the **realised** caution
path and scored on the oracle surface.

#### Instrument check: the seed arm reproduces the production argmin exactly

`arg_min(candidate_pit_lap_offset, total_cost_s)` over the `window` scope reproduces
`int_pit_strategy_value.optimal_pit_lap_in_stint` for **4,257 of 4,257 stints**, and inside the DP
pipeline for **2,649/2,649 dev and 1,391/1,391 test stints**. The harness is the production surface,
not a reimplementation of it.

#### Acceptance 1 — reproduction of the realised call, with its interval

Test half, 1,391 stints over 46 races and 24 circuits. Race-clustered bootstrap, n = 2,000.

| arm | exact (±0) | ±1 lap | **±2 laps** | ±3 laps |
| :--- | ---: | ---: | ---: | ---: |
| `int_pit_strategy_value` argmin (production, as shipped) | 6.90% | 19.63% | **33.86%** [29.0–38.6] | 44.93% |
| seed DP (same surface, caution-aware) | 11.57% | 24.95% | **38.46%** [33.5–43.3] | 50.32% |
| **model DP** (v11, in-sample) | 20.92% | 39.04% | **53.70%** [47.3–60.0] | 64.85% |
| **shadow DP** (2018–20 fit, out of sample) | **21.28%** [17.2–25.6] | 38.68% | **52.98%** [47.0–58.7] | 64.13% |
| oracle DP (half-sample) | 9.49% | 22.93% | 32.64% [28.5–36.6] | 43.06% |

On the **known-good** subset — a green-flag stint ending (`int_stint_end_regime.end_regime = 'green'`,
so a real strategy call rather than a caution or a red flag) by a driver who finished in the points,
607 stints over 45 races — the same ordering, higher: seed 41.35% [35.0–48.0], **shadow 54.04%
[46.4–61.7]**, model 56.67% [49.0–64.3], oracle 38.71% [32.6–43.9] at ±2 laps.

**Adding the degradation forecast to the decision surface roughly triples exact agreement
(6.9% → 21.3%) and adds ~19 points at ±2 laps, and the gain survives an out-of-sample fit.**

#### Acceptance 2 — the model-vs-oracle policy gap in seconds, and why it is not identified

Mean per-stint cost on the **held-out half-sample** surface (oracle built from a stint's odd laps,
every arm scored on its even laps). Seconds; race-clustered 95% CI.

| arm | test half | known-good subset |
| :--- | ---: | ---: |
| human (`L_actual`) | **5.22** [4.35–6.17] | **4.08** [3.10–5.19] |
| model DP, in-sample, with the realised per-stint drift | 7.46 [6.10–8.96] | 4.61 [3.58–5.82] |
| **shadow DP, out of sample** | **9.32** [7.58–11.27] | 7.07 [5.39–8.84] |
| model DP, in-sample, no drift | 9.63 [7.73–11.65] | 8.02 [5.51–10.70] |
| **oracle DP** | **11.52** [9.22–14.36] | 10.53 [7.66–14.06] |
| seed DP (the incumbent) | 12.91 [10.98–15.17] | 9.61 [7.48–11.99] |

| difference (seconds per stint) | test half | known-good |
| :--- | ---: | ---: |
| seed − shadow (**what the ML forecast buys, out of sample**) | **+3.59** [1.64–5.66] | +2.54 [0.59–4.48] |
| seed − model (in-sample, no drift) | +3.29 [1.44–5.09] | +1.59 [−0.29–3.33] |
| **oracle − shadow/model (THE ACCEPTANCE NUMBER)** | **+1.90** [−0.35–4.20] | +2.51 [−0.34–5.35] |
| human − shadow | **−4.10** [−5.76 – −2.58] | −2.99 [−4.65 – −1.52] |
| seed − human | +7.69 [5.83–9.97] | +5.53 [3.60–7.49] |

**The model-vs-oracle policy gap is +1.90 s [−0.35, +4.20] — the wrong sign, with an interval
covering zero.** The oracle is *worse* than the model it is supposed to bound. On the raw surface
it looks perfect (0.10 s regret); that is entirely the winner's curse the pre-registration named in
advance, and the half-sample split removes it completely. Per the pre-declared rule, **the oracle
half of the acceptance criterion is reported as UNIDENTIFIED, not as a headroom number.**

The reason is not a defect in the construction. The realised cost surface carries lap-to-lap noise
that no forecast can or should chase; a policy fitted to it picks a lap that was lucky, and on an
independent half of the same stint that lap is not lucky. **There is no estimable oracle over this
surface at this data volume**, which is the same shape of answer `11a` got about per-circuit
conformal quantiles, arrived at along a completely different route.

And the number that ought to have settled the item settles it the other way: **every DP arm loses to
the human calls it was built to grade, by 4.10 s/stint out of sample** [−5.76, −2.58].

#### The stochastic arm does not pay for itself

`int_sc_hazard_history`'s first use as a decision input. A caution is available in **31.7%** of test
stints (0.380 usable gaps per stint at a hazard of 0.0243/lap). The hazard term changes **37–50%**
of calls and pushes them **0.59–1.09 laps later** on average. Held-out cost of switching the hazard
**off**:

| arm | stochastic | deterministic | deterministic − stochastic |
| :--- | ---: | ---: | ---: |
| seed | 12.91 | 11.90 | **−1.01** [−1.72 – −0.45] |
| model, no drift | 9.63 | 9.39 | −0.23 [−0.58 – +0.06] |
| shadow | 9.32 | 9.08 | −0.24 [−0.56 – +0.00] |
| oracle | 11.52 | 12.08 | +0.56 [+0.32 – +0.84] |

**A flat per-lap hazard of 0.024 and a 50% pit-loss multiplier buy a systematically later stop that
is on average wrong.** It costs the seed arm a full second per stint and is neutral on the model
arms. The published yellow-flag extension is implemented and it does not earn its place on this
substrate; a hazard with a lap axis (cautions cluster at starts, restarts and late-race) might, and
that is not what the table holds.

#### The extrapolation policy dominates everything else in the study

Test half, same arms, only the rule for extending δ past the age a tyre reached:

| arm | `flat` (pre-declared) | `persist` (last-3-lap slope) |
| :--- | ---: | ---: |
| seed | 12.91 | 75.72 |
| shadow | 9.32 | 43.85 |
| human | 5.22 | 69.19 |
| shadow, ±2-lap reproduction | 52.98% | 20.27% |

Compounding a noisy three-lap slope over ~20 unobserved laps inflates every regret **4–7×** and
collapses reproduction. Restricting the search radius instead (±5 / ±10 laps about the realised
call) shrinks every regret and leaves the ordering intact — shadow 5.45 / 7.57 s, human 3.38 /
4.36 s — with the human still best.

**A headline metric that moves by 40 seconds on a choice made inside the harness, when the quantity
being measured is worth 3.6 seconds, is not reporting on the model.**

#### The pre-registered e-values, reported whatever their value

Test half, 46 races.

| hypothesis | statistic | E |
| :--- | :--- | ---: |
| E1 — v11 forecast beats the seed surface (in-sample) | 38/46 races = 82.6% | **1,996** |
| E3 — shadow forecast beats the seed surface (out of sample) | 37/46 races = 80.4% | **1,010** |
| E2 — the DP's call carries information about the realised call | 53.70% at ±2; **0 of 999** permutations reached it | **1,000** (cap) |

All three exceed their declared ceiling of ~8, because the realised win rate (0.83 / 0.80) came in
far above the declared alternative (0.65) — the opposite of `11a`, where the declared power was the
binding constraint. Three hypotheses join the campaign e-BH family; the campaign-level decision
belongs to `04c`/`09b` and is not made here.

**Note what these do and do not license.** E1/E3 say the ML forecast improves the induced policy
over the seed-only surface. E2 says the DP's call is not independent of the realised call. **Neither
tests the quantity the item's acceptance criterion asked for** — the model-vs-oracle gap — because
that quantity is not identified, and no e-value can rescue a statistic with no reference point.

#### Verdict on the induced-policy metric

**Do not adopt the seconds gap as a headline beside pinball/CRPS.** Six reasons, in order of how
hard they are to fix:

1. **No reference point.** The oracle is +1.90 s [−0.35, +4.20] *worse* than the model on held-out
   data. A headroom metric without an estimable ceiling is not a headroom metric.
2. **Dominated by the harness.** `flat` → `persist` moves every arm 4–7×; the ML forecast is worth
   3.6 s. The measurement is louder than the signal.
3. **It is not a DP over the models.** The running cost is a 438-row hand-seeded polynomial that
   over-charges degradation by ~0.14 s/lap, and the ML target is that polynomial's residual.
4. **Half the declared state is absent.** No compound action (`next_compound` is fixed to the
   realised choice) and no track-position transition kernel.
5. **It is not a rollout.** The model's δ path is a sequence of 5-lap-ahead forecasts made on the
   *realised* feature rows; a genuine DP standing at lap 1 has no features for lap 20. What is
   measured is forecast quality re-expressed in seconds, conditional on the realised path.
6. **It grades the strategists as worse than an argmin over a seed.** Every arm loses to the human
   by 4.10 s/stint. A metric whose verdict is that the entire 2023–24 field mis-times its stops is
   measuring surface misspecification.

**Adopt this instead, as a secondary diagnostic and not a headline: the ±2-lap reproduction rate
against the realised call, on the known-good subset, with a race-clustered interval.** It is
bounded, it needs no oracle, it is invariant to the extrapolation policy in the way the seconds are
not (it is the *radius* sweep it survives, not the `persist` sweep — state both), and it moves with
the model in the right direction and by a large amount: **33.9% → 53.0% out of sample**, exact
agreement **6.9% → 21.3%**. It is also readable by a strategist without a single caveat, which was
the original argument for a decision-layer metric.

#### Definition of done

- **The DP, assembled and runnable** — [`../implementations/11b/s2_dp.py`](../implementations/11b/s2_dp.py),
  backward induction over (lap, tyre age, caution) with the published yellow-flag extension, four
  interchangeable degradation arms, and both a stochastic and a deterministic solve.
- **A verdict on the induced-policy metric** — the section above. It is negative on the seconds gap
  and positive on the reproduction rate.
- **Nothing shipped.** No production artefact written, no refit, no ONNX re-export, warehouse opened
  read-only throughout.

#### Three things for a human, not decided here

1. **Should `int_pit_strategy_cost_curve` consume `mart_degradation_predictions`?** Worth **+3.59
   s/stint** [1.64–5.66] and **+19 points** of ±2-lap reproduction, out of sample. It is a change to
   a production dbt model and it makes an intermediate table depend on an ML artefact, which is a
   lineage direction this repo has not taken before.
2. **The seed compound curve over-charges by ~0.14 s/lap, and the degradation trio spends most of
   its signal undoing it.** Refitting `compound_cliff_params` would move the decision surface *and*
   the definition of `next_5_lap_cumulative_jump_s` — i.e. every degradation number in the tree. A
   foundations-level change with a blast radius across `08` and `02`, not a parallel-surfaces item.
3. **Three stale records.** `ml_headroom.md` #6 and R6 Part 3 both say `int_sc_hazard_history` is
   consumed by nothing (it is consumed by the cost curve); R6's table says the cost curve holds
   386,036 rows (414,289) and the hazard 36 (149, and keyed on season too). Amend, or leave and let
   this RESULT carry the correction?

#### Incidental verifications

- **`fct_lap_residuals` is a trap for caution flags.** It carries `is_safety_car_lap`, `is_vsc_lap`
  and `is_red_flag_lap`, and **all three are FALSE on all 137,447 rows** — the mart is already
  filtered to green racing laps. `int_stint_geometry` is the table with the real flags (162,729
  rows; 8,927 SC, 2,980 VSC, 426 red-flag). The first pass of this item read them from
  `fct_lap_residuals` and got a caution path that silently never fired.
- **`data/marts/mart_degradation_predictions.parquet` is current**, contrary to `11a`'s incidental
  finding: 137,447 rows, `model_version` v11, `predicted_at` 2026-09-16 07:10:33. It was regenerated
  at the start of this session and read, not rewritten.
- **`int_pit_strategy_value`'s window-scope argmin is exactly reproducible** from the cost curve —
  4,257/4,257. Anyone re-minimising at a different pit loss or a different hazard can do it off the
  published columns, as that model's header promises.
