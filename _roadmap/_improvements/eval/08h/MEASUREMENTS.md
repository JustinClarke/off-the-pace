# 08h Measurements — `baseline_observations_n` add-ablation

**Status: COMPLETE**
**Date: 2026-09-17**
**Substrate: `v12` / post-`08m` (the rebuilt target). Contract: 32 columns.**
**Decision: REJECT**

---

## Executive summary

`baseline_observations_n` does not meet the standing gate for addition to `FEATURE_COLUMNS`.

- **0 of 5 families clear their own 5-reseed floor.** The best is `p50` at **0.98×** — under it.
- **0 of 5 clear on information** once the permutation-null separates capacity from signal.
- `stint_life_regressor`'s information delta is **negative** (−0.38× floor), and its paired
  e-value points the wrong way.
- **No family shows synergy with `push_residual` that clears a floor.** The pair arm's apparent
  size is `push_residual`'s own information, not the candidate's.
- The column is **ρ = 0.97–0.98 with `lap_in_stint`**, which is already in the contract.

---

## Gate step 1 — instrument check

The prior draft called step 1 "not applicable". It applies: the 32-column baseline must reproduce
the published `v12` headline, or every delta measured against it is meaningless. It reproduces
**exactly**, on all five:

| family | published `v12` | 08h baseline(32) | \|diff\| |
| :--- | ---: | ---: | ---: |
| `degradation_regressor_p10` | 0.4764640778 | 0.4764640778 | 0.00e+00 |
| `degradation_regressor_p50` | 0.9823587336 | 0.9823587336 | 0.00e+00 |
| `degradation_regressor_p90` | 0.5128462338 | 0.5128462338 | 0.00e+00 |
| `cliff_classifier` | 0.3524660979 | 0.3524660979 | 0.00e+00 |
| `stint_life_regressor` | 1.9913358779 | 1.9913358779 | 0.00e+00 |

The whole suite was additionally run twice, from two independent invocations, and every
`real_by_seed` value matched bit-for-bit (`maxdiff = 0.00e+00`). The harness is deterministic
here, so the numbers below are reproducible rather than merely repeated.

---

## Gate steps 2–3 — add-ablation against each family's own floor

Positive delta always means improvement. Floor is `2*sqrt(2)*sd` over 5 reseeds, quoted against
the larger of the baseline-arm and add-arm floor (the `08g` convention).

| family | metric | baseline (32) | add (33) | delta | floor | floor ratio | clears |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :---: |
| `degradation_regressor_p10` | pinball | 0.476464 | 0.474687 | +0.001777 | 0.006343 | **0.28×** | NO |
| `degradation_regressor_p50` | pinball | 0.982359 | 0.971406 | +0.010953 | 0.011151 | **0.98×** | NO |
| `degradation_regressor_p90` | pinball | 0.512846 | 0.508681 | +0.004165 | 0.008395 | **0.50×** | NO |
| `cliff_classifier` | macro F1 | 0.352466 | 0.355676 | +0.003209 | 0.005083 | **0.63×** | NO |
| `stint_life_regressor` | AFT nloglik | 1.991336 | 1.991175 | +0.000161 | 0.006113 | **0.03×** | NO |

**0 of 5 clear.** Every delta points the right way, which is worth saying plainly — the column is
not harmful on the headline. It is simply smaller than the noise the refit already carries.

`p50` is the near miss at 0.98×, and it is the only family where anything below also leans
positive. It still does not clear, and a delta that lands one part in fifty under its own floor
is exactly the case the floor exists to refuse.

---

## Gate step 4 — permutation null: capacity vs information

The candidate is row-shuffled in train *and* eval, so capacity is preserved exactly and only the
row alignment to the label is destroyed.

| family | capacity | × floor | information | × floor | info clears |
| :--- | ---: | ---: | ---: | ---: | :---: |
| `degradation_regressor_p10` | +0.001331 | 0.21× | +0.000446 | **0.07×** | NO |
| `degradation_regressor_p50` | +0.005601 | 0.50× | +0.005352 | **0.48×** | NO |
| `degradation_regressor_p90` | +0.001224 | 0.15× | +0.002941 | **0.35×** | NO |
| `cliff_classifier` | −0.001302 | −0.26× | +0.004511 | **0.89×** | NO |
| `stint_life_regressor` | +0.002477 | 0.41× | **−0.002316** | **−0.38×** | NO |

**0 of 5 clear on information.** Two readings worth keeping:

- On `p10` and `p50` the capacity term is as large as, or larger than, the information term. A
  third column of anything gives the booster a little more room; that is not a reason to ship one.
- On `stint_life_regressor` the information term is **negative** while capacity is positive. The
  headline improvement on that family (+0.000161, 0.03× floor) is capacity, and the column's
  actual content makes that target slightly worse. Both numbers are inside the floor, so this is
  a direction, not a finding — but it is the opposite direction from the one that would justify
  the column.

---

## Gate step 7 — e-values, declared before the arms ran

