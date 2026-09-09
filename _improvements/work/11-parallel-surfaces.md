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
