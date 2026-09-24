# ML Headroom II — Taking the Audit to a Conclusion

Fourth document in the `_improvements/` series, and a direct continuation of
`ml_headroom.md`. That audit left three findings open (#1 cliff classes, #2 stint-life
censoring, #5 `tyre_allocations`) and named one experiment it could not get to converge.
This pass closes all four, corrects two of the audit's claims, and implements the change
that came out of it.

Measured against `data/dev.duckdb` on **2026-08-23**, working tree at the state
`transform_gaps.md` left it (all five phases in, uncommitted).

**Headline: finding #1 was diagnosed as a class-imbalance problem. It is not — it is a
label-definition defect, and fixing it is worth +16.6% macro-F1 with `6_plus` going from
dead to the best minority class.** The audit's own recommendation for #1 turned out to
have shipped in the first ML commit. Finding #2's blocked experiment converges once you
notice it was taking `log(0)`, and then wins on every fold.

> **Superseded as a tracker by `ml_execution_plan.md` (2026-08-23).** That file is the
> plan; this one is frozen as the evidence base. Do not add findings here. §6 is wrong
> and carries an appended correction; the rest stands as measured.

---

## Measurement harness

Same harness as `ml_headroom.md` — expanding-window season CV (train 2018…*k*−1, test
season *k*, six folds), XGBoost 300 trees / depth 6 / lr 0.08, `S.RANDOM_STATE`, the
project's own `S.FEATURE_COLUMNS` / `S.CATEGORICAL_COLUMNS` / `S.BOOLEAN_COLUMNS`
encodings, `is_training_eligible` only.

**Reproduction check, because two of this document's claims contradict the audit:**

| Run | this pass | `ml_headroom.md` |
| :--- | ---: | ---: |
| cliff classifier, no sample weights | 0.2844 | 0.2851 |
| cliff classifier, balanced sample weights | 0.3188 | 0.3197 |

Within 0.3%. The harness is the same harness. Where a number below disagrees with the
audit, it is not a harness difference.

Headline results are additionally re-run at the **production tuned hyperparameters**
(`ml/models/cliff_classifier_best_params.json`) and through the project's own
`ml/src/train.py`, so nothing here rests on the untuned setting alone.

---

## Findings, ranked

| # | Finding | Kind | Measured effect |
| :--- | :--- | :--- | :--- |
| 1 | `laps_until_cliff_class` never tests horizon 4, and `6_plus` means *exactly 6* | **defect — fixed** | **+16.6%** macro-F1 tuned; `6_plus` F1 0.045 → **0.321** |
| 2 | The audit's #1 recommendation (balanced class weights) shipped in the first ML commit | **correction** | the "+12.1% available" is already banked |
| 3 | `survival:aft` converges — the NaN was `log(0)` on 2,264 zero-life rows | **closes the open experiment** | **−18.0%** censored NLL, **+14.0%** C-index, 6/6 folds |
| 4 | The survival framing does **not** transfer to the cliff target | **closes a thread** | −15% macro-F1 against the repaired 4-class model |
| 5 | `tyre_allocations` carries **zero** information given circuit identity | **closes #5 as ML** | H(allocation \| circuit) = **0.000 bits** |
| 6 | The stint-life model has no user-facing app surface at all | **correction** | audit's stated blast radius for #2 does not exist |
| 7 | Four smaller items: NULL labels explained, a latent target defect, and two blind gates | **housekeeping** | see §7 |

---

## 1. The cliff label has a hole at 4 and a truncation at 6 — *fixed*

The audit read the dead `6_plus` class as class imbalance and label granularity. It is
neither. Read the label as it was written (`fct_cliff_prediction_features.sql`, pre-fix):

```
LEAD 1 > 1.0s  -> '0_to_2'
LEAD 2 > 1.0s  -> '0_to_2'
LEAD 3 > 1.0s  -> '3_to_5'
LEAD 5 > 1.0s  -> '3_to_5'      <- 4 is never tested
LEAD 6 > 1.0s  -> '6_plus'      <- and nothing past 6 is
otherwise      -> 'none_in_stint'
```

`6_plus` does not mean "six or more". It means **exactly six**. And a cliff whose first
crossing is four laps away is labelled `none_in_stint` unless it happens to still be
crossing at five.

Re-deriving the first crossing lap *k* over a 15-lap scan and cross-tabbing it against
the shipped class (training-eligible rows):

| first crossing at | `0_to_2` | `3_to_5` | `6_plus` | `none_in_stint` |
| :--- | ---: | ---: | ---: | ---: |
| k = 1 | 6,205 | | | |
| k = 2 | 3,912 | | | |
| k = 3 | | 3,146 | | |
| **k = 4** | | 599 | 164 | **1,710** |
| k = 5 | | 2,043 | | |
| k = 6 | | | 1,663 | |
| **k = 7…15** | | | | **6,260** |
| no crossing in 15 | | | | 80,598 |

Every row in the two bold cells is a real cliff labelled "no cliff in this stint". Over
the full stint horizon (not just 15 laps) that is **9,405 training rows on the wrong side
of a class boundary**, and it is why `6_plus` was unlearnable: nothing physical separates
"cliff in exactly 6 laps" from "cliff in 7 laps", and the second one was in the other
class.

**A third, smaller defect in the same expression.** `LEAD(k)` steps *k rows*, not *k
laps*, and `int_lap_residual_decomposed` drops laps. The row offset and the lap offset
diverge on 1.72% of steps at horizon 1, 4.86% at horizon 3 and **9.00% at horizon 6** —
so at the `6_plus` boundary, nearly one row in eleven was being tested at the wrong
horizon *and* detrended with the wrong `k × drift_s_per_lap`.

### The repair

Scan every remaining lap of the stint at true lap offsets, take the first crossing, and
bucket it the way the class names already promise:

```sql
cliff_scan AS (
    SELECT a.lap_id, MIN(f.lap_in_stint - a.lap_in_stint) AS laps_until_cliff
    FROM base AS a
    INNER JOIN base AS f
        ON  a.stint_id = f.stint_id
        AND a.lap_in_stint < f.lap_in_stint
        AND (f.driver_skill_residual_s - a.driver_skill_residual_s
             - (f.lap_in_stint - a.lap_in_stint) * a.drift_s_per_lap) > 1.0
    GROUP BY a.lap_id
)
```

Class support, training-eligible (NULL = last lap of a stint, unchanged at 6,664):

| Class | shipped | repaired |
| :--- | ---: | ---: |
| `none_in_stint` | 96,538 (79.8%) | 87,015 (72.0%) |
| `0_to_2` | 10,117 (8.4%) | 9,823 (8.1%) |
| `3_to_5` | 5,788 (4.8%) | 7,579 (6.3%) |
| `6_plus` | 1,827 (1.5%) | 9,853 (8.1%) |

### What it buys

Balanced class weights on both sides, because that is what production does (§2). Same
four classes, same metric, same rows — apples to apples.

| Run | shipped label | repaired label | change |
| :--- | ---: | ---: | ---: |
| harness, untuned | 0.3188 | 0.3737 | **+17.2%** |
| harness, production tuned params | 0.3273 | 0.3816 | **+16.6%** |
| `ml/src/train.py`, 5-fold, tuned | 0.3372 ¹ | 0.3888 | **+15.3%** |

¹ from the last recorded v4 training log, `2026-07-06`.

The repaired label wins in **6 of 6 folds** in both harness runs. Per-class on the final
fold at tuned params:

```
                    shipped                    repaired
              prec  recall     F1        prec  recall     F1
0_to_2       0.249   0.277  0.262       0.255   0.242  0.248
3_to_5       0.106   0.293  0.155       0.135   0.290  0.184
6_plus       0.026   0.165  0.045       0.236   0.502  0.321
none_in_stint 0.929  0.781  0.849       0.914   0.764  0.832
```

`6_plus` goes from **F1 0.045 to 0.321** — from the worst class on the page to the best
of the three cliff-window classes. That is the audit's finding #1, and it was never about
class weights.

**Implemented.** See §8.

---

## 2. Correction — balanced class weights are not headroom, they shipped in `555fbf2`

`ml_headroom.md` §1 recommends "take the balanced-weight change (+12.1%, same contract,
same four classes, no downstream schema change)" and sequences it first.

