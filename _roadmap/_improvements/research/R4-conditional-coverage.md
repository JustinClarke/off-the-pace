# R4 — Uncertainty: the band is marginally calibrated and conditionally is not

**Track:** T4 · **Prices:** the app surface, `06`, and any claim made from the p10/p90 band
**Status:** DRAFTED, reconciled against `data/dev.duckdb` + `mart_degradation_predictions.parquet`

---

## What was measured, and the protocol it was measured under

`data/marts/mart_degradation_predictions.parquet` (v11, 137,447 rows) joined back to
`fct_cliff_prediction_features` on `lap_id`, restricted to rows with a non-null
`next_5_lap_cumulative_jump_s` and `is_training_eligible` (n = 82,315). Coverage of the
p10–p90 band, nominal 80%.

> **Protocol anchor — read this before quoting any number below.** `features.load_features`
> trains on `race_year < holdout_season`, and `resolve_holdout_season` returns
> `MAX(race_year)+1` = 2025, which is not ingested. So the production v11 boosters were fitted
> on **every season 2018–2024**, and `load_scoring_frame` then scores **every lap**. Every
> coverage figure here is therefore **in-sample**. It is not comparable to a `cv_final_fold`
> number and must never be diffed against one. Its use is one-directional: an in-sample
> conditional spread is a **lower bound** on the out-of-sample spread, so a gap that shows up
> here is real and will be wider honestly measured.

**Verified — marginal coverage is essentially perfect.**

| | value |
| :--- | ---: |
| pooled coverage | **80.38%** (nominal 80) |
| below p10 | 9.75% |
| above p90 | 9.88% |
| by season | 78.54% (2021) … 83.13% (2023) |

The tails are also symmetric, which is not automatic on a target with skew −0.83.

**Verified — and conditional coverage is not.**

| conditioning variable | groups | coverage range | spread |
| :--- | ---: | :--- | ---: |
| lap-in-stint band (1-5 / 6-10 / 11-20 / 21-30 / 31+) | 5 | 79.9% – 81.2% | **1.3 pts** |
| `cliff_onset_passed` | 2 | 80.3% – 80.8% | **0.5 pts** |
| compound | 8 | 73.9% – 86.7% | 12.8 pts |
| **circuit** (n ≥ 300) | **36** | **72.4% – 85.6%** | **13.2 pts** |

Worst circuits: Mexico 72.4%, Qatar 72.7%, Hungary 76.4%, Singapore 76.5%.
Best: Tuscan 85.6%, Brazil 84.7%, China 84.5%.

The compound spread is an artefact of small groups — HYPERSOFT n=295 at 73.9%, WET n=60 at
86.7%; the four compounds carrying 96% of the rows sit at 80.0–81.5%. **The circuit spread is
not**: those are 36 groups with n ≥ 300, at 13.2 points of dispersion, in-sample.

## The finding, stated precisely

> The degradation band's uncertainty model is **excellent along the axes the model was built
> to reason about** — tyre age, stint position, cliff state — and **wrong along circuit
> identity**. At Mexico an "80% interval" is a 72% interval. At Interlagos it is an 85%
> interval, i.e. needlessly wide.

That is a per-venue miscalibration of roughly ±6 points around nominal, and the app renders this
band as a confidence statement.

**Assumed** — that the mechanism is circuit-level heteroscedasticity the 33-feature contract
cannot express. `circuit_key` is deliberately excluded from `X` as an identifier, and the
contract reaches circuit identity only indirectly (through compound parameters, pit-loss and
corner-derived terms). Plausible, unproven; the alternative explanation — differing traffic and
deployment regimes per venue — is not excluded by anything measured here.

---

## What the literature offers

### 1. Mondrian / group-conditional conformal prediction — recommended, and cheap

