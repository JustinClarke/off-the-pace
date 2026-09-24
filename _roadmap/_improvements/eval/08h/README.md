# 08h Evaluation — `baseline_observations_n` as a feature

## Status

**MEASURED and REJECTED — 2026-09-17, on the `v12`/`08m` substrate.**

The column is **not** added to `FEATURE_COLUMNS`. The contract stays at **32** columns.
The rejection is pinned by a test (`ml/tests/test_features.py::test_baseline_observations_n_is_never_a_feature`)
so that a later session has to re-run the gate rather than re-add the column by edit.

## The Question

`08e` rebuilt `int_lap_thermal_proxy.stint_baseline_pace` as a trailing median of valid prior
laps and shipped `baseline_observations_n` into the mart contract, deliberately excluding it from
`FEATURE_COLUMNS`. That deferred an add-ablation gate: **does the model want this uncertainty?**

The column records how many valid prior laps informed each row's baseline (0–75, mean 12.5 over
the 137,447 mart rows; mean 13.4 over the 119,822 training-eligible rows). A lap-3 row's baseline
rests on two prior laps and a lap-30 row's on twenty; the model currently cannot tell those apart,
and that difference is exactly the uncertainty the `08e` rebuild introduced.

## Two corrections to the spec, made before running

1. **The contract is 32 columns, not 33.** The leaf doc's "33 → 34" predates `08j`, which pruned
   `cliff_candidate_flag`, and `08k`, which rebuilt the artefacts against the resulting
   32-feature contract. The arms below are **32 → 33**.
2. **The column has no NULLs.** The hazard text says "the NULLs are deterministic on
   count-of-valid-prior-laps". `baseline_observations_n` itself is non-NULL on all 137,447 mart
   rows — it is `0`, not NULL, where there is no evidence. The NULLs that are deterministic on it
   are `push_residual`'s and the three other thermal columns'. Verified directly: `push_residual`
   is NULL on **100.0%** of rows where the count is 0, in both train and eval.

## Hazard

The count is **not a contract axis** — `02a`'s declarability argument does not carry over. `02a`
could call its NULLs declarable because they were deterministic on `lap_number`, already in the
contract via `age_in_stint`. This count rises with safety cars and pit disruption, so it is
plausibly correlated with the outcome, and nothing in the contract declares it. Shipping the
count so a consumer can condition on the missingness is one thing; putting it in `X` makes the
model's behaviour depend on an axis nothing declares. That is the trade this item prices.

## Method

Add-ablation on `cv_final_fold` (train 2018–2023, eval 2024), 32 → 33 columns, through
`evaluate.py`'s own `_fit`/`_score`/`_predict_index` — not a reimplementation — against each
family's own 5-reseed floor from `attribution.py::refit_noise_floor`, with the permutation-null
arm. Run on all five production families.

Protocol, in `gates.md` numbering:

1. **Instrument check** — the 32-column baseline must reproduce the published `v12` headline.
   It does, on all five, to `0.00e+00`. (The earlier draft of this file wrongly called step 1
   "not applicable"; it applies, and it passes.)
2. **Add-ablation** — 32 vs 33 columns, identical split for every family.
3. **Floor** — `2*sqrt(2)*sd` over 5 reseeds (`RANDOM_STATE`..`RANDOM_STATE+4`), quoted against
   the **larger** of the baseline-arm and add-arm floor, the `08g` convention.
4. **Permutation null** — the candidate row-shuffled in train *and* eval, so capacity is
   preserved exactly and only the row alignment to the label is destroyed. Capacity
   (`shuffled − baseline`) and information (`real − shuffled`) reported separately.
7. **E-value** — Construction B (paired safe-t), `g = 1.0`, `n = 5`, on the **information**
   contrast (real vs its own per-seed shuffle), declared before the arm ran. Validity checked by
   pushing i.i.d. normal deltas through the implementation at four sigmas: mean `E` = 1.00 each
   time, as an e-value requires.

Deltas are oriented so **positive always means improvement**, on every metric.

### Two arms beyond the three the spec named

- **Negative control (shuffle vs shuffle).** Both sides are shuffles of the same column, so H0
  is true by construction and a large `E` would indict the harness rather than the data.
- **Reference arm: `push_residual` shuffled alone.** This is what makes the pair arm
  interpretable, and it is the correction to the first pass at this item. See below.

### The pair arm, and why the first pass misread it

The leaf doc asks for the column to be run **as a pair with `push_residual`**, to distinguish
"the model wants the uncertainty" from "the model wants another counter". `push_residual` is
already *in* the 32-column contract, so the pair arm is a **joint permutation-null** over
`{baseline_observations_n, push_residual}`.

A joint shuffle of those two destroys `push_residual` as well as the candidate — and
`push_residual` is an already-gated column carrying real signal (`08e` family T). So the pair
arm's raw `E` is mostly `push_residual`'s own information and says **nothing on its own** about
the candidate. The first pass at this item read a large pair-arm `E` as evidence that "the model
is exploiting the correlation between `baseline_observations_n` and `push_residual`". That
inference does not hold, and it is contradicted directly: the two columns' rank correlation is
**+0.07**.

The pair arm is only interpretable against the single-column arms, on common random numbers:

    synergy = info(pair) − info(candidate alone) − info(push_residual alone)

Synergy ≈ 0 means the two are **additive** — the count is a separate channel, not the
uncertainty qualifying the estimate. Synergy >> 0 would mean the model wants the count
*because* it qualifies `push_residual`, which is the reading that would have justified the
column. All three arms use the same permutation draw per seed, so the contrast is
common-random-numbers rather than three independent draws.

### The "another counter" test, asked directly

`attribution.py` carries the relevant prior: above `RANK_DEGENERATE_RHO = 0.99`, a tree sees the
same feature, because XGBoost splits on global thresholds and any globally-monotone relabelling
induces the same partitions. So the direct form of the "another counter" question is the rank
correlation between the candidate and every column already in `X`.

## Results

See [`MEASUREMENTS.md`](MEASUREMENTS.md) for the full tables. Headline:

- **0 of 5 families clear their own floor.** Best is p50 at **0.98×** — just under.
- **0 of 5 clear on information.** Best is `cliff_classifier` at **0.89×**.
- `stint_life_regressor`'s information delta is **negative**.
- **No synergy with `push_residual` on any family.** The pair arm's size is `push_residual`'s
  own signal.
- The candidate is **ρ = 0.97** with `lap_in_stint`, which is already in the contract.

## Definition of Done

> The column is either in `FEATURE_COLUMNS` with a delta that cleared its floor and was
> attributed to information by the permutation-null, or it is recorded as measured and rejected
> with the number, and the declarability hazard is ruled on either way.

Met by the second branch. The numbers are in `MEASUREMENTS.md`, the ruling on the hazard is
there and in the leaf doc, and the rejection is pinned by a test.

## Files

- `README.md` — this file
- `MEASUREMENTS.md` — the full per-family tables and the ruling
- `../../../ml/artefacts/08h_baseline_observations_n_arms.json` — every fit, floor, null and e-value
- `../../../ml/artefacts/08h_baseline_observations_n_arms.log` — generation log
- `../../../scripts/arms_08h_baseline_observations_n.py` — the arms, re-runnable