`ml/src/train.py::_sample_weight` has applied `compute_class_weight("balanced", …)` to
every classification target since **`555fbf2` — the commit that created the file**:

```python
def _sample_weight(spec: S.TargetSpec, y, meta=None) -> np.ndarray | None:
    if spec.kind == "classification":
        classes = np.unique(y)
        w = compute_class_weight("balanced", classes=classes, y=y)
        ...
```

The audit's harness did not pass sample weights, so its "current 4-class 0.2851" is an
*unweighted* baseline that production has never run. The production number is 0.3188
untuned / 0.3273 tuned. The +12.1% is real and already banked; there is nothing to take.

This also revises the audit's per-class table. It reports `6_plus` recall = 0.000 —
"never predicted, once, in a whole season". With the weights production actually uses,
`6_plus` recall is 0.165 at precision 0.026. Still worthless, but for the reason in §1,
not for the reason stated.

---

## 3. `survival:aft` converges — the NaN was `log(0)`

The audit: *"I attempted it in this pass and it returned NaN; the cause was not chased
down (likely the loss scale or the infinite upper bound)."*

It was neither. AFT fits in log space, and `remaining_stint_life_laps` is
`GREATEST(stint_length - lap_in_stint, 0)` — **2,264 training rows are exactly zero**
(the last lap of a stint, 1.87% of rows). `log(0) = -inf` on the first gradient step.
Shifting the label by one lap (`label_lower_bound = y + 1`, subtract 1 back at predict)
makes it converge on the first try. The infinite upper bound is fine; the scale matters
but is a tuning knob, not the blocker.