Split conformal gives distribution-free **marginal** coverage; that is already fine here.
The **Mondrian** variant partitions the calibration set by a group function and computes a
separate conformal quantile per group, buying **group-conditional** coverage — which is exactly
the property that is missing ([MAPIE's write-up of the construction](https://mapie.readthedocs.io/en/v0.9.0/theoretical_description_mondrian.html)).

Applied here: **key the taxonomy on `circuit_key`.** With 36 groups at n ≥ 300 the per-group
calibration sets are an order of magnitude larger than the ~9 rows a 90% quantile needs, so the
construction is comfortably feasible on data that already exists.

Properties that matter for this repo specifically:

- **It does not touch the model.** No refit, no contract change, no re-tune, no ONNX re-export
  of the boosters. It is a post-hoc layer over the existing p10/p50/p90 outputs, so it cannot
  regress the headline and does not need `gates.md` step 1's six-decimal reproduction.
- **It composes with the existing quantile trio.** Conformalized Quantile Regression
  ([Romano, Patterson & Candès, NeurIPS 2019](https://arxiv.org/abs/1905.03222)) is specified
  over exactly this object: fitted conditional quantiles, conformalised by the calibration
  residual `max(q_lo − y, y − q_hi)`. The repo already produces the input CQR expects.
- **The guarantee is finite-sample and distribution-free**, which is a stronger epistemic
  object than anything else in the programme, and it costs one held-out split.

### 2. The exchangeability problem, which is real here

Conformal's guarantee needs exchangeability between calibration and test. Seasons are not
exchangeable — regulation eras, compound allocations and circuit calendars all move. Three
lines of work address this directly:

- [Conformal Prediction Beyond Exchangeability](https://www.stat.cmu.edu/~ryantibs/papers/nexcp.pdf)
  (Barber, Candès, Ramdas, Tibshirani) — weighted conformal with a coverage gap bounded by the
  total-variation drift, so the degradation under shift is *quantified* rather than assumed away.
- [Adaptive Conformal Inference under distribution shift](https://arxiv.org/pdf/2208.08401)
  (Gibbs & Candès) — online update of the target level; the natural fit if this is ever run
  race-by-race rather than as a batch recalibration.
- [Conformal Prediction with Conditional Guarantees](https://arxiv.org/pdf/2305.12616)
  (Gibbs, Cherian & Candès) — a general framework that recovers Mondrian as a special case and
  extends to overlapping/continuous covariate shifts, which is the more principled version if
  circuit turns out to be a proxy for something continuous.

### 3. What was checked and came back negative

**Quantile crossing is not an argument for a distributional model here.** The parquet shows
0 crossings in 137,447 rows on all three pairs — but that is **not evidence about the models**:
`predict.py:53` row-sorts the trio with `np.sort` before writing, and only logs a warning if the
raw rate exceeds 1% (`CROSSING_WARN_THRESHOLD`). The raw crossing rate is therefore **unmeasured
by this probe**, and the parquet cannot show it by construction. Recorded so that a later session
does not mistake the sort for a property. (If someone wants the real number it is one line in
`predict.py`'s log at write time.)

---

## Proposed promotion into `status/build-log.json`

A new item, `SPEC`, no dependencies — it is genuinely parallel to the ML ladder:

> **Mondrian-conformal recalibration of the degradation band, keyed on circuit.** Hold out a
> calibration split by season (or by race within season, stated explicitly); compute per-circuit
> conformal quantiles over the CQR score; report coverage marginally and per circuit, before and
> after, **out of sample** — the numbers above are in-sample and are the motivation, not the
> baseline. Report interval width alongside coverage, because a conformal fix that buys coverage
> by inflating Mexico's band to twice its width is a real cost the app pays.

Cost: 1–2 days. Nothing about the model changes; the deliverable is a calibration table and a
per-circuit offset the app can apply.

**One caution, pre-registered.** Circuit-conditional coverage measured on the same rows that
motivated the split is a garden-of-forking-paths problem — 36 groups were scanned and the two
worst reported. The out-of-sample re-measurement is the test; this document's table is the
hypothesis. See [R1](R1-instruments.md) on why the campaign has this failure mode structurally.
