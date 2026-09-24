# 10c Evaluation — competing-risks metrics, with the dependent-censoring caveat quantified

## Status

**MEASURED — 2026-09-18, on the `v12`/`08m` substrate.** Gates 1, 2 (substituted), 3 and 5 run;
4 and 7 are inapplicable and stated. 6 refits through `evaluate.py`'s own `_fit`, a 5-seed reseed
floor per metric and a 200-draw race-level cluster bootstrap. 64s. Nothing committed; nothing
written to `ml/models/`, to the warehouse or to `ml/artefacts/evaluation_metrics.json`.

**This replaces `10c`'s 2026-09-10 verdict**, which `10b` §10 had already ruled "doubly superseded
and must not be quoted": its AUC 0.844 / Brier 0.141 were in-sample (`10d`'s gate-1 finding) *and*
measured under the `10b` label, which `10b` rejected on 2026-09-18.

## The headline

> **On the tyre-limit set — stints that ended in a green-flag pit stop — the shipped v12
> configuration predicts the *realised* stint ending with IPCW-Brier 0.1904 and time-dependent AUC
> 0.6896, 95% [0.639, 0.734] over 24 eval races. Read instead as the *latent* tyre limit, the same
> model scores 0.1452 Brier, bracketed at [0.1367, 0.1729] across Kendall's τ ∈ [−0.5, +0.5] of
> dependence between safety-car arrival and tyre state, with the observable evidence pointing at
> the upper half of that bracket.**

**The finding underneath it.** The framing choice is worth **0.045** Brier and the dependence band
a further **0.036**. `10e`'s S1x — the largest model improvement this campaign has measured — was
**0.023**. Both of the choices this item exists to make explicit move the headline by more than any
model change group 10 produced.

## Contents

- `README.md` — this file
- `eval_10c_cause_specific_framework.json` — every framing, every τ, floors, bootstrap, anchors
- `eval_10c_cause_specific_framework.log` — the generation log, in order

Script: `scripts/eval_10c_cause_specific_framework.py`. Full working and the verdict:
[`../../work/10-competing-risks.md`](../../work/10-competing-risks.md) § 10c — Verdict.

## The three framings, which is the whole design

| | rows | events | censored | estimand |
| :--- | :--- | :--- | :--- | :--- |
| **F1** stratum | `stint_end_cause = green_pit` | all 9,149 | none | the **realised** green-pit ending, conditional on it having been one |
| **F2** cause-specific | all 19,973 eval laps | endings of cause `c` | every other ending | the **latent** cause-`c` limit |
| **F3** mixture | all 19,973 | whatever `standard` calls uncensored | the rest | diagnostic only — ruled out as a headline on 2026-09-10, ruling stands |

F1 buys freedom from censoring by conditioning on the outcome. F2 buys an unconditioned population
at the price of 54% censoring that is not independent. Neither is free.

## The band, and the three widths it is compared against

Clayton copula between the latent cause time and the censoring time, via the Rivest & Wells closed
form for the Zheng–Klein copula-graphic estimator. τ grid declared in the leaf doc before the
estimator existed.

| | point (τ=0) | dependence band | reseed floor | bootstrap 95% width | band ÷ floor | band ÷ boot |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **F2 green-pit IPCW-Brier** | 0.1452 | **0.0362** | 0.001839 | 0.0313 | **19.7×** | **1.16×** |
| F2 green-pit Uno AUC | 0.7882 | 0.0037 | 0.004633 | 0.0786 | 0.80× | 0.05× |
| F1 Brier / AUC / slope | 0.1904 / 0.6896 / 0.6736 | **0** | 0.0021 / 0.0060 / 0.0250 | 0.0331 / 0.0948 / 0.4796 | 0 | 0 |

**The level is dominated by the dependence assumption; the ranking is not.** The Brier band is 20×
refit noise and wider than the sampling noise on 24 races. The AUC band sits inside its own reseed
floor. Per the declared rule the Brier is reported as a band and the AUC's band is stated and
priced as immaterial at this sample size, not dropped.

## The caveat, measured

Kendall's τ between predicted median life and the observed censoring time:

| censoring population | n | τ̂ |
| :--- | ---: | ---: |
| all censoring | 10,824 | +0.1905 |
| **`sc_pit` / `vsc_pit` only** | 1,166 | **+0.2615** |
| administrative (`race_end` / `retirement`) | 9,639 | +0.2034 |

Safety-car censoring is more associated with predicted tyre state than administrative censoring is
— the caveat's own claim, in a number. It is an **observable** association, not the latent
dependence the copula parameterises, and it is contaminated by both quantities depending on the
race clock. It is good for **direction**: positive, nearest the +0.25 node, and the Brier rises
with τ, so **independence is the optimistic end of the plausible range**.

## D-calibration, and the result that answers the definition of done

`survival.py::d_calibration` was a binned calibration slope wearing that name. The real test —
Haider et al.'s Pearson goodness-of-fit on the transformed survival times — now exists as
`d_calibration_chisq`. Bin counts as a ratio to expected; a high bin means the stint ended earlier
than the model predicted:

| framing | χ²(9) | mean \|dev\|/exp | bin 1 → bin 10 |
| :--- | ---: | ---: | :--- |
| **F1** realised green-pit | 1066.6 | 0.252 | 0.22 · 0.89 · 0.90 · 0.87 · 0.92 · 0.95 · 1.09 · 1.30 · 1.33 · **1.55** |
| **F2** latent green-pit (τ=0) | 246.9 | 0.095 | **1.16** · 1.21 · 1.10 · 1.00 · 0.96 · 0.91 · 0.91 · 0.96 · 0.91 · 0.87 |
| F3 mixture *(diagnostic)* | 89.3 | 0.051 | 1.01 · 1.14 · 1.11 · 1.00 · 0.98 · 0.93 · 0.94 · 0.99 · 0.96 · 0.96 |

**The tilt reverses sign between framings.** Same model, same predictions: over-predicting against
the realised ending, under-predicting against the latent limit. A stint-life headline that does not
name its cause has not stated which sign its error has. The mixture is flattest of the three
because the two errors partly cancel — the original claim, in a new metric.

## What landed in the tree

- `ml/src/survival.py` — `copula_graphic_survival`, `step_eval`, `ipcw_brier_dependent`,
  `time_dependent_auc_ipcw`, `d_calibration_chisq`, `clayton_theta`. The existing `ipcw_brier`,
  `time_dependent_auc` and `d_calibration` are **untouched**, so every figure `10b`/`10d`/`10e`
  published is still produced by the code that produced it.
- `ml/tests/test_survival.py` — 13 new tests, 36 total, all passing. The load-bearing one asserts
  the copula-graphic estimator at τ = 0 **is** Kaplan–Meier with heavy ties, to 1e-12.
- `ml/src/evaluate_10c.py` — the live trap `10b` §10 flagged is closed: `--variant` defaulted to
  the rejected `10b` label and now defaults to `standard`, in the CLI and both function signatures.

## Nothing to land, and what is still open

There is no arm here and nothing proposes to move. What is open:

- **The dependence is bracketed, not identified.** Quantifying it needs an instrument for SC
  arrival — `02d` rebuilds `int_sc_hazard_history`, `07a` builds the instrument.
- **A τ-aware D-calibration does not exist.** F2's calibration row is a τ = 0 reading with no band.
- **A-calibration was not implemented** — its 2025 definition could not be verified from inside the
  run, and a calibration test built from a half-remembered description is worse than none.
- **No cause-specific *model* exists.** Every number scores the marginal `standard` fit against
  cause-specific estimands. `R3`'s option 1 has never been built.