### Evaluating it honestly

RMSE against `remaining_stint_life_laps` cannot arbitrate this. On a censored row the
label is a *lower bound*, so RMSE rewards under-prediction exactly where the label is
wrong. Two metrics that do not have that defect:

* **profiled censored NLL** — read each model's prediction as a log-location
  `μᵢ = log(predᵢ + 1)`, give every model one free scale σ profiled on the test fold, and
  score the log-normal likelihood with the density on uncensored rows and the survival
  function on censored ones. Same functional form for every model.
* **Harrell C-index** — ranking only, censoring-aware by construction.

Censoring here is `tyre_changed = ends_with_pit OR a later stint exists`; its complement
is 2,525 of 6,911 stints and **44.6% of training rows**.

| Model | censored NLL ↓ | C-index ↑ | RMSE uncens. | coverage on censored |
| :--- | ---: | ---: | ---: | ---: |
| squared error (production framing) | 1.0903 | 0.6372 | 8.81 | 0.288 |
| squared error, uncensored rows only | **1.3319** | **0.5607** | **7.39** | 0.139 |
| AFT log-normal, scale 0.2 | 0.9541 | 0.6954 | 9.31 | 0.635 |
| AFT log-normal, scale 0.35 | 0.9151 | 0.7143 | 10.41 | 0.723 |
| **AFT log-normal, scale 0.5** | **0.8937** | **0.7263** | 12.52 | 0.801 |
| AFT log-normal, scale 0.75 | 0.9098 | 0.7337 | 19.82 | 0.870 |

AFT at scale ≈ 0.5 beats the production framing by **−18.0% censored NLL** and **+14.0%
C-index**, and it does so in **6 of 6 folds on both metrics** — no fold is carrying the
average.

**The bolded second row is the important one.** Training on uncensored stints only is the
variant `ml_headroom.md` reported as "+12.4% on the intra-race population" and called a
genuine gain at the question "when does this tyre die". Under metrics that can see
censoring it is the **worst model on the page** — worst NLL, worst ranking, coverage
0.139. Its good RMSE-on-uncensored is the selection effect measuring itself: uncensored
stints are the short ones, so a model fitted only to them under-predicts everywhere and
scores well on a metric built from the same biased sample. RMSE-on-uncensored is not a
neutral referee, and the audit's +12.4% should not be carried forward.