Construction B (paired safe-t), `g = 1.0`, `n = 5`, on the **information** contrast (real vs its
own per-seed shuffle). Validity checked by pushing i.i.d. normal deltas through the
implementation: mean `E` = 1.0016 / 0.9992 / 1.0108 / 1.0014 at sigma 0.001 / 0.01 / 0.1 / 1.0.
Max attainable `E` at `n=5, g=1` is 36.0.

| family | E(information) | direction is improvement | negative control E |
| :--- | ---: | :---: | ---: |
| `degradation_regressor_p10` | 0.549 | yes | 1.249 |
| `degradation_regressor_p50` | **6.729** | yes | 0.521 |
| `degradation_regressor_p90` | 0.412 | yes | 1.017 |
| `cliff_classifier` | 0.851 | yes | 1.709 |
| `stint_life_regressor` | 2.414 | **no** | 0.416 |

The negative control shuffles *both* sides, so H0 is true by construction and a large `E` would
indict the harness. All five sit near 1. The harness is not manufacturing evidence.

`p50`'s `E = 6.729` is the one number in this item that looks like something. It is reported, and
it is counted in the campaign e-BH family whatever it is worth, per gate step 7. It does **not**
override step 3: `gates.md` is explicit that clearing the floor and returning a large `E` are two
instruments, and that a delta below the floor can still return `E > 1`. That is precisely this
case. `stint_life_regressor`'s `E = 2.414` is **directionally negative** — evidence against
exchangeability in the wrong direction — and is not evidence for the column.

---

## The pair arm with `push_residual`, and the correction to the first pass

The leaf doc asks for the column to be run as a pair with `push_residual`, because "a count of
evidence is only meaningful beside the estimate it qualifies". `push_residual` is already in the
32-column contract, so the pair arm is a joint permutation-null over both columns.

**The raw pair-arm `E` cannot answer the question.** Shuffling the pair destroys `push_residual`
too, and `push_residual` is an already-gated column carrying real signal. So the pair arm's size
is mostly `push_residual`'s. The reference arm — `push_residual` shuffled **alone**, on the same
permutation streams — is what makes it interpretable, and it was missing from the first pass:

| family | info(candidate) | info(`push_residual`) | sum of singles | info(pair) | synergy | × floor | E(pair) | E(`push_residual`) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | +0.000787 | +0.050047 | +0.050834 | +0.050961 | +0.000126 | 0.02× | 35.67 | **34.70** |
| `degradation_regressor_p50` | +0.006960 | +0.055799 | +0.062759 | +0.068317 | +0.005558 | 0.50× | 33.49 | **34.77** |
| `degradation_regressor_p90` | +0.000270 | +0.006865 | +0.007135 | +0.014007 | +0.006872 | 0.82× | 12.07 | **6.44** |
| `cliff_classifier` | +0.001968 | −0.001106 | +0.000862 | +0.001694 | +0.000831 | 0.16× | 0.72 | **0.47** |
| `stint_life_regressor` | −0.000945 | +0.000894 | −0.000051 | −0.000802 | −0.000751 | −0.12× | 0.45 | **0.48** |

Read the last two columns together. On `p10`, E(pair) = 35.67 and E(`push_residual` alone) =
34.70 — **the pair arm is `push_residual`**. On `p50` the pair arm is actually *weaker* than
`push_residual` alone (33.49 vs 34.77).

**This overturns the first pass's reading of this item.** That pass compared E(pair) against
E(candidate) — 35.67 vs 0.549 — and concluded the model was "exploiting the correlation between
`baseline_observations_n` and `push_residual`", calling it a correlation artifact on 3 of 5
families. That inference does not survive two checks:

1. The two columns' rank correlation is **+0.07** (Spearman; Pearson +0.009). There is almost no
   correlation to exploit.
2. The synergy is **positive** on four of five families. Positive synergy is complementarity —
   the pair carrying *more* than the sum of its parts — which is the **opposite** of the
   redundancy the artifact story requires.

The honest finding is the plainer one: **synergy does not clear a floor on any family.** The
largest is `p90` at 0.82×, then `p50` at 0.50×. So the pair arm answers the question the leaf doc
asked — the count is **not** acting as the uncertainty that qualifies `push_residual`; whatever
little it carries is a separate, additive channel — and it answers it without supporting the
column.

---

## "Another counter" — asked directly

`attribution.py` carries the relevant prior: above `RANK_DEGENERATE_RHO = 0.99` a tree sees the
same feature, because XGBoost splits on global thresholds and any globally-monotone relabelling
induces the same partitions.

| family (eval split) | max abs Spearman | against | ≥ 0.99? |
| :--- | ---: | :--- | :---: |
| `degradation_regressor_p10/p50/p90` | +0.9745 | `lap_in_stint` | no |
| `cliff_classifier` | +0.9789 | `lap_in_stint` | no |
| `stint_life_regressor` | +0.9801 | `lap_in_stint` | no |

Next-highest is `age_in_stint` (+0.964 to +0.970); everything else is below +0.63.

So the column is **not** formally rank-degenerate — it sits just under the threshold, and a tree
can still separate it from `lap_in_stint`. That matters, because it means the null result is a
real measurement and not a foregone conclusion: there *was* a distinguishable signal available
for the model to use, and it did not amount to anything above the floor.