### Not implemented, and why

This changes the model contract, not just a number, and the ONNX gate is the real
obstacle. Probed directly:

* `onnxmltools.convert_xgboost` **accepts** an AFT booster — no conversion error.
* The exported graph emits the **raw margin**, not `predict()`'s `exp(margin)`. Measured
  over 500 rows: `onnx − log(bst) = 1.193147`, **std 4.5 × 10⁻⁷** — a constant offset.
* `exp(onnx − 1.193147)` restores parity inside the project's `ATOL/RTOL = 1e-5`.

So the gate is passable, but only by appending a two-node `Sub` + `Exp` post-transform at
export time (the constant is recoverable from a single row) or by applying it in
`predict.py` and `app/src/ml/verifyParity.ts`. That is a real piece of work on a model
with no user-facing consumer (§6), which is why it is written up here as the next change
rather than made in this pass.

---

## 4. The survival framing does not transfer to the cliff target (negative result)

`laps_until_cliff_class` is also a censored time-to-event target — `none_in_stint` is
just the censored bucket, and 25.9% of training rows have fewer than 6 laps left in the
stint, so `6_plus` is not even reachable for them. The obvious move after §3 is to fit
one AFT on the first-crossing lap and read the four class probabilities off the survival
curve, preserving the 4-column output contract exactly. **Measured, it loses.**

Evaluated on rows with ≥ 15 laps left, where all four buckets are fully observed over a
fixed 15-lap horizon and nothing in the metric depends on when the team pitted:

| Model | macro-F1 ↑ | log-loss ↓ |
| :--- | ---: | ---: |
| multiclass `multi:softprob` on the repaired label | **0.3704** | 1.1503 |
| AFT → bucket probabilities, scale 0.35 | 0.2918 | 2.5485 |
| AFT → bucket probabilities, scale 0.7 | 0.3331 | 1.3009 |
| AFT → bucket probabilities, scale 0.9 | 0.3329 | 1.1350 |
| AFT → bucket probabilities, scale 2.0 | 0.2566 | **0.9593** |

The scale was swept rather than fixed at one value, precisely so this negative result is
not the mistake §3 was. The trade is legible: AFT gets better *calibration* at wide
scales (log-loss 0.959 vs 1.150) and worse *discrimination* everywhere (macro-F1 never
reaches the multiclass model, and at the log-loss optimum it has collapsed to predicting
the base rate). Macro-F1 is this target's headline metric, so the multiclass model wins.

**Recommendation: close this thread.** The survival reframe is right for stint life and
wrong for the cliff class. Do not generalise §3 across the ML layer.

---

## 5. `tyre_allocations` carries zero information given circuit identity

The audit left #5 as an untested hypothesis with a real mechanism, gated on backfilling
2018–2022. It is testable without the backfill, on the seed's own 44 rows:

* 23 distinct circuits, and **every one of them has exactly one (hard, medium, soft)
  triple**.
* 21 circuits appear in both 2023 and 2024. **All 21 are identical year-on-year.**
* Only two triples exist in the whole seed: `C2/C3/C4` (36 races) and `C3/C4/C5` (8).

H(allocation) = **0.684 bits** per race. H(allocation | circuit_key) = **0.000 bits**.
The absolute compound code is a deterministic function of circuit identity on all
available evidence — and circuit identity is in the feature set three times over
(`track_energy_index`, `circuit_abrasiveness_index`, and the per-circuit-per-season
compound parameters).

That last one settles the mechanism the audit hypothesised. `dim_compounds_season` is
already fitted at **circuit_key × compound × season** — 403 cells across 37 circuit keys.
Pooling "by physical compound rather than weekend nomenclature" is pooling on strictly
less information than the fit already conditions on.

Two further facts for the housekeeping decision:

* The seed is **wide** (`season, circuit_key, hard_code, medium_code, soft_code`); the
  stub declares **long** (`race_year, circuit_key, compound_code, compound_label,
  allocated_sets_per_driver`). Wiring is a reshape, not a `ref()`.
* `allocated_sets_per_driver` — the one allocation column `ml_headroom.md` §3 actually
  tested (0.0% coverage) — **is not in the seed and cannot be filled from it**.

**Recommendation: #5 is closed as an ML question, with the same structural argument that
closed air density (audit #4) — a near-constant that circuit identity already encodes.
What remains is a half-hour housekeeping call: reshape the seed and narrow the stub's
comment to "2018–2022 not yet seeded", or delete the seed. Either is fine; leaving a
loaded seed beside a stub that declares it missing is not.** This is a user decision;
nothing was changed.

---

## 6. Correction — the stint-life model has no app surface

`ml_headroom.md` §2 closes with *"Why this reaches the app:
`predicted_remaining_stint_life_laps` surfaces in the `blind-test-scoreboard` feature. On
41% of its rows the model is being publicly scored on whether it predicted the chequered
flag."*

It is not scored, and it is not shown. Traced end to end:

* `app/src/features/blind-test-scoreboard/queries.ts` selects the column and types it on
  `ScoreboardRow`.
* `transform.ts` — which builds every panel the page renders — **never reads it**. Nor
  does `BlindTestScoreboardChart.tsx`, nor `page.tsx`. The only other match in the whole
  app is `app/src/ml/verifyParity.ts`, the ONNX parity checker.

So `stint_life_regressor` is trained, tuned, exported to ONNX, scored across every lap
into `mart_degradation_predictions`, carried through an app query — and rendered nowhere.
It is an orphan of exactly the kind this series keeps finding, one layer up from the dbt
leaves (`int_sc_hazard_history`, audit #6).

This does not make §3 wrong; the censoring defect is real and the fix is measured. It
changes the **sequencing**: repairing a model with no consumer sits behind repairing one
that four app features read, and the honest first move may be to decide whether
`stint_life_regressor` should have a surface at all.

### Correction, 2026-08-23 — this section is wrong. The model has a surface.

Appended rather than edited in place, because the way it went wrong is the useful part.

The trace above checked one of two consumers. `transform.ts` in `blind-test-scoreboard`
genuinely never reads the column, and that much stands. But the app has a second path
into the same prediction, and it does not go through any parquet query:

```
app/src/ml/infer.ts:29                     remaining_stint_life_laps on LapPrediction
  → degradation-simulator/transform.ts:219 remainingLifeLaps
  → DegradationSimulatorChart.tsx:391      <LifeGauge laps={...} />
```

`LifeGauge` (`DegradationSimulatorChart.tsx:166`) renders the value to one decimal
against a 40-lap bar with a red ≤3 / amber ≤8 / green colour band. The `verifyParity.ts`
match dismissed above as "the ONNX parity checker" was the visible edge of the ONNX
scoring path that feeds it, not a dead end.

So the model whose C-index is **0.637** and whose target is **44.6% censored** (§3) is
already on screen as a confident point estimate. Three consequences:

1. The open decision this section raised — *does `stint_life_regressor` get an app
   surface, or is it retired?* — is not a decision. The code already answered it.
2. §3 is not correctness-for-its-own-sake. It is a live user-facing repair, and it moves
   **ahead** of the pit-strategy rewrite rather than behind it.
3. The fix is bigger than §3 describes, because the gauge itself has to change: AFT
   yields a log-normal median, not the conditional mean over a censored mixture that
   `LifeGauge` currently renders, and the ONNX path needs the post-transform in §3
   applied in `infer.ts` as well as in `predict.py`.

**The method failure, stated plainly:** "rendered nowhere" was concluded from one
consumer's `transform.ts` plus a grep whose remaining hit was waved off. A column reached
through a typed ONNX inference struct does not appear in the same greps as a column
selected in SQL. Both entry points have to be walked before "nothing reads this" is a
claim rather than a guess. This is the second time in the series a finding has been
traced down one path and generalised.

Carried into `ml_execution_plan.md` as Corrections §1, and as its Phase 3.

---

## 7. Smaller items

**The 6,664 NULL cliff labels are explained.** The audit flagged them as unexplained and
"worth a look". They are the **last lap of a stint** — the row where there is no horizon
to scan. 6,664 of the 6,911 training-eligible stints have their final lap in the eligible
set; the other 247 lose it to the eligibility gate. Nothing is unaccounted for. The
repaired label preserves the count exactly.

**`next_3_lap_cumulative_jump_s` and `next_5_lap_cumulative_jump_s` are arithmetically
wrong.** Both are built as `Σ LEAD(residual, 1..k) − residual` — the sum of *k* future
residuals minus **one** copy of the current one. A cumulative jump over *k* laps is
`Σ (LEAD(residual, i) − residual) = Σ LEAD(residual, i) − k × residual`. Neither column
subtracts the per-stint drift either, unlike the primary target they sit beside. Both are
in `EXCLUDED_LEAKAGE_COLUMNS`, are not modelled targets, and have no consumer — so this
is latent, not live. **Left unfixed deliberately**: changing them moves the mart again for
zero measurable benefit. Recommend fixing them the next time the mart is touched, or
dropping them.

**`audit_forward_window` cannot see a self-join.** `ml/src/features.py` detects
forward-looking definitions by walking compiled SQL for `LEAD()` and `FOLLOWING` window
frames. The repaired label in §1 looks forward through a self-join on
`f.lap_in_stint > a.lap_in_stint`, which the audit does not model. It is correct here —
`laps_until_cliff_class` is a target, and targets are exempt — but the guard is now weaker
than it reads: a *feature* defined by a forward self-join would pass it silently. Worth a
follow-up on the audit's expression walker.

**The data-profile gate is blind to categorical distribution.** `laps_until_cliff_class`
was completely redefined in §1 — 9,405 rows changed class, `6_plus` grew 5× — and
`snapshot_data_profile.py --check` passed with **no drift across 15 tables**. Its baseline
for that column is `{"null_rate": 0.051613}`, and the null rate is unchanged by
construction. Categorical columns should carry a category-share vector, not just a null
rate.

**The docs had the cliff class balance inverted, and had for a long time.**
`docs/ml/overview.mdx`, `docs/ml/models.mdx` and `docs/ml/features-and-targets.mdx` all
described `6_plus` as the majority class at ≈58% and `none_in_stint` as ≈12%. On the same
denominator (labelled rows, which is what the classifier sees) the shipped reality was
`none_in_stint` **84.5%** and `6_plus` **1.6%** — the two classes the docs name are
swapped, and `models.mdx` even explained the balanced-weight scheme with "a rare
`0_to_2` lap carries several times the gradient of a common `6_plus` lap", which was
backwards. Corrected to the repaired distribution; `docs-facts` does not reconcile these
numbers, which is why they drifted unnoticed.

---

## 8. What was implemented

Only finding #1. Everything else on this page is a measurement, a correction, or a
user decision.

- [x] `transform/models/marts/fct_cliff_prediction_features.sql` — `cliff_horizon` +
      `cliff_scan` CTEs and a `with_cliff_class` wrapper; the fixed-LEAD `CASE` is gone.
      `sqlfluff lint` clean.
- [x] `transform/models/marts/schema.yml` — column description rewritten to state the
      partition property.
- [x] `transform/tests/assert_cliff_class_horizon_partition.sql` — **new singular test**.
      Re-derives the first crossing lap independently of the mart's own CTEs, so it fails
      if the definition drifts back to a fixed offset set, changes the 1.0s threshold, or
      drops the `k × drift` detrending. Registered in `transform/tests/README.md`.
- [x] Docs corrected: `docs/ml/overview.mdx`, `docs/ml/models.mdx`,
      `docs/ml/features-and-targets.mdx`, `docs/decomposition/tyre-cliff.mdx`.
      `scripts/build_reference.py` and `transform_docs_facts.py --write` re-run.

### Gates run

| Gate | Result |
| :--- | :--- |
| `sqlfluff lint` (model + new test) | clean |
| `dbt run --select fct_cliff_prediction_features --target dev` | PASS, 0.87s |
| `dbt test --target dev` (full) | **PASS=553 ERROR=0** |
| `dbt build --target ci` (fixtures, full) | **PASS=628 ERROR=0 SKIP=0** |
| byte-stability oracle | drift in **exactly one** model, `fct_cliff_prediction_features`; all other 6 `fct_*` byte-identical. Baseline re-snapshotted after verification. |
| `snapshot_data_profile.py --check` | no drift (see §7 — it cannot see this change) |
| `python -m ml.src.features --check` | forward-window CLEAN, leakage CLEAN, 42 features |
| `pytest ml/tests` | 25 passed, 3 skipped |
| `docs_audit.py --headers` / `docs_facts.py` / all four `*_docs_facts.py` | PASS |

Row count, column set and every non-label column verified identical to the pre-change
mart before the rebuild: 137,447 rows, 55 columns, and 0 rows differing on
`next_lap_degradation_jump_detrended_s`, `next_5_lap_cumulative_jump_s`,
`survival_weight` or `is_training_eligible`.

### Not done — needs a user decision

- [ ] **Retrain and re-export the cliff classifier.** A `cliff_classifier_relabel.bst`
      was written as a measurement (gitignored) and is **not** wired into anything; v4
      artefacts are untouched. Shipping the gain needs `ml-train → ml-onnx → ml-predict →
      ml-evaluate → ml-card`, which rewrites tracked `manifest.json` / `model_card.json`
      and the app's prediction parquet. Also worth re-tuning: the current best params were
      searched against the old label.
- [ ] **Re-tune, or accept the old params.** +16.6% is measured *at the old tuned params*,
      so it is a floor, not a ceiling.
- [ ] Nothing is committed. The user commits.

---

## Suggested sequencing

1. **Ship #1.** It is implemented and gated; what remains is the retrain/export cycle and
   a decision on re-tuning. Largest measured win on the page, no schema change, no app
   change.
2. **Decide `stint_life_regressor`'s future (§6) before doing §3.** If it stays without a
   surface, the AFT work is correctness-for-its-own-sake and belongs behind the pit-strategy
   rewrite (for contrast, the cliff classifier's outputs are read by two app features,
   `blind-test-scoreboard` and `model-metrics`). If it gets one, do §3 first — the
   current model's ranking is measurably poor (C-index 0.637) and would be shipped
   straight into a UI.
3. **`tyre_allocations` (§5).** Reshape-and-narrow or delete. Half an hour either way.
4. **Pit-strategy `Total_Cost(L)` rewrite.** Unchanged from `ml_headroom.md` — still the
   only item in the series that adds an app capability rather than repairing a number.
5. **The two blind gates (§7).** Category shares in the data profile; self-join detection
   in `audit_forward_window`. Both are small, and both would have caught something.

**Not recommended:** generalising the survival framing to the cliff target (§4); treating
the audit's balanced-weight recommendation as available headroom (§2); carrying forward
the "train on uncensored stints only, +12.4%" result (§3).

---

## Checkpoint

- 2026-08-23: Findings #1–#7 measured. **#1 implemented** in the working tree and gated
  (§8); the mart in `data/dev.duckdb` and the CI fixture warehouse are rebuilt, and the
  byte-stability baseline re-snapshotted after verifying the blast radius is one model.
  Nothing committed. #3 is measured and written up but deliberately **not** implemented —
  the ONNX post-transform is described in §3 and is the first thing to check when it is
  picked up. #4 and #5 are negative results, complete as written. #2 and #6 are
  corrections to `ml_headroom.md` and need no work beyond being read.
- Open decision for the user, blocking step 1: retrain at the existing tuned params, or
  re-tune against the repaired label first?
- Open decision for the user, blocking step 2: does `stint_life_regressor` get an app
  surface, or is it retired?