**What the non-redundant part actually is.** `lap_in_stint − baseline_observations_n` is the
count of prior laps in the stint that were invalidated, plus a structural offset:

| gap | share | reading |
| ---: | ---: | :--- |
| 1 | 1.13% | — |
| 2 | **64.37%** | the structural case: lap 1 is an out-lap, and the current lap is not a prior lap |
| ≥ 3 | **34.50%** | at least one *extra* invalidated prior lap |

So on about a third of training-eligible rows the column carries something `lap_in_stint` does
not — and that something is "how disrupted was this stint", which is exactly the safety-car and
pit-disruption channel the hazard is about. The non-redundant part of this column **is** the
undeclared axis.

---

## Declarability — the ruling

`08e` named the hazard and this item has to rule on it either way.

**First, a correction.** The hazard is written as "the NULLs are deterministic on
count-of-valid-prior-laps". `baseline_observations_n` has **no NULLs** — 137,447 of 137,447 mart
rows are non-NULL; it is `0`, not NULL, where there is no evidence. The NULLs deterministic on it
are `push_residual`'s and the three other thermal columns'. Verified: `push_residual` is NULL on
**100.0%** of rows where the count is 0, in both train and eval. (One way only: 2.3% of train
rows with a non-zero count also have a NULL `push_residual`, because the *current* lap can be
invalid too. `transform/models/marts/schema.yml` says the thermal columns are "NULL exactly where
it is 0"; "exactly" overstates it, and that wording should be softened when the file is next
touched.)

That correction does **not** soften the hazard, because the hazard was never about a NULL
pattern. It is about the **axis**: putting the count in `X` makes the model's behaviour depend on
count-of-valid-prior-laps, which no contract column declares, and which rises with safety cars
and pit disruption — so it is plausibly correlated with the outcome. `02a` could call its own
NULLs declarable because they were deterministic on `lap_number`, already in the contract via
`age_in_stint`. That argument does not carry here.

**Ruling: the hazard is DECLINED, and the measurement makes that cheap rather than close.**

The trade has a specific shape now that it is measured:

- The part of the column that **is** declarable — its 0.97–0.98 rank correlation with
  `lap_in_stint` — is already in the contract, so shipping the column buys nothing there.
- The part that is **not** redundant is the ~34.5% of rows carrying extra invalidated laps, and
  that part **is** the undeclared, outcome-correlated axis.

So the declarable part is redundant and the non-redundant part is the hazardous part. There is no
split of this column that gives the model the uncertainty without also giving it the undeclared
axis. A gain large enough to justify taking that on might have changed the answer; the gain is
0 of 5 families above the floor. The hazard is declined on the numbers, not deferred again.

---

## Final decision

### REJECT — `baseline_observations_n` does not enter `FEATURE_COLUMNS`

The contract stays at **32** columns and `v12`. Nothing in the warehouse, the model artefacts or
`ml/src/schema.py` changes.

1. **Fails step 3** — 0 of 5 families clear their own reseed floor. Best 0.98× (`p50`).
2. **Fails step 4** — 0 of 5 clear on information; `stint_life_regressor` is negative.
3. **Step 7 reported, not decisive** — `p50` returns `E = 6.729` and is counted in the campaign
   family; `gates.md` is explicit that this does not override a delta inside its floor.
4. **The pair arm does not rescue it** — no family shows synergy with `push_residual` above its
   floor, so the count is not functioning as the uncertainty that qualifies the estimate.
5. **The hazard is declined** — the declarable part is redundant with `lap_in_stint`, the
   non-redundant part is the undeclared axis, and nothing in the measurement pays for it.

**The column stays in the mart.** That is not a consolation prize — it is the thing `08e` shipped
it for: the four thermal columns are NULL where it is 0, and a consumer needs it to condition on
that missingness. `08e`'s call to ship it and not feature it was correct, and is now measured
rather than assumed.

**Pinned.** `ml/tests/test_features.py::test_baseline_observations_n_is_never_a_feature` fails if
a later session adds the column without re-running this gate.

### Paths not taken

- Encode the missingness as an explicit indicator — a separate design decision, and the
  measurement gives no reason to open it.
- Run the gate on complete cases only — changes the mart row population, so it would not be
  comparable to anything else in the programme.
- Residualise the count against `lap_in_stint` and feature only the disruption remainder — this
  is the one variant with a real rationale, since it isolates the ~34.5% non-redundant part. It
  is also the variant that puts the **undeclared axis alone** into `X`, i.e. it maximises the
  hazard rather than avoiding it. Not run, and not recommended without a declarability answer
  first.

---

## Artefacts

- Script: `scripts/arms_08h_baseline_observations_n.py`
- JSON: `ml/artefacts/08h_baseline_observations_n_arms.json`
- Log: `ml/artefacts/08h_baseline_observations_n_arms.log`
- E-value validity check: passed (mean `E` ≈ 1.00 under H0 at all four sigmas)
- Negative control: passed (all five families near `E` = 1)
