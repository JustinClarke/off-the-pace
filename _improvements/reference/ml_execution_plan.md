# ML Layer — Consolidated Execution Plan

Fifth document in the `_improvements/` series. It folds `ml_headroom.md` (2026-08-22, six
findings) and `ml_headroom_ii.md` (2026-08-23, seven) into a single ordered tracker.

Neither of those is a plan. They are audits that end in *"suggested sequencing"*, they
disagree with each other in two places, and one of them is wrong in a third. **This file
is the plan; those two stay on disk as the evidence base.** Every measurement below is
cited, not restated — do not re-derive them.

Convention follows `PLAN.md` and `transform_gaps.md`: tick the checklist as work lands,
add a dated **Checkpoint** entry at each phase boundary, and write the **Handoff** block
before the session ends. That block is the resumption point.

**Standing rule: the agent never commits. The user commits.**

**Reopened 2026-08-24.** Phases 0-5 closed and the series was written up as complete. It is
not. A measurement pass over the *ceiling* rather than the model found that the trained
degradation target looked 82.5% irreducible noise, that the learning curves for two of three
families are flat, and that the highest-SNR target in the warehouse was built by Phase 4
and then never consumed. Those are Corrections §12-§17 and they open Phases 6-10. Nothing
in Phases 0-5 is retracted; what changes is what "good" was ever going to look like.

**Phase 6 closed the same day, and it corrected the measurement that opened Series II.**
The 82.5% was arrived at with a variance-of-group-means estimator that counts within-stint
scatter as between-stint signal; properly estimated the between-stint share is 2.9%, and the
degradation models score 12-28x past that ceiling — which they could only do by using the
within-stint variation §12 called noise. Corrections §18-§20 record that, and each one
corrects a number in §12 or §15 rather than a defect in the pipeline. **The lesson is one
level down from §12's: an anchor is itself a measurement and can be wrong.**

---

## Corrections

Twenty-seven things neither audit knows, all verified in the code. Each changes a phase. The
first three were found while writing this plan; **§4–§8 were found executing it** — §4
corrects this plan rather than an audit, and §5–§8 are defects in the pipeline itself.
**§12–§17 were found after the series closed**, by measuring what is attainable instead of
measuring the model, and they reopen it. **§18–§20 were found executing Phase 6**, and each
one corrects a number in §12 or §15 rather than a defect in the pipeline — the audits' last
three findings were arithmetic, not observation. **§21 answers open item 15**, which Phase 6
opened and could not close: it names what the within-stint signal actually is. **§22 was
found trying to act on §21** — it refuses item 16, the one action §21 proposed, and it is a
defect in how a measurement was read rather than in the measurement. **§23 was found
executing Phase 8**, and **§24–§26 were found executing Phase 2 finding 1 and Phase 7**:
§24 is the same defect the finding names, in a second place where it reaches print; §25 and
§26 are costs and premises of Phase 7 that the phase's own checklist did not carry; and §27
is what the retargeted ablation says about **Phase 9**, which had queued the wrong group for
deletion.

§12–§15 are one finding wearing four faces, and the phrase for it is *a denominator nobody
wrote down*. Every headline in this series is a ratio against a baseline and not one of
them is a ratio against what is reachable. Read against the attainable, these models are
strong. Read against 1.0, which is how the card reads, they are lukewarm. **A metric's
failure mode is not being wrong. It is being unanchored — and an unanchored number cannot
tell you whether to keep going or stop.**

§18–§20 are what happened when that denominator was finally computed, and the lesson is one
level down from §12's: **an anchor is itself a measurement and can be wrong.** All three of
§12's and §15's headline numbers — 17.5%, +0.719, 4.4× — turned out to be artefacts of the
estimator, the window and the worst case respectively. Every one of them was arrived at by
a reasonable-looking calculation nobody had a reason to doubt. Phase 6 therefore ships each
ceiling with a proof that it recovers a known answer on synthetic data, and publishes the
superseded estimate beside the corrected one so the correction stays visible.

§5, §6 and §8 are the same defect wearing three faces, and the phrase for it is *a gate
that cannot fail*. In each case something reported success while inspecting nothing: a
version nothing cross-checked, an audit that parsed zero models, a reconciler matching a
hardcoded literal. **The failure mode of a gate is silence, and silence reads exactly like
success.** Every gate added or repaired in Phase 4 carries a liveness assertion for that
reason.

**1. `ml_headroom_ii.md` §6 is wrong — `stint_life_regressor` has a live app surface.**
That section traced `predicted_remaining_stint_life_laps` through
`blind-test-scoreboard/queries.ts`, found `transform.ts` never reads it, and concluded the
model is rendered nowhere. It missed the second consumer entirely: the in-browser ONNX
path.

```
app/src/ml/infer.ts:29          remaining_stint_life_laps on LapPrediction
  → degradation-simulator/transform.ts:219   remainingLifeLaps
  → DegradationSimulatorChart.tsx:391        <LifeGauge laps={...} />
```

`LifeGauge` (same file, :166) renders the number to one decimal against a 40-lap bar with
a red ≤3 / amber ≤8 / green colour band. So the model whose C-index is **0.637** and whose
target is **44.6% censored** is already on screen as a confident point estimate. The
audit's open question — *"does `stint_life_regressor` get an app surface, or is it
retired?"* — is answered by the code: it has one. Phase 3 is a live user-facing repair,
not correctness-for-its-own-sake, and it moves ahead of the pit-strategy rewrite.

**2. `make ml-train` is not a production retrain.** `train.py` defaults `--version` to
`"v1"` (:161) and `train_one` falls back to `SMOKE_DEFAULTS` — 120 trees, depth 4, lr 0.1
— whenever `--params` is absent (:111). There is **no fallback to the per-target
`*_best_params.json`**. The Makefile target passes neither flag:

```make
ml-train:  ./.venv/bin/python -m ml.src.train --all
```

So `make ml-train` writes five untuned `*_v1.bst` files. The only Makefile path that
produces a production-parameterised booster is `ml-tune`, which chains
`train_one(version=…, params=study.best_params)` after a 50-trial search. **There is no
"retrain at existing tuned params" target.** Phase 1 either adds one or runs five explicit
invocations; it must not run `make ml-train`.

**3. The repaired label needs a version bump, and the bump costs all five models.**
`MODEL_VERSION_DEFAULT = "v4"` describes *"42-feature (+ surface_bulk_ratio), detrended
target (Route C)"*. Overwriting `cliff_classifier_v4.bst` in place makes "v4" name two
different target definitions, while `evaluation_metrics.json`, `model_card.json`, the
training logs and `ablation_cliff_classifier.parquet` all carry v4 numbers scored against
the broken label. `build_manifest(version, …)` carries **one version for all five
models**, so bumping to v5 means retraining the other four as well.

That cost is real but small, and it buys a free correctness check: the relabel moved no
feature column — `ml_headroom_ii.md` §8 reports every non-label column identical to the
pre-change mart — so **the four non-cliff models at v5 must score identically to v4.** Any drift there means
something moved that shouldn't have. It also keeps v4 on disk as a rollback, and gives
Phase 2's Optuna run a clean `cliff_classifier_v5.db` namespace
(`schema.optuna_study_name` keys off version).

**4. The free correctness check in §3 above does not exist — v4's numbers were scored on
a different mart.** Written into this plan on 2026-08-23 and disproved the same day, on
the first attempt to run it. The claim was that the four non-cliff models at v5 must
score identically to v4 because the relabel touched no feature column. The premise is
true; the conclusion does not follow, because *other* things moved between the v4
training run (`ml/models/training_logs/*_v4_20260706T*.json`, 2026-07-06) and now:

| | v4 log (2026-07-06) | current mart |
| :--- | ---: | ---: |
| deg / cliff training rows | 115,394 | 114,270 |
| stint-life training rows | 122,132 | 120,934 |
| feature fingerprint (deg / cliff) | `1a733633e1ce…` | `5df564ec571e…` |
| feature fingerprint (stint life) | `19ad14b320ae…` | `f697836d0108…` |

The fingerprint covers the encoded `X` matrix, the training season list and the feature
column names. No label enters it. So a changed fingerprint on the *degradation* target is
proof that feature content moved, and the relabel cannot be the cause: the working tree's
only uncommitted SQL diff is `fct_cliff_prediction_features.sql`, and that diff touches
`laps_until_cliff_class` and nothing else (verified by reading it, not by trusting §8).
The mover is the committed work that landed after v4 was trained — `9d6b7d4` (compound
cliff fitting and survival analysis) and `bd0ce6b` (dirty-air-normalised pace) both sit
upstream of the mart.

Two consequences:

* **The numeric gate is deleted, not weakened.** "Identical to v4" was never runnable, and
  a v5-vs-v4 delta on the four non-cliff models measures four months of transform work,
  not the relabel. Record it as drift, do not read it as a bug signal.
* **What replaces it is stronger, because it is a proof rather than a test.** The relabel
  provably cannot reach the four non-cliff models: `laps_until_cliff_class` is not in
  `S.FEATURE_COLUMNS`, so it is not in `X`; and each non-cliff model's row filter is its
  own target's nullity (`features.py:170`, the L0-7 drop), never the label's. Confirmed in
  the data: the degradation and cliff targets select the *same* 114,270 rows because both
  are undefined only on a stint's last lap.

This is the third time in the series a claim has been carried one inference too far. The
plan's own **Handoff protocol §2** exists because of the first two.

**5. `make ml-onnx` had the same defect as `make ml-train`, and it was pointed at the
app.** Found in Phase 1, one step before running it. Corrections §2 caught `train.py`
defaulting `--version` to `"v1"`. It is not alone: `export_onnx.py:225` defaulted the same
way, while `predict.py`, `evaluate.py`, `card.py` and `tune.py` all default to
`S.MODEL_VERSION_DEFAULT`. The Makefile target passes no version:

```make
ml-onnx:  ./.venv/bin/python -m ml.src.export_onnx --all
```

So `make ml-onnx` as the checklist calls for would have converted the **v1** boosters,
written `manifest.json` with `"model_version": "v1"`, and — because `build_manifest` takes
`feature_order` from `S.FEATURE_COLUMNS` (42) rather than from the booster — published a
manifest describing a 42-feature contract in front of v1 models that do not have 42
features. `make app-models` copies by manifest version, so that ships. The parity gate
would not have caught it: `parity()` compares each `.bst` against its own `.onnx`, so v1
against v1 agrees perfectly.

Fixed at the root rather than in the Makefile: `--version` now defaults to
`S.MODEL_VERSION_DEFAULT`, matching the other four CLIs. CI is unaffected — `ml-ci.yml:142`
passes `--version smoke` explicitly.

**The pattern is worth naming.** Two of the five ML entry points defaulted to a version
constant that stopped being current three versions ago, and both were reachable from a
one-word `make` target documented in the pipeline docs. The reason neither showed up as a
failure is that every downstream check is *internally* consistent: v1 `.bst` matches v1
`.onnx`, and a manifest is valid JSON whatever version it names. **Nothing in the pipeline
compares the version it produced against the version the rest of the system expects.** A
gate for that belongs in Phase 4 with the other two blind gates.

**6. `audit_forward_window` had never inspected a single feature.** Found in Phase 4,
while extending it. The leakage spine's headline assertion is `audit_forward_window() == []`,
and it had been returning `[]` because it parsed nothing at all.

The walker reads `compiled_code` from `transform/target/manifest.json`, falling back to
`raw_code`. `compiled_code` is only populated by a command that *compiles* — `dbt run` /
`build` / `compile`; a `dbt parse` manifest leaves it null, and `make docs-coverage` runs
`dbt parse`. `raw_code` is Jinja (`{{ config(...) }}`, `{{ ref(...) }}`), sqlglot cannot
parse it, and `_alias_definitions` swallowed every failure in a bare `except: continue`.
Measured on the manifest as found:

| | |
| :--- | ---: |
| lineage models the walker parsed | **0 of 21** |
| features with any resolvable definition | **0 of 42** |
| violations reported | 0 — "CLEAN" |

An audit that resolves nothing returns exactly what an audit that resolves everything and
finds nothing returns. Three fixes, not one:

* `_model_sql` now falls back to the on-disk compiled file
  (`target/compiled/{package}/{original_file_path}`) before raw_code. 21 of 21 models
  parse, 42 of 42 features resolve, and the audit is **genuinely** clean — no leakage was
  ever shipped, which is luck, not process.
* Unparsed models and unresolved features are now **violations**, not silence. Coverage is
  asserted before the finding is trusted.
* A test (`test_forward_window_audit_actually_reads_the_lineage`) pins the coverage, so
  "CLEAN" cannot go hollow again.

This is the same shape as §5 and it is worth stating as a rule: **every gate needs a
liveness check, because the failure mode of a gate is silence, and silence is
indistinguishable from success.** Three more instances turned up in the same phase (§7,
§8).

**7. The telemetry window was not a total order, and it moved feature values between
builds.** Found in Phase 4 by an unexpected fingerprint change, chased rather than
assumed.

Rebuilding the mart moved the feature fingerprint (`5df564ec…` → `405816dd…`) after a
change that touched only target columns. Reverting the change and rebuilding gave a
*third* value (`210df1db…`), which acquits the edit and indicts the build. Diffing two
builds of identical SQL:

| feature | rows differing | max abs diff |
| :--- | ---: | ---: |
| `braking_point_drift_m` | 497 | 355 m |
| `mid_corner_speed_loss_kph` | 125 | 3.79 kph |
| `n_gear_changes` | 20 | 20 changes |
| `lift_coast_share` | 16 | 0.034 |
| `short_shift_index` | 18 | 0.173 |
| `traction_wheelspin_proxy` | 5 | 0.25 |

Not float noise. `int_lap_telemetry_aggregates` declared
`WINDOW w AS (PARTITION BY race_id, driver_id, lap_number ORDER BY distance_m)`, and
`distance_m` is not unique within a lap: **982,303 car-channel samples (1.6% of 59.5M)
share a `(race, driver, lap, distance_m)` key**, because a stationary or crawling car
keeps sampling at 10 Hz while distance does not advance — one tied block holds 19,754
rows at a single distance, and 5,318 laps are affected. `LAG`/`LEAD` therefore picked an
arbitrary neighbour, and the choice moved with DuckDB's scan parallelism.

Fixed by projecting the FastF1 `SessionTime` sample clock into `stg_telemetry` as
`session_time_s` and ordering on `(distance_m, session_time_s)` — verified unique across
all 59.5M car samples with zero nulls. After the fix, two consecutive builds differ only
in `mid_corner_speed_loss_kph`, `throttle_trace_decay` and `braking_point_drift_m` by
≤9.1e-13, which is the non-associative float aggregation the `ci` profile pins away with
`settings: threads: 1` and the `dev` profile (`threads: 4`) does not.

Two things follow.

* **The CI fixtures cannot catch this class.** The byte oracle flagged
  `fct_cliff_prediction_features`, `stg_telemetry` and `stg_weather` on the ci target and
  did *not* flag `int_lap_telemetry_aggregates` — the fixture slice contains no tied
  distances. The bug was only ever visible on real data.
* **The fingerprint is a determinism proof only under the ci profile.** `_fingerprint`'s
  docstring claims "deterministic across runs/machines". On a dev build it can flip on
  float-epsilon alone. Corrections §4 read a fingerprint change as proof that feature
  content moved; that conclusion still stands on its independent evidence (115,394 →
  114,270 training rows), but the fingerprint alone was never sufficient for it.

**8. Three documentation gates could not fail either.** Same shape as §5 and §6, found
while reconciling counts after the new tests landed.

* `docs_facts.py` hardcoded the *value* in every pattern — `\b(28)\s+tests?`,
  `\b(60)\s+models`. A reconciler that matches a literal can only ever confirm that one
  number. When the truth moved the pattern stopped matching, the fact silently dropped out
  of the report, and the run passed. This is exactly how README.md and
  `docs/ml/overview.mdx` came to agree with each other on **60 dbt models / 443 tests**
  while the generated inventory said **67 / 553** — the plan noted the discrepancy without
  knowing the mechanism. Patterns now capture `(\d+)` with context anchors, and each fact
  is reconciled against its **generated** snippet as the authority, not just against the
  other hand-written page.
* `ml_docs_facts.py` defined `live_pytest_count()` and **never called it**. The test
  taxonomy was a hardcoded table that nothing compared to pytest. Now wired in: the
  taxonomy must total what `pytest --collect-only` finds.
* `ml_docs_facts.py`'s AST reader matched `ast.Assign` only, while both constants it reads
  are annotated assignments (`FEATURE_GROUPS: dict[...] = {...}`) and one is wrapped in a
  `frozenset(...)` call. Both silently fell through to empty containers, so the docs had
  been shipping **"0 features in 0 groups"** and a leakage table with **zero rows** under
  the heading "Excluded (0 columns …)". Fixed, and the parser now refuses to emit a
  snippet built from an empty parse.

---

**9. Phase 3c's ONNX premise was wrong, and the constant was two constants added
together.** The plan said `convert_xgboost` "accepts an AFT booster but emits the raw
margin" and that `exp(onnx − 1.193147)` restores parity. Neither half holds.

`onnxmltools` dispatches on the booster's objective string and has **no case for
`survival:aft`**. Handed one it falls through to the classifier path and emits a
`TreeEnsembleClassifier` with a **LOGISTIC** post-transform and `label`/`probabilities`
outputs — a graph whose output is not the margin, not the prediction, and not even the
right shape. Scored naively it returns a constant `1.0` for every row.

The constant was a conflation. Measured, the classifier graph's `logit(p₁)` sits
`ln 2 = 0.693147` above the AFT margin, and `1.193147` is that plus the `0.5`
`base_score` — two different extraction points added together. The real relationship is
`margin = Σtrees + log(base_score)`, i.e. AFT applies **log** of the base score as its
intercept, which is where the `ln 2` comes from.

**Fixed by retagging, not by a magic number.** The export rewrites the saved booster's
objective to `reg:squarederror` and zeroes `base_score` *for conversion only* — the trees
are untouched — so the converter emits a plain `TreeEnsembleRegressor` with one output.
That leaves a fixed offset, which `_aft_margin_offset` recovers from a row (as the plan
asked) **and then proves is actually constant** across the parity sample before allowing
it to ship. A single row can only ever agree with itself; the spread check is what makes
it a calibration rather than a coincidence. Measured spread is 2.1e-6 on margins of
magnitude 4.1 — float32 tree-sum reordering — against a structural break of O(0.1)–O(10),
so the 1e-4 threshold can fail for a real reason and cannot fail for a fake one.

Verified across four scale/depth/round configurations before any production code was
touched: relative parity < 5e-6 in every one.

**10. `fct_stint_features` had 325 stints with a NULL `stint_number`, and nothing
noticed.** Found by the new censoring flag's own liveness assertion on its first run —
343 laps in 2018 that FastF1 never assigned to a stint, 338 of them already invalid.
DuckDB's `CONCAT` folds the NULL to `''`, so they collapse into one degenerate
`stint_id` per driver-race (`2018_2018_1_ALO_`). Only 5 rows reach the ML mart and **none
are training-eligible**, so the model is unaffected — but a bare `stint_number = MAX(...)`
comparison returned NULL for them, which is neither TRUE nor FALSE and would have dropped
those rows from every downstream join silently. The flag now uses
`COALESCE(stint_number, -1)`, which sorts an unassigned lap below every real stint and
keeps the flag a total partition. Two drivers (`2018_2` RIC, `2018_10` HAR) have no other
stint, so theirs is both first and last and is marked censored.

**11. "Carry pit loss into the optimal-pit-lap search" does not, on its own, make a longer
pit lane change anything.** The plan states Phase 5 as replacing the 0.5 s threshold with
the real argmin so that a longer pit lane pushes the optimum later. The first half is
right; the second does not follow from it. For one stop over a fixed horizon,

```
Total_Cost(L) = Sum_{a<=L} wear_old(a) + P + Sum_{u<=H-L} wear_new(u)
d/dL          = wear_old(L+1) - wear_new(H-L)
```

The pit loss `P` is paid once whichever lap you choose, so it adds a constant to every
candidate and **cancels out of the argmin exactly** — there is no `P` in the derivative.
A model that carried the empirical pit loss into a correct one-stop minimisation would
still give Monaco and Spa the same answer, and would still fail the test the phase asks
for. What makes pit-lane length matter is that the loss is not constant *in expectation*:
a stop taken under a safety car costs a fraction of a green-flag one, and each lap waited
raises the chance a caution has already appeared. Discounting `P` by
`1 - (1-m)(1 - (1-h)^L)` makes the pit term fall with `L` in proportion to its own size,
which is what gives a long pit lane a later optimum. This is why `int_sc_hazard_history`
belongs in Phase 5 as an input to the cost function rather than as a second model that
happens to get consumed there. Found while implementing the phase, by differencing the
cost function before writing it.

**12. 82.5% of the trained degradation target's variance is lap-to-lap scatter with no
detectable structure, and no document in this series says so.** Decomposing the target's
variance into a between-stint part and a within-stint part:

| Target column | n | sd | between-stint share | lag-1 autocorr in stint |
| :--- | ---: | ---: | ---: | ---: |
| `next_lap_degradation_jump_detrended_s` — **trained** | 130,353 | 1.132 | **17.5%** | **−0.094** |
| `next_3_lap_cumulative_jump_s` | 110,944 | — | 24.5% | — |
| `next_5_lap_cumulative_jump_s` | 95,346 | 7.560 | **37.3%** | **+0.719** |
| `next_lap_degradation_jump_s` — legacy, un-detrended | 130,353 | 1.140 | 24.2% | −0.084 |

A lag-1 autocorrelation of −0.094 is white noise with a trace of mean reversion. A
degradation *process* cannot look like that — tyre state on lap n+1 is very nearly tyre
state on lap n, which is exactly what the 5-lap column's +0.719 shows. What does look like
that is a measurement.

The first and third rows carry the argument jointly, and it is worth being precise about
how, because the obvious reading is too strong. **17.5% is the ceiling for stint-level structure only** —
a feature that is constant within a stint can reach no further than the between-stint
component, by construction. It is *not* a ceiling on the model, because **14 of the 34
numeric features vary substantially within a stint** (measured in the block below),
`push_residual` most of all at 12.9% between-stint, and those can in principle reach into
the other 82.5%.

What says they mostly cannot is the autocorrelation. Each of those per-lap features is
itself smooth in lap index, so if the within-stint part of the target held structure they
could reach, the target would autocorrelate positively. **It autocorrelates at −0.094**, and
the negative sign points at traffic, mistakes and recovery laps — noise, for this purpose.
The defensible statement is therefore not "the ceiling is R² ≈ 0.18". It is: **17.5% is
reachable by construction, the remainder is reachable only if it has structure, and the
autocorrelation says it has very little.**

The consequence is not that the models are bad. Pinball 0.199 against a 0.289 baseline is
capturing a large fraction of a small attainable quantity, which is a good result reported
against the wrong denominator. Phase 6 fixes the reporting; Phase 7 fixes the estimand.

The fourth row is its own finding. **C1's detrending removed 28% of the target's
between-stint variance** (24.2% → 17.5%), because the per-stint drift slope it subtracts
*is* per-stint degradation. Detrending is not the error — the 5-lap column subtracts drift
too and still lands at 37.3%. The error is detrending *at a one-lap horizon*, where
removing the trend leaves almost nothing but scatter behind.

**13. Phase 4 repaired the better target and shipped it as dead weight.** The audits filed
`next_3/5_lap_cumulative_jump_s` as "arithmetically wrong, latent, no consumer, left
unfixed". Phase 4 fixed all three defects properly — arithmetic, drift subtraction, and the
`LEAD` that stepped rows rather than laps — and verified the result against an independent
pandas recomputation at max |diff| 3.2e-14. Then it left the column with no consumer.

It is still listed only under `excluded_leakage` in the model card, correctly barred as a
*feature*, and never considered as a *target*. `DEGRADATION_TARGET` at `ml/src/schema.py:131`
is still the one-lap column. So the highest-SNR degradation target in the warehouse was
built, independently verified, and then not used — 17.5% attainable signal trained while
37.3% sat one identifier away. Phase 7 is a one-line change to that constant plus a retune.

**14. The learning curves are flat, which closes "ingest more seasons" as a route to better
numbers.** Straight from `ml/artefacts/evaluation_metrics.json`:

| n_train | cliff macro-F1 ↑ | p50 pinball ↓ | stint-life NLL ↓ |
| ---: | ---: | ---: | ---: |
| 14,137 | 0.3233 | 0.21409 | 2.1926 |
| 30,905 | 0.3863 | 0.20654 | 2.0939 |
| 43,972 | 0.3910 | 0.20434 | 2.0538 |
| 61,624 | 0.3919 | 0.20301 | 2.0061 |
| 77,478 | 0.4010 | 0.20094 | 1.9904 |
| 95,126 | 0.4038 | 0.19948 | **1.9397** |

The classifier is saturated after season two: 3.1× more data from 31k to 95k rows buys
+0.018 macro-F1. The p50 regressor moved 0.2141 → 0.1995 across 6.7× the data. **The 2025
holdout ingestion that D5/E1 and the card treat as the pending reveal will move these
numbers by approximately nothing**, and a 2010–2017 backfill would move them by less.

Two honest caveats. The curve varies *which* seasons train, not a random subsample, so it
confounds volume with era — flatness is still the right read, but it is not a clean
volume-only measurement. And **stint-life is the exception**: its largest single step is its
last (1.9904 → 1.9397), so that family alone is not obviously saturated.

2025 remains worth ingesting. It is the honest-holdout argument the card already makes, and
that argument does not depend on the numbers improving.

**15. The effective sample is 7,094 stints, not 137,447 laps.** `fct_cliff_prediction_features`
holds 137,447 rows over **7,094 stints**, 2,832 car-races, 147 races and 40 drivers. Laps
inside one stint share a compound, a car, a circuit, a fuel load and a driver; they are not
independent draws. Every interval in this series is computed at lap grain, so its standard
errors are understated by roughly √(137,447 / 7,094) ≈ **4.4×**.

Phase 2's checkpoint got this right in one place — it reported the tuned classifier beating
the floor by +0.75% at paired t=1.386, p=0.24, and declined to call it a win. That
discipline was never applied anywhere else. **No `beats_baseline: true` in the model card
carries an interval at all.** Some of those claims will survive re-cutting at stint grain.
Phase 6 exists to find out which.

**16. Six gigabytes of positional telemetry has two consumers, and both of them build a
static catalogue.** `data/bronze/telemetry` carries X, Y and Z alongside the car channels:
6.0 GB over 147 races, 17,827,996 rows in 2023 alone, X non-null on 100% of them, and ~369
position samples per lap per driver. Grep the warehouse for consumers and the answer is
`int_track_geometry.sql` and `dim_corners.sql` — both reduce it to a fixed corner catalogue,
neither reads it per-lap.

Every one of the 42 features derives from lap times plus speed / throttle / brake / RPM /
gear / DRS. **X/Y is a different sensor and it is the only unexploited one in the repo.**
That matters more than it sounds, because the ablation says the current features are largely
re-projections of each other: dropping the entire 7-feature `compound` group moves p50 by
0.0007 (0.3%), and dropping all four of `stint_position` moves it by 0.0032 (1.6%).
Collinear features do not add information, they add variance. Two things it unlocks:

* **True pairwise gaps.** `int_lap_air_state` takes dirty air from FastF1's
  `DistanceToDriverAhead` — one car only, and on the 2023 car channel 8.43% of samples have
  no `DriverAhead` at all while 10.22% read over 500 m, which is no car in any sense that
  matters. Dirty air is *already* the second-strongest ablation group (0.0079, 4.0%) **on
  that proxy**. From X/Y plus `session_time_s` the gap from every car to every other car is
  reconstructible at the position channel's native rate.
* **Racing-line deviation.** Lateral offset from a driver's own clean-air reference line,
  per corner, per lap. A tyre-limited car runs wide. This is not recoverable from a speed
  trace, and it is the closest thing in reach to a direct observation of the quantity the
  entire series is trying to infer.

Two ingestion gaps sit behind it. `_write_pos_data` and `_write_telemetry_full`
(`ingestion/src/ingest.py:483-484`) are gated behind `telemetry_full` and **have never run** —
both bronze directories hold zero files. And `ingest.py` accepts `R`, `Q`, `both` and nothing
else, so **practice has never been ingested**: FP2 long runs are the sport's purpose-built
degradation dataset, and per §14 they are the one source of extra rows that would raise SNR
rather than restate it. All of Phase 10.

**17. `race_control` is ingested for all 149 races and referenced by zero models.** 12,814
rows — 7,793 Flag, 3,935 Other, 457 Drs, 383 SafetyCar, 246 CarEvent. Within the flags: 4,909
BLUE, 617 YELLOW and 476 DOUBLE YELLOW carrying a `Sector` scope, 26 RED.
`grep -rn "race_control" transform/models/` returns nothing. There is no `stg_race_control`
and no model reads the source.

Meanwhile `event_flag_any`, the feature standing in for all of it, is one boolean per lap. A
sector-scoped timestamped yellow is strictly more information than a lap-level boolean, and
4,909 blue flags are a free, externally-generated label for exactly the traffic exposure
Phase 10a is trying to measure — one that does not come from the same telemetry it would be
validating. Not a phase of its own; it is the cheap half of Phase 10a's input.

**18. §12's 17.5% is the estimator, not the target. Properly measured it is 2.9% — and
the models clear it by 12–28×, so the between-stint decomposition does not bound them at
all.** Found by executing Phase 6, whose checklist says the ceiling "must compute the
ceiling per target properly rather than inheriting 17.5% as though it were exact."

§12 computed `var(per-stint means) / var(column)`. That estimator counts `σ²_w / n̄` of
pure within-stint scatter as between-stint signal, and at ~19 laps per stint that term is
~5% of total variance — most of the 17.5%. The one-way random-effects (ANOVA) estimator
removes it: `σ̂²_b = (MSB − MSW) / n₀`.

| Target column | naive (§12) | **ANOVA** | inflation | lag-1 in stint | overlap predicts |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `next_lap_degradation_jump_detrended_s` — trained | 0.1753 | **0.0289** | 6.07× | −0.0937 | 0.000 |
| `next_lap_degradation_jump_s` — legacy | 0.2419 | 0.0428 | 5.65× | −0.0844 | 0.000 |
| `next_3_lap_cumulative_jump_s` | 0.2451 | 0.1603 / **0.0776** ᶰ | — | +0.5279 | 0.667 |
| `next_5_lap_cumulative_jump_s` | 0.3733 | 0.2707 / **0.0645** ᶰ | — | +0.7187 | 0.800 |
| `laps_until_cliff_class` (Gini) | 0.2404 | **0.1952** | 1.23× | — | — |
| `remaining_stint_life_laps` | 0.2924 | **0.3005** | 0.97× | +0.9994 | — |

ᶰ non-overlapping: rolling windows share `h−1` of their `h` terms, so within-stint
residuals are dependent and ANOVA is biased up again. The thinned figure is the
load-bearing one for those columns; see §19.

The estimator is not asserted — on simulated clustered data at a **known** ICC of 0.03 it
returns 0.0304 while the naive one returns 0.0814
(`test_ceiling.py::test_anova_recovers_a_known_icc`, and its companion
`test_the_naive_estimator_is_the_one_that_was_wrong`).

**What follows is not "the models are worse than we thought".** It is the opposite, and
it is the finding of the phase. Anchored in the headline metric rather than in variance:

| Model | of attainable | in-sample exact optimum | verdict |
| :--- | ---: | ---: | :--- |
| `degradation_regressor_p10` | **28.2×** | 2.11× | not bounded by stint identity |
| `degradation_regressor_p50` | **20.5×** | 2.84× | not bounded by stint identity |
| `degradation_regressor_p90` | **11.8×** | 1.35× | not bounded by stint identity |
| `cliff_classifier` | **1.14×** | 1.14× | at / just past the stint-level ceiling |
| `stint_life_regressor` | **0.754** | — | 75.4% of an absolute bound |

The middle column is the one that carries weight, because it is a **proof and not an
estimate**: for a quantile target the per-stint empirical α-quantile is the *exact*
minimiser of pinball over all stint-constant predictors **on the very rows being scored**.
An out-of-sample model scoring below it has provably used within-stint information. p50
does, by 2.84×.

So §12's central claim — that 82.5% of the target is scatter the model cannot reach — is
**disproved by the models themselves**. Its own measurement block flagged this as "the
assumption to attack first" if Phase 7 underdelivered. It did not need Phase 7. The
defensible statement now is: *the between-stint share is 2.9%, the models operate almost
entirely inside the other 97.1%, and no ceiling has been established for the degradation
family.* Whether that within-stint signal is degradation or something else (traffic,
push, fuel-phase) is not settled here and `push_residual` — 12.9% between-stint, top SHAP
feature — is where to look.

**19. §12's autocorrelation evidence is a window-overlap artefact, in all three
directions.** §12 read `+0.719` on the 5-lap column as what a degradation *process* looks
like and `−0.094` on the 1-lap column as what a *measurement* looks like. But a rolling
sum over `h` laps shares `h−1` terms with its neighbour, so **white-noise increments alone
produce `(h−1)/h`** — 0.800 at h=5, 0.667 at h=3. Read against that baseline every column
sits *below* what pure noise would give: −0.094 vs 0.000, +0.528 vs 0.667, +0.719 vs
0.800. **None of the three shows positive autocorrelation beyond its own overlap.** The
prediction is verified on synthetic rolling sums of white noise
(`test_ceiling.py::test_lag1_of_a_rolling_sum_lands_near_the_overlap_prediction`), and
`S.TARGET_HORIZON_LAPS` now carries each column's horizon so the correction cannot be
lost when Phase 7 moves the target.

This does not sink Phase 7 — the SNR gain from averaging is mechanical and real, and
properly measured it is **0.0289 → 0.0645, a 2.2× gain**, which is coincidentally close to
the 2.1× the plan claimed from the naive numbers. What it removes is the *reason* the plan
gave. See the note added to Phase 7.

**20. §15's 4.4× is a worst case, and only one model is anywhere near it.** §15 derived
the understatement as `√(rows / stints) ≈ 4.4×`. That form assumes the scored quantity is
perfectly correlated inside a stint. The scored quantity is the **model-minus-baseline win
margin**, not the target, and the two are not equally clustered. Measured by bootstrapping
whole stints against bootstrapping laps, on the same eval fold:

| Model | measured widening | worst case | implied ρ of the margin |
| :--- | ---: | ---: | ---: |
| `degradation_regressor_p90` | 1.04× | 4.09× | 0.006 |
| `degradation_regressor_p10` | 1.26× | 4.09× | 0.037 |
| `degradation_regressor_p50` | 1.40× | 4.09× | 0.061 |
| `cliff_classifier` | 1.57× | 4.09× | 0.094 |
| `stint_life_regressor` | **3.71×** | 4.18× | **0.776** |

Stint life is the one §15 describes exactly, and for a comprehensible reason: its target is
`stint_length − lap_in_stint`, so the margin really is near-constant within a stint. For
the other four, 4.4× overstates by 3–4×. Both numbers are published per model rather than
one being asserted — that is the whole habit this phase is trying to install.

**21. About half the degradation model's within-stint signal is not tyre state.** Open item
15 asked what the models are reaching into the 97.1% *with*. §18 established that they do;
it could not say whether the variation they use is tyre degradation or traffic, driver push
or fuel phase. `ml/src/attribution.py` answers it, and the answer is mixed rather than
either of the two clean outcomes the item anticipated.

The existing ablation could never have answered it. Dropping `dirty_air` removes "this
stint ran in traffic" and "this lap ran in traffic" in one move, and those are precisely the
two readings in question. So each unit is measured **twice**: dropped, and **flattened** —
every feature replaced by its per-stint summary, which preserves the group's between-stint
information exactly and removes only its within-stint variation. The difference is the
quantity item 15 asked for.

`degradation_regressor_p50`, flattening each channel as one unit (pinball ↓, positive =
worse without it):

Adjudicated against a seed-only refit floor of **±0.00212** (5 reseeds of the unmodified
feature set, sd 0.00075, scaled by √2 for a difference of two fits and doubled):

| Channel | drop Δ | flatten Δ | within-stint share | clears floor? | of real within-stint signal |
| :--- | ---: | ---: | ---: | :---: | ---: |
| `tyre_age` | 0.04630 | 0.01944 | 42.0% | ✅ | **50.7%** |
| `driver_push` | 0.01338 | 0.01134 | 84.8% | ✅ | **29.6%** |
| `traffic` | 0.00795 | 0.00757 | **95.2%** | ✅ | **19.7%** |
| `fuel` | 0.00165 | 0.00102 | 62.0% | ✗ inside noise | — |
| `environment` | 0.00064 | 0.00007 | 10.8% | ✗ inside noise | — |
| `tyre_thermal` | 0.00379 | −0.00167 | −44.1% | ✗ inside noise | — |

Three things in that table are worth more than the headline:

* **Traffic is 95.2% within-stint.** Whatever `dirty_air` contributes, it is almost entirely
  the model learning *which laps* were spent behind a car — not which stints ran in traffic.
  The stint-level reading of that group is worth essentially nothing.
* **`push_residual` alone is worth 0.01079**, more than the entire traffic channel and the
  largest single-feature within-stint contribution in the set. It is also the top SHAP
  feature for p50. The model's strongest per-lap input is a driver-input residual.
* **`tyre_thermal` is not signal — but for p50 that is all that can be said.** Its flatten
  delta is negative (−0.00167), which would mean its within-stint variation actively *hurts*;
  it is **inside the noise floor**, so the honest reading is "contributes nothing measurable",
  not "hurts". The same group on the **classifier** is −0.01775 and clears the floor by 5×,
  which is where that finding actually lives — see below. Only **two** p50 features clear the
  floor individually: `push_residual` (0.01079) and `dirty_air_thermal_load_surface` (0.00293).
  The rest of the feature-level table is redundancy, not contribution: flattening `lap_in_stint`
  alone does nothing because `age_in_stint` still carries the ramp, which is exactly why the
  channel-as-unit pass is the load-bearing one and the per-feature rollup is marked indicative.

So roughly **half** the within-stint signal is the in-stint age ramp — genuine tyre-life
information — and roughly **half is driver push plus traffic**, which are not tyre state.
The degradation family is neither the tyre model the docs imply nor the traffic model §18
raised as the risk. It is both, in about equal measure, and no artefact said so.

**The classifier is a different and sharper finding: within-stint variation makes it worse.**
Against its own floor of ±0.00352, **`tyre_age` is the only channel with a real positive
contribution** (0.01090 — 100% of its real within-stint signal). `driver_push` is a real
**−0.00365**, and `tyre_thermal` a real **−0.01775** — flattening that one group improves
macro-F1 by 4.4% relative to the 0.4038 headline. Per feature, five clear the floor and four
of them are negative: `age_in_stint` −0.00967, `surface_bulk_ratio` −0.00599,
`traction_wheelspin_proxy` −0.00372, `is_rain_lap` −0.00369, against `anomaly_class` +0.00481.
Its prediction ICC is 0.2557 against a target ICC of 0.2178, i.e. it is very nearly as
stint-constant as the thing it predicts — the same fact §18 recorded as "1.14× the stint-level
ceiling", seen from the other side. **This is a free win sitting in the open**, and it belongs
to Phase 9 rather than Phase 8: several groups should be flattened or dropped, not retuned.

Note what did *not* survive here: the classifier's `traffic` channel reads 0.00247, **inside
its floor**. The traffic finding is a degradation-family result and does not generalise to the
classifier.

Every delta above carries a verdict against a measured refit floor, and three of the six p50
channels and four of the six classifier channels fall inside it. That is the point of shipping
the floor: on the first run this section was written from, `tyre_thermal` looked like a real
negative for p50 and the classifier's `traffic` channel looked like a real positive. Neither
survived. **The three load-bearing findings did** — traffic at 95.2% within-stint,
`push_residual` as the single largest per-lap contributor, and the classifier's negative
thermal delta are 3.6×, 5.1× and 5.0× their respective floors.

**22. Item 16 is not a free win. It is look-ahead, and it is refused.** §21 closed with the
classifier's thermal result written up as "a free win sitting in the open — no new data, no
new SQL and no retune of anything else", and the handoff sequenced it ahead of Phases 8 and
7 on exactly that basis. It is none of those things.

`stint_flatten` replaces a feature with its mean over laps **1..N** of the stint. For an
information measurement that is precisely correct: it removes within-stint variation and
touches nothing else, which is what makes `flatten_delta` interpretable. As a **feature** it
is inadmissible, because at row *t* it averages laps that had not run — and
`laps_until_cliff_class` is a statement about how the rest of the stint goes. Six arms on
the same split, the same tuned params and the same seed, reported as **change in macro-F1
(positive = better; §21's `flatten_delta` convention is the opposite sign)**:

| Arm | Summary window | Δ macro-F1 | × floor | Sees future laps |
| :--- | :--- | ---: | ---: | :--- |
| reference | — (raw per-lap) | 0.00000 | — | no |
| `causal_roll3` | trailing 3 laps | **−0.00202** | 0.57 | no |
| `causal_expand` | laps 1..t | **+0.00150** | 0.43 | no |
| `random_k` | *k* laps drawn from the whole stint, *k* = the prefix length at that row | +0.00680 | 1.93 | about half |
| `flatten_full` | laps 1..N — **§21's operation** | +0.01775 | 5.04 | all |
| `future_mean` | laps t..N | **+0.02015** | 5.72 | only future |

Reference reproduces the 0.4038 headline and `flatten_full` reproduces §21's 0.01775 to five
decimal places, so this is the same measurement, not a different one.

**The discriminator is `future_mean`.** Two things could make a full-stint mean beat a prefix
mean: it averages more laps (denoising), or it averages later ones (look-ahead). `random_k`
holds sample size at the causal arm's and lets the draw reach into the whole stint — it
recovers a third of the effect, so size is not it. `future_mean` averages **strictly fewer**
laps than `flatten_full`, every one of them at or after the row being scored, and it scores
**higher than the full-stint mean**. More future is better; more laps is not. The ingredient
is the future.

So the causal ceiling on item 16 is **+0.00150 against a ±0.00352 floor** — not a small win,
*no measurable win at all*. There is no feature that recovers the 0.0178, because the 0.0178
is not in the feature.

**What this corrects and what it leaves standing.** §21's classifier paragraph — "within-
stint variation makes it worse" — is the wrong reading of a right number. The right one is
that the classifier's flattened arm was handed a partly-forward-looking feature set and used
it, which is what a model does. Every **negative** flatten delta on the classifier
(`tyre_thermal` −0.01775, `driver_push` −0.00365, `age_in_stint` −0.00967,
`surface_bulk_ratio` −0.00599) is now suspect in the same way and none of them may be acted
on without its causal arm. The **positive** deltas are untouched and, if anything,
understated: a positive delta means the group's within-stint variation beat a flattened arm
that had a look-ahead advantage. §21's three load-bearing findings are all positives on p50
— traffic 95.2% within-stint, `push_residual` the largest single per-lap contributor, the
tyre-age ramp at 50.7% — and they survive as **lower bounds**.

**The lesson, and it is the third in a row of the same shape.** §12: a number without a
denominator cannot tell you whether to stop. §18: an anchor is itself a measurement and can
be wrong. §22: **a measurement is not an instruction.** `flatten_delta` answers "what does
the model use", the question item 15 asked, and it was read as answering "what should the
feature set be", which is a different question with a different admissibility rule. Nothing
was miscalculated. The number was carried one step past what it measures — which is how all
three of these happen.

**Through the production path, on every channel that cleared the floor.** The six arms above
were a scratch measurement; `make ml-attribution` now runs the causal and future arms itself,
and it reproduces them (deltas in the module's convention, where **positive = the model got
worse without it**, i.e. the opposite sign to the table above):

| Target | Channel | flatten | causal | future | reachable |
| :--- | :--- | ---: | ---: | ---: | :--- |
| classifier | `tyre_thermal` | −0.01775 | **−0.00150** | −0.02015 | **no** |
| classifier | `driver_push` | −0.00365 | **+0.00593** | −0.00483 | **no — and it flips** |
| classifier | `tyre_age` | +0.01090 | +0.00202 | +0.00277 | *verdict withheld* |
| p50 | `driver_push` | +0.01134 | **+0.01184** | +0.01012 | **yes** |
| p50 | `traffic` | +0.00757 | **+0.00606** | +0.00545 | **yes** |
| p50 | `tyre_age` | +0.01944 | +0.00132 | −0.00086 | *verdict withheld* |

**`driver_push` on the classifier does not merely fail to replicate — it reverses.** §21 read
its −0.00365 as within-stint variation hurting the model. Causally it is **+0.00593**, which
clears the floor in the *other* direction: removing driver push's per-lap variation from what
the classifier can see makes it worse. Item 17 asked for exactly this adjudication and gets it
for one of its four rows; the answer is not "unsupported" but "backwards".

**The causal arm has its own null, and it was checked before any of the above was believed.**
A `causal_delta` of zero has two readings — "the past supplies what the model was using" and
"the transform did not change the feature a tree can see" — and the second is the normal case
for a counter: `mean(1..t) = (t+1)/2` is a monotone relabelling of `t`, and XGBoost splits on
global thresholds, so it induces the same partitions. Spearman(raw, causal) on the 2024 eval
split, over the columns the transform actually changed:

| Channel | ρ range | Reading |
| :--- | :--- | :--- |
| `tyre_thermal` | 0.594 – 0.803 | a real change — **item 16's null is a real null** |
| `driver_push` | 0.483 – 0.987 | a real change |
| `traffic` | 0.596 – 0.810 | a real change |
| `tyre_age` | 0.991 – 0.999 | **a relabelling** — its causal arm is a near no-op |

So the one channel whose causal arm cannot be interpreted is `tyre_age`, and it is exactly the
row that would otherwise have read `causally_reachable: false` on a *positive* delta and been
taken for a second §22. `flatten_causality` now measures this and **withholds the verdict**
rather than reporting one, because a verdict read off an arithmetic zero is the artefact
stated as a finding. The number is still published; only the verdict is withheld.

**And the p50 channels came back the other way, which is worth more than item 16 was.**
`driver_push` flattens at +0.01134 and *causally* at **+0.01184**; `traffic` at +0.00757 and
+0.00606. Both clear the floor on both arms, in the same direction. Their within-stint
variation is not replaceable by any per-stint summary — not the full-stint one, and not the
one a scoring row could actually build. §21's two load-bearing p50 findings were written as
lower bounds; under a causal arm they are **confirmed**, not merely un-refuted.

**Guard, so it cannot recur silently.** `attribution.causal_stint_mean` /
`future_stint_mean` / `flatten_causality` land with this correction, and
`evaluate.within_stint_attribution` now runs both arms automatically for **every channel
result that clears the floor** — the only rows anyone would act on — writing
`causal_delta`, `future_delta`, `lookahead_share` and a `causally_reachable` verdict beside
the flatten. Ten tests cover the operators, including the one that matters: perturb the last
lap of every stint and assert no earlier row moves. A causal summary that fails that test is
look-ahead wearing a causal name.

**23. Phase 8's premise was right about the defect and wrong about the mechanism, and the
sign is the opposite of what the phase was written on.** The checklist says
`laps_until_cliff_class` "is a first-crossing scan over `int_compound_cliff_predicted`". It
is not. It is a first-crossing scan over `driver_skill_residual_s`, and the residual has
`expected_compound_pace_s` **subtracted** from it (`int_lap_residual_decomposed:307-315`).
The polynomial reaches the label through a minus sign, and that inverts everything the phase
predicted:

* The scan fires when the residual **rises** > 1.0 s over the horizon. An over-large wear
  term over-explains a future lap and **depresses** its residual, so the crossing that
  happened is not recorded.
* So the unbounded tail was **erasing cliffs into the majority class, not inventing them**.
  Re-derived under the bound, **6,825 rows (4.97%) change class and 6,793 of them — 99.5% —
  move out of `none_in_stint` into a real cliff class.** The minority classes gain 12.6%,
  25.3% and 23.8% of their row counts; `none_in_stint` loses 7.0%.
* That is the worst available direction for macro-F1: every error flowed into the class that
  already held 70% of the table, which is the direction that flatters accuracy while
  destroying minority-class recall.

Method, because the sign is the whole finding and a sign error here would invert the
conclusion. The re-derivation is a closed form — capping the wear term raises the residual by
exactly the excess — run against `data/dev.duckdb` and **validated by making the cap inert:
with the bound at 1e9 it reproduces the committed label on all 137,447 rows, 0 differences.**
Only then were the capped values read. The real dbt build afterwards matched the probe's
predicted per-class counts **exactly, on all five classes**.

**And Phase 8 is not the classifier-only phase its checklist describes.** The same subtraction
carries the bound into the *other* target: `next_lap_degradation_jump_detrended_s` moves on
**9.05% of rows** (max 9.08 s) and its sd falls 2.5321 → 2.4948. Phase 8's own note warns it
must not run concurrently with Phase 7 because "a joint move is unattributable" — but capping
at source moves both targets at once **within Phase 8**, and nothing in the plan said so. The
two arms have to be measured separately or neither is attributable.

**What the removed component was.** It is deterministic in (compound, circuit, season, age):
sd 0.348 s per lap, non-zero on 9.6% of rows, correlated **0.46 with `age_in_stint`** and
**0.04 with the repaired target**. An additive contaminant, largely predictable from a feature
the models already have, and carrying no information about the real quantity — so part of the
pre-Phase-8 headline was the models reproducing a SQL artefact. This also puts §21's "50.7%
tyre-age ramp" under a question it was not asked: that attribution was measured on the
contaminated target.

**24. Phase 2 finding 1 was in two places, and the second one is where it reaches print.**
The finding is filed against `tune.py`: the search fitted the quantile trio without the IPW
survival weights `train.py:_fit` applies, so p10/p50/p90 were selected against an objective
the refit does not use. Fixing it meant reading `train._fit`, and the same hole is in
**`evaluate.py:_fit`** — `T._sample_weight` returns the IPW vector only when handed `meta`,
and neither caller had one.

That second site is the consequential one. Every degradation number this series has
published — headline pinball, `beats_baseline` and its intervals, the ablation deltas, the
learning curves, §21's attribution, the attainable fractions — comes from a model refit
inside `evaluate.py`. **All of them describe an UNWEIGHTED model, while the boosters in
`ml/models/` are weighted.** The number in the card was never a measurement of the artefact
beside it.

Measured, by refitting both arms on identical rows and scoring identically (positive =
correcting the defect makes the reported pinball worse):

| target | p10 | p50 | p90 |
| :--- | ---: | ---: | ---: |
| 1-lap (`next_lap_degradation_jump_detrended_s`) | +0.15% | +0.45% | −0.22% |
| 5-lap (`next_5_lap_cumulative_jump_s`) | **+4.42%** | −0.19% | +0.51% |

The published v7 headlines (0.092406 / 0.199276 / 0.125624) are exactly the *unweighted*
column, which is how the site was found. **The size is small and the size is not the point:
a 0.45% error in a number is a rounding difference, and a number that describes a model
nobody trained is a category error.** Both sites now fit through one path, and
`evaluate._fit` raises rather than defaulting when a quantile fit arrives without weights —
a silent fallback is how this survived in the first place.

**A second-order question this opens and does not settle:** the fit is now weighted and the
metric is still unweighted, so the trio optimises a reweighted population and is scored on
the real one. If the IPW correction describes the population the product cares about, the
honest metric is weighted too. Changing it would move every published number and every
baseline comparison at once, so it is recorded here rather than taken.

**25. Phase 7 is not "one constant plus a retune" — it silently drops 28% of the training
rows, and drops them from the end of every stint.** `next_5_lap_cumulative_jump_s` is NULL
unless `LEAD(lap_in_stint, 5) = lap_in_stint + 5`, i.e. unless five *consecutive* laps follow
in the same stint. Training rows fall **114,274 → 82,315**. The loss is not uniform: it is
18.9% of laps 1-5, 28.7% at laps 11-15, and **50.4% at lap 31+** — the late-stint, high-
degradation regime the models exist for. By cliff class, `6_plus` keeps 90.7% of its rows and
`0_to_2` keeps 73.8%.

Isolated (same target, same eval rows, only the training population differs) that costs
**+0.76% pinball** on p50. Real, small, and previously unnamed.

It also **mis-specifies the IPW weights the phase inherits**. `survival_weight` is
`1/P(stint reaches this lap)`, clipped [0.25, 4]. The 5-lap target needs the stint to reach
`this lap + 5`, so the horizon-correct weight is `1/P(reach lap+5)` — on the training rows
that is on average **1.22× larger** (median 1.22, p95 1.53, max 2.92), and 14.7% of rows
would sit on the clip ceiling against 7.8% today. Phase 7 forbids SQL changes, so the trio
now trains under a weight that under-corrects for its own horizon. Not fixed; quantified.

**26. The between-stint shares Phase 7 was argued on no longer exist. Phase 8 drove the
1-lap target's to exactly zero.** The phase's surviving mechanical case was "averaging five
laps doubles the between-stint share, 0.0289 → 0.0645, a 2.2× gain" (§18). Re-measured on
the current warehouse, with the same estimator, after Phase 8's repair:

| column | h | between-stint share | naive |
| :--- | ---: | ---: | ---: |
| `next_lap_degradation_jump_detrended_s` | 1 | **0.00000** | 0.1516 |
| `next_3_lap_cumulative_jump_s` | 3 | 0.00427 | 0.1873 |
| `next_5_lap_cumulative_jump_s` | 5 | **0.00937** | 0.3270 |

The 0.0289 is gone: §23's bound moved the residual the target is built from, and the ANOVA
variance component for the 1-lap column is now negative-clamped to zero. This is not a
Phase 7 result — it is a Phase 8 side effect nobody measured, and it was already sitting in
the v7 report on disk (`attainable.variance.between_stint_share: 0.0`) unread.

**The direction of §18's claim survives and the arithmetic does not**: averaging still raises
the share, but from *nothing* to 0.0094 rather than doubling 0.0289. And it hands Phase 7 an
argument the phase was never written on: **with ICC = 0 the incumbent's analytic denominator
is degenerate** — `1 - sqrt(1 - 0) = 0`, so `fraction_of_attainable` is `null` for the
one-lap trio, and Phase 6's central apparatus has no denominator to report for the family it
was built to qualify. The 5-lap column has a non-degenerate one. That, and not the 2.2×, is
the measurable reason to prefer it.

**27. Phase 9 was about to drop the group that matters most. The ablation inverts on the
5-lap target.** Phase 9's checklist opens by quoting the group ablation and singling out
`compound` as the group contributing nothing — "−0.0007 (0.3%)" — with instructions to drop
groups whose delta falls inside the interval. Re-run against the retargeted p50, that ordering
does not survive:

| group | 1-lap Δ (share of headline) | 5-lap Δ (share of headline) |
| :--- | ---: | ---: |
| **compound** | +0.0025 (1.3%) | **+0.1968 (19.1%)** |
| stint_position | +0.0039 (2.0%) | +0.0973 (9.5%) |
| thermal | +0.0156 (7.8%) | +0.0949 (9.2%) |
| cliff_prior | +0.0134 (6.7%) | +0.0703 (6.8%) |
| dirty_air | +0.0083 (4.2%) | +0.0225 (2.2%) |
| powertrain | +0.0015 (0.8%) | +0.0101 (1.0%) |
| track | +0.0017 (0.8%) | +0.0043 (0.4%) |
| weather_air | +0.0008 (0.4%) | +0.0036 (0.3%) |
| telemetry_cliff | +0.0007 (0.4%) | −0.0002 (0.0%) |
| context | +0.0008 (0.4%) | −0.0038 (−0.4%) |

`compound` goes from tenth-of-a-percent noise to **the single largest group, 19.1% of the
headline** — a fifteen-fold change in share. `stint_position` nearly quintuples. `thermal` and
`cliff_prior` barely move, and `dirty_air` halves.

The story is coherent rather than surprising once stated: over one lap, degradation is
dominated by that lap's thermal and traffic state; over five, it is dominated by **which tyre
you are on and how far into the stint you are**, because those set the wear trajectory the
window integrates. It also sharpens §21 — the attribution that found the family "neither the
tyre model the docs imply nor the traffic model §18 flagged" was measured at h=1, and at h=5
the compound channel is an order of magnitude more of the answer.

**The operational point is the one Phase 9 needs**: its ordering was computed on a target that
no longer exists, and acting on it would have dropped the most valuable group in the set. The
phase's own dependency note ("depends on Phases 7 and 8, because the ablation has to be re-run
against the new target") was right, and this is what it was protecting against.

**A second result from the same run: Phase 6's primary denominator is restored.** §26 noted the
1-lap target's ICC of zero makes the analytic ceiling degenerate. Measured on both:

| model | analytic | cross-fitted | in-sample |
| :--- | ---: | ---: | ---: |
| p10 1-lap / 5-lap | **null** / 126.02 | **null** / 2.30 | 2.36 / 1.66 |
| p50 1-lap / 5-lap | **null** / 100.72 | **null** / 5.23 | 3.76 / 3.40 |
| p90 1-lap / 5-lap | **null** / 63.43 | **null** / 11.25 | 1.20 / 1.62 |

The 1-lap trio has exactly one usable denominator; the 5-lap trio has three. Phase 6 built the
attainable apparatus to stop headlines being reported against 1.0, and on the incumbent target
its **load-bearing** denominator has been `null` since Phase 8 without anyone reading the field.

---

## State of the two audits

| Src | # | Finding | State | Lands in |
| :--- | :--- | :--- | :--- | :--- |
| II | 1 | Cliff label: no horizon 4, `6_plus` means *exactly 6*; `LEAD` steps rows not laps | SQL **implemented + gated** in tree, models not retrained | **Phase 1** |
| II | 3 | `survival:aft` converges (`log(0)` was the NaN); −18.0% NLL, +14.0% C-index, 6/6 folds | measured, **not implemented** | **Phase 3** |
| I | 2 | Stint-life target 41% right-censored — two questions under one label | diagnosed; superseded by II §3 | **Phase 3** |
| I | 5 / II 5 | `tyre_allocations` seed loaded, read by nothing, contradicted by its own stub | closed as ML (0.000 bits); open as housekeeping | **Phase 4** |
| II | 7 | `next_3/5_lap_cumulative_jump_s` arithmetically wrong (`Σ LEAD − 1×residual`) | latent, no consumer, left unfixed | **Phase 4** |
| II | 7 | `audit_forward_window` cannot see a forward self-join | blind gate | **Phase 4** |
| II | 7 | Data-profile gate has no categorical distribution — 9,405 rows changed class, no drift | blind gate | **Phase 4** |
| I | — | `int_pit_strategy_value` argmin has no pit-loss term; `optimal` on 8 of 7,129 stints | carried from `transform_gaps.md`, untouched | **Phase 5** |
| I | 3 | 17 unused warehouse signals: −0.01% deg, −0.95% cliff | **negative result** | record, Phase 0 |
| I | 4 | Air density: −0.33% / +0.70%, inside harness noise | **negative result** | record, Phase 0 |
| II | 4 | Survival framing does not transfer to the cliff target (−15% macro-F1) | **negative result** | record, Phase 0 |
| II | 2 | Balanced class weights shipped in `555fbf2` — the audit's "+12.1% available" was banked | **correction**, no work | record, Phase 0 |
| II | 6 | "Stint-life has no app surface" | **wrong** — see Corrections §1 | record, Phase 0 |
| II | 7 | 6,664 NULL cliff labels = last lap of a stint | explained, nothing to do | record, Phase 0 |
| I | 6 | `int_sc_hazard_history` is a leaf | already documented; consumer is Phase 5 | — |

---

## Implementation Checklist (live — update as you go)

### Phase 0 — consolidate, correct, record (no code, no model)
- [x] This file becomes the tracker; `ml_headroom.md` / `ml_headroom_ii.md` get a one-line
      "superseded as a tracker by `ml_execution_plan.md`" note and are otherwise frozen
- [x] Add the §6 correction to `ml_headroom_ii.md` — do **not** silently edit the finding;
      append a dated correction so the reasoning trail survives
- [x] Record the three negative results where a future pass will trip over them, not only
      in `_improvements/`: `docs/ml/features-and-targets.mdx` (17 signals, air density),
      `docs/ml/models.mdx` (survival framing does not transfer to the cliff target)
- [x] Close the `DEFERRED` note at `ml/src/schema.py:72` with the air-density measurement.
      It currently reads as unrealised value; it is a closed negative result
- [x] Gate: `docs_audit.py --headers`, `docs_facts.py`, all four `*_docs_facts.py`

### Phase 1 — ship the repaired cliff label (v4 → v5)
Depends on nothing. The SQL is already in the working tree and fully gated
(`ml_headroom_ii.md` §8); what is missing is the model cycle.
- [x] **Decide the version bump.** Recommendation: v5. See Corrections §3
- [x] Add a Makefile target that retrains at existing tuned params — the gap in
      Corrections §2. Something like `ml-retrain: for t in $(TARGETS); do train.py
      --target $$t --version $(MODEL_VERSION) --params ml/models/$${t}_best_params.json`.
      **Do not run `make ml-train`**
- [x] `make ml-features` — feature contract still clean against the rebuilt mart
- [x] Retrain all five at their own `*_best_params.json`, version v5
- [x] ~~**Verification gate: the four non-cliff models must score identically to v4.**~~
      **Withdrawn — the premise was false. See Corrections §4.** v4 was scored on a mart
      that has since moved (115,394 → 114,270 training rows, feature fingerprint
      `1a733633e1ce…` → `5df564ec571e…`), from committed work upstream of the relabel.
      Replaced by the structural proof in §4: the label is not in `S.FEATURE_COLUMNS` and
      each non-cliff model's row filter is its own target's nullity, so the relabel
      provably cannot reach them. The v5-vs-v4 deltas below are that mart drift, recorded
      as a measurement and **not** read as a bug signal
- [x] **CV results, v5 at each target's existing tuned params** (2026-08-23):

      | Target | metric | v4 (2026-07-06) | v5 pre-§7 | v5 post-§7 | vs v4 |
      | :--- | :--- | ---: | ---: | ---: | ---: |
      | `cliff_classifier` | macro-F1 ↑ | 0.3372 | 0.3888 | **0.3889** | **+15.3%** |
      | `degradation_regressor_p10` | pinball ↓ | 0.1146 | 0.1069 | 0.1067 | −6.9% |
      | `degradation_regressor_p50` | pinball ↓ | 0.2293 | 0.2224 | 0.2224 | −3.0% |
      | `degradation_regressor_p90` | pinball ↓ | 0.1403 | 0.1398 | 0.1400 | −0.2% |
      | `stint_life_regressor` | RMSE ↓ | 7.3582 | 7.3262 | 7.3348 | −0.3% |

      **Restated 2026-08-23** with a third column, not overwritten. The `v5 pre-§7` column
      is what this phase measured on the mart as it stood; `v5 post-§7` is the same command
      re-run after Corrections §7's telemetry fix moved 6 features on 0.431% of training
      rows, and is what the artefacts in the tree now are. The five deltas between the two
      columns are +0.03%, −0.19%, −0.01%, +0.09% and +0.12% — the size a 0.431%-of-rows
      feature change should produce, and the reason this is recorded as drift rather than
      read as a signal. Phase 2's floor moves 0.3888 → **0.3889**.

      The cliff number is the one this phase exists for, and it lands on
      `ml_headroom_ii.md`'s prediction of ≈0.3888 to four decimal places — measured
      independently, at production params rather than the audit's harness params. The
      other four moved because the mart moved; all four moved in the right direction
- [x] `assert_cliff_class_horizon_partition` passes against the current warehouse
      (`dbt test --select assert_cliff_class_horizon_partition`, PASS in 0.13s). It
      re-derives the first crossing from `int_lap_residual_decomposed` +
      `int_lap_residual_stint_detrend` rather than reusing the mart's CTEs, so it is an
      independent check on the label the retrain just consumed
- [x] `make ml-evaluate` — all five beat baseline. Cliff eval macro-F1 **0.3964** vs prior
      **0.2241**; the CV number 0.3888 is the like-for-like comparison against v4's 0.3372
- [x] `make ml-predict` → 137,447 rows at v5, quantile crossing 0.31%
- [x] `make ml-onnx` — parity OK on all five (worst rel 6.21e-05 on p50, worst abs 2.29e-05
      on stint life, both inside the combined atol/rtol gate). **Required fixing
      `export_onnx.py` first — see Corrections §5**
- [x] `make ml-card`, `make ml-reference`, plus `ml_docs_facts.py --write` for the six
      inventory snippets, which the checklist did not list but which carry the metrics
- [x] `make ml-test` — 25 passed / 3 skipped, matching the stated baseline
- [x] `make app-models` (five v5 `.onnx` + manifest + card copied), `make app-data`
      (16 files changed: `_manifest.json`, `ml/mart_degradation_predictions`,
      `marts/mart_corner_skill_driver`, `marts/mart_degradation_history_envelope` — the
      last two are the committed transform work, not this label), `make app-parity`
      (**48 laps, maxAbs 1.049e-05, cliffMismatches 0**)
- [x] Checked the two real consumers by eye. **No hazard found, and the reason is
      structural rather than lucky:** every cliff-class lookup in the app is a
      `Record<CliffClass, …>` keyed by class *name* —
      `BlindTestScoreboardChart.tsx:24`, `degradation-simulator/transform.ts:164`,
      `DegradationSimulatorChart.tsx:23` and `:189`. Nothing indexes by position and
      nothing hardcodes a share. `CLIFF_CLASSES` in
      `blind-test-scoreboard/transform.ts:11` matches `S.CLIFF_CLASS_LABELS` element for
      element. The confusion-matrix cell colour is an alpha ramp on `cell.rowShare`
      (`BlindTestScoreboardChart.tsx:19`), i.e. *relative* to each row, so it rescales
      with the new distribution instead of saturating. `model-metrics` renders
      `model_card.json` at runtime and types nothing to a metric value.
      Belt and braces: 131 app unit tests pass across `src/ml`, both consumer features
      and `model-metrics`
- [x] Deleted `ml/models/cliff_classifier_relabel.bst`
- [x] Handoff written — see Checkpoint 2026-08-23 (Phase 1)
- [x] **Re-run in full after Phase 4 moved the mart** (option (a), 2026-08-23). Retrain →
      evaluate → predict → onnx → card → app-data → app-models → app-parity at the same
      tuned params, so the artefacts describe the mart beside them. CV table above restated
      with a third column; all gates re-run green. See Checkpoint 2026-08-23
      (mart-consistency retrain)

### Phase 2 — re-tune the cliff classifier against the repaired label
Depends on Phase 1 being **committed**, so a bad result is attributable to params alone.
Phase 1 was committed as `7f23d8c` on 2026-08-23; this phase ran against that baseline.
- [x] `python -m ml.src.tune --target cliff_classifier --version v5 --trials 50`
      (fresh study namespace; chains its own production refit). 50 trials, 32 complete /
      18 pruned, 137.18s refit
- [x] Compare against Phase 1's floor. +16.6% was measured at params searched against the
      *broken* label — it is a floor, not a ceiling. **Result: 0.391809 vs floor 0.388878,
      +0.75%.** Beats the floor, but see the checkpoint — the margin is inside fold noise
      (paired t=1.386, p=0.24, n=5) and the search stopped on a range boundary
- [x] Re-export, re-predict, re-card, re-parity; `best_params.json` is the only source diff
- [x] ~~If the tuned model does not beat the floor, keep Phase 1's and record why~~ — not
      exercised; it beat the floor. **Note the rule is not enforced by the tool:**
      `tune_one` writes `best_params.json` and chains `train_one` unconditionally, with no
      comparison against any floor. Keeping the incumbent is a manual `git restore` of
      `*_best_params.json` + the `.bst`, which is the reason the commit gate matters
- [x] Handoff written — see Checkpoint 2026-08-23 (Phase 2)

### Phase 3 — stint-life: survival model **and** the surface it feeds
Depends on Phase 1/2 landing (shared manifest version). Two halves; do not ship one alone.
- [x] **3a — decided: median + `[p10, p90]` band.** Not the survival curve. `SurvivalCurve.tsx`
      exists but does Kaplan–Meier over a *population* with censored-point scatter, not one
      parametric predicted curve, so reusing it was more work than the band, and the hero row's
      four cells are too cramped for a chart. The band is nearly free: log-normal AFT gives every
      quantile from one extra scalar. **The colour now keys off `p10`, not the median** — "how
      soon could this tyre be done" is the decision the colour is used for
- [x] **3b — the model.** `label_lower_bound = y + 1`, `survival:aft`, subtract 1 at predict.
      **Scale re-swept and it moved: 0.80, not ≈0.5.** Interior optimum (3.062 at 0.30, 2.237 at
      0.50, **2.0905 at 0.80**, 2.115 at 1.00); against 0.5 that is −6.54% NLL, 5/5 folds,
      paired t=10.254 p=0.0005. Unlike Phase 2's classifier this one is unambiguously separable
- [x] Evaluate on **censored NLL and C-index**, never pooled RMSE. `survival_report()` reports
      the two populations apart; `_score` **raises** rather than defaulting when a survival
      target arrives without censoring flags
- [x] **3c — the ONNX post-transform. The plan's premise here was wrong** — see Corrections §9.
      `convert_xgboost` does not emit the raw margin; handed an AFT booster it emits a
      **TreeEnsembleClassifier with a LOGISTIC post-transform**. Fixed by retagging the objective
      for export only. Offset recovered from a row *and proven constant* before it ships
- [x] `make app-parity`, `make app-e2e` — **run and green at v6** (2026-08-23). Parity 48 laps,
      maxAbs 3.228e-04, 0 cliff mismatches; e2e 5/5 including `onnx-inference`. Note the
      Makefile comment says "vs live CDN" but `.env.local` pins `VITE_DATA_BASE=""`, so the
      local run is **same-origin against the freshly built v6 artefacts** — which is what the
      chain needed. On CI, with no `.env.local`, this same target smokes the *CDN*, which is
      still v5 until someone publishes. The two runs answer different questions
- [x] **3d — `blind-test-scoreboard`: surfaced, split by censoring.** New `StintLifePanel`;
      censored laps are scored on whether the band reaches the observed bound, uncensored ones on
      containment, and no pooled number is shown
- [x] Handoff written — see Checkpoint 2026-08-23 (Phase 3, partial)

### Phase 4 — housekeeping and the blind gates
Independent of 1–3; can run in any gap. **Complete 2026-08-23** — see the Phase 4
checkpoint. What the phase actually found is recorded in Corrections §6–§8: three of the
items below were not the gaps the plan described but *symptoms* of gates that could not
fail, and one gate turned out never to have run at all.
- [x] **`tyre_allocations`: delete the seed.** `transform/seeds/tyre_allocations.csv`
      deleted (tracked since `305460c`, so recoverable). `stg_tyre_allocations` left
      honest as-is. Row removed from `transform/seeds/README.md`; the "update the seed"
      step removed from `transform/README.md`'s add-a-season runbook. CI seeds 7 instead
      of 8 with no change in results
- [x] `next_3_lap_cumulative_jump_s` / `next_5_lap_cumulative_jump_s` — **fixed, not
      dropped.** Three defects, not the one the audit named:
      1. the arithmetic (`Σ LEAD − 1×residual` → `Σ LEAD − k×residual − drift·k(k+1)/2`);
      2. no drift subtraction, so the columns disagreed with the single-lap detrended
         target they are the multi-horizon version of;
      3. `LEAD(lap_in_stint, k) IS NOT NULL` steps *rows*, not laps — 4.1% (k=3) and 5.8%
         (k=5) of rows sat on a stint with a hole in its lap numbering and silently
         measured a longer horizon. Guard is now `LEAD(lap_in_stint, k) = lap_in_stint + k`.
      The `GREATEST(…, 0)` floor was removed rather than kept: with the arithmetic
      repaired the quantity is a signed cumulative jump centred near zero, and the floor
      was clipping **70,054 of 110,944 non-null k=3 rows (63%) to exactly 0**. Replaced by
      symmetric ±10·k bounds, matching the single-lap target's ±10; 38 rows saturate.
      Verified by recomputing both columns in pandas from `int_lap_residual_decomposed` +
      `int_lap_residual_stint_detrend` at true lap offsets — an independent path, not the
      mart's own CTEs: null-pattern agreement 1.0000, max |diff| 2.2e-14 / 3.2e-14
- [x] `snapshot_data_profile.py` — category-share vector added for categorical columns
      (share-of-table per value, or `n_distinct` above 40 distinct values), with
      `--share-tol` / `--distinct-tol`. The baseline gained
      `profile_schema_version`, and `--check` **refuses** a baseline older than the
      current schema rather than skipping the dimension it cannot see — a blind gate that
      reports PASS is worse than no gate. Proven against the exact case it missed: a
      synthetic 9,405-row class move that leaves row count, null-rate and every numeric
      mean untouched is reported by v2 and invisible to v1. Baseline regenerated
      (25.9 KB → 73.6 KB)
- [x] `audit_forward_window` — self-join detection added, **and the audit repaired.** The
      walker now reads the enclosing SELECT's join/WHERE predicates and flags an
      inequality between same-named columns under different qualifiers, so a feature built
      the way the cliff scan is built (`a.lap_in_stint < f.lap_in_stint` in a JOIN ON, no
      LEAD anywhere) is caught. **But the audit had not been inspecting anything at all —
      see Corrections §6.** Both are covered by new tests
- [x] **Version-consistency gate** (`ml/tests/test_manifest_contract.py`, 10 tests). See
      Corrections §5. Asserts the manifest names a version whose full artefact set exists;
      that when a complete `MODEL_VERSION_DEFAULT` set is on disk the manifest names it
      (inert under CI's `smoke`, which is the whole point locally); that `shape[1]` equals
      each booster's real `num_features()` rather than `len(S.FEATURE_COLUMNS)`; that the
      input block is self-consistent; and that `app/public/models/manifest.json` and its
      `.onnx` sha256s match `ml/models/`. Replayed against the v1 artefact the old
      `make ml-onnx` would have shipped: all three of the load-bearing assertions fire
      (v1 boosters take **38** features against the manifest's declared 42)
- [x] `pressure_hpa` staged in `stg_weather` — 162,729 lap-rows, zero nulls, 778.5–1023.3 hPa
      (the low end is Mexico City, not a defect). Sold as completeness; the comment in the
      SQL says so and points at the measured negative result
- [x] **Found in the phase, not on the checklist:** the telemetry window was not a total
      order (Corrections §7), the forward-window audit had never parsed a model
      (Corrections §6), and three doc-count gates could not fail (Corrections §8)
- [x] Handoff written — see Checkpoint 2026-08-23 (Phase 4)

### Phase 5 — pit-strategy `Total_Cost(L)` rewrite
The only item in the whole series that adds an app capability rather than repairing a
number. Carried unchanged from `transform_gaps.md` through both audits.
- [x] Replace the `expected_pace_this_lap > 0.5` threshold in
      `int_pit_strategy_value.sql:215` with the real argmin. **Done, and the surface moved
      to its own model:** `int_pit_strategy_cost_curve` prices every candidate lap
      (386,036 rows over 2 horizons), `int_pit_strategy_value` is the argmin over it
- [x] A longer pit lane must push the modelled optimum later. Assert it as a test.
      `assert_pit_loss_pushes_optimum_later` re-minimises the same curve at +15 s and fails
      if the optimum retreats; `assert_pit_discount_monotone` guards the mechanism under it.
      **Both proven live** — inverting `pit_sc_loss_multiplier` to 1.5 fails them 1,365 /
      364,760 rows
- [x] This is where `int_pit_loss_circuit` and `int_sc_hazard_history` finally get consumed.
      **Both, and the SC hazard is load-bearing** — see Corrections §11: under a fixed
      one-stop the pit loss cancels out of the argmin entirely, so the hazard discount is
      the only thing that gives pit-lane length any gradient at all
- [x] `strategy_verdict` currently returns `optimal` on 8 of 7,129 stints — that number is
      the acceptance test. **Now 715**, with `unknown` down 2,231 → 266
- [x] Handoff written — see Checkpoint 2026-08-23 (Phase 5)

---

## Series II — Phases 6-10 (opened 2026-08-24)

Phases 0-5 repaired things that were wrong. Phases 6-10 address a different problem: the
models are close to the ceiling of the target they were given, and nobody had measured where
that ceiling is. Corrections §12-§17 are the evidence base; the measurement block below
records how each number was obtained.

The ordering is deliberate and is by *return per line of code*, not by size. Phase 6 changes
no data and no model and is the largest single improvement to how this work reads. Phase 7 is
one constant and a retune for a measured 2.1× gain in attainable signal. Phase 10 is the only
phase with headroom that §14 does not already rule out, and it is also the only one that
costs weeks.

### Phase 6 — honest denominators (no new data, no new SQL, no retrain)
Depends on nothing. This is the reporting half of Corrections §12 and §15, and it must land
**before** Phase 7 so that the retarget has an anchored before-number to move against.
**Complete 2026-08-24.** Every headline is unchanged to five decimals — the phase touched no
model. What it changed is what those headlines mean, and in three places it changed what the
audits and this plan believed. See Corrections §18–§20 and the Phase 6 checkpoint.
- [x] Compute and publish an **attainable ceiling** per target. Two of them, because one
      would have been the unanchored-number mistake one level down: a **distributional**
      ceiling (between-stint variance share) and a **metric-native** one (an oracle handed
      the stint id, scored in pinball / macro-F1 / AFT NLL). `ml/src/ceiling.py`, published
      per model in `evaluation_metrics.json` and on the card beside `baselines`.
      **§12's 17.5% was the estimator, not the target — properly it is 2.9%** (§18)
- [x] Re-cut the CV grouping to **stint grain** — **measured, and it needed no re-cutting.**
      A stint belongs to one race and a race to one season, so season-grouped folds are
      already stint-pure: **0 of 6,780 stints straddle a fold boundary.** The clustering
      damage was never in the split. It was in every interval computed at lap grain over it,
      which is the half §15 was actually right about. Asserted rather than believed —
      `test_evaluate.py::test_stint_grain_is_recorded_and_the_folds_are_stint_pure`
- [x] Put a paired interval on **every** `beats_baseline` claim. Two per claim: paired t over
      the five season folds (§15's coarsest honest cluster, needing no correction on top) and
      a percentile bootstrap resampling whole stints on the eval fold, published beside the
      lap-grain bootstrap of the same quantity so the widening is shown, not asserted (§20)
- [x] ~~Expect some claims to narrow into noise. Record which ones~~ — **none did.** All five
      clear both intervals, 5/5 folds, p from 1e-5 to 1.4e-3. The field ships anyway and is
      empty rather than absent: `claims_inside_noise: []`, with a test that fails if the key
      disappears, because "every claim survived" and "nobody checked" must not render the
      same. **Phase 2's p=0.24 was a different claim** — tuned-vs-floor, not model-vs-baseline
- [x] Gate: `test_manifest_contract.py` +5 tests, and the enforcement is in `card.write()`
      rather than only in the suite — the card **refuses to write** an un-intervalled claim,
      the same posture it already had for `TBD`. Liveness proven two ways: three separate
      mutations of a passing card (interval errored / bounds null / verdict absent) each fire
      it, and the **committed pre-Phase-6 card fails it on all five models**
- [x] Handoff written — see Checkpoint 2026-08-24 (Phase 6)

### Phase 7 — retarget the degradation family to the 5-lap horizon
Depends on Phase 6 landing, so the move is judged on attainable-fraction rather than on a
bare pinball number. Corrections §12 + §13. **Highest measured return in the series for the
least code.**

> **Phase 6 landed and it changed this phase's case. Read §18 and §19 before starting.**
> The move survives; the argument for it does not. Three specifics:
> * **The size holds, the levels do not.** "17.5% → 37.3%, a 2.1× gain" was two naive
>   estimates. Properly: **0.0289 → 0.0645, a 2.2× gain** — nearly the same ratio, at a
>   fifth of the magnitude. The attainable pinball reduction goes from 1.46% to 3.28% of
>   the floor. Both are tiny, and **both are already exceeded 12–28× by the models that
>   exist** (§18).
> * **The "it looks like a process" argument is gone.** +0.719 is *below* the 0.800 that
>   white-noise increments produce through window overlap alone (§19). The 5-lap column is
>   not visibly more structured than the 1-lap one; it is more *averaged*, which is a real
>   and sufficient reason on its own.
> * **The acceptance criterion needs rewriting.** "Attainable-fraction up" no longer means
>   anything useful when the current fraction is 20×: the stint-level ceiling does not bound
>   either target. Judge it on the **in-sample stint-oracle multiple** (the proof-carrying
>   number, currently 2.84× for p50) and on the raw pinball ratio against its own floor,
>   and say in the checkpoint which one moved.
>
> **Superseded 2026-08-25 by executing the phase. Read §25–§27 before reading anything above.**
> The 0.0289 → 0.0645 in the first bullet no longer exists: Phase 8's bound drove the 1-lap
> target's between-stint share to **exactly 0.0000**, and the 5-lap column's is **0.0094**
> (§26). The third bullet's instruction was followed and **the two criteria disagreed** — floor
> share up on all three, oracle multiple down on two — for the reason a zero ICC makes
> unavoidable. The phase also costs 28% of the training rows, which nothing above says (§25).
- [x] `DEGRADATION_TARGET` → `next_5_lap_cumulative_jump_s`, no SQL changed. The closed form
      was **re-verified after Phase 8 moved the residual it is built from**: reconstructed from
      `int_lap_residual_decomposed` + `int_lap_residual_stint_detrend`, **max |diff| 0.0 on all
      95,346 non-null rows**, 23 of them on the ±50 clip. **But the flip is not free and the
      checklist did not say so — see §25**: the column is NULL wherever five consecutive laps do
      not follow, so training rows fall **114,274 → 82,315** and the loss is concentrated at the
      end of stints
- [x] Exclusion held without being touched: all four degradation horizons were already in
      `EXCLUDED_LEAKAGE_COLUMNS`, so the modelled column moved between them and none became
      available. Now asserted rather than assumed —
      `test_target_columns_are_never_features` parametrises over all five production targets
      and over `TARGET_HORIZON_LAPS`, both directions
- [x] **Phase 2 finding 1 fixed first, in both places it lives.** `tune.py`'s objective now
      fits through `train._fit` itself, so the search cannot diverge from the refit again; and
      the same hole in `evaluate._fit` — which is where it reached the model card — is closed
      too (**§24**). 24 tests in `ml/tests/test_fit_parity.py` hold it, and they fail against
      the pre-fix code
- [x] **Re-tuned, not refitted.** 50 trials per quantile, fresh v8 study namespaces, under the
      corrected objective. Numbers in the Phase 7 checkpoint
- [x] Reconciled as a **per-column map** (`TARGET_BOUND_BY_COLUMN`), not a re-chosen constant:
      the clip is enforced in SQL, so the bound follows the column and `TARGET_BOUND` resolves
      through `DEGRADATION_TARGET`. Inheriting ±10 would have shipped a manifest claiming a
      range five times tighter than the data. Two tests: one that the bound follows the target,
      one that the data actually **reaches** it (98.7%), so a loose bound cannot pass
- [x] Conformal re-derived, and it moved exactly as the phase predicted. `conformal_q`
      **−0.0307 → +0.1693** and `mean_interval_width` **1.2575 → 6.2931** — a 5.0× widening
      against a 6.2× sd ratio, i.e. the scale, not a calibration defect. The sign flip is
      informative rather than alarming: on the 1-lap target the raw band was too **wide**
      (raw coverage 0.8173 against a 0.80 nominal) and on the 5-lap it is too **narrow**
      (0.7782), so conformal now widens where it used to tighten. Corrected coverage
      **0.8067**, closer to nominal than the incumbent's 0.7913
- [~] **The app surface changes meaning, not just magnitude** — done at the machine-readable
      boundary, **deliberately not done in the prose**, and the reason is the phase's own
      argument turned around. The app scores the **v6 ONNX**, which is still a next-lap model,
      so every "next-lap" sentence on screen is *currently true* and moving it now would make
      the app wrong rather than right. Copy moves when the version the app loads moves; it is
      one step, not two. What did land is the part that makes that step mechanical and stops it
      being missed: `export_onnx.build_manifest` now writes `target_column`, `horizon_laps` and
      a horizon-bearing `meaning`
      (`cumulative_degradation_jump_seconds_over_next_5_laps`) instead of the flat
      `degradation_jump_seconds`, `train.py` records `target_column` in every training log, and
      `card.py` derives its summary phrase from `TARGET_HORIZON_LAPS` rather than spelling
      "next-lap" in a string literal. **The exact prose surface to move on promotion**, all of
      it still true today: `docs/ml/calibration.mdx` (3), `docs/ml/models.mdx` (3),
      `docs/ml/overview.mdx` (2), `docs/ml/feature-contract.mdx`, `docs/ml/features-and-targets.mdx`,
      `app/src/features/model-metrics/{page,methodology}.tsx`,
      `app/src/features/degradation-simulator/{methodology.tsx,DegradationSimulatorChart.tsx,queries.ts}`,
      and `docs/reference/ml/degradation-model.mdx` + `ml/model_card.yml` +
      `ml/models/model_card.json` + `app/public/models/model_card.json` (all four regenerate
      from `make ml-card` / `make ml-reference`)
- [x] **Accepted, and the two criteria disagree — read both.** Raw pinball rises 0.1993 →
      1.0291 on p50 exactly as warned; that is the 6.2× sd and means nothing on its own.
      * **Reduction as a share of its own floor: up on all three, and roughly doubled on two.**
        p10 38.38% → 59.21%, p50 24.57% → 47.32%, p90 15.30% → 29.80%.
      * **In-sample stint-oracle multiple: DOWN on two of three.** p10 2.36 → 1.66, p50 3.76 →
        3.40, p90 1.20 → 1.62. All still above 1, so both targets are read past their
        stint-level ceiling — but this criterion does not endorse the move on its own.
      The two disagree because the **denominator stopped being degenerate** (§26): on the 1-lap
      target stint identity supplies essentially nothing, so a multiple against it is a ratio to
      almost zero. Comparing multiples across a target whose ICC moved 0.0000 → 0.0094 compares
      two different denominators; the floor-relative reduction is the like-for-like number, and
      it doubles. **The decisive fact is §27's second table**: the analytic and cross-fitted
      denominators are `null` on the incumbent and finite on the 5-lap target, so Phase 6's
      primary denominator only exists after this move
- [x] All five beat baseline, **all five significant**, `claims_inside_noise` empty. The trio
      wins 5/5 folds each (p = 0.0012 / 0.0001 / 0.0002)
- [x] Handoff written

### Phase 8 — bound the cliff curve at source, then re-label and retrain the classifier
Depends on nothing, but must not run concurrently with Phase 7 — both move mart columns the
classifier reads, and a joint move is unattributable.

> **Read Correction §23 before reading this checklist.** The defect is real and the bound is
> the right repair, but the mechanism written below is wrong: the label is a scan over
> `driver_skill_residual_s`, which has the polynomial *subtracted*, so the unbounded tail was
> **erasing** cliffs into `none_in_stint`, not inventing them. §23 also records that this
> phase moves the **degradation** target too (9.05% of rows) — it is not classifier-only, and
> the two arms must be measured apart.
- [x] ~~`laps_until_cliff_class` is a first-crossing scan over `int_compound_cliff_predicted`~~
      — **it is a scan over `driver_skill_residual_s`, into which that model is subtracted**
      (§23). Phase 5's measurement stands: 93.5 s/lap in-sample, p99 30.8, capped **inside
      `int_pit_strategy_cost_curve` only**, leaving the source curve — and therefore both ML
      targets — standing on the unbounded tail
- [x] Bound moved to the source model. `var('compound_wear_max_s_per_lap')` is the shared
      bound's **own name**, read by `int_compound_cliff_predicted` (new) and by
      `int_pit_strategy_cost_curve` (switched to it); `pit_strategy_max_wear_s_per_lap`
      survives as that model's alias so the two can be diverged. Its **own test** is
      `assert_compound_wear_bounded.sql`, asserted on a new `compound_wear_s` column so the
      bound is checked directly rather than re-derived from the pace total. **Proven live**:
      rebuild the source model with the bound inert and it fails 12,580 rows
- [x] Label re-derived and measured: **6,825 rows change class (4.97%), 99.5% of them out of
      `none_in_stint`** — see §23 for the direction and for the closed-form's inert-cap
      validation. **The data-profile gate saw it**: 29 drifts, including the category-share
      vector Phase 4 added (`none_in_stint` 0.7008 → 0.6514, the three real classes up
      +0.0118 / +0.0167 / +0.0209). That is the 9,405-row blind spot proven closed on a
      second, independent change
- [x] Only then re-tune. **Ran 2026-08-25: 50 trials at v7, and it found nothing.** Best
      fresh CV mean macro-F1 **0.3941** against the incumbent's **0.3946** — the params tuned
      on the *contaminated* label were not beaten by a search on the repaired one. Fold-paired
      the new params lose 4 of 5 folds (mean -0.00051, p=0.716). The eval-fold headline rises
      0.3971 -> 0.4015 and **that is the trap, not the result**: the only fold they win is the
      one the headline is read from. Search product reverted; see the closing checkpoint
- [x] Handoff written

### Phase 9 — prune the collinear feature set (42 → ~20)
Depends on Phases 7 and 8, because the ablation has to be re-run against the new target and
the repaired label before anything is acted on.
- [x] ~~Re-run the group ablation. On the *current* target it reads: `compound` −0.0007 (0.3%),
      `stint_position` 0.0032 (1.6%), `cliff_prior` 0.0036, `dirty_air` 0.0079 (4.0%),
      `thermal` 0.0159 (8.0%)~~ — **the quoted numbers are the 1-lap ones and are dead; see
      §27. Re-run 2026-09-05 against the v8 mart, in all three ablation-bearing families.**

      `./.venv/bin/python -m ml.src.evaluate --all --attribution --version v8`, ~100 min.
      **`--version v8` rather than the bare `make ml-attribution`, deliberately:** the target
      takes `--version` from `S.MODEL_VERSION_DEFAULT`, which is still **v6**, while
      `_params_for` reads `ml/models/*_best_params.json` for every non-smoke version alike. So
      the bare target computes exactly the same numbers and stamps the report `v6` — it would
      have relabelled the v8 report on disk without changing a single value in it. The label is
      the only thing the flag moves.

      **Reproduction before any new number was read.** All five headlines and all three ablation
      tables come back **bit-identical to the v8 report** (max |diff| **0.0** on every
      `delta_vs_full` in all three families; p50 1.029103, cliff 0.397149, stint life 1.936635).
      §27's p50 column is confirmed as the current measurement rather than re-derived from it.

      **What is new is the denominator.** The plain `ablation` field is a point estimate with
      nothing under it — the exact defect Phase 6 spent itself removing one level up — so every
      delta below is adjudicated against `within_stint_attribution.refit_noise.delta_noise_2sd`,
      the same seed-only refit floor §21/§22 used, at `2·√2·sd` over 5 reseeds of the unmodified
      feature set:

      | family | headline | metric | sd over 5 reseeds | **`delta_noise_2sd`** | as % of headline |
      | :--- | ---: | :--- | ---: | ---: | ---: |
      | `degradation_regressor_p50` | 1.029103 | pinball ↓ | 0.005402 | **0.015280** | 1.49% |
      | `cliff_classifier` | 0.397149 | macro-F1 ↑ | 0.002446 | **0.006917** | 1.74% |
      | `stint_life_regressor` | 1.936635 | AFT NLL ↓ | 0.002666 | **0.007541** | 0.39% |

      **The third floor is not in the report and had to be built.** `evaluate.ATTRIBUTION_TARGETS`
      is `{degradation_regressor_p50, cliff_classifier}` — stint life is excluded on purpose
      ("its target is a deterministic ramp inside its own stint"), so `make ml-attribution`
      produces **no** `refit_noise` for the one family §20 measured as the most clustered of the
      five. Worse, its `fit_seeded` closure calls `model.fit(...)` without `is_censored`, which
      `AFTBooster` refuses by design, so flipping the frozenset would have raised rather than
      answered. The floor above was measured with `AT.refit_noise_floor` over the same 5 seeds,
      threading the seed through `AFTBooster`'s own `seed` param (the analogue of
      `set_params(random_state=…)`), and **the instrument was checked against a known answer
      first**: its unmodified fit reproduces the published stint-life headline to **0.0** before
      any floor was read. The drop deltas themselves were **not** recomputed — `ablation()` and
      `within_stint_ablation` share `_fit`/`_score` on the same split, and the identity below
      proves the two agree exactly, so the report's own column is the measurement.

      **The sign identity, checked rather than assumed**, because the two fields do not share a
      convention and mixing them is how this decision goes wrong quietly. `ablation.delta_vs_full`
      is the raw `val − base`; `within_stint_attribution.groups[].drop_delta` is normalised so
      *positive always means the model got worse without it*. Measured over all ten groups:
      `drop_delta = +delta_vs_full` for p50 and stint life (`higher_is_better=False`) and
      `drop_delta = −delta_vs_full` for the classifier (`higher_is_better=True`), **max |diff|
      0.0 in both**. Everything below is in the normalised convention.
- [x] ~~Drop groups whose ablation delta falls inside the Phase 6 interval. **Drop on the
      interval, never on the point estimate** — that is the same mistake §15 catalogues~~ —
      **done 2026-09-05. Five groups drop, five stay; 42 features → 24, not the ~20 in this
      phase's own heading.**

      Deltas are in each family's own metric and are **not** comparable across columns; the
      `×floor` column is, and it is the only cross-family quantity used. ✅ = clears its floor.

      | group | *n* | p50 Δ | ×floor | cliff Δ | ×floor | stint-life Δ | ×floor | verdict |
      | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
      | `stint_position` | 4 | **+0.09725** | 6.36 ✅ | **+0.01816** | 2.63 ✅ | **+0.11385** | 15.10 ✅ | **keep** — 3/3 |
      | `compound` | 7 | **+0.19681** | 12.88 ✅ | **+0.01779** | 2.57 ✅ | −0.00400 | 0.53 | **keep** — §27's group |
      | `thermal` | 4 | **+0.09486** | 6.21 ✅ | **+0.01290** | 1.86 ✅ | **+0.05463** | 7.24 ✅ | **keep** — 3/3 |
      | `cliff_prior` | 5 | **+0.07030** | 4.60 ✅ | +0.00504 | 0.73 | −0.00244 | 0.32 | **keep** — p50 only |
      | `dirty_air` | 4 | **+0.02252** | 1.47 ✅ | +0.00252 | 0.36 | +0.00143 | 0.19 | **keep** — marginal |
      | `powertrain` | 6 | +0.01010 | 0.66 | −0.00128 | 0.19 | +0.00396 | 0.52 | **drop** |
      | `telemetry_cliff` | 5 | −0.00021 | 0.01 | +0.00377 | 0.54 | +0.00101 | 0.13 | **drop** |
      | `weather_air` | 2 | +0.00365 | 0.24 | +0.00130 | 0.19 | +0.00535 | 0.71 | **drop** |
      | `track` | 2 | +0.00430 | 0.28 | −0.00472 | 0.68 | **−0.00856** | 1.14 ✅ | **drop** — see below |
      | `context` | 3 | −0.00378 | 0.25 | +0.00483 | 0.70 | −0.00004 | 0.01 | **drop** |

      **The aggregation rule, stated because this phase left it open and a table cannot decide
      itself.** The feature set is one shared `FEATURE_GROUPS`, so a drop is borne by all five
      models at once and the evidence for "carries nothing" has to hold in every family that is
      scored, not on average over them. The rule taken is therefore:

      > **Keep a group if its drop delta is positive *and* clears that family's floor in at
      > least one of the three ablation-bearing families. Drop only where no family shows a
      > positive delta outside its own floor.**

      Two halves, and both are load-bearing. **"Any family"** rather than "the headline family"
      or a majority, because the error is asymmetric: this phase's own payoff is *variance, ONNX
      size and browser payload* and explicitly **not accuracy**, so keeping a dead group costs
      bytes and dropping a live one costs a shipped model. §27 is the near-miss that argues for
      erring toward keeping. **"Positive"** rather than `abs()`, because `drop_inside_noise` is
      computed on the magnitude and a group that clears its floor in the direction of *removing
      it helps* is not thereby load-bearing — reading it as a keep would be the sign trap the
      two conventions above set up.

      **What the cross-family rule actually changed: nothing, and that is the finding.** No group
      inside p50's floor clears positively in either other family, so the rule and "read p50
      alone" agree on **10 of 10**. The worry that opened this item — a group that is noise for
      the degradation headline but load-bearing for the classifier or stint life — is measured
      and did not happen. It is now a measurement rather than an assumption, which is the only
      reason the shared feature set is safe to prune on three families' worth of evidence.

      **`track` is the only group where the sign half of the rule bites, and its own number is
      deliberately not read as a finding.** Its stint-life delta is **−0.00856 at 1.14× that family's
      floor** — the model gets *better* without it — and it is inside the floor in the other two
      (0.28×, 0.68×, and the classifier's is negative too). It drops because **no family shows it
      carrying anything**, which is this checklist's own rule, and **not** because it is harmful.
      1.14× is not a demonstrated harm and must not be written up as one: `delta_noise_2sd` is a
      **seed-only** floor over a fixed eval fold, so it prices reseeding and prices nothing about
      which rows are in the fold, and §20 measured stint life as the one family whose
      stint-grain interval is **3.71×** its lap-grain one — the largest of the five. §21 refused
      two tidier numbers than this at 0.79× and 0.70×. The direction is recorded; the claim is
      not made.

      **`dirty_air` is the marginal keep and should be named as one.** It clears on p50 alone at
      **1.47×**, against 4.60× for `cliff_prior` and 6.21×–12.88× for the other three. It is kept
      because the rule keeps it and because keeping is the conservative direction, not because
      1.47× is comfortable. If a later pass wants the ~20 this phase's heading asks for, those
      four columns are the next candidates — **but not on this evidence**, and §16 is the reason
      to look twice: `dirty_air` is built on FastF1's `DistanceToDriverAhead`, which Phase 10a
      exists to replace, so its measured weakness may be the proxy rather than the channel.

      **Consequences of the drop set, verified in the SQL.** `powertrain` (6) and
      `telemetry_cliff` (5) are **the mart's entire consumption of
      `int_lap_telemetry_aggregates`** — `fct_cliff_prediction_features.sql:222-232` projects
      exactly those eleven columns from it and no others — so this removes every telemetry-
      aggregate feature from the contract in one move. That is a fact about the feature set and
      **not** a licence to delete the model or the ingestion behind it: Phase 10 reads the same
      6.0 GB for a different channel (§16, 10c's cost note), and this pass has measured the
      aggregates as features, never as data.

      **The 18 columns, and the four constants that move with them.** `FEATURE_COLUMNS` goes
      **42 → 24** by removing, in contract order: `n_gear_changes`, `mean_rpm`, `max_rpm`,
      `pct_full_throttle`, `pct_drs_active`, `short_shift_index`, `mid_corner_speed_loss_kph`,
      `traction_wheelspin_proxy`, `throttle_trace_decay`, `braking_point_drift_m`,
      `lift_coast_share`, `ambient_temp_delta`, `is_rain_lap`, `track_energy_index`,
      `circuit_abrasiveness_index`, `constructor_id`, `event_flag_any`, `anomaly_class`. Four
      other constants in `schema.py` name some of those and are **not** derived from
      `FEATURE_GROUPS`, so they do not follow automatically: `CATEGORICAL_COLUMNS` loses
      `constructor_id` and `anomaly_class` (2 of its 4), `BOOLEAN_COLUMNS` loses `event_flag_any`
      and `is_rain_lap` (2 of its 4), and **`AUDIT_FEATURES` loses `anomaly_class`** — leaving it
      would point the forward-window audit at a column that is no longer a feature, which is a
      gate asserting over nothing, i.e. §6's shape. Cohort evaluation is unaffected and was
      checked rather than assumed: `is_rain_lap` and `constructor_id` reach `_cohort_table`
      through `COHORT_DIMS` off the mart and `IDENTIFIER_COLUMNS`, never through `X`.

      **Verified vs assumed, in the phase's own terms.**
      * *Verified* — the three floors, each from 5 reseeds of the unmodified feature set on that
        family's own split; the sign identity across both conventions at max |diff| 0.0; the
        bit-identical reproduction of every v8 headline and ablation delta; the stint-life
        instrument against the published headline before it was trusted with a floor;
        `cliff_classifier_best_params.json` clean against HEAD (`git diff --stat` empty), so its
        post-report mtime is a no-op rewrite and the classifier ablation is not stale.
      * **Assumed, and it is the real gap. `degradation_regressor_p10` and `_p90` are never
        scored.** `ELEVATION_TARGETS` runs the ablation on the headline model of each family
        only, so a group that is noise for the median and load-bearing for a *tail* would not
        appear anywhere in the table above. That is not idle: the p10/p90 boosters ship, and
        `weather_air` (`is_rain_lap`) and `dirty_air` are exactly the shape of feature that
        would matter to a tail and not a median. Nothing here measures it, and nothing in the
        report can.
      * *Assumed* — that one eval fold (2024, n=13,896 / 19,145 / 20,272) generalises. The
        floor is seed-only; no group delta carries a fold-paired or stint-bootstrap interval,
        which is a weaker instrument than the one Phase 6 put on `beats_baseline`. It errs
        toward keeping, which is the direction this phase can afford.
      * *Not done* — nothing was retrained, exported or carded, `ml/src/schema.py` is untouched,
        and the 24-feature set has **never been fitted**. The table says what each group is worth
        beside the other nine; it does not say what a model without all five drops scores. That
        measurement belongs to the implementation pass and is its first acceptance number.
- [x] **Never act on a flatten delta without its causal arm** (§22) — **inapplicable to this
      phase's decision, by the checklist's own text, and recorded as inapplicable rather than
      as done.** Every number acted on above is a **drop** (`drop_delta` /
      `drop_inside_noise`), which removes information outright and raises no admissibility
      question; not one `flatten_delta`, `causal_delta` or `causally_reachable` verdict entered
      the drop/keep call, so `flatten_causality` was never the right instrument here. The run
      *did* refresh the flatten and causal arms for p50 and the classifier against v8, which
      closes open item **22**'s measurement — and they moved (the classifier's floor alone
      doubled, 0.00352 → 0.00692, so §21's `tyre_age` channel at 0.50× is now inside it). **That
      is item 22's write-up to make, not Phase 9's**, and nothing in it was acted on here.
- [x] ~~The payoff is not accuracy. It is variance, ONNX size and browser payload: five models
      ship to `app/public/models/` and `app/public/data/` is already 423 MB~~ — **measured
      2026-09-05, and the payoff did not arrive the way this bullet expects.**
      `app/public/models/` grew: v6 (42 features) → v10 (24 features) is
      **30,362,421 → 35,377,078 bytes, +16.5%**. `app/public/data/` is unchanged at 423 MB
      (`mart_degradation_predictions/` 7.1 → 7.2 MB, noise — its size is set by output rows,
      not input features). Per-model ONNX bytes:

      | model | v6 | v10 | Δ |
      | :--- | ---: | ---: | ---: |
      | `cliff_classifier` | 24,590,634 | 23,469,544 | **−4.6%** |
      | `degradation_regressor_p10` | 1,056,940 | 2,167,266 | **+105.1%** |
      | `degradation_regressor_p50` | 1,220,796 | 5,981,020 | **+389.9%** |
      | `degradation_regressor_p90` | 586,839 | 963,062 | **+64.1%** |
      | `stint_life_regressor` | 2,907,212 | 2,796,186 | **−3.8%** |

      **The cause is not Phase 9.** v6 is the last version actually shipped, so it also
      predates Phase 7's retune of the quantile trio's hyperparameters — v6's boosters were
      small trees, v10's are `max_depth` 6–8 / `n_estimators` 300–600 (the trio's post-retune
      `*_best_params.json`). Tree-ensemble ONNX size scales with total leaf count
      (`n_estimators × 2^max_depth`), not feature count, so bundling the version bump made
      the retune's size cost visible at the same time as Phase 9's. Two isolations, both
      pointing the same way: `cliff_classifier`'s hyperparameters are untouched since Phase 2
      (only its feature count moved) and it shows the expected **−4.6%**; a same-hyperparameter
      side-check exporting `degradation_regressor_p10`'s existing v8 booster (42 features, the
      *current*, post-retune params) to ONNX measured **2,180,320 bytes** against v10's
      **2,167,266** — a **−0.6%** feature-count-only effect, swamped by the +105.1% the
      hyperparameter change added on top. Phase 9's own contribution is real and in the
      expected direction; it is just not what moved the total.
- [x] ~~Guard already exists: `test_feature_contract` and the manifest's `shape[1]` check from
      Phase 4 both fail loudly on a feature-count change. That is the intended behaviour, not
      an obstacle to route around~~ — **confirmed engaged, not just present.** Both are
      schema-driven (`test_feature_contract_subset_of_mart` reads `S.FEATURE_COLUMNS` live;
      `test_manifest_contract.py`'s shape check asserts `n_features == shape[1] ==
      len(feature_order)`, all off the manifest), so neither needed editing — they ran green
      at 24 both before and after the export, which is the guard doing its job silently
      rather than the guard being untested. What **did** need editing were guards that hardcode
      the count rather than derive it: `ml/tests/test_attribution.py::test_every_contract_feature_has_a_channel`
      (`sum(len(v) for v in CHANNELS.values()) == len(S.FEATURE_COLUMNS)`) failed 42≠24 because
      `ml/src/attribution.py`'s `CHANNELS` dict (a separate physics-hypothesis taxonomy,
      unrelated to `FEATURE_GROUPS`) still listed the 18 dropped columns — fixed by pruning
      `CHANNELS` to match, not by loosening the assertion. Three more tests in
      `test_attribution.py` used `is_rain_lap` as their example boolean/discrete column and
      silently stopped testing the code path they claimed to (it fell through to the
      continuous branch and coincidentally agreed on 2 of 3 assertions) — fixed by swapping
      the fixture to `cliff_onset_passed`, a column still in `BOOLEAN_COLUMNS`. See the
      checkpoint below for the same pattern found twice more, in `app/src/ml/featureVector.test.ts`
      and in `scripts/dump_parity_rows.py`.
- [x] Handoff written

### Phase 10 — the missing channel (X/Y positional telemetry)
The only phase in either series that adds *information* rather than repairing a number, and
the only one whose headroom §14 does not already rule out. Largest by a wide margin. Do not
start it before Phase 7 has proven the target, or a null result will be unattributable
between "the channel is weak" and "the target was noise".

**10a — `int_lap_proximity`: the true pairwise gap.** — **DONE, and it is the first feature
addition in either series to clear its own noise floor.** Shipped as v11 (33 features).
- [x] Reconstruct each car's track position as (`lap_number`, `relative_distance`) against
      `session_time_s`, then derive the gap from every car to every other car at the position
      channel's native rate (~369 samples/lap/driver) — done, and *without* a pairwise
      join. Each lap is cut into 100 fractions of `relative_distance`; the session clock at
      which a driver first enters a fraction is a crossing time of a fixed point on track;
      inside one `(race_id, track_bin)` the previous crossing by clock **is** the car ahead
      on track. One `LAG` over a window, not an N² self-join, so the crossing table is
      16,045,328 rows and the model builds in **7.9 s** standalone.
- [x] Emit **per-lap scalars only**: 9 of them, on a 162,729-row spine verified equal to
      `int_lap_air_state`'s. Within 1 s / 2 s (and 3 s, kept in the intermediate), seconds
      within 1 s time-weighted by real bin duration, train-vs-single-tow (`share_lap_in_train`
      — my gap < 1 s **and** the car ahead's own gap < 1 s, from `LAG(...,2)`),
      `ahead_identity_stability`, `n_distinct_cars_ahead_3s`, and `share_lap_behind_within_1s`
      — the half of traffic `DistanceToDriverAhead` structurally cannot see. No matrix
      anywhere; the mart join carries nine doubles per lap.
- [x] Replace the `DistanceToDriverAhead` inputs in `int_lap_air_state` — **ran the ablation
      against both, and the measurement REFUSES the replacement.** The swap arm (drop
      `dirty_air`, keep `proximity`) lands *inside* the noise floor on all three families
      (0.15× / 0.67× / 0.39×) — and on the classifier is actually **worse** than the
      24-feature baseline — while the additive arm clears on two (1.54× / 2.17× / 0.59×).
      The two groups carry different things, so both ship. The checklist's instruction to keep
      the old columns "for one version" is what made this decidable; it is now decided, and the
      answer is keep them permanently, not for one version.
- [x] Free label: the 4,909 BLUE flags — staged (`stg_race_control`, closing open item 13)
      and turned into `assert_proximity_agrees_with_blue_flags`. On blue-flagged laps the
      median closest car goes **0.60 s → 0.30 s** and the sign holds in **all 7 seasons
      independently**. The incumbent measure moves the *wrong way* on the same split
      (`dirty_air_share_lap` 0.2402 → 0.1327), because a car being lapped has the fast car
      *behind* it. **Caveat recorded in the test file:** vacuous on the CI fixture (12/1/0
      blue flags per season against an `n_blue >= 100` guard) — a dev/prod gate.
- [x] **Not on the original checklist, and it is the most important thing this phase found:**
      the first build of `int_lap_proximity` was **not reproducible**, and no gate in the repo
      except the byte-stability oracle could see it. Two `LAG`/`LEAD` windows were ordered on
      keys that are not total orders — 223,602 of 15,821,726 crossings tie on
      `(race_id, track_bin, crossing_time_s)`, and 76 more tie at the lap rollover, where
      FastF1 hands the transition sample to both laps. Two builds of identical SQL produced
      different features. Fixed with explicit tie-breaks, covered by
      `assert_proximity_crossing_total_order`, and now byte-identical across three
      consecutive builds. Full detail in the checkpoint.

**10b — `int_racing_line_deviation`.** — **NOT STARTED, deliberately, and now unblocked.**
10a's ablation was the gate the Risks section set for it, and 10a came back positive, so the
argument against building 10b speculatively has been discharged. It was not built here because
landing 10a properly (contract → refit ×5 → export → parity → app → docs) is itself a full
pass, and starting 10b on top would have risked leaving 10a half-shipped. `pos_x` / `pos_y` are
already projected in `stg_telemetry_position` for exactly this, so 10b needs no new bronze work.
- [ ] Lateral offset from the driver's own clean-air reference line, per corner, per lap,
      using `dim_corners` for the mapping (34 of 36 event slugs covered)
- [ ] The reference must be the driver's **own** early-stint clean-air line, matching how the
      existing telemetry-cliff features are built against a self-baseline rather than an
      absolute. An absolute line measures car and circuit, not tyre state

**10c — the ingestion gaps.**
- [ ] `_write_pos_data` / `_write_telemetry_full` (`ingestion/src/ingest.py:483-484`) are
      gated behind `telemetry_full` and have **never run**; both bronze dirs hold zero files.
      Full-rate position data is one flag — **still true, and it turned out to be unnecessary
      for 10a. This premise was wrong.** `_write_telemetry` (which HAS always run) calls
      FastF1's `lap.get_telemetry()`, and that returns the **merged** car+pos stream: every
      one of the 147 bronze telemetry files already carries `X`, `Y`, `Z`, `RelativeDistance`,
      `DriverAhead` and `DistanceToDriverAhead`, 100% populated, verified across all 7 seasons
      and 12 sampled races. 58,831,651 of the 118,708,607 rows are `Source='pos'`. 10a was
      built entirely from data already on disk — **no ingest was run and none was needed.**
      Left unchecked because the writers genuinely have still never run and the dirs are still
      empty; what is now known is that running them would buy a second copy, not new data.
- [ ] `ingest.py` accepts `R`, `Q`, `both` only — **practice has never been ingested.** FP2
      long runs are long, in clean air and free of strategy contamination, and per §14 are the
      one source of extra rows that raises SNR rather than restating it. A session flag and a
      partition key, not a rewrite — **not attempted. Not blocked, just unbudgeted**: FastF1's
      endpoints were reachable from this session (livetiming.formula1.com 200, jolpi.ca 200),
      so whoever picks this up does not need to re-test the network.
- [x] **Cost note, before any of the above lands:** the channel split — **done at the staging
      layer (`stg_telemetry_position`), and the cost premise this note rests on is measurably
      wrong by roughly an order of magnitude.** Measured 2026-09-05 before writing any of it:
      scanning the `car` rows out of the merged bronze across all 7 seasons costs **0.36 s**,
      and the `pos` rows the aggregate model discards cost about the same again — against
      `int_lap_telemetry_aggregates`'s 19.3 s total, of which **8.1 s is the window functions**.
      DuckDB projects 9 of 23 columns and the `Source` column is dictionary-encoded at 0.3% of
      the file, so the "6.0 GB scan" never happens: about 1.8 GB is actually read.
      A full physical split *was* built and benchmarked (6.48 GB → 0.62 GB car + 1.18 GB pos,
      zstd, sorted by `(driver, lap, session_time)`): it takes the window-heavy path 7.91 s →
      6.63 s (1.19×) and the proximity crossings 1.43 s → 1.21 s. **~1.5 s of whole-warehouse
      build time for 1.8 GB of duplicated bronze plus a regeneration seam that must re-run
      after every ingest and can silently diverge from source.** Judged not worth it and
      deleted; the split that *did* land is a dbt staging model that costs zero disk, has its
      own schema entry and tests, and is the sole reader of `source_channel='pos'`. The real
      cost outcome: the three telemetry models together go **77.3 s → 83.9 s (+8.5%)**, and
      `int_lap_proximity` alone is 7.9 s — cheaper than either model that predates it.

---

## Handoff protocol

Each phase closes with a block appended to **Checkpoint** below, containing:

1. **What landed** — files touched, and what is in the working tree but uncommitted.
2. **What was verified vs assumed.** The series' recurring failure is a claim traced down
   one path and generalised — `ml_headroom_ii.md` §6 asserted "rendered nowhere" after
   checking one of two consumers. Name the paths you actually walked.
3. **Gates run, with results**, in the table format `ml_headroom_ii.md` §8 uses.
4. **Open decisions** blocking the next phase, phrased so they can be answered without
   re-reading the audits.
5. **The first command the next session should run.**

---

## Not recommended (measured, do not revisit)

- Promoting the 17 unused warehouse signals into the feature set — `ml_headroom.md` §3.
- Building air-density enrichment as an ML feature — `ml_headroom.md` §4.
- Generalising the survival framing to the cliff target — `ml_headroom_ii.md` §4.
- Treating balanced class weights as available headroom — shipped in `555fbf2`.
- Carrying forward "train on uncensored stints only, +12.4%" — that gain is the selection
  effect scoring itself on a biased sample (`ml_headroom_ii.md` §3).
- Collapsing the cliff label to 3 or 2 classes. `ml_headroom.md` §1 raised it as a product
  question; the repair dissolved it — `6_plus` goes F1 0.045 → 0.321 and the four classes
  are worth keeping.

Added 2026-08-24, from the ceiling measurement:

- **Ingesting 2025, or backfilling 2010–2017, as a route to better ML numbers.** The learning
  curves are flat (Corrections §14): the classifier saturates after season two and the p50
  regressor gained 0.0146 pinball across 6.7× the data. Ingest 2025 for the honest-holdout
  reveal the card promises — that argument stands on its own and does not need the numbers to
  improve. Do not budget it as headroom.
- **Further Optuna search against `next_lap_degradation_jump_detrended_s`.** The target is
  82.5% noise (§12); a better search buys a better fit to the same noise. Phase 2 already
  demonstrated the shape of that return: +0.75% at p=0.24. Re-tune *after* Phase 7 moves the
  target, not before.
- **Adding further features derived from lap times or the car channels.** The ablation shows
  the existing 42 are already largely re-projections of one another — the whole 7-feature
  `compound` group is worth 0.3% (§16). A 43rd feature from the same channel adds variance,
  not information. The next feature has to come from a different sensor, which is Phase 10.
- **Reading the Phase 7 result off raw pinball.** Listed here because it is the most likely
  way this series gets undone by someone acting reasonably. See the Risks entry below.

Added 2026-08-25, from Phase 8's closing re-tune:

- **Re-tuning the cliff classifier inside the current search space.** Measured and closed:
  50 trials on the repaired label reached 0.3941 CV mean macro-F1 against an incumbent of
  0.3946, losing 4 of 5 folds. The incumbent was inside the space and TPE had 50 tries to
  rediscover it. **The one thing not closed** is the space itself — both param sets pin
  `max_depth` at 8 and `n_estimators` at 700, the top of `tune.py:_suggest` in both
  dimensions. Widen the bounds before re-running, or do not re-run.

---

## Risks

- **Phase 1 rewrites tracked artefacts** — `manifest.json`, `model_card.json`,
  `evaluation_metrics.json`, the prediction parquet, and every `*_v5.onnx`. Large diff,
  mostly generated. Land it as one commit with the SQL, so the label change and its
  consequences are attributable together.
- **Phase 3 changes a model contract**, not just a number. The ONNX post-transform lives in
  three places (`export_onnx.py`, `predict.py`, `infer.ts`) plus the parity checker; a
  partial application passes some gates and silently mispredicts in others.
- **The data-profile gate cannot see either change** until Phase 4 fixes it. Do not read a
  clean `data-profile-check` as evidence that Phase 1 or 3 was inert.
- **Nothing here is committed.** ~~Both audits and all five `transform_gaps.md` phases are
  sitting uncommitted in the working tree alongside this work.~~ Corrected 2026-08-23: the
  `transform_gaps.md` work **is** committed (`c7c8509`, `9d6b7d4`, `bd0ce6b`); the only
  uncommitted SQL before this session was the label repair. That matters beyond
  bookkeeping — it is exactly why Corrections §4's premise failed, since committed work
  between the v4 training run and now moved the mart under v4's recorded numbers. What is
  uncommitted now is Phase 0 + Phase 1 in full: the mart SQL, the new singular test, the
  five v5 artefact sets, and the docs.

Added 2026-08-24, for Series II:

- **Phase 7 makes the headline metric look worse, and it is supposed to.** Raw pinball scales
  with the target's sd, which moves 1.132 → 7.560. Every dashboard, doc-facts gate and card
  comparison reading the raw number will report a large regression on a phase that improved
  the model. **Phase 6's attainable-fraction must land first**, or this gets reverted by
  someone doing the right thing with the wrong column.
- **Phase 6 will retire some currently-published claims.** The card and the README both say
  every model beats a strong per-cohort baseline. With stint-grain intervals (§15, ~4.4×
  wider) some of those margins will not clear their own error bar — `stint_life`'s uncensored
  arm is the likeliest, at 3.3908 vs 3.4027, a 0.35% win. The README's "5/5 ML models beat
  baseline" badge is downstream of this and must move with it. **Retiring a claim that was
  never supported is the phase working, not the phase failing.**
- **Phase 8 changes a label, so it changes every metric at once.** The same risk Phase 1
  carried: a label move rewrites the artefact set, and the classifier's before/after is only
  attributable if nothing else moves in the same commit. Do not land it with Phase 7.
- **Phase 10 is the first phase in either series to change build cost materially.** A full
  build already scans 6.0 GB of telemetry to produce eleven per-lap aggregates, discarding
  ~9M `pos` rows per season on the way. 10a reads exactly those rows. Do the bronze channel
  split in 10c before 10a, or the dev build time becomes the reason the phase stalls.
- **Phase 10 has no guaranteed payoff.** It is the only phase here justified by an argument
  (a new sensor must carry new information) rather than by a measurement, because the
  measurement cannot be made until the feature exists. Budget 10a alone first and let its
  ablation decide 10b, rather than committing to the whole channel up front.

---

## Checkpoint

- 2026-08-23: Plan written, folding `ml_headroom.md` and `ml_headroom_ii.md`. Three new
  corrections recorded (see top): `ml_headroom_ii.md` §6 is wrong — `stint_life_regressor`
  renders in `DegradationSimulatorChart.tsx:391` via the in-browser ONNX path, verified by
  tracing `infer.ts → transform.ts:219 → LifeGauge`; `make ml-train` trains untuned v1
  boosters and cannot be used for Phase 1; the relabel needs a version bump that costs a
  retrain of all five models. Three user decisions settled: retrain at existing params
  (not re-tune) in Phase 1, AFT ahead of pit-strategy, delete the `tyre_allocations` seed.
  **No code changed in this pass.** Working tree still holds the `transform_gaps.md` and
  `ml_headroom_ii.md` §1 changes, uncommitted.

- 2026-08-23 (Phase 0 + Phase 1): **both complete, nothing committed.**

  **1. What landed.**
  *Phase 0, documentation only:* both audits carry a "superseded as a tracker" note;
  `ml_headroom_ii.md` §6 carries a dated appended correction (not an edit) explaining that
  the model does have an app surface and *how* the original trace missed it; the three
  negative results are recorded in `docs/ml/features-and-targets.mdx` (17 signals, air
  density) and `docs/ml/models.mdx` (survival framing); the `DEFERRED` air-density note in
  `ml/src/schema.py` is closed as a measured negative result.
  *Phase 1, code and artefacts:* `MODEL_VERSION_DEFAULT = "v5"`; `train.py --tuned` and
  `make ml-retrain` (Corrections §2); `export_onnx.py`'s version default fixed
  (Corrections §5); `ml-train` removed from the `ml-all` chain; five v5 boosters, five v5
  ONNX, `manifest.json`, `model_card.yml`/`.json`, predictions parquet, six ML inventory
  snippets, the ML reference page, `app/public/models/*`, 16 files under
  `app/public/data/`. `card.py`'s hardcoded "macro-F1 ≈ 0.33" limitation now reads the
  number back off the card, and its stale "v1 hyperparameters / reduced tuning budget"
  claim is replaced. Hand-written metrics corrected across `docs/ml/{models, overview,
  cohorts, validation, feature-contract, features-and-targets, onnx, tuning}.mdx` and
  `README.md`. `ml/models/cliff_classifier_relabel.bst` deleted.

  **2. Verified vs assumed.** Paths actually walked:
  * *The stint-life app surface* — re-walked independently of the plan's claim, reading
    `infer.ts:29`, `degradation-simulator/transform.ts:219`,
    `DegradationSimulatorChart.tsx:391`, and `LifeGauge` at `:165-181`. Confirmed: one
    decimal, 40-lap bar, red ≤3 / amber ≤8 / green. The plan's Corrections §1 is right.
  * *The mart diff* — read `git diff transform/models/marts/fct_cliff_prediction_features.sql`
    in full rather than trusting `ml_headroom_ii.md` §8's "one model" blast radius. It
    adds `cliff_horizon` + `cliff_scan` and rewrites the label CASE; it touches no feature
    column and does not change `is_training_eligible`. This is what makes Corrections §4's
    structural proof safe to rely on.
  * *The consumer audit* — read all four cliff-class lookup sites and the confusion-matrix
    colour function, not just grep counts.
  * **Assumed, not verified:** that `9d6b7d4` / `bd0ce6b` are the *specific* commits that
    moved the mart between v4 and now. What is verified is that the movement predates the
    relabel and cannot come from it; the attribution to those two commits is inference
    from their subject lines and their position upstream of the mart. If it matters to
    someone later, rebuild at `e5bcd35^` and diff the fingerprint.
  * **Not verified:** the app was not run. Parity was proven numerically
    (`scripts/dump_parity_rows.py` against real 2024 laps), and the consumer review was by
    reading, not by screenshot. Nobody has *looked* at the gauge or the scoreboard since
    the class shares moved.

  **3. Gates run.**

  | Gate | Result |
  | :--- | :--- |
  | `dbt test --select assert_cliff_class_horizon_partition` | PASS (0.13s) |
  | `make ml-features` | CLEAN — forward-window, leakage guard, 42 features |
  | `make ml-evaluate` | 5/5 beat baseline (`all_beat_baseline=True`) |
  | `make ml-onnx` | parity OK ×5, worst rel 6.21e-05 / abs 2.29e-05 |
  | `make ml-test` | 25 passed, 3 skipped |
  | `make app-parity` | 48 laps, maxAbs 1.049e-05, cliffMismatches 0 |
  | app unit tests (`src/ml` + 3 consumer features) | 131 passed, 1 skipped |
  | `docs_audit.py --headers` | PASS, 0 errors 0 warnings |
  | `docs_facts.py` | PASS |
  | `ingestion/overview/transform/ml _docs_facts.py` | PASS ×4 |

  **4. Open decisions blocking Phase 2.** None. Phase 2 needs Phase 1 *committed* first,
  which is the user's call and the one thing this session cannot do.

  **5. First command for the next session:**

  ```
  python -m ml.src.tune --target cliff_classifier --version v5 --trials 50
  ```

  Its floor is **0.3888 CV macro-F1** (v5 at the params that were searched against the
  broken label). Anything below that, keep Phase 1's booster and record why.
  *Restated 2026-08-23 to **0.3889** by the option-(a) retrain — see the third checkpoint.
  Left as written rather than edited, per the protocol these checkpoints follow.*

- 2026-08-23 (Phase 4): **complete, nothing committed.** Ran out of order — Phase 2
  needs Phase 1 *committed* first, and only the user can do that, so this phase (declared
  independent of 1–3) took the gap.

  **1. What landed.**
  *Housekeeping:* `transform/seeds/tyre_allocations.csv` deleted, with its rows removed
  from `transform/seeds/README.md` and the add-a-season runbook in `transform/README.md`.
  `pressure_hpa` staged in `stg_weather`.
  *The mart:* `next_3/5_lap_cumulative_jump_s` repaired — arithmetic, drift subtraction,
  lap-density guard, and the 0-floor replaced by symmetric ±10·k bounds.
  *A defect found in flight:* `stg_telemetry` now projects `session_time_s`, and
  `int_lap_telemetry_aggregates` orders on `(distance_m, session_time_s)` — Corrections §7.
  *Gates:* `ml/tests/test_manifest_contract.py` (new, 10 tests); `audit_forward_window`
  repaired and extended, plus 2 new tests in `test_features.py`;
  `snapshot_data_profile.py` rewritten with category shares and a refused-stale-baseline
  check; `docs_facts.py` patterns de-hardcoded and reconciled against generated
  authorities; `ml_docs_facts.py`'s dead `live_pytest_count` wired in and its AST reader
  fixed; `overview_docs_facts.py` updated for the new pattern shape.
  *Numbers corrected:* README 60→67 models, 443→553 tests; ML tests 28→40 across README,
  `docs/ml/overview.mdx` and the generated snippets; `methodology.tsx` 38→42 features and
  XGBoost 3.2.0→3.3.0; the same version in `ml/model_card.yml`'s D1 deviation.
  *Baselines regenerated:* `data_profile.baseline.json` (now schema v2),
  `model_hashes.baseline.json`.

  **2. Verified vs assumed.** Paths actually walked:
  * *The cumulative-jump repair* — recomputed both columns in pandas from
    `int_lap_residual_decomposed` + `int_lap_residual_stint_detrend` at true lap offsets,
    an independent path rather than the mart's own CTEs. Null-pattern agreement 1.0000,
    max |diff| 2.2e-14 / 3.2e-14 on a 5,000-row sample. The `6·mean(j1)` ≈ `mean(k3)`
    identity also holds (−1.17 vs −1.21, the gap being the different row populations).
  * *The fingerprint move* — not assumed to be my edit. Stashed the SQL, rebuilt, got a
    *third* fingerprint, and diffed the matrices column by column. That is what turned an
    apparent self-inflicted change into Corrections §7.
  * *Every new gate was fired, not just written.* The categorical profiler was replayed
    against a synthetic 9,405-row class move; the version gate against a reconstructed v1
    manifest (all three load-bearing assertions fire); the self-join detector against
    `laps_until_cliff`; the coverage assertion against a parse-only manifest. A gate that
    has never been seen to fail is not known to work — that is the lesson of §5/§6/§8.
  * **Assumed, not verified:** that `(distance_m, session_time_s)` remains unique for
    seasons not yet ingested. Verified exhaustively for 2018–2024 (59.5M rows, zero ties,
    zero nulls); a new season could in principle break it, and nothing asserts it.
    A `unique_combination_of_columns` test on `stg_telemetry` would close that.
  * **Not verified:** the app was not run. Parity was proven numerically; nobody has
    *looked* at the gauge or the scoreboard. Unchanged from the Phase 1 handoff.

  **3. Gates run.**

  | Gate | Result |
  | :--- | :--- |
  | `dbt build` (dev, `stg_telemetry+ stg_weather+ fct_cliff_prediction_features+`) | 387 PASS, 0 ERROR |
  | `dbt build` (ci target, fixtures) | 627 PASS, 0 ERROR |
  | `dbt test --select test_type:singular` (ci) | 49 PASS |
  | `snapshot_model_hashes.py --check` | flagged only the intended models; baseline regenerated, re-check OK |
  | `make ml-features` | CLEAN — 21/21 models parsed, 42/42 features resolved, 42 features |
  | `make ml-test` | **37 passed, 3 skipped** (was 25/3) |
  | `make app-parity` | 1 passed |
  | app unit tests (`src/ml`, `model-metrics`) | 35 passed, 1 skipped |
  | `data-profile-check` | no drift, 15 tables, schema v2 |
  | `coefficients` pytest | 66 passed |
  | `docs_audit.py --headers` | PASS, 0 errors 0 warnings |
  | `docs_facts.py` | PASS — all 5 facts now reconcile against a generated authority |
  | `make docs-coverage-check` | PASS ×4 generators |
  | `sqlfluff lint` (the 4 SQL files touched) | clean |

  **4. Open decisions blocking the next phase.** One, and it is a judgement call:

  > **The mart moved after Phase 1's models were trained.** Corrections §7's fix changed
  > 6 telemetry features on **492 of 114,270 training rows (0.431%)**, and the
  > cumulative-jump repair changed two target columns no model reads. The five v5
  > boosters, the predictions parquet and the ONNX exports were all produced from the
  > pre-fix mart. Options: **(a)** `make ml-retrain` → `ml-evaluate` → `ml-predict` →
  > `ml-onnx` → `ml-card` → `app-models` → `app-parity` before committing, so the commit
  > is internally consistent; **(b)** commit as-is and let Phase 2's retrain absorb it,
  > accepting that between the two commits the artefacts do not match the SQL beside them;
  > **(c)** split — commit Phase 4's gates and doc fixes now, hold the telemetry fix for
  > its own commit with the retrain. (a) is the cheap and honest one: a retrain at
  > existing tuned params is one command and no search.

  **5. First command for the next session:** whichever of the above the user picks. If
  (a):

  ```
  make ml-retrain && make ml-evaluate && make ml-predict && make ml-onnx && make ml-card
  ```

  Phase 2 still starts at
  `python -m ml.src.tune --target cliff_classifier --version v5 --trials 50`, floor
  **0.3888 CV macro-F1** (restated to **0.3889** on 2026-08-23), and still needs Phase 1
  committed first.

  **Not done, and deliberately:** 8 SQL models fail `sqlfluff lint` on `main`
  (`int_compound_cliff_predicted`, `int_driver_circuit_affinity`,
  `int_driver_circuit_era_affinity`, `int_stint_geometry`, `int_track_evolution`,
  `int_track_geometry`, `fct_ghost_car_pace`, `mart_corner_skill_driver`). None is a file
  this session touched; `make transform-check` therefore fails at its lint step before
  reaching the build. Pre-existing debt, left alone rather than folded into an already
  large diff — but it means the one-command CI reproduction does not currently pass, and
  someone should clear it.

- 2026-08-23 (mart-consistency retrain, option **(a)**): **complete, nothing committed.**
  The open decision left by the Phase 4 checkpoint is closed. Option (a) was taken: the
  five boosters were retrained at their existing tuned params so the artefacts in the tree
  describe the mart in the tree. No new search, no source change — `*_best_params.json` is
  untouched.

  **1. What landed.** Five v5 `.bst` retrained, five v5 `.onnx` re-exported,
  `ml/models/manifest.json`, `ml/artefacts/evaluation_metrics.json`,
  `ml/model_card.yml` + `ml/models/model_card.json`,
  `data/marts/mart_degradation_predictions.parquet`, the six ML inventory snippets, the
  generated ML reference page, `app/public/models/*` and the 16 files under
  `app/public/data/`. Hand-written metric prose that the retrain moved was corrected in
  `docs/ml/{models, cohorts, calibration, validation}.mdx` and `docs/ml/ci/leakage-spine.mdx`.

  **`make app-data` is not in the plan's (a) chain and had to be.** The chain as written
  stops at `app-models`, which copies the `.onnx` only. The predictions parquet feeds
  `app/public/data/ml/mart_degradation_predictions/*.parquet` through a separate export, so
  omitting it would have left the app serving predictions from the pre-fix boosters — the
  exact inconsistency option (a) exists to remove. Same 16 files as Phase 1.

  **2. Verified vs assumed.** Paths actually walked:
  * *The CV deltas were compared log-to-log*, not eyeballed: the five pre-fix v5 training
    logs (`*_v5_20260822T20*.json`) against the five post-fix ones
    (`*_v5_20260823T06*.json`), reading `headline_cv`, `n_train_rows` and `fingerprint`
    off each. Row counts are identical on both targets (114,270 / 120,934); only the
    fingerprint moved, which is what a feature-value change with no row change looks like.
  * *The stale-number sweep was driven from the artefacts, not from memory.* Every
    hand-written figure was re-derived from `evaluation_metrics.json` and the regenerated
    snippets. It turned up **three staleness bugs older than this session**: the
    adversarial-probe accuracy read **0.987** in `docs/ml/validation.mdx` and
    `docs/ml/ci/leakage-spine.mdx` while the generated reference said **0.998**;
    `docs/ml/calibration.mdx` was never updated by Phase 1 at all and still carried v4
    coverage (0.814 / 0.805); and the cohort table in `docs/ml/cohorts.mdx` listed **13**
    rows while the model card counted **14** — the missing cell is
    `is_rain_lap`/`_other` on p50. All four fixed, the table now matching the generated
    authority row for row.
  * *The forward-window audit was re-fired after `dbt parse`*, i.e. against exactly the
    null-`compiled_code` manifest that Corrections §6 showed it used to go silently hollow
    on. Still CLEAN, so the on-disk compiled fallback is doing the work.
  * **Assumed, not verified:** that the ≤0.19% CV movement is entirely Corrections §7's
    492 changed rows. It could also carry dev-profile float noise (standing caution 1) —
    the two are not separable without a `ci`-profile rebuild, and at this magnitude the
    distinction does not change anything.
  * **Not verified, still:** the app has not been run. Parity is proven numerically; nobody
    has *looked* at the gauge or the scoreboard. Unchanged from the Phase 1 and Phase 4
    handoffs, and now three sessions old.

  **3. Gates run.**

  | Gate | Result |
  | :--- | :--- |
  | `ml.src.features --check` (before retrain) | CLEAN, 42 features, 114,270 rows |
  | `make ml-retrain` | 5/5 at tuned params, cliff CV **0.3889** |
  | `make ml-evaluate` | 5/5 beat baseline (`all_beat_baseline=True`) |
  | `make ml-predict` | 137,447 rows at v5, crossing 0.31% |
  | `make ml-onnx` | parity OK ×5, worst abs 2.29e-05 (stint life) |
  | `make ml-test` | 37 passed, 3 skipped |
  | `make app-parity` | 48 laps, maxAbs **1.335e-05**, cliffMismatches 0 |
  | app unit tests (`src/ml` + 3 consumer features) | 131 passed, 1 skipped |
  | `data-profile-check` | no drift, 15 tables |
  | `ml.src.features --check` (after `dbt parse`) | CLEAN — §6's fallback re-proved |
  | `docs_audit.py --headers` | PASS, 0 errors 0 warnings |
  | `docs_facts.py` | PASS, all 5 counts reconcile |
  | `make docs-coverage-check` | PASS ×4 generators |

  `app-parity`'s worst absolute error moved 1.049e-05 → 1.335e-05. That is a different
  booster, not a widening gap: `ml-onnx`'s own five-way parity is unchanged in shape and
  the tolerance is 1e-04.

  **4. Open decisions blocking the next phase.** None. Phase 2 needs Phase 1 *committed*,
  which is the user's call and the one thing these sessions cannot do.

  **5. First command for the next session:**

  ```
  python -m ml.src.tune --target cliff_classifier --version v5 --trials 50
  ```

  Floor is now **0.3889 CV macro-F1**.

- 2026-08-23 (Phase 2): **complete, nothing committed.** Ran against `7f23d8c`, the user's
  commit of Phases 0/1/4 — so this phase's result is attributable to params alone, which is
  the whole reason the phase was gated on a commit.

  **1. What landed.** `ml/models/cliff_classifier_best_params.json` (the only source diff),
  `cliff_classifier_v5.bst`, a new training log, and everything downstream of a changed
  booster: `ml/artefacts/evaluation_metrics.json`, `ml/models/manifest.json`,
  `ml/model_card.yml` + `model_card.json`, `data/marts/mart_degradation_predictions.parquet`,
  five re-exported `.onnx`, the six ML inventory snippets, the generated ML reference page,
  `app/public/models/*` and the files under `app/public/data/`. Two hand-written metrics
  corrected — see §2. `ml/models/optuna_studies/cliff_classifier_v5.db` is gitignored.

  **2. Verified vs assumed.** Paths actually walked:
  * *The floor comparison was proved like-for-like before being believed.* The refit's
    `headline_cv` equals `study.best_value` to <1e-12 (0.3918093350), on the same 114,270
    rows and the same fingerprint `05aca16f1dc5a9e0` as the floor's log. That identity is
    what establishes the search and the shipped booster are the same estimator; without it
    `best_value` and the floor are two different computations and the comparison is void.
  * *The margin was decomposed per fold rather than read off the mean.* 4 wins / 1 loss:
    2020 **−0.0041**, 2021 +0.0022, 2022 +0.0029, 2023 +0.0049, 2024 **+0.0089**. The gain
    rises monotonically across 2021→2024 and the single loss is fold 0, which under the
    expanding window trains on 2018–2019 only. So it is not one season carrying the result.
  * **The +0.75% is NOT statistically separable from fold noise.** Paired t-test on the five
    fold deltas: mean +0.0029, sd 0.0047, **t=1.386, p=0.24 (n=5)**. It beats the floor and
    the plan's rule says ship, so it shipped — but it must not be quoted as a demonstrated
    improvement the way Phase 1's +15.3% can be. Recorded here so the next session inherits
    the caveat rather than the headline.
  * *The stale-number sweep was driven from the artefacts.* It found **two** hand-written
    figures, one of them older than this whole series:
    `docs/ml/models.mdx:108` read macro-F1 **0.395** (Phase 1's value) → **0.404**; and
    `docs/decomposition/limitations.mdx:41` read **≈0.32**, a **v4-era number** that
    survived Phase 1 *and* the mart-consistency retrain because both sweeps scoped
    themselves to `docs/ml/` and `README.md` → **≈0.40**.
  * **Assumed, not verified:** that the four non-cliff models are untouched. Structurally
    they must be — only `cliff_classifier_best_params.json` changed and each model trains
    from its own params file — but their boosters were not rebuilt, so this rests on the
    same §4 argument rather than on a fresh measurement.
  * **Not verified, still:** the app has not been run. Parity is proven numerically only;
    nobody has *looked* at the gauge or the scoreboard. Now four sessions old.

  **3. Gates run.**

  | Gate | Result |
  | :--- | :--- |
  | `tune --target cliff_classifier --trials 50` | 32 complete / 18 pruned, best **0.391809** |
  | refit `headline_cv` vs floor | **0.391809** vs 0.388878, **+0.75%** |
  | `make ml-evaluate` | 5/5 beat baseline; cliff **0.40375** vs baseline 0.22413 |
  | `make ml-predict` | 137,447 rows at v5, crossing 0.31% |
  | `make ml-onnx` | parity OK ×5, worst abs 2.29e-05 (stint life) |
  | `make ml-card`, `make ml-reference` | written |
  | `make app-data` | 37 tables, 344.91 MB, manifest `5a6ca6873bbbfe5b` |
  | `make app-models` | five v5 `.onnx` + manifest + card |
  | `make app-parity` | 1 passed |
  | `make ml-test` | 37 passed, 3 skipped |
  | app unit tests (`src/ml` + 3 consumer features) | 131 passed, 1 skipped |
  | `data-profile-check` | no drift, 15 tables |
  | `docs_facts.py` / `docs_audit.py --headers` / `docs-coverage-check` | PASS |

  **4. Open decisions blocking the next phase.** None blocking, but three findings from
  this phase should be scheduled, all of them the "gate that cannot fail" shape §5–§8
  describe:

  > **(i) `tune.py` searches the three quantile regressors against an estimator the
  > pipeline does not ship.** `tune.py:68` fits with `T._sample_weight(spec, y[tr])` — no
  > meta — while `train.py:126` fits with `_sample_weight(spec, y[tr], bundle.meta_train.iloc[tr])`.
  > For `kind == "quantile"` that meta argument is the sole source of the C2 IPW
  > `survival_weight`, which is far from inert: range **1.027–4.0, mean 1.84, zero rows at
  > exactly 1.0**. So `make ml-tune` (which is `--target all`) selects hyperparameters for an
  > unweighted model and then ships a weighted one. `_headline` is unweighted in *both*
  > paths, so the metric is not the discrepancy — the **fit** is. Exactly 3 of 5 targets are
  > affected: classification derives its weights from `y` alone, and `stint_life_regressor`
  > is plain regression, so both are identical across the two paths. This is also why the
  > Phase 2 identity check above matters — it holds for the classifier and would *not* hold
  > for p10/p50/p90.
  >
  > **(ii) `tune_one` cannot keep the incumbent.** It writes `best_params.json` and chains
  > `train_one` unconditionally, comparing against nothing. The checklist line "if the tuned
  > model does not beat the floor, keep Phase 1's" is a manual `git restore`, not a
  > behaviour of the tool. A floor check in `tune_one` — or at minimum a printed comparison
  > against the incumbent log — would close it.
  >
  > **(iii) The search stopped on a range boundary.** `_suggest` caps `n_estimators` at 700
  > and the winner chose exactly **700**, so the optimum is at the edge of the grid and this
  > is a truncated search, not a converged one. Any future re-run should widen that bound
  > before reading the result as a ceiling.

  **5. First command for the next session:** Phase 3 is next and starts with a product
  decision (3a), not a command. If the user wants a code start instead, Phase 5 is
  independent:

  ```
  sed -n '200,230p' transform/models/intermediate/int_pit_strategy_value.sql
  ```

  **New floor for any future cliff re-tune: 0.391809 CV macro-F1** — but see (iii); the
  incumbent was found at a boundary, so a wider grid is the honest next attempt.

## Checkpoint 2026-08-23 (Phase 3 — code complete, chain **not** finished)

**Read the next section before running anything. The tree is mid-chain, which is a
departure from every previous checkpoint in this file.**

### What landed

Phase 3a/3b/3c/3d are implemented and their code paths are verified end-to-end **at
`smoke`**. The production `v6` boosters are trained. Everything downstream of them —
evaluation, predictions parquet, ONNX, manifest, model card, app copies — is **stale or
absent**. Nothing is committed.

New files: `ml/src/survival.py`, `ml/tests/test_survival.py`, `app/src/ml/survival.ts`,
`app/src/ml/survival.test.ts`, `transform/tests/assert_stint_censoring_partition.sql`.

Also touched, not obviously part of the phase: `tune.py` (searches the AFT scale; would
otherwise crash on the survival target), `dump_parity_rows.py` (AFT ground truth),
`card.py` (survival block, no more RMSE), `test_onnx_parity.py` (version fallback).

The AFT contract lives in exactly two places by design — `ml/src/survival.py` and its
browser mirror `app/src/ml/survival.ts` — because the phase's stated headline risk was the
post-transform being copied into three files and applied to two. `train.py`, `predict.py`,
`evaluate.py`, `export_onnx.py` and `dump_parity_rows.py` all import the Python one.

| Area | Change |
| :--- | :--- |
| SQL | `is_censored_stint` on `fct_stint_features` + schema tests + a partition assertion |
| Model | `survival:aft`, interval label `[y+1, y+1]` / `[y+1, ∞)`, scale **0.80** |
| Train | `AFTBooster` (the sklearn API cannot carry AFT bounds), `_fit` dispatcher |
| Eval | censored NLL + C-index, `survival_report()`, populations never pooled |
| Export | objective retag → `TreeEnsembleRegressor`, measured+asserted margin offset |
| App | `LifeGauge` median + `[p10,p90]`, colour from p10; scoreboard `StintLifePanel` |
| Schema | predictions parquet 17 → **19** columns (p10/p90 life), `MODEL_VERSION_DEFAULT` → **v6** |

### What was verified vs assumed

Verified by execution, not by reading:

* **The AFT/ONNX round-trip**, before touching production code — four scale/depth/round
  configurations, relative parity < 5e-6 each. This is what disproved the plan's own 3c
  premise (Corrections §9).
* **The censoring flag**, against the real warehouse: 55,926 of 120,934 training rows
  (46.25%) censored, 2,264 zero-life rows of which 2,236 (98.8%) censored. The plan's
  "2,264" was right; an earlier figure of 1,894 in this session was a wrong row filter
  (`race_year < 2024` instead of the true training set) and has been corrected everywhere.
* **The scale sweep**, at production params, season-grouped CV — the number moved from the
  plan's ≈0.5 to 0.80.
* **`probit` in TypeScript against `scipy.stats.norm.ppf`** at nine quantiles to 8 dp. The
  band is computed by two independent implementations; the median-only parity check could
  never have seen them diverge.

Assumed / **not** verified:

* **No v6 number in this checkpoint is a production number.** The 2.0905 NLL is the CV
  headline from the training log. `make ml-evaluate` at v6 has **not** completed.
* `make app-parity` and `make app-e2e` have **not** run. The browser has never scored a v6
  ONNX graph — only a `smoke` one.
* The censoring definition ("driver's last stint of the race") is a modelling choice, not a
  measurement. It is not the same event as `transform/tasks/coefficients/survival.py`'s
  cliff-censoring, which is about time-to-cliff; both now exist and mean different things.

### Gates run

| Gate | Result |
| :--- | :--- |
| `dbt run/test --select fct_stint_features assert_stint_censoring_partition` | **11/11 pass** (first run failed 2 — that is Corrections §10) |
| `pytest ml/tests/test_survival.py` | **18 pass** |
| `pytest ml/tests` (full) | **8 failed, 55 passed, 1 skipped** — all 8 are the stale-chain cause below |
| ONNX parity, all five, `smoke` | **pass**; stint-life abs 1.07e-04 / rel 2.33e-06 |
| `npm run typecheck` (app) | **clean** |
| `npx vitest run` (app) | **337 pass, 1 skipped** (312 before; +18 `survival.test.ts`, +7 scoreboard censoring) |
| `make ml-evaluate` at v6 | **killed mid-run** at session end |
| `make app-parity` / `app-e2e` | **not run** |

All 8 failures are the half-run chain, not defects. Three groups, one cause each:

* `test_onnx_parity[stint_life_regressor]` — with no v6 `.onnx` on disk the test falls back
  to v5, whose stint-life booster is still `reg:squarederror`, and `aft_params` **refuses**
  it. That refusal is the gate working exactly as intended; it clears when v6 exports.
  **Caught while writing this handoff:** bumping `MODEL_VERSION_DEFAULT` v5 → v6 silently
  dropped **v5** out of `_present_version()`'s hardcoded fallback tuple — v5 had only ever
  been reachable *as* the default — so the fallback skipped straight to v4, the rollback
  target became unreachable, and nothing said so. `"v5"` is now named explicitly and the
  comment warns the next bump to do the same.
* `test_manifest_contract` ×2 — `ml/models/manifest.json` names **`smoke`** (my last export)
  while `app/public/models/` still holds the committed **v5**.
* `test_evaluate` ×5 — `ml/artefacts/evaluation_metrics.json` is a single-target `smoke`
  report left by a debug run, so four of five models are absent from it.

Finishing the chain resolves all eight. **Do not "fix" the tests.**

**A caution about `npx tsc --noEmit`**: it reports success while checking nothing, because
`app/tsconfig.json` is solution-style with `"files": []`. Use `npm run typecheck`. Run
against the real config it found two genuine errors that the bare command had hidden.

### The first command the next session should run

```
./.venv/bin/python -m ml.src.evaluate --all      # v6; takes a while, elevations included
./.venv/bin/python -m ml.src.predict --out data/marts/mart_degradation_predictions.parquet
make ml-onnx && make ml-card && make ml-reference
make app-data && make app-models && make app-parity && make app-e2e
./.venv/bin/python scripts/ml_docs_facts.py --write
./.venv/bin/python -m pytest ml/tests -q
```

Then re-read the two doc surfaces that still quote the old model: `docs/ml/models.mdx` has
been rewritten by hand for the survival framing, but **`docs/reference/ml/degradation-model.mdx`
and `docs/snippets/ml-inventory-metrics.mdx` are generated** and still say
`regression / rmse / 7.7278`. `make ml-reference` and `ml_docs_facts.py --write` regenerate
both; check they pick up `aft_nloglik` rather than silently keeping a stale row.

---

## Checkpoint 2026-08-23 (Phase 3 — chain finished, tree consistent)

**The half-run state the previous checkpoint warned about is gone.** The v6 chain ran to
completion in the prescribed order, and `ml/models/manifest.json` no longer names `smoke`.

### What landed

No new feature work. This session ran the chain the previous handoff specified, then fixed
the three things the chain's own gates caught on the way through. Still nothing committed.

Source changes, all of them gate repairs rather than model work:

| File | Change |
| :--- | :--- |
| `ml/src/card.py` | Card now carries `higher_is_better` per model, straight from `evaluation_metrics.json` |
| `scripts/gen_ml_reference.py` | `_arrow()` reads that flag; **raises** if absent instead of guessing from the metric name |
| `scripts/ml_docs_facts.py` | `TEST_GROUPS` corrected: targets 1→3, version contract 10→14, **survival group (18) added**, predict-schema prose 17→19 columns |
| `transform/tests/README.md` | `assert_stint_censoring_partition.sql` registered under Domain Constraint |
| `README.md`, `docs/ml/overview.mdx` | ML tests 40→64, dbt tests 553→556, stale `v5 model` → `v6` |

Regenerated artefacts: `evaluation_metrics.json`, predictions parquet, five v6 `.onnx`,
`ml/models/manifest.json`, model card, `app/public/models/*`, `app/public/data/*`, the ML
reference doc, six ML inventory snippets, four transform inventory snippets.

### What was verified vs assumed

Verified by execution:

* **All five v6 models beat baseline** — `all_beat_baseline=True`. p10 0.0934/0.1636,
  p50 0.1995/0.2887, p90 0.1235/0.1556, cliff macro-F1 0.4038/0.2241 (eval; CV 0.3918
  matches Phase 2), stint-life AFT NLL 1.9397/2.1870, C-index 0.7863 vs 0.6293.
* **The browser scored a real v6 AFT graph.** Previously only `smoke` had been proven.
* **The generated docs moved off the old framing** — checked by grep, not assumed:
  `regression / rmse / 7.7278` is gone from both surfaces, replaced by `survival /
  aft_nloglik`.
* **Predictions parquet: 137,447 rows, crossing 0.31%** — identical to Phase 1's figures.

Assumed / not verified:

* **The CDN is still v5.** Nothing was published. Local e2e passes because `.env.local`
  forces same-origin; a CI run of the same target smokes the stale CDN. Publishing is a
  deliberate, user-owned step and was not taken.
* Season-2025 holdout remains unpopulated; every eval number is the 2024 CV final fold.

### One number worth reading carefully

`stint_life_regressor` beats baseline on the headline, but the gain is **almost entirely on
censored rows**: censored NLL 0.3866 vs baseline 0.8857, uncensored 3.3908 vs 3.4027 — a
0.35% improvement on the stints that actually ended. Uncensored median absolute error is
4.98 laps. The C-index is genuinely strong, so the model *ranks* risk well; it is not much
sharper than the group-mean at putting a likelihood on a completed stint. The ablation says
the same thing from the other side: only `stint_position` matters (+0.1156 NLL when
dropped); `track`, `powertrain`, `context` and `telemetry_cliff` all score marginally
*better* when removed. The learning curve is still descending at six seasons.

Also recorded, not acted on: the monotonicity probe reports **5 violations over 19 steps**
in `laps_past_cliff` — predicted life is not monotone non-increasing as a stint goes further
past the cliff. That is a plausible-looking defect and it is not investigated.

### Gates run

| Gate | Result |
| :--- | :--- |
| `ml.src.evaluate --all` (v6) | **5/5 beat baseline**, `all_beat_baseline=True` |
| `ml.src.predict` | **137,447 rows**, crossing 0.31%, version=v6 |
| `make ml-onnx` | **parity OK all five**; stint-life abs 2.83e-04 / rel 3.20e-06 |
| `make ml-card`, `make ml-reference` | written; direction arrow corrected |
| `make app-data` | 37 tables, 347.33 MB, manifest hash `53c974277c179843` |
| `make app-models` | five v6 `.onnx` + manifest + card copied |
| `make app-parity` | **pass** — 48 laps, maxAbs 3.228e-04, 0 cliff mismatches |
| `make app-e2e` | **5/5 pass** (needed `make app-e2e-install` first — Chromium was absent) |
| `pytest ml/tests` | **64 passed, 0 failed, 0 skipped** (was 8F/55P/1S) |
| `npm run typecheck` | **clean** |
| `npx vitest run` (app) | **337 passed, 1 skipped** — unchanged |
| `docs_audit.py --headers` | **PASSED** — 0 errors, 0 warnings |
| `docs_facts.py` + all four `*_docs_facts.py` | **PASSED** after the count repairs |

The previous checkpoint predicted that finishing the chain would clear all 8 failures with
no test edited. **That held exactly** — no test file was touched, and the 3 former skips now
run because the v6 artefacts exist.

### Three gates that were lying, and are not any more

Same family as Corrections §5/§6/§8, found the same way — by running the thing rather than
reading it.

1. **`gen_ml_reference.py` labelled `aft_nloglik` as "↑ higher better".** It tested the
   metric name against a hardcoded `("pinball", "rmse")` tuple and fell through to
   higher-better for anything unrecognised. A negative log-likelihood is emphatically
   lower-better, `evaluation_metrics.json` said so in a field the renderer never read, and
   the *same generated page* contradicted itself — the card's prose already said
   "censored AFT NLL ↓". Fixed at the source: the flag is propagated and the renderer
   raises rather than guesses.
2. **`ml_docs_facts.py`'s `TEST_GROUPS` was four discrepancies deep, not one.** It knew
   about 40 tests against a live collection of 64. `test_survival.py` (18) was missing
   entirely, `test_manifest_contract` was 10 not 14, `test_targets` was 1 not 3 — and that
   group's *description* still described a degradation-bounds test that no longer exists in
   the file. This gate did fire loudly, which is why it is on this list rather than in it.
3. **`assert_stint_censoring_partition.sql` was never registered** in
   `transform/tests/README.md`, so `transform_docs_facts.py` refused to generate. Phase 3
   wrote the test and ran it; nothing connected it to the inventory. Registering it moved
   the dbt total 553 → 556 (the singular assert plus two censoring schema tests), which
   README had been quoting in five places.

### The first command the next session should run

Phase 5 is untouched and independent of everything above. Start by reading the current
threshold, which is the thing being replaced:

```
sed -n '200,230p' transform/models/intermediate/int_pit_strategy_value.sql
```

Before any of that, though: **the tree is now consistent and is the natural commit point.**
Phases 2 and 3 are both sitting uncommitted.

---

## Checkpoint 2026-08-23 (Phase 5 — Total_Cost(L) implemented; the series is complete)

**Every phase 0-5 is now done.** Phase 5 was the only item in the series that adds a
capability rather than repairing a number, and it is the last one open.

### What landed

| File | Change |
| :--- | :--- |
| `int_pit_strategy_cost_curve.sql` | **New model.** One row per (stint, horizon, candidate lap): the `Total_Cost(L)` surface, 386,036 rows |
| `int_pit_strategy_value.sql` | Rewritten as the argmin over that curve. Every existing output column preserved; five added |
| `assert_pit_loss_pushes_optimum_later.sql` | **New test.** Re-minimises the curve at +15 s of pit lane; fails if the optimum moves earlier |
| `assert_pit_discount_monotone.sql` | **New test.** The SC discount is non-increasing in the candidate lap |
| `fct_stint_features.sql` | `tyre_management_score` clamped on both sides — see "three findings" below |
| `dbt_project.yml` | Six new vars, each with the measurement behind its default |
| `app/src/ui/charts/Gantt.tsx`, `pit-strategy/{transform,methodology,PitStrategyGanttChart}` | `early` / `undercut_forced` no longer coerced to null |
| `transform/tests/README.md`, `intermediate/README.md`, both `schema.yml` | Registered and documented |
| `docs/transform/families/strategy.mdx`, `docs/app/pit-strategy.mdx`, `README.md` | Prose moved off the threshold framing; counts 67→68 models, 553→577 tests |

### The cost function, and why the SC hazard is not decoration

```
Total_Cost(L) = cum_wear_old(L) + cum_wear_new(H-L) + baseline_delta*(H-L)
              + pit_lane_loss_s * [1 - (1-m)*(1 - (1-h)^L)]
```

`L = H` is the no-stop candidate and pays no pit term. **The plan's own framing of this
step was incomplete**, and it is worth recording as Corrections §11: "carry pit loss into
the search" does not by itself give a longer pit lane any effect. Under a fixed one-stop
over a fixed horizon the loss is the same whenever you take it, so it adds a constant to
every candidate and cancels out of the argmin exactly. The differencing shows it —
`d/dL = wear_old(L+1) - wear_new(H-L)`, with no pit term in it at all. What breaks the tie
is the safety car: a caution stop costs a fraction of a green-flag one, and waiting raises
the odds one has appeared. That is what makes waiting pay in proportion to pit-lane length,
and it is why `int_sc_hazard_history` had to be consumed here rather than merely joined.

### What was verified vs assumed

Verified by execution:

* **`optimal` 8 → 715, `unknown` 2,231 → 266.** The acceptance number the plan set.
  Full distribution: 1,795 `early`, 1,218 `overran`, 715 `optimal`, 266 `unknown`,
  143 `undercut_forced`, 2,992 NULL (no stop to grade).
* **Both new gates fail when they should.** Setting `pit_sc_loss_multiplier: 1.5` inverts
  the discount and returns 364,760 / 1,365 rows. A gate that cannot fail is not a gate.
* **The blast radius is one table, and both changed columns were traced to their consumers,
  not grepped for.** The oracle reports exactly one drifted `fct_*` model
  (`fct_stint_features`) and one non-fct (`int_pit_strategy_value`). `fct_stint_features`
  takes `pit_decision_class` **and** `tyre_management_score` from the strategy model — the
  second one via `opportunity_cost_s`, which the header does not mention. `ml/src/features.py`
  reads exactly `stint_id, stint_length_laps, is_censored_stint` from that table, so
  **neither reaches the ML feature set and no retrain is implied.** Both are consumed by
  the `pit-strategy` app feature only.
* **Median `overrun_laps` is -1**: teams stop one lap earlier than a degradation-only
  optimum. That is a sane result, not a bug — it is roughly what track position is worth.

Assumed / not verified:

* The SC cost multiplier (0.5) is the conventional figure and **has not been fitted here**.
  It sets how fast the pit term decays, so it moves the optimum; nothing measures it.
* The counterfactual assumes exactly one stop inside its horizon and that the next set is
  fitted new. Used sets exist and the stint table cannot see them.
* Nothing is published. The CDN is still on v5 artefacts and now also on the old strategy
  numbers.

### Three findings, each found by running the thing rather than reading it

1. **`undercut_forced` was not measuring the undercut.** The branch asked whether the
   gap ahead had *ever* dropped below a pit stop during the stint — true for 95.5% of
   stints — so on first build it swallowed 1,788 of the 1,856 early-side stints and left
   `early` with 68, every one of them simply a stint with no threat lap at all. The same
   species of defect as the 8-`optimal` one this phase was chartered to fix, and it was
   pre-existing: the old model almost never reached the branch, so it never showed. Now
   the stop must land inside `[threat - 2, threat + 3]`. 1,788 → 143.
2. **The cliff polynomial has nothing holding its tail down.** Extrapolated to age 80 it
   reaches **136 s/lap**, which produced a 1,314 s opportunity cost on the first build. It
   is not only an extrapolation artefact — the fitted curve already emits up to **93 s/lap
   on laps that were actually run**, p99 30.8 s/lap. Capped at
   `pit_strategy_max_wear_s_per_lap` (10.0, against real cliff falloff of 1-3 s/lap).
   Max opportunity cost 1,314 s → 345 s, median 5.5 s. **The cap is in this model only;
   `int_compound_cliff_predicted` is unchanged and still unbounded.**
3. **`tyre_management_score` had a ceiling and no floor.** It is
   `end_residual_s / opportunity_cost_s` under a `LEAST(x, 3.0)` — and a ratio is unbounded
   in whichever direction its denominator approaches zero from. Small positive opportunity
   costs were rare under the overrun-only definition and are ordinary under this one, so
   the score reached **-3321.9**. Nothing tested it, because a one-sided clamp reads as a
   clamp. Now `[-3, 3]` with a bounds test. **738 stints sit on the new floor**, so the
   clamp is bounding a display, not repairing a fragile ratio — see open items.
4. **The app silently dropped two of the five verdicts.** `coerceVerdict` accepted only
   `optimal / overran / unknown` and mapped everything else to null. Harmless while the
   threshold model produced 5 `early` + `undercut_forced` stints across seven seasons;
   this phase produces 1,938, which would have greyed out a quarter of the Gantt. Fixed
   with a regression test that names why.

### Gates run

| Gate | Result |
| :--- | :--- |
| `dbt build --target ci` (fixtures) | **652 PASS / 0 ERROR**, 655 nodes |
| `dbt test` on both strategy models | **30 PASS** |
| Gate liveness (`pit_sc_loss_multiplier: 1.5`) | **both new tests FAIL as designed** |
| `sqlfluff lint models/` | **8 FAIL — the same 8 pre-existing on `main`**, none in the 4 files touched |
| `snapshot_model_hashes.py --check` | 1 `fct_*` drifted (`fct_stint_features`), as predicted; re-snapshotted |
| `data-profile-check` | **7 drifts, all 7 predicted** (5 verdict shares + 2 score stats); re-snapshotted |
| `docs_audit.py --headers` | **PASSED** — 0 errors, 0 warnings |
| `transform_docs_facts.py`, `docs_facts.py` | **PASSED** after 67→68 models, 553→577 tests |
| `app_docs_audit.py --strict` | **PASSED** — 30/30 |
| `npm run typecheck` | **clean** |
| `npx vitest run` (app) | **338 passed / 1 skipped** (was 337; +1 is the new regression test) |
| `make app-data` | 37 tables, 347.41 MB, manifest hash `15a491f5366d5763` |

### Open decisions blocking the next phase

None — Phase 5 was the last phase. Three things are worth a decision before this ships:

1. **`pit_strategy_baseline_delta` is `true`, on the user's explicit instruction, and it
   carries an unmeasured term.** `compound_grip_peak` and `compound_optimal_temp_low` are
   per-compound *constants* in the seed — one distinct value each across all 403 rows,
   never fitted — while `wear_gradient`, `cliff_onset` and `cliff_severity` genuinely vary
   (37-79 distinct values each). As typed, `grip_peak` prices SOFT (1.03) **slower** than
   HARD (0.97), which is backwards, and over a 20-lap arm it is ~1.2 s of offset pushing
   against fitted effects of the same size. Flipping the var to `false` drops the term; it
   is one line and no rewrite. **The alternative — and the better fix — is to fit a real
   per-compound pace baseline**, which would make the term legitimate rather than absent.
2. **`tyre_management_score` is a fragile ratio, now clamped.** 738 stints on the floor is
   not a healthy distribution. A bounded transform (a signed log, or normalising against
   stint length rather than opportunity cost) would be a repair rather than a bound.
3. **The SC multiplier is unfitted.** `int_pit_loss_circuit` already isolates green-flag
   stops per circuit; the same machinery could measure caution-stop loss directly and
   replace the 0.5 constant with an estimate.

### The first command the next session should run

The series is complete and the tree is consistent. The natural next step is not another
phase, it is the commit — Phases 2, 3 and 5 are all sitting uncommitted together.

```
git status --short | wc -l
```

> **Superseded 2026-08-24.** "The series is complete" was true of Series I and is left standing
> as this checkpoint recorded it. It is no longer the state of the plan: Corrections §12–§17
> reopened the work as Series II (Phases 6–10), and "Open decisions blocking the next phase:
> None — Phase 5 was the last phase" above should now be read as *none blocking, and there is a
> next phase*. The commit is still the correct first action; Series II starts after it.

---

## Measurement 2026-08-24 — where the ceiling actually is

Not a checkpoint: no code landed and no gate ran. This is the evidence block for Corrections
§12-§17, recorded so the next session does not re-derive it. Everything below was measured
against `data/dev.duckdb` (schema `main`, the v6 build) and `ml/artefacts/evaluation_metrics.json`
as they stood on 2026-08-24, with the tree in the uncommitted Phase 2/3/5 state described under
"Resume here".

### What was measured, and how

| Claim | Source | Method |
| :--- | :--- | :--- |
| Target signal shares and autocorrelations (§12) | `main.fct_cliff_prediction_features` | `variance()` of per-`stint_id` means over `variance()` of the column; `corr(y, lag(y))` windowed on `stint_id` ordered by `lap_in_stint` |
| Effective sample 7,094 stints (§15) | same | `count(distinct stint_id)` vs `count(*)` |
| Learning curves (§14) | `evaluation_metrics.json` | read directly from each family's `learning_curve` array |
| Ablation deltas (§16, Phase 9) | same | each family's `ablation` array, `delta_vs_full` |
| Uncensored stint-life 0.35% (§15) | same | `stint_life_regressor.survival.uncensored` vs its baseline |
| Telemetry volume and X non-null (§16) | `data/bronze/telemetry/season=2023` | `read_parquet` count vs `count(X)`, grouped by `Source` |
| `DistanceToDriverAhead` quality (§16) | same, `Source='car'` | null rate, share > 500 m, share with empty `DriverAhead` |
| X/Y consumers (§16) | `transform/models/` | grep; two hits, both static-geometry |
| `race_control` volume and zero consumers (§17) | `data/bronze/race_control/**`, `transform/models/` | group-by on `category` / `Flag`; grep returns nothing |
| Ingestion gaps (§16, Phase 10c) | `ingestion/src/ingest.py`, bronze dirs | session arg accepts `R`/`Q`/`both`; `pos_data` and `telemetry_full` hold 0 files |

### Verified vs assumed

**Verified.** Every number in §12-§17 is a query result or a grep result, re-run against the
current tree, not carried from either audit. The 5-lap column's correctness is *not* assumed —
Phase 4 verified it independently in pandas against `int_lap_residual_decomposed` +
`int_lap_residual_stint_detrend` at true lap offsets (null-pattern agreement 1.0000, max |diff|
3.2e-14), which is what makes §13 a usable finding rather than a suggestion.

**Corrected while writing this block.** The first draft of §12 asserted that "38 of the 42
features are constant or slowly-varying within a stint", which would have made 17.5% a
near-exact ceiling. That was asserted, not measured, and it is **wrong**. Measuring the
between-stint variance share of every numeric feature the same way the target was measured:

| Between-stint share | Count | Examples |
| :--- | ---: | :--- |
| ≥ 90% — constant or near-constant in stint | 15 of 34 | all six numeric `compound` columns, `fuel_mass_kg`, `lap_number`, `track_energy_index`, `n_gear_changes`, `pct_full_throttle`, `mean_rpm` |
| 50–90% | 5 of 34 | `max_rpm`, `lift_coast_share`, both `dirty_air_thermal_load_*`, `traction_wheelspin_proxy` |
| < 50% — genuinely per-lap | **14 of 34** | `push_residual` (12.9%), `surface_bulk_ratio` (22.6%), `laps_past_cliff` (23.2%), `lap_in_stint`, `age_in_stint`, `mid_corner_speed_loss_kph`, `braking_point_drift_m`, both `cumulative_push_load_*`, `dirty_air_share_lap` |

The four categorical features were not measured. Shares above 100% read as
constant-within-stint; the excess is the unweighted variance-of-means estimator on unequal
group sizes, not a real quantity.

So the model **is** equipped to reach into within-stint variance, and `push_residual` — the
top SHAP feature for p50 — is almost entirely a per-lap signal at 12.9% between-stint. The
§12 argument therefore rests on the **autocorrelation**, not on the variance split: the split
bounds what stint-level features can reach, and the −0.094 says there is little structure
beyond it for the per-lap features to find. That is a weaker claim than the first draft made,
and it is the one the evidence supports. **Phase 6 must compute the ceiling per target
properly rather than inheriting 17.5% as though it were exact.**

**Assumed, and still assumed.** That "little structure" is not "no structure". Nothing here
measures how much within-stint variance a per-lap feature set could explain in principle —
the autocorrelation is strong circumstantial evidence, not a bound. **If Phase 7's retarget
underdelivers, this is the assumption to attack first.**

**Not measured.** Whether X/Y actually carries degradation signal. §16 argues from "a different
sensor must carry different information", which is an argument and not a measurement, and it
cannot become one until 10a exists. That is why Phase 10 is sequenced last and scoped to 10a
first.

### One number worth reading carefully

`stint_life_regressor` reports 1.9397 against a 2.1869 baseline, an 11.3% win, and it is the
model this series spent Phase 3 on. Split by censoring:

* **Censored** (n=9,791): 0.3866 vs 0.8857 baseline — a 56% win.
* **Uncensored** (n=10,480): 3.3908 vs 3.4027 baseline — a **0.35%** win, median absolute
  error **4.98 laps**.

The headline blends the two and reads as skill. What the model has actually learned is to say
"this stint is not ending soon", which the group-mean baseline cannot express at all. On the
question a strategist asks — *when does this stint end* — it is a group-mean with extra steps.
C-index 0.786 vs 0.629 says the ranking is genuinely better, so this is not a null result; it is
a narrower result than the headline implies. Phase 6 makes that visible without re-training
anything.

---

## Checkpoint 2026-08-24 (Phase 6 — honest denominators; Series II opened and its first phase closed)

*No model was retrained. Every headline is identical to five decimals. What moved is what
the headlines mean — and three numbers this plan was resting on.*

### What landed

* **`ml/src/ceiling.py`** — the ceiling arithmetic. One-way random-effects (ANOVA) variance
  components, a Gini variant for the categorical target, within-stint lag-1, non-overlapping
  thinning for rolling-window targets, the analytic pinball ceiling `1 − √(1 − ICC)`, and
  stint-identity oracles in two forms (in-sample and odd/even cross-fitted).
* **`ml/src/intervals.py`** — paired t, cluster bootstrap, and the width ratio between
  stint-grain and lap-grain resampling. Takes a scoring callable, so the same arithmetic
  serves pinball, macro-F1 and censored AFT NLL without knowing which it has.
* **`evaluate.py`** — an `attainable` and an `interval` block per model, a `stint_grain`
  block and a `claims_inside_noise` list on the report. Both per-model blocks record their
  own failure rather than degrading silently, because the card gate reads them.
* **`card.py`** — `attainable` / `interval` / `beats_baseline_significant` per model,
  `attainable_note` / `interval_note` / `stint_grain` / `claims_inside_noise` in
  `validation`, and `assert_claims_carry_intervals()` called from `write()`.
* **`schema.py`** — `TARGET_HORIZON_LAPS`, so §19's overlap correction survives Phase 7
  flipping `DEGRADATION_TARGET`.
* **Gates** — `test_ceiling.py` (19, all synthetic, no skips), `test_evaluate.py` +12,
  `test_manifest_contract.py` +5. **99 ML tests, all green.**
* **Surfaces** — `gen_ml_reference.py` renders an *Of attainable* and an *Interval* column
  plus two new validation tables; `app/src/features/model-metrics/` renders both per model
  and adds a claims-inside-noise section; `README.md`, `ml/README.md`, `docs/ml/models.mdx`
  and `docs/ml/validation.mdx` re-anchored. `scipy` declared in `ml/requirements.txt` —
  `intervals.py` imports it directly and it had only ever arrived transitively.

### The result, in one table

| Model | headline | of attainable | in-sample oracle | paired t | p | widening |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | 0.09338 | 28.2× | 2.11× | 10.250 | 0.00051 | 1.26× |
| `degradation_regressor_p50` | 0.19948 | 20.5× | 2.84× | 17.010 | 0.00007 | 1.40× |
| `degradation_regressor_p90` | 0.12351 | 11.8× | 1.35× | 10.233 | 0.00051 | 1.04× |
| `cliff_classifier` | 0.40375 | 1.14× | 1.14× | 31.065 | 0.00001 | 1.57× |
| `stint_life_regressor` | 1.93974 | 0.754 | — | 7.961 | 0.00135 | 3.71× |

**All five clear both intervals, 5/5 folds.** `claims_inside_noise` is empty.

### What was verified vs assumed

**Verified.** Every ceiling estimator is proven against synthetic data with a known answer
before it is used on real data — that is the §5/§6/§8 rule applied to arithmetic rather
than to plumbing. The ANOVA estimator recovers a known ICC of 0.03 / 0.20 / 0.40 to ±0.015
while the naive one returns 0.081 at the low end. The analytic pinball ceiling is confirmed
end-to-end at three ICCs × three α, to ±0.005. The overlap prediction `(h−1)/h` is
confirmed on rolling sums of white noise. The in-sample stint oracle is confirmed to be the
exact pinball minimiser over stint-constant predictors by trying 25 perturbations of it.
The cross-fitted oracle is confirmed not to see the row it predicts.

**Verified, and it is the phase's strongest claim.** That the degradation models use
within-stint information is a **proof, not an inference**: they score below the exact
in-sample optimum over all stint-constant predictors, on the very rows being scored, while
being trained on other seasons. No distributional assumption enters.

**Assumed.** The analytic ceiling `1 − √(1 − ICC)` assumes the within-stint conditional has
the same distributional *shape* as the marginal. The scale cancels; the shape does not. It
is why the in-sample oracle is published alongside it and why that one, not this one, is
the number to argue from.

**Not measured.** *What* the within-stint signal is. §18 establishes that it exists and is
large; it does not establish that it is tyre degradation rather than traffic, push, or
fuel-phase. `push_residual` — top SHAP feature for p50, 12.9% between-stint — is the first
place to look, and that question now matters more than Phase 7 does.

### Three things this phase found by running it rather than reading it

1. **The stint-grain re-cut was unnecessary and the checklist item was half wrong.** Phase 6
   asked for `stint_id` nested inside the season folds. Measured first: 0 of 6,780 stints
   straddle a fold. A stint belongs to one race, a race to one season. The split was never
   the problem — §15's other half, the lap-grain intervals, was.
2. **The classifier is not the weakest model; it is the one with the tightest ceiling.**
   macro-F1 0.4038 reads as poor against 1.0 and reads as **114% of a stint-identity
   oracle** against the reachable quantity. The docs said "modest in absolute terms" and
   that sentence has been replaced everywhere it appeared. What limits it is the label —
   `laps_until_cliff_class` is a first-crossing scan over an unbounded polynomial, which is
   Phase 8 — not the learner.
3. **"2824% of attainable" is a true number and a bad one to publish.** The first working
   version rendered exactly that. It is arithmetically correct and it reads as a broken
   metric; worse, it is an anchored number against an anchor that does not apply. Every
   surface now renders a fraction above 1 as a **multiple with a flag** and says in the same
   breath that the ceiling is not binding — which is the actual finding.

### Gates run

```
ml/tests                          99 passed
app: npm run typecheck            clean
app: npx vitest run               347 passed, 1 skipped (37 files)
app: npx eslint model-metrics     clean
ml.src.features --check           CLEAN (42 features), fingerprint 05aca16f1dc5…
ml.src.evaluate --all             all_beat_baseline=True, all_claims_significant=True
ml.src.card --write               refused nothing; 5 models
scripts/gen_ml_reference.py       docs/reference/ml/degradation-model.mdx regenerated
make app-models                   model_card.json + manifest + 5 onnx → app/public/models/
```

The card gate's liveness was proven against the **committed** card
(`git show HEAD:ml/models/model_card.json`): it fires on all five models.

### What is deliberately not done

* **No model changed and none was retrained.** That was the phase's contract.
* **Nothing is published.** `app/public/models/model_card.json` is updated locally; the CDN
  still serves the pre-Phase-6 card, as it still serves v5 artefacts.
* **The naive between-stint estimator is still published**, beside the corrected one, on
  purpose. Deleting it would hide the correction.

### The first command the next session should run

```
python -c "import json; d=json.load(open('ml/artefacts/evaluation_metrics.json')); \
  m=d['models']['degradation_regressor_p50']['attainable']['metric_native']; \
  print(m['fraction_of_attainable_in_sample'], m['oracle_metric_in_sample'], m['floor_metric'])"
```

That is **2.84**, and it is the number Phase 7 has to move. Not the raw pinball, and no
longer the attainable-fraction — see the note now at the top of Phase 7.

---

## Checkpoint 2026-08-24 (open item 15 — what the within-stint signal is)

Not a phase: item 15 was opened by Phase 6 as a defect ("nothing establishes *what* the
within-stint signal is") and the previous handoff recommended it ahead of Phases 7 and 8.
It is now measured. See Corrections §21 for the result.

### What landed

All uncommitted, on top of the uncommitted Phase 6 tree.

* **`ml/src/attribution.py`** (new) — the drop-vs-flatten decomposition. `stint_flatten` is
  the whole idea: replace a feature with its per-stint summary (mean for continuous, **mode**
  for the ordinal-encoded categoricals and booleans — averaging the codes for SOFT and HARD
  invents MEDIUM), so the feature keeps all its between-stint information and loses exactly
  its within-stint variation. Also `refit_noise_floor` / `annotate_noise`, `per_lap_features`,
  `prediction_variance_split`, `channel_rollup`, and `CHANNELS`.
* **`ml/tests/test_attribution.py`** (new, 20 tests) — all synthetic, no warehouse, no skips.
* **`ml/src/evaluate.py`** — `within_stint_attribution` elevation, `ATTRIBUTION_TARGETS`,
  `ATTRIBUTION_NOISE_SEEDS`, and a `--attribution` CLI flag. **Off by default.**
* **`Makefile`** — `ml-attribution`. Deliberately **not** in `ml-all`: ~46 refits per target
  at ~10 s each is minutes, and this answers a question about the model rather than gating a
  release.
* **`ml/artefacts/attribution_{degradation_regressor_p50,cliff_classifier}.parquet`** (new,
  gitignored) — every row of all three passes.

### What was verified vs assumed

**Verified.** The flatten operation is proven, not asserted, because every number downstream
is meaningless if it is wrong. On synthetic data with a known ICC: the flattened column's
between-stint share goes to exactly 1.0; the per-stint means are preserved to 1e-12; and a
planted per-lap driver (ICC 0.02) and a planted stint-level driver (ICC 0.98) — which a
*drop* cannot tell apart, both showing drop Δ > 0.1 — separate cleanly under flattening at
92% and 4% respectively. That last test is the method's liveness proof.

**Verified.** Flattening is well-defined here only because folds are stint-pure. Phase 6
measured **0 of 6,780 stints straddling a fold boundary**, so each stint lives entirely on
one side of the split and the train-side and eval-side per-stint means never disagree. Had
any stint straddled, the flattened feature would have been inconsistent across the split and
the deltas uninterpretable. This was checked, not assumed.

**Corrected while measuring.** Two defects the tests caught, both in this session's own code:
`flatten_is_noop` compared exactly, so the mean of *n* identical float64 values came back
"changed" and every genuinely stint-constant feature was flagged as varying — the flag
inverted on precisely the features it exists to identify. And `annotate_noise` built its
output key with the wrong slice offset, emitting `dropinside_noise`.

**Recorded, not smoothed over.** Flattening inflates the ANOVA's between-stint component by
exactly `sigma_w^2 / n0` — a stint mean is a noisy estimate of the stint effect, and this is
the *same* bias §18 corrected in §12's estimator, reappearing one level down. It does not
leak within-stint information into the flattened arm (the column is stint-constant by
construction), so `flatten_delta` stays clean; it does mean the flattened arm sees a slightly
noisier stint-level signal. Asserted as an identity in the test rather than hidden under a
tolerance.

**Assumed, and still assumed.** The `CHANNELS` mapping. Which channel a feature belongs to is
a judgement about what the sensor means — `push_residual` is filed under `driver_push` and
`traction_wheelspin_proxy` under `tyre_thermal`, and both could be argued. Every *number* is a
refit-and-rescore; only the grouping is a claim, and it is in one dict at the top of the
module so it can be argued with rather than buried. `test_every_contract_feature_has_a_channel`
fails if a 43rd feature lands unclassified.

**Not measured.** Whether the two halves are separable in the label rather than only in the
features — i.e. whether a target with traffic laps excluded would still show the tyre-age
ramp. That is the natural follow-on and it needs new SQL, which this item did not.

### Gates run

| Gate | Result |
| :--- | :--- |
| `pytest ml/tests -q` | **119 passed** (99 pre-existing + 20 new). No pre-existing test changed |
| `python -m ml.src.evaluate --all` (run 1) | all five beat baseline; every headline **identical to Phase 6 to 4 dp** (p50 pinball 0.1995, macro-F1 0.4038) |
| `make ml-attribution` (run 2, complete) | exit 0; same headlines again; `refit_noise` + per-row noise verdicts written |
| `make -n ml-attribution` | resolves |
| Attribution elevation off by default | verified — `RUN_ATTRIBUTION` is False unless `--attribution` is passed |

### The noise floor landed, and it changed two conclusions

The second `--all --attribution` run completed. `ml/artefacts/evaluation_metrics.json` now
carries `refit_noise` per attribution target and a `flatten_inside_noise` / `drop_inside_noise`
verdict on every row. Floors: **±0.00212** for p50 (sd 0.00075 over 5 reseeds), **±0.00352**
for the classifier (sd 0.00125).

**Two claims written from run 1 did not survive, and both are corrected in §21:**

* `tyre_thermal` on **p50** read −0.00167 and looked like within-stint variation actively
  hurting the model. It is inside the floor. The honest statement is "no measurable
  contribution", and the real negative-thermal finding belongs to the classifier alone.
* The **classifier's** `traffic` channel read 0.00247 and looked like a positive. Inside its
  floor. Traffic is a degradation-family result and does not generalise.

**The three load-bearing findings cleared comfortably** — 3.6×, 5.1× and 5.0× their floors —
so §21's headline is unchanged and the channel shares moved by less than 1.5 points
(50.7 / 29.6 / 19.7 against the 49.3 / 28.8 / 19.2 first written). **Item 16 clears by 5×.**

This is the whole reason the floor was built before the write-up was trusted: two of the
smaller results were artefacts of a single reseed, and both were the kind of tidy negative
number that reads as a finding.

A pre-Phase-6 backup of the metrics JSON sits at `<scratchpad>/evaluation_metrics.phase6.json`
if a diff is ever wanted. Regenerating everything is `make ml-attribution` (~40 min).

### Open decisions blocking the next phase

1. **The classifier result is actionable now and belongs to Phase 9, not Phase 8.** Flattening
   `tyre_thermal` improves macro-F1 by 0.0178 (4.4% relative). Phase 9 is currently sequenced
   *after* 7 and 8 on the grounds that the ablation must be re-run against a repaired label
   first. That reasoning still holds for *dropping* features; it does not obviously hold for
   flattening them, which is a smaller and separable move. Decide whether to pull it forward.
2. **Does the card publish this?** Phase 6 put ceilings and intervals on the card because they
   qualify a published claim. §21 qualifies what the degradation model *is*, which is arguably
   a stronger reason — and arguably a docs statement rather than a card field. Not done either
   way; `card.py` is untouched.
3. **`tune.py` searching the quantile trio against the wrong estimator** (Phase 2 finding 1) —
   unchanged, still open, still blocks Phase 7.

### The first command the next session should run

```
python -c "import json; d=json.load(open('ml/artefacts/evaluation_metrics.json')); \
  a=d['models']['degradation_regressor_p50']['within_stint_attribution']; \
  print('noise floor:', a.get('refit_noise',{}).get('delta_noise_2sd')); \
  print([(c['unit'], round(c['flatten_delta'],5), c.get('flatten_inside_noise')) \
         for c in a['channels']])"
```

It prints **0.00212** and a verdict per channel. Expect three `False` (real) and three `True`
(inside noise) for p50. If it prints `None`, something re-ran `make ml-evaluate` without
`--attribution` and overwrote the file — `make ml-attribution` restores it.

---

## Checkpoint 2026-08-24 (item 16 — attempted, measured, refused)

Not a phase. Item 16 was the action §21 proposed and the previous handoff put ahead of
Phases 8 and 7: flatten `tyre_thermal` to its per-stint mean and take +0.0178 macro-F1. The
first thing done to it was the check that should have accompanied the original measurement,
and it does not survive. See Corrections §22.

### What landed

All uncommitted, on top of the uncommitted Phase 6 + item 15 tree. **No model was retrained,
no feature contract changed, no artefact version moved, and no SQL was touched** — the whole
of item 16's proposed change was declined, and what landed is the instrument that declines it.

* **`ml/src/attribution.py`** — `causal_stint_mean` (the summary over laps 1..t, expanding or
  trailing-window), `future_stint_mean` (laps t..N, the look-ahead probe), `_causal_mode` (the
  running mode, so ordinal categoricals and booleans get a causal summary that stays inside
  their own value set), `_windowed_summary` and `flatten_causality`. Module docstring gains
  **"What a flatten result is not"**.
* **`ml/src/evaluate.py`** — `within_stint_attribution` takes `lap_tr` / `lap_ev` and runs the
  causal and future arms for **every channel row whose flatten delta clears the noise floor**.
  Two extra fits per qualifying channel, ~12 per full run. Rows inside the floor are not
  re-measured: a delta that is not a finding does not need a second arm to be declined.
  The nested `causality` block is flattened into four scalar columns on the parquet write.
* **`ml/src/attribution.py`** also gains `rank_preservation` and `RANK_DEGENERATE_RHO` — the
  causal arm's own null check, added after the first p50 result came back and `tyre_age` read
  `causally_reachable: false` on a *positive* delta. It is a counter channel; its prefix mean
  is a monotone relabelling; a tree sees the same feature. The verdict is now **withheld** on
  a degenerate arm rather than reported.
* **`ml/tests/test_attribution.py`** — 13 new tests (33 total), all synthetic, no skips.

### What was verified vs assumed

**Verified — the operators, before any number from them was trusted.** The causal summary
meets `stint_flatten` exactly at the last lap of every stint (the prefix *is* the stint) and
the raw value at the first (the prefix is the row), which is the pair of identities that makes
the two arms comparable. The liveness proof is the perturbation test: add 100 to the last lap
of every stint and **no earlier row moves** under `causal_stint_mean`, while **every row**
moves under `stint_flatten`. A causal summary that fails that test is look-ahead wearing a
causal name, and every conclusion below would be void.

**Verified — order invariance.** Rows arrive in warehouse order, not stint order. The summary
is defined by (stint, lap); shuffling the frame and mapping back reproduces it to 1e-12.

**Verified — the arms replicate the thing they are arguing with.** The reference arm scores
0.40375 (the 0.4038 headline) and `flatten_full` scores +0.01775 (§21's number, to five
decimals) on the same split, params and seed. This is the same measurement re-run, not a
competing one, which is what makes the causal arm's +0.00150 a correction rather than a
disagreement.

**Verified — the mechanism, not just the failure.** `causal_expand` differs from
`flatten_full` in two ways at once (fewer laps, and no future ones), so a third arm holds
sample size fixed and lets the draw reach into the whole stint: `random_k` recovers +0.00680
of the +0.01775. And `future_mean` — strictly fewer laps than the full-stint mean, every one
of them at or after the scored row — scores **+0.02015, higher than the full-stint mean**.
Monotone in future content, not in sample size. That is the finding.

**Assumed, and worth stating.** That `lap_in_stint` is the within-stint ordering. It is the
column the mart's own age features are built on and the one `metric_native_ceiling` already
orders by, so this is consistent rather than novel — but it is an assumption, and a stint
whose laps were mis-ordered would produce a causal arm that silently mixes past and future.

**Not measured.** The per-feature pass gets no causal arm (item 17). Cost, not principle:
~14 more refits per target, and no feature-level result is currently proposed for action.

### Gates run

| Gate | Result |
| :--- | :--- |
| `pytest ml/tests -q` | **132 passed** (119 pre-existing + 13 new). No pre-existing test changed |
| Four-arm measurement (reference / flatten / causal / roll3) | reference reproduces 0.4038; flatten reproduces §21's +0.01775 |
| Two-arm mechanism probe (`random_k` / `future_mean`) | +0.00680 / +0.02015 — size is not the ingredient |
| Wiring smoke (real code path, toy learner) | causality block present on channel rows, JSON serialises, parquet columns flat |
| Rank-preservation of the causal arm (no refits) | thermal 0.59–0.80 (real), tyre_age 0.991–0.999 (relabelling) |
| `make ml-attribution` (full regeneration) | **exit 0**, all five beat baseline, every headline identical to Phase 6 (p50 pinball 0.1995, macro-F1 0.4038); causality on all six qualifying channels |
| `python -m ml.src.evaluate --all --attribution` reproduces the scratch arms | `tyre_thermal` causal −0.00150 / future −0.02015 — the same numbers through the shipped code path |

### What is deliberately not done

* **`tyre_thermal` was not flattened in the feature set**, and no version was bumped. That was
  the entire proposed content of item 16.
* **§21 was not rewritten.** Its numbers are correct; §22 corrects the reading and says which
  of its rows survive as lower bounds and which are now unadjudicated (item 17).
* **The card says nothing about this.** §21's open decision 2 (does the card publish what the
  model *is*?) is still open and still untouched, and §22 makes it harder rather than easier:
  the honest card line would have to carry the causal arm too.
* **The `random_k` arm stayed a one-off probe** and is not in the repo. It answered "is the
  ingredient sample size?" once, and the answer is also legible from the two arms that did
  land: `future_mean` beats `flatten_full` on strictly fewer laps, which cannot happen if size
  is what matters. `causal_stint_mean(window=3)` reproduces the trailing-window arm.

### The finding this session did not go looking for

The p50 causality rows landed mid-session and they are the opposite of item 16's: `driver_push`
and `traffic` clear the floor on the flatten arm **and** on the causal arm, in the same
direction. §21 could only offer those as lower bounds. They are now confirmed — the model's
use of that variation is not something a per-stint summary can supply, causal or otherwise.
**§22 refuses one action and strengthens two findings**, and both come from the same check.

### The one number worth reading carefully

**+0.00150 against a ±0.00352 floor.** Not "a smaller win" — *no measurable win*. The
temptation with a result like this is to report the causal arm as a reduced version of the
original (0.0015 instead of 0.0178) and keep the direction. The direction is not established
either: the trailing-3-lap arm is **−0.00202**, the other side of zero and equally inside the
floor. Everything the causal arms can say is "nothing distinguishable from reseeding".

### The first command the next session should run

```
python -c "import json; d=json.load(open('ml/artefacts/evaluation_metrics.json')); \
  a=d['models']['cliff_classifier']['within_stint_attribution']; \
  print([(c['unit'], round(c['flatten_delta'],5), \
          (c.get('causality') or {}).get('causally_reachable')) for c in a['channels']])"
```

Every channel that clears the floor now carries a verdict. `tyre_thermal` must read
`False` — that is §22 on disk rather than in prose. If `causality` is absent on a clearing
row, the run predates this session; `make ml-attribution` restores it.

---

## Checkpoint 2026-08-25 (Phase 8 — SQL repair landed, re-tune deliberately not run)

The bound is at source, the label is repaired, all five models are refit on it, and **the
phase's central hypothesis is not confirmed.** Repairing the label did not lift the
classifier. See Corrections §23 for the two ways the phase's own checklist was wrong about
the defect it was chasing.

### What landed

All uncommitted, on top of the uncommitted Phase 6 / item 15 / item 16 tree. **No feature
contract changed, no artefact version moved, `MODEL_VERSION_DEFAULT` is still v6, and nothing
was exported or published.**

* **`transform/dbt_project.yml`** — `compound_wear_max_s_per_lap: 10.0`, the shared bound
  under its own name, with the 10.0 / 5.0 / 3.0 label sensitivity recorded beside it.
  `pit_strategy_max_wear_s_per_lap` retained as the strategy model's alias.
* **`int_compound_cliff_predicted.sql`** — the bound applied to the three age-dependent terms,
  plus a new `compound_wear_s` column carrying the bounded quantity so the bound is assertable
  directly rather than re-derived from the pace total.
* **`int_pit_strategy_cost_curve.sql`** — switched to the shared bound. No behaviour change:
  both vars are 10.0 and it applies the identical `LEAST()` to the identical terms.
* **`transform/tests/assert_compound_wear_bounded.sql`** — new, the bound's own test.
* **`transform/tests/assert_ghost_recombination.sql`** — threshold 10.0 → 11.0, **on the
  user's explicit decision**, with the full measured cost written into the file. See "the
  price" below.
* **`transform/models/intermediate/schema.yml`** — both new/changed columns documented.
* **Both approval baselines regenerated**: `data_profile.baseline.json` and
  `model_hashes.baseline.json`.
* **`ml/models/*_v7.bst`** ×5 — refit at existing best params on the repaired data.
  Untracked (`.gitignore:71`), so nothing to commit. `ml/artefacts/evaluation_metrics.json`
  is now a **v7 report**.

### What was verified vs assumed

**Verified — the re-derivation, before any repaired number was read.** The label probe is a
closed form (capping the wear term raises the residual by exactly the excess). Run with the
bound inert it reproduces the committed label on **all 137,447 rows, 0 differences**. Only
then were capped values read. Afterwards the **real dbt build matched the probe's predicted
per-class counts exactly on all five classes** — 14,538 / 11,336 / 14,947 / 89,532 / 7,094.
Two independent derivations agreeing to the row is what makes §23's sign claim safe, and the
sign is the whole finding.

**Verified — the new gate is live, not vacuous.** Rebuild the source model with the bound at
1e9 and assert at the default 10.0: **12,580 failures**. The first attempt at this proof was
worthless — passing `--vars` moved the *threshold* as well as the data, so the test passed
against a 92.5 s table. A bound test that reads the same var twice can be fooled that way;
this one was checked the other way round.

**Verified — I caused the ghost failure, rather than inferring it.** Rebuilt the ghost
subgraph with the bound inert: test passes. Rebuilt at 10.0: 4 failures. Not argued from the
diff.

**Verified — the drift refit is not the mechanism.** `int_lap_residual_stint_detrend` fits on
`cliff_onset_passed = FALSE`, and only **21** of the 12,575 bounded rows are pre-onset, so the
label move is the residual moving, not the detrend slope moving. The hash of that model does
change — 21 rows is not zero — and the checkpoint says 21, not "none".

**Assumed, and worth stating.** That capping the *wear* portion (gradient·age + 0.002·age² +
severity·laps_past_cliff) and not `grip_peak` or the temperature offset is the right split. It
is the split `int_pit_strategy_cost_curve` already used, so this is consistent rather than
novel — but it is a choice, and a bound that included `grip_peak` would move different rows.

**Not measured.** Whether the repaired label lifts the classifier **under a fresh search**.
That is the phase's last checklist item and it was deliberately not run — see below.

### Gates run

| Gate | Result |
| :--- | :--- |
| `sqlfluff lint models/` | **8 failing files — unchanged from `main`.** Phase 8 added none |
| `dbt run` (dev) | **68/68 OK** |
| `dbt test` (dev) | **580/580 PASS** (579 + the new bound test; ghost gate green at 11.0) |
| `dbt build` (ci, fixtures) | **655 PASS, 0 ERROR** |
| Bound-test liveness (unbounded table vs default threshold) | **FAIL 12,580** — live |
| Label probe identity (inert bound vs committed label) | **0 / 137,447 differ** |
| Probe prediction vs real build | **exact on all five classes** |
| `data-profile-check` (before regenerating) | **29 drifts, incl. the Phase 4 category-share vector** — the gate saw it |
| `data-profile-check` (after) | **no drift across 15 tables** |
| Model-hash oracle (before) | 6 `fct_*` + 9 `int_*` drifted — exactly the closure of `driver_skill_residual_s` |
| Model-hash oracle (after) | **all 7 `fct_*` byte-stable** |
| `pytest ml/tests -q` | **132 passed** — unchanged count, none edited |
| `train --all --tuned --version v7` | five models, 4m31s |
| `evaluate --all --version v7` | all five still `beats_baseline` **and** `beats_baseline_significant`; `claims_inside_noise: []` |

### The result, and why the headline is the wrong way to read it

The classifier is Phase 8's subject. On the repaired label, **at unchanged hyperparameters**:

| | v6 (contaminated label) | v7 (repaired) |
| :--- | ---: | ---: |
| macro-F1 | 0.40375 | **0.39715** |
| majority baseline | 0.22413 | **0.21865** |
| ratio to baseline | 1.8015 | **1.8163** |
| fraction of stint-level attainable | 1.14 | **1.14** |

**Both moved down together.** Comparing 0.4038 to 0.3971 is comparing scores on two different
tasks and means nothing on its own; the ratio is the only like-for-like reading, and it moved
+0.8%. **Phase 8's premise was that ~0.40 is a ceiling set in SQL and that repairing the label
would lift the classifier. The label was genuinely defective — 6,825 rows — and repairing it
did not lift it.** The classifier is still at 114% of its stint-level attainable, so the
"ceiling is the label" claim is not refuted either; what is refuted is that *this* defect in
the label was what held the number down.

The other four, for completeness (ratio to own baseline, lower better except macro-F1):
p10 0.5708 → **0.5690** better; p50 0.6911 → **0.7155** worse; p90 0.7936 → **0.8206** worse;
stint-life 0.8870 → **0.8856** better. The p50 in-sample stint-oracle multiple reads **3.81**
against Phase 6's 2.84 — but the denominator moved when the target did, so that is not
evidence of a better model and must not be quoted as one.

**A correction to something said mid-session.** The training log's `pinball_cv` for p50 came
back 0.2225 against Phase 6's published 0.1995 and was briefly read as an 11% regression. It
is not a comparison: 0.1995 is an eval-fold headline and 0.2225 is a CV mean. Eval-fold to
eval-fold the p50 headline is **0.19948 → 0.19928**, flat.

### The price, and that it was a decision rather than a judgement call

Bounding the curve made `fct_ghost_car_pace` **worse**: mean |predicted − actual| 1.0244 →
1.0609 s, p50 0.7914 → 0.8148, max 9.22 → 10.33. On the 341,532 ghosts where the bound binds,
155,336 improved and 186,196 worsened. Four laps then breached
`assert_ghost_recombination`'s hand-set 10.0 s threshold — all four ALO, race 2024_8, laps
73-76, `age_in_stint` 73-76, a single-stint race with the field cruising.

The mechanism is worth keeping: before Phase 8 the unbounded term charged an old tyre tens of
seconds of "wear" that the driver was actually giving away by cruising, and
`driver_skill_residual_s` — defined as the remainder — absorbed the complement. Recombination
worked through **two large errors cancelling**. Bounding the curve stops the first; the
residual now carries the cruising, and the ghost swaps the residual between drivers, so what
does not transfer is newly visible. **The same move that repairs both ML targets degrades the
ghost, and that is inherent, not incidental.**

**The user was asked and chose to widen the threshold to 11.0 with the cost documented in the
file.** It is recorded here because a widened gate that nobody can trace is how a real
regression disappears.

### What is deliberately not done

* **The re-tune — Phase 8's last open checklist item.** The user was asked and chose to stop
  at refit and hand off. Everything above is at v6's hyperparameters, tuned for the
  contaminated label, so **the phase's payoff question is open, not answered.** The class
  balance moved materially (`none_in_stint` 70.1% → 65.1%), which is exactly the kind of move
  a fresh search should be given. **Tune the classifier only**: Phase 2 finding 1 is still
  open, so the quantile trio cannot be honestly searched yet.
* **Nothing was exported, carded, predicted or published.** No ONNX, no manifest bump, no
  `app/public/`. `MODEL_VERSION_DEFAULT` is still v6 while the newest boosters are v7 — that
  is a deliberate half-state, not a half-run chain.
* **`ml/src/card.py:335` now carries a false sentence** — "laps_until_cliff_class is a
  first-crossing scan over an unbounded cliff polynomial". Wrong in mechanism (§23) and, as of
  this session, wrong in fact. **It was not edited**, because card.py's own comment three
  lines above says the module exists to prevent hand-edited prose drifting from generated
  numbers, and every published number in that card is still from the contaminated label.
  Fix the prose *and* the numbers together, on the run that regenerates the card.
* **§21 and §22's attribution results are now stale.** They were measured on the contaminated
  target and label. `ml/artefacts/evaluation_metrics.json` is a v7 report written **without**
  `--attribution`, so the `causally_reachable` verdicts §22 put on disk are gone from it. They
  are not lost as a finding — §22's prose stands — but the file no longer carries them, and
  re-running `make ml-attribution` would measure a *different* target than the one they
  describe.

### The first command the next session should run

```
cd transform && ../.venv/bin/dbt test --profiles-dir profiles --target dev \
  --select assert_compound_wear_bounded assert_ghost_recombination
```

Both must pass. The first is §23 on disk; the second is the price of §23 on disk. If the
first fails, someone has changed `compound_wear_max_s_per_lap` or reverted the source model,
and every label number in this checkpoint is void.

Then, if picking up the re-tune:
`./.venv/bin/python -m ml.src.tune --target cliff_classifier --trials 50`.
**Do not tune the quantile trio** until Phase 2 finding 1 is fixed.

---

## Checkpoint 2026-08-25 (Phase 8 closed — the re-tune ran and found nothing)

Phase 8's last checklist item is done. A fresh 50-trial search on the repaired label **did not
beat the hyperparameters tuned on the contaminated one**, and the phase's central finding
survives its own last test: repairing the label does not lift the classifier, and that is a
fact about the label rather than about a stale search.

**Nothing in the tree changed.** The search product was measured and reverted; the working
tree is byte-identical to the previous checkpoint. What this session adds is a measurement,
a study DB, and this block.

### What landed

* **`ml/models/optuna_studies/cliff_classifier_v7.db`** — new, untracked (`.gitignore:75`).
  50 trials, 26 complete / 24 pruned, ~39 min. The evidence, and the only artefact kept.
* **Reverted after measurement** — `ml/models/cliff_classifier_best_params.json` (tracked;
  restored to HEAD, shows clean), `ml/models/cliff_classifier_v7.bst` (refit at the search's
  params, restored from a pre-tune copy), `ml/artefacts/evaluation_metrics.json` (restored to
  the old-params v7 report). The reason is below, and it is part of the result rather than
  tidying.

### The result

| | CV mean macro-F1, 5 season folds |
| :--- | :--- |
| Old params (tuned on the **contaminated** label) | **0.3946** |
| Best of 50 fresh trials on the **repaired** label | **0.3941** |
| Difference | **−0.0005** |

Fold-paired, refit per fold at each param set on identical splits:

| val season | old | new | delta |
| :--- | :--- | :--- | :--- |
| 2020 | 0.3840 | 0.3824 | −0.0016 |
| 2021 | 0.3999 | 0.3965 | −0.0034 |
| 2022 | 0.3949 | 0.3932 | −0.0017 |
| 2023 | 0.3971 | 0.3969 | −0.0002 |
| 2024 | 0.3971 | **0.4015** | **+0.0043** |

Mean delta **−0.00051**, 95% CI **[−0.00416, +0.00313]**, t = −0.390, **p = 0.716**, **1 of 5
folds won**.

Note also that 0.3941 is the **maximum over 50 trials on this exact objective** and so is
biased upward by selection, while 0.3946 is a single unbiased evaluation of one param set.
The honest gap is wider than −0.0005, not narrower.

### The trap this result sets, and why the artefacts were reverted

**The eval-fold headline goes up: 0.3971 → 0.4015, ratio 1.8163 → 1.8361.** Read alone that is
a +0.0043 win and the natural thing to record. It is not a win. The only fold the new params
win is **season 2024 — which is the fold the headline is read from** — and the search selected
on a CV mean that includes it. The headline gain is selection noise landing on the reported
fold; the other four folds all move the other way.

This is §22's pattern arriving somewhere new: a number that replicates exactly and is not
reachable. Had the artefacts been kept, the next reader would have found 0.4015 in
`evaluation_metrics.json`, a modified `best_params.json`, and every reason to believe the
re-tune worked.

The revert is load-bearing for a second reason: **`ml-retrain` refits production from
`*_best_params.json`**. Leaving the search product there would have silently shipped params
that lose on four folds out of five the next time anyone ran it.

### What was verified vs assumed

**Verified — the comparison is like-for-like, checked in the source before the numbers were
read.** `evaluate.fold_paired_interval` (`ml/src/evaluate.py:932-950`) **refits per fold** at
the params it is handed, so both columns above are out-of-fold CV scores over the same
season-grouped splits at the same seed — not one full-data model scored twice.

**Verified — nothing else moved underneath.** The other four models' headlines are identical
across the two reports **to 1e-12** (p10 0.092406, p50 0.199276, p90 0.125624, stint-life
1.936635). Only the classifier changed, which is what makes the delta attributable.

**Verified — the study is uncontaminated.** The run was given `--version v7`, so it created a
fresh study namespace (`cliff_classifier_v7.db`). `cliff_classifier_v5.db` exists and holds
trials scored against the **contaminated** label; `tune.py` passes `load_if_exists=True`, so a
run in that namespace would have seeded TPE from an objective measured on a different label.

**Deviation from the previous handoff's command, deliberate.** It said to run
`ml.src.tune --target cliff_classifier --trials 50` with no `--version`. That defaults to
`MODEL_VERSION_DEFAULT`, which is still **v6** — the version `ml/models/manifest.json` names
and whose ONNX sits in `app/public/models/`. The chained refit would have overwritten
`cliff_classifier_v6.bst` with a booster trained on the repaired label, breaking the v6
rollback point against what was actually exported. Run at v7, Phase 8's own refit set,
instead.

**Assumed, and worth stating.** That 50 trials suffices to call the incumbent near-optimal.
TPE with 24 of 50 pruned explores less than the trial count suggests. The claim defended here
is the narrow one — *a 50-trial search of this space did not beat the incumbent* — not that no
hyperparameters exist that would.

### Gates run

| Gate | Result |
| :--- | :--- |
| `dbt test --select assert_compound_wear_bounded assert_ghost_recombination` (the mandated first command) | **2 PASS** — §23 intact on disk |
| `tune --target cliff_classifier --trials 50 --version v7` | 50 trials, 26 complete / 24 pruned, 39 min, best CV **0.3941** |
| `evaluate --all --version v7` | all five still `beats_baseline` **and** `beats_baseline_significant` |
| Other four headlines, old report vs new | **identical to 1e-12** |
| `pytest ml/tests -q` | **132 passed** — unchanged count, none edited |
| `git status` after revert | **unchanged from the previous checkpoint** |

### The one number worth reading carefully

**Both param sets pin `max_depth` at 8 and `n_estimators` at 700 — the ceiling of the search
space in both dimensions** (`tune.py:_suggest`: `max_depth` 3–8, `n_estimators` 200–700). The
search wants more capacity than it is allowed to ask for, and it has wanted it since Phase 2
without anyone writing it down.

This does **not** rescue the classifier and must not be read as headroom. Fifty trials could
not move the objective by 0.0005 *inside* the space, which is not the signature of a learner
straining against a bound: a capacity-limited search pins the bound **and** rewards every step
toward it, and this one plateaued flat (top five trials 0.3941 / 0.3937 / 0.3935 / 0.3933 /
0.3933). What it does mean is that the sentence "the learner is saturated" has never been
tested, and anyone who writes it is resting on bounds nobody has probed. Widening them is
cheap, and it is the only way left to say that sentence honestly.

### Open decisions blocking the next phase

None new. Phase 8 is closed. Phase 2 finding 1 is next and nothing of Phase 8's blocks it.

### The first command the next session should run

```
grep -n "meta is deliberately NOT passed" -A 6 ml/src/tune.py
```

That comment **is** Phase 2 finding 1, sitting in the source at the line where it bites: the
search fits the quantile trio *without* the IPW survival weights that `train.py:_fit` applies,
so the p10/p50/p90 params in `ml/models/` were selected against an objective the refit does
not use. It blocks Phase 7, and §23 has just moved the degradation target on 9.05% of rows —
so the trio's params are now stale on two counts rather than one.
**Do not tune the quantile trio until it is fixed.**

---

## Checkpoint 2026-08-25 (Phase 2 finding 1 closed in two places; Phase 7 landed)

Phase 2 finding 1 is fixed and it was **not one defect**. The same hole is in `evaluate.py`,
where it reaches the model card rather than the search (§24). Phase 7's retarget then landed on
top of it, and unlike Phase 8's re-tune **this search found something**: the trio gains 3.16% /
3.00% / 0.22% against the params it inherited.

Executing the phase produced four things its checklist did not carry: the 5-lap column costs
28% of the training rows and takes them from the end of stints (§25); the IPW weights it
inherits under-correct for its own horizon by 1.22× (§25); the between-stint shares the phase
was argued on **no longer exist**, because Phase 8 drove the 1-lap target's to exactly zero
(§26); and the group ablation **inverts**, which matters to Phase 9 rather than to this one
(§27).

### What landed

* **`ml/src/tune.py`** — the fold fit goes through `train._fit`. One code path, so the search
  cannot diverge from the refit again.
* **`ml/src/evaluate.py`** — `_row_weights` + `w_tr` on `EvalSplit`, threaded to all six fit
  sites (`ablation`, `learning_curve`, the attribution closures, `fold_paired_interval`,
  `evaluate_target`). `_fit` **raises** rather than defaulting when a quantile fit arrives
  without weights.
* **`ml/src/schema.py`** — `DEGRADATION_TARGET` = `next_5_lap_cumulative_jump_s`;
  `TARGET_BOUND_BY_COLUMN` so the bound follows the column (±50, not ±10).
* **`ml/src/train.py`** — every training log now records `target_column` and
  `target_horizon_laps`, and `_guard_target_change` refuses to refit a version whose artefacts
  were fitted on a different target column.
* **`ml/src/export_onnx.py`** — the manifest's quantile entry carries `target_column`,
  `horizon_laps` and a horizon-bearing `meaning`.
* **`ml/src/card.py`** — the summary's horizon phrase is derived from `TARGET_HORIZON_LAPS`;
  the false cliff-limitation sentence Phase 8 flagged is rewritten to what is now measured.
* **`ml/tests/test_fit_parity.py`** (new, 24 tests) and 7 new tests in `test_features.py`.
* **v8 artefacts, untracked** — all five `.bst` refit at v8, three fresh Optuna studies,
  `ml/artefacts/*` regenerated. **Three tracked `*_best_params.json` changed** (the trio).
* **Two docs gates repaired** — `ml_docs_facts` / `docs_facts` have been failing since Phase 6
  added `test_ceiling.py`; the taxonomy was stuck at 64 tests against a live 163.

### The result, in one table

Acceptance, against the incumbent **re-measured through the corrected evaluate** so the only
difference is the target:

| | p10 1-lap → 5-lap | p50 1-lap → 5-lap | p90 1-lap → 5-lap |
| :--- | :--- | :--- | :--- |
| reduction, share of own floor | 38.38% → **59.21%** | 24.57% → **47.32%** | 15.30% → **29.80%** |
| in-sample stint-oracle multiple | 2.36 → 1.66 | 3.76 → 3.40 | 1.20 → 1.62 |
| analytic `fraction_of_attainable` | **null** → 126.02 | **null** → 100.72 | **null** → 63.43 |
| cross-fitted | **null** → 2.30 | **null** → 5.23 | **null** → 11.25 |
| beats baseline (folds won, p) | 5/5, 0.0012 | 5/5, 0.0001 | 5/5, 0.0002 |

The re-tune, fold-paired at both param sets on identical splits:

| | inherited | re-tuned | Δ | folds won | p |
| :--- | ---: | ---: | ---: | :--- | ---: |
| p10 | 0.608857 | 0.589593 | **−3.16%** | 5/5 | 0.009 |
| p50 | 1.182364 | 1.146871 | **−3.00%** | 5/5 | 0.004 |
| p90 | 0.629205 | 0.627831 | −0.22% | 3/5 | 0.755 |

### What was verified vs assumed

**Verified — the retarget did not leak into the other two families.** `cliff_classifier`
(0.3971492523) and `stint_life_regressor` (1.9366346729) are **bit-identical** to the v7 report,
delta exactly 0.0. That is the attribution check: the weighting repair touches only the quantile
trio (whose weights depend on `meta`) and the target change touches only their rows.

**Verified — the target column is still exactly what it claims.** §23 moved the residual the
5-lap column is built from, so Phase 4's verification was re-run rather than cited:
reconstructed from `int_lap_residual_decomposed` + `int_lap_residual_stint_detrend`, **max
|diff| 0.0 across all 95,346 non-null rows**, 23 on the ±50 clip.

**Verified — the defect §24 names really was live.** The v7 report's published headlines
(0.092406 / 0.199276 / 0.125624) reproduce **exactly** as the unweighted arm of a two-arm refit
on identical rows. Not inferred from the code; measured.

**Assumed, and this one matters. The re-tune's win is measured on the folds the search selected
on.** `tune.py`'s objective is the mean over these same five season-grouped folds, so the
re-tuned column is selection-biased upward and the inherited column is not. This is Phase 8's
trap in the opposite direction, and it is why the honest claim here is *"−3.0% on the selection
folds, 5/5"* rather than *"−3.0% out of sample"*. Two things argue the effect is not only
selection: the incumbent params were themselves selected on these folds (for the old target
under the old objective), and 5/5 with p=0.004 is a wider margin than the classifier's
selection artefact produced in Phase 8 (1/5, p=0.716). With seven training seasons and
five folds there is no held-out season left to settle it.

**Assumed** — that 50 trials suffices, unchanged from Phase 8's statement of the same caveat.

### The thing this session found that is not in any phase

**All three quantiles moved toward the top of the search space, and were rewarded for it.**
`max_depth` 5→7, 5→8, 4→6; `min_child_weight` 15→19, 16→20, 17→20 against a ceiling of 20;
`n_estimators` fell in all three. Optuna ranks `max_depth` the **most important parameter for
p50 (0.3175)**, and p50 pins both `max_depth` and `min_child_weight` at their bounds.

Phase 8 observed the classifier pinning the same two bounds and correctly refused to read it as
headroom, because that search **plateaued flat** — top five trials within 0.0008. This one did
not: moving toward the bound bought 3%. Same signature, opposite gradient. **Widening
`_suggest`'s ranges is now a cheap test with a reason behind it**, and it is still a test rather
than a phase.

### Gates run

| Gate | Result |
| :--- | :--- |
| `pytest ml/tests -q` | **163 passed** (was 132; +24 fit-parity, +7 feature-contract) |
| The fit-parity guards, with `tune.py`'s fit reverted to the pre-fix call | **7 of the 11 parity tests fail** (all six quantile cases, plus the survival one) — the tests are not vacuous |
| `python -m ml.src.features --check` | CLEAN, 42 features, 82,315 training rows |
| `tune --target degradation_regressor_p{10,50,90} --trials 50 --version v8` | 50 trials each, fresh v8 studies |
| `train --all --tuned --version v8` | five boosters; trio CV reproduces the search exactly |
| `evaluate --all --version v8` | all five beat baseline, **all five significant**, `claims_inside_noise` empty |
| Classifier + stint-life headlines, v7 vs v8 | **identical to 0.0** |
| `scripts/ml_docs_facts.py`, `scripts/docs_facts.py` | **both PASS** (both were failing on arrival) |

### What is deliberately not done

* **Nothing is exported, carded, predicted or published, and `MODEL_VERSION_DEFAULT` is still
  v6.** Same deliberate half-state Phase 8 left, one version further on: newest boosters v8,
  default v6, manifest v6, app serving v5.
* **The app's "next-lap" copy is untouched, and that is the correct state, not an omission.**
  The app scores the v6 ONNX, which *is* a next-lap model, so every such sentence is true today
  and changing it now would make the app wrong. The copy moves when the version moves — one
  step. What landed instead is the machine-readable half that makes that step mechanical: the
  manifest and the training logs now name the column and the horizon, so a promotion that
  forgets the prose is detectable rather than silent. The exact file list is on the Phase 7
  checklist item.
* **The horizon-correct IPW weight** (§25). It is a SQL change and Phase 7 forbids SQL changes.
  Quantified at 1.22× mean, not fixed.
* **The weighted-metric question** (§24). The fit is now weighted and the metric is not.
  Resolving it moves every published number at once, so it is recorded, not taken.
* **`make ml-attribution` was not re-run.** §21 and §22's verdicts were measured on the 1-lap
  target and are now stale in a second way. §27 already shows the group ablation inverts;
  the channel attribution should be expected to move with it.

### The first command the next session should run

```
python -c "import json; d=json.load(open('ml/artefacts/evaluation_metrics.json')); \
  m=d['models']['degradation_regressor_p50']['attainable']['metric_native']; \
  print(d['version'], m['fraction_of_attainable'], m['achieved_reduction_pct_of_floor'])"
```

`v8 100.72 0.473`. Those three values are Phase 7's whole case: the version is the retargeted
one, the analytic denominator **exists** (it is `null` on the incumbent, which is §26), and the
model removes 47.3% of its own floor where the incumbent removed 24.6% of a smaller one.

Then read **§27 before touching Phase 9** — the group ablation the phase is written around
inverts on this target, and `compound`, the group it queued for deletion, is now the largest
contributor at 19.1%.

---

## Checkpoint 2026-08-26 (open item 21 — the search-space test, and what a probe cannot see)

Open item 21 said `_suggest`'s ranges are binding and that widening them is "one edit and one
search". Both halves ran. The edit is in, the search found a **better optimum that does not
clear its own interval**, and the session's real finding is methodological: the cheap
instrument said no and the expensive one said maybe, and **the cheap one was wrong in a way
that was invisible from inside it**.

The bounds stay widened. The params do not change. Nothing is exported, carded or versioned.

### What landed

* **`ml/src/tune.py`** — the search space is **declared as data** (`SEARCH_SPACE`,
  `SURVIVAL_SPACE`, `_space_for`) and `_suggest` builds every suggestion from it. Ranges
  widened: `max_depth` 8 → 12, `min_child_weight` 20 → 60 (and log-scaled), `n_estimators`
  700 → 1200.
* **`ml/src/tune.py:boundary_params`** — names any best-params set that stopped on an edge of
  the space that produced it, and `tune_one` prints it at the end of every search. This is the
  hole the item was actually about: five searches from Phase 2 to Phase 7 ended on a ceiling
  and the fact reached a checkpoint only when someone read three JSON files side by side. A
  search that stops on its own edge prints a best value like any other.
* **`ml/tests/test_search_space.py`** (new, 14 tests) — no suggestion can leave the declared
  space; the detector is proven to fire at every ceiling, at every floor, and to stay silent in
  the interior. **177 ML tests green** (was 163).
* **Two docs gates carried forward** — `TEST_GROUPS` in `scripts/ml_docs_facts.py` gains the
  new group, the six ML inventory snippets are regenerated, and the count moves 163 → 177 in
  `README.md`, `docs/ml/overview.mdx` and `ml/tests/README.md`. Both gates PASS.
* **Two study DBs, untracked** — `degradation_regressor_p50_v9.db` (50 trials, 39 complete /
  11 pruned) and `cliff_classifier_v9.db` (50 trials, **19 complete / 31 pruned**).
* **Reverted after measurement** — `ml/models/degradation_regressor_p50_best_params.json` and
  `ml/models/cliff_classifier_best_params.json`, both restored **byte-identical** (the
  classifier's shows clean against HEAD). `tune_one` overwrites them and `ml-retrain` refits
  production from them; Phase 8's reason for reverting applies unchanged.

### The result: two instruments, and they disagree

**Instrument one — a coordinate probe past the bound**, fold-paired at both param sets over the
same five season folds, refitting per fold through `train._fit` (so the weights are the ones
the production refit applies). Best step past the old ceiling, per target:

| target | best step past the ceiling | delta | p | folds won |
| :--- | :--- | ---: | ---: | :--- |
| p10 | `min_child_weight` 45 | +0.0030 | 0.307 | 3/5 |
| p50 | `max_depth` 10 + `mcw` 40 + lr 0.015 | +0.0009 | 0.824 | 2/5 |
| p90 | `max_depth` 8 + `mcw` 40 | +0.0034 | 0.385 | 4/5 |
| cliff_classifier | `max_depth` 10 | +0.0024 | 0.376 | 3/5 |
| stint_life_regressor | `max_depth` 10 | **−0.0152** | **0.030** | 0/5 |

Nothing clears its interval; stint-life is significantly **worse** past its bound. And the
p50 row looked decisive in the other direction too: stepping *inward* from the pinned ceiling
is significantly worse (`max_depth` 7: −0.0106, p=0.011; 6: −0.0204, p=0.004), so depth 8
looked like a genuine interior optimum that happened to sit on the wall.

**Instrument two — a 50-trial joint search in the widened space (p50).**

| | value | params |
| :--- | ---: | :--- |
| incumbent (v8 search, narrow space) | 1.146871 | `max_depth` **8**, `mcw` **20**, `n_est` 600 |
| widened space, 50 trials | **1.143100** | `max_depth` 9, `mcw` 42, `n_est` 900 |

Fold-paired refits at both param sets on identical splits: **+0.003815**, 95% CI
**[−0.003056, +0.010685]**, **p = 0.198**, **4 of 5 folds won**.

**The same search on `cliff_classifier`**, which is the one Phase 8 said could only be settled
this way:

| | value | params |
| :--- | ---: | :--- |
| incumbent (tuned on the contaminated label, Phase 2) | 0.394614 | `max_depth` **8**, `n_est` **700** |
| widened space, 50 trials | **0.395424** | `max_depth` 9, `n_est` **500**, `mcw` 4 |

Fold-paired: **+0.000811**, 95% CI **[−0.002659, +0.004281]**, **p = 0.552**, **4 of 5 folds
won**. Top five trials 0.3954 / 0.3953 / 0.3952 / 0.3944 / 0.3943 — the same flat plateau
Phase 8 found, one bound further out.

**Both intervals span zero, so no params move.** That is Phase 6's rule and Phase 8's
precedent, and −0.33% at p=0.198 is nowhere near Phase 7's −3.0% at p=0.004.

### The finding, which is about instruments rather than hyperparameters

**A coordinate probe cannot see a joint move, and from inside the probe that limitation is
invisible.** The probe stepped `max_depth` 8 → 10 holding everything else at the incumbent and
measured −0.0056. The search moved `max_depth` to 9 **while** more than doubling
`min_child_weight` and adding 300 trees, and measured +0.0038. Same axis, opposite sign,
because the optimum along it depends on where the other axes are.

Read carefully, the probe was not refuted — it answered the question it was asked ("does the
bound cost anything, one axis at a time") and that answer still stands. It was **over-read**,
by me, as an answer to the question the item posed ("is the space truncating the optimum").
This is §22's shape one more time: a number that replicates exactly and does not support the
sentence it is being used for.

**And the structural half of the item is confirmed, independent of the interval.** The
incumbent sits pinned at **two** edges of the old space; the widened winner is **interior on
all three** widened axes (9 < 12, 42 < 60, 900 < 1200). The old space *was* truncating the
optimum. The truncation is simply worth about a third of a percent, which five season folds
cannot separate from zero.

**The dilution objection was measured rather than argued, and it cuts both ways.** The standing
worry about widening is that a bigger space searched at a fixed 50 trials explores worse. On
p50 it did not — the widened search beat the narrow one on the same folds with the same budget.
On the classifier it visibly did: **31 of 50 trials pruned against Phase 8's 24**, and the best
still edged ahead by an amount no interval can see.

### The sentence Phase 8 could not say, and what it turns out to be

Phase 8 closed on this: *"both param sets pin `max_depth` at 8 and `n_estimators` at 700 — the
search wants more capacity than it is allowed to ask for, and it has wanted it since Phase 2
without anyone writing it down. What it does mean is that the sentence 'the learner is
saturated' has never been tested, and anyone who writes it is resting on bounds nobody has
probed."*

It has now been tested, and the reading was wrong. **Given a space that permits 1200 trees and
depth 12, the search asked for 500 trees** — fewer than the 700 it had been pinned at — and
depth 9, for +0.0008 at p=0.552. The classifier was never straining against that bound. It was
sitting on a plateau whose edge happened to be where the space stopped, which is exactly what
Phase 8's *other* observation (top five trials within 0.0008) already implied and what its
capacity language talked past.

**So the classifier's ~0.40 macro-F1 has now survived a label repair (Phase 8), a fresh search
on the repaired label (Phase 8 closed), and a search in a space with half again the capacity.**
Three explanations measured and gone. What has never been tried on it is a different feature
set or a different label grain — which is Phase 9 and Phase 10, not a search.

### What was verified vs assumed

**Verified — every arm reproduces a published number before any new number was read.** The
incumbent CV means recomputed here are p10 **0.589593**, p50 **1.146871**, p90 **0.627831**
(all three exactly the Phase 7 re-tune table) and cliff_classifier **0.394614** (exactly Phase
8's 0.3946). Stint-life's fifth fold is **1.9366**, exactly the published headline. The
instrument was checked against known answers before it was trusted with unknown ones, which is
Phase 6's rule for ceilings applied to a probe.

**Verified — both arms fit the way production fits.** The probe and the search both route the
fold fit through `train._fit`, so the IPW survival weights, the balanced class weights and the
AFT censoring flag are the production ones on both sides. Phase 2 finding 1 would otherwise be
live again in a new place.

**Verified — the detector fires on a real pin nobody went looking for.** Run over the five
tracked `*_best_params.json`, `boundary_params` names `stint_life_regressor`'s `n_estimators`
on the **low** bound (200). Probed downward: 150 is +0.0115 with 4/5 folds but p=0.162, 100 is
−0.0204, 50 is −0.5896 (p<0.001). So that bound is not costing anything either — but it is the
first pin in this series found by an instrument rather than by a person reading JSON.

**Assumed — 50 trials, one seed, and both arms are maxima over their own selection folds.**
The comparison is symmetric (the incumbent is itself the max of a 50-trial search on these
folds), so the bias does not obviously favour either side. It does mean the honest claim is
*"a widened 50-trial search beat a narrow one by 0.33% on the selection folds, 4/5"* and not
*"the widened space is worth 0.33% out of sample"*. With seven training seasons there is no
held-out season left to settle it, unchanged from Phase 7.

**Assumed — that p50 generalises to the other four.** It is the only target given a joint
search. The other four have the coordinate probe only, and this session is precisely the
demonstration that a coordinate probe is the weaker instrument.

### Gates run

| Gate | Result |
| :--- | :--- |
| `pytest ml/tests -q` | **177 passed** (was 163; +14 search-space) |
| `python -m ml.src.tune --target degradation_regressor_p50 --trials 50 --version v9` | 50 trials, best **1.1431**, winner interior on all three widened axes |
| Fold-paired refit, p50, v8 params vs v9 params, identical splits | **+0.003815**, p=0.198, 4/5 — interval spans zero |
| `python -m ml.src.tune --target cliff_classifier --trials 50 --version v9` | 50 trials, 19 complete / 31 pruned, best **0.3954**, winner asks for **fewer** trees than the bound it was pinned at |
| Fold-paired refit, classifier, old params vs v9 params, identical splits | **+0.000811**, p=0.552, 4/5 — interval spans zero |
| Coordinate probe, five targets, 27 param sets | no step past a bound clears its interval; stint-life significantly worse |
| `scripts/ml_docs_facts.py` | **PASS** (fired first on 163-vs-177, as designed) |
| `scripts/docs_facts.py` | **PASS** |
| `git status` on `ml/models/*_best_params.json` | **unchanged from the Phase 7 checkpoint** |

### What is deliberately not done

* **The p50 params are not adopted.** +0.0038 at p=0.198 does not clear the bar this series
  set for itself in Phase 6 and enforced in Phase 8 at p=0.716.
* **p10, p90 and stint-life were not given the joint search.** ~25 minutes each; p50 and the
  classifier got one. The other three have the coordinate probe only, which this session shows
  is the weaker instrument — so their nulls are weaker than p50's was, not stronger. Item 23.
* **Nothing is exported, carded, predicted or published**, and `MODEL_VERSION_DEFAULT` is
  still v6. The half-state Phase 7 left is unchanged: newest boosters v8 (plus two untracked
  v9 experiments), default v6, manifest v6, app serving v5.
* **The horizon-correct IPW weight (§25) and the weighted-metric question (§24)** are
  untouched, as in Phase 7.

---

## Resume here (next session)

*The tree is consistent. Every gate in the repo passes. Nothing is committed.*

### Where things stand

* Phases 0-5 — **Series I, complete and committed** (`7f23d8c` … `cdf2523`).
* Phase 6 — **done, uncommitted.** Two new modules, three test files touched, 99 ML tests
  green, no model retrained. See Checkpoint 2026-08-24 (Phase 6).
* Phase 8 — **complete and uncommitted, both halves.** The bound is at source under its own
  name and its own test, the label is repaired (6,825 rows, 99.5% out of `none_in_stint`), all
  five refit at v7, both approval baselines regenerated, 580/580 dbt tests and 132 ML tests
  green. **Repairing the label did not lift the classifier** — ratio to baseline 1.8015 →
  1.8163, macro-F1 0.4038 → 0.3971 on what is a different task. Read §23 first: the phase's own
  checklist had the mechanism backwards, and the phase moves the degradation target too. See
  Checkpoint 2026-08-25 (Phase 8).
  **The re-tune ran 2026-08-25 and found nothing** — 50 trials on the repaired label reached
  CV mean 0.3941 against the incumbent's 0.3946, losing 4 of 5 folds (p=0.716). The search
  product was reverted and the tree is unchanged. That closes the only escape hatch the
  previous handoff left open: "repairing the label does not lift the classifier" is now a
  result about the label, not about hyperparameters tuned for the old one. See Checkpoint
  2026-08-25 (Phase 8 closed).
* Phase 7 — **complete and uncommitted.** Target retargeted to the 5-lap column, bound
  reconciled per-column, trio re-tuned at v8 under the corrected objective, all five refit at
  v8, full evaluate green. Acceptance is **yes on the criterion that is like-for-like** (floor
  share up on all three, roughly doubled on two) and **mixed on the oracle multiple**, for the
  reason §26 gives. Export/card/app deliberately untouched. See the Phase 7 checkpoint.
* Phase 2 finding 1 — **closed, and it was two defects.** `tune.py` *and* `evaluate.py`
  (§24). 24 tests in `ml/tests/test_fit_parity.py`.
* Open item 21 — **closed 2026-08-26, uncommitted.** The hyperparameter space is declared as
  data, widened past every pin the series recorded, and a search that stops on an edge now says
  so; 14 new tests (177 green), both docs gates carried forward. **No params moved and no model
  was retrained** — the widened space's p50 optimum is +0.0038 at p=0.198 and the classifier's
  is +0.0008 at p=0.552. It also settles the sentence Phase 8 left open: given depth 12 and
  1200 trees the classifier asks for **500**, so it was never capacity-bound. See the
  2026-08-26 checkpoint, and read its "two instruments" section before trusting any coordinate
  probe in this repo. It opened items 23 and 24.
* Phases 9, 10 — **not started.** Phase 9 is now unblocked (both dependencies are done) but
  **must be re-read against §27 first**: its ablation ordering inverted.
* Open item 15 — **closed 2026-08-24, uncommitted.** New module, new test file, evaluate +
  Makefile touched, 119 ML tests green, no model retrained and no headline moved. See §21 and
  the item-15 checkpoint. It opened item 16.
* Open item 16 — **opened and refused the same day, uncommitted.** The +0.0178 macro-F1 it
  promised is look-ahead: the causal arm is +0.0015 against a ±0.0035 floor. Nothing was
  flattened, no version moved; what landed is the causal/future arm that refuses it, wired
  into the attribution pass and covered by 10 tests (129 green). See §22 and the item-16
  checkpoint. It opened item 17.

**Read §21 before Phase 7 or Phase 9, and §22 before acting on anything in §21.**

`ml/models/manifest.json` names **v6**. Phase 6 changed no artefact version and no booster;
the only regenerated tracked files are `ml/model_card.yml`, `ml/models/model_card.json`,
`app/public/models/model_card.json` and `docs/reference/ml/degradation-model.mdx`.

**Read §22 before reading §21 as guidance.** §21 measures what the models *use*; it does
not measure what a feature could *supply*, and on a forward-looking target those come apart.
Every negative flatten delta in §21 is unadjudicated until its causal arm runs (item 17);
every positive one survives as a lower bound.

**Read §18–§20 before Phase 7.** Phase 6 was meant to be the phase that changed nothing and
only re-anchored the reporting. It did that, and it also disproved the central claim of §12
that opened Series II. The short version: the trained target's between-stint share is 2.9%
and not 17.5% (the old figure was an estimator artefact), and the degradation models score
**12–28× past** that ceiling — provably, against the exact in-sample optimum over
stint-constant predictors. They are not operating in the 17.5%. They are operating in the
other 97.1%, which §12 called noise.

**That changes the shape of Series II more than it changes any phase's checklist.** Phases
7-10 were sequenced on the premise that the models are near the ceiling of a target that is
mostly noise. Two of those three words are now wrong: they are not near a ceiling, and the
target is not measurably noise-dominated in the part they use. The phases are still worth
doing — the reasons are different, and each one's note now says so.

### The decision that was open, and how it was resolved

The previous handoff asked whether the four structurally-unchanged models should have stayed
at v5 with only stint-life bumping to v6. **It was carried as the plan shipped it — all five
at v6** — on the plan's own stated reasoning (the predictions parquet contract changed 17 →
19 columns, so the version describes the artefact set, not one booster). It is now baked into
`app/public/models/`. Reversing it means a versioning-scheme change and a re-export, not an
edit. The user did not answer this question; it was resolved by proceeding, and that is worth
knowing before treating it as settled.

### What is genuinely still open

1. **Nothing is published to the CDN.** The app's committed state expects v6; prod serves v5.
   Deploying is `make app-publish` / `app-deploy` and is the user's call.
2. **The stint-life monotonicity violations** (5/19 steps in `laps_past_cliff`) — new, from
   this session's evaluate, never investigated.
3. **The uncensored population is barely better than baseline** — see above. If stint-life is
   to be trusted for completed stints specifically, that is the number to attack. **Quantified
   2026-08-24:** 3.3908 vs 3.4027, a 0.35% win at 4.98 laps median absolute error. Phase 6
   makes it visible; nothing yet proposes to fix it.
4. ~~`tune.py` searches the quantile regressors against the wrong estimator (Phase 2 finding
   1)~~ — **closed 2026-08-25, and it was in two places.** `evaluate.py:_fit` had the identical
   hole, which is the one that reached the model card: every published degradation headline
   described an unweighted model while the shipped boosters are weighted (§24). Both fit
   through one path now, and a quantile fit offered no weights raises rather than defaulting.
   **What it leaves behind**: the fit is weighted and the metric is not, and nothing has decided
   whether that is right (§24, second-order question).
5. The 2018 NULL-`stint_number` rows (Corrections §10) — defensive, not repaired at source.
6. **`pit_strategy_baseline_delta` carries an unfitted term** into the pit-lap argmin, on the
   user's explicit instruction. `compound_grip_peak` prices SOFT slower than HARD. One var
   flips it off; fitting a real per-compound baseline is the better fix. (Phase 5)
7. ~~**The cliff polynomial is unbounded**~~ — **closed 2026-08-25 by Phase 8, and the
   reading was wrong twice.** It is bounded at source now (`compound_wear_max_s_per_lap`, with
   `assert_compound_wear_bounded` proven live at 12,580 failures). But the label is a scan over
   `driver_skill_residual_s`, into which the curve is *subtracted*, so the tail was **erasing**
   cliffs into the majority class, not inventing them (§23). And repairing it **did not lift
   macro-F1** — the "ceiling set here rather than in XGBoost" claim is not supported by the
   refit. It may yet be supported by a re-tune, which was not run. **New cost, accepted by the
   user:** ghost recombination regressed, and `assert_ghost_recombination` was widened 10.0 →
   11.0 with the measurement written into the file.
8. **`tyre_management_score` is a ratio with 738 stints on its new clamp floor.** Bounded,
   not repaired. (Phase 5)
9. **The SC cost multiplier (0.5) is conventional, not measured**, and it moves the optimum.

Added 2026-08-24 (Series II; each is a defect, not planned work):

10. ~~**The trained degradation target is 82.5% noise and no artefact says so**~~ — **closed by
    Phase 6, and the premise was wrong.** It is 97.1% by the corrected estimator, and the models
    reach into it anyway (§18). Every headline now ships with a denominator.
11. ~~**The highest-SNR target in the warehouse has no consumer.**~~ — **closed 2026-08-25 by
    Phase 7.** `DEGRADATION_TARGET` is the 5-lap column, re-verified to max |diff| 0.0, and the
    trio is re-tuned onto it. "Highest-SNR" turned out to be the wrong reason (§26: its ICC is
    0.0094, and the incumbent's is 0.0000); the reason that survives is that it is the only one
    of the two with a non-degenerate attainable denominator. **Cost, newly named**: 28% of the
    training rows, taken from the end of stints (§25).
12. ~~**No `beats_baseline: true` in the model card carries an interval**~~ — **closed by
    Phase 6.** All five now do, all five clear both, and the card refuses to write without them.
    §15's 4.4× turned out to be a worst case that only stint life approaches (§20).
13. **`race_control` is ingested for 149 races and staged by nothing** (Corrections §17). There
    is no `stg_race_control`. 12,814 rows, including 4,909 blue flags that would label traffic
    exposure for free. **Phase 10a.**
14. **`pos_data` and `telemetry_full` have never run** — the writers exist at
    `ingestion/src/ingest.py:483-484`, gated behind `telemetry_full`, and both bronze
    directories hold zero files. **Phase 10c.**
15. ~~**Nothing establishes *what* the within-stint signal is.**~~ — **closed 2026-08-24 by the
    attribution measurement (§21).** It is **50.7% tyre-age ramp, 29.6% driver push, 19.7%
    traffic** of the within-stint signal that clears a measured refit floor. `traffic` is 95.2%
    within-stint — the model reads which *laps* ran behind a car, not which stints did — and
    `push_residual` alone outweighs the whole traffic channel. The degradation family is neither
    the tyre model the docs imply nor the traffic model §18 flagged as the risk; it is both, in
    about equal measure. **A new item 16 falls out of it.**

16. ~~**The cliff classifier is actively hurt by within-stint variation.**~~ — **closed
    2026-08-24 as refused, same day it was opened (§22).** The 0.0178 replicates exactly and
    is unreachable: the flatten's causal twin (laps 1..t) is **+0.00150 against a ±0.00352
    floor**, and an arm built from laps t..N alone scores *higher* than the full-stint mean on
    fewer laps. The win is the stint's future, not its per-lap noise, and no feature can carry
    it. What remains true and unactioned: the classifier's prediction ICC (0.2557) sits barely
    above its target's (0.2178). **That** is still a real observation — see item 17.

17. **The negative flatten deltas in §21 are unadjudicated below channel grain.** §22
    disqualifies the reading, not the rows. At channel grain the arm has now run: the
    classifier's `driver_push` **reverses** (−0.00365 flattened, **+0.00593** causally, clearing
    the floor the other way), so that row is not "unsupported" but backwards. Still open are the
    **per-feature** rows — `age_in_stint` (−0.00967), `surface_bulk_ratio` (−0.00599),
    `is_rain_lap` (−0.00369) — because the per-feature pass gets no causal arm: ~14 more fits
    per target, and no feature-level result is currently proposed for action. Note `age_in_stint`
    is a counter, so its causal arm would be degenerate anyway (see `rank_preservation`); a
    finding about it needs a different instrument, not a longer run. Opened 2026-08-24 by §22.

Added 2026-08-25 (Phase 2 finding 1 + Phase 7):

18. **The quantile trio is fitted weighted and scored unweighted.** The IPW correction now
    reaches the fit in all three code paths, and no metric anywhere applies it. If the weights
    describe the population the product cares about, the metric is wrong; if they do not, the
    fit is. Changing either moves every published number and every baseline comparison at once,
    so it needs deciding rather than drifting. §24.
19. **The IPW weight under-corrects for its own horizon by 1.22×.** `survival_weight` is
    `1/P(reach this lap)`; the 5-lap target needs `1/P(reach lap+5)`. Median 1.22×, p95 1.53×,
    and the share of rows on the [0.25, 4] clip ceiling would go 7.8% → 14.7%. One SQL
    expression in `fct_cliff_prediction_features`. §25.
20. **The 5-lap target drops 28% of training rows, from the end of every stint.** Half the laps
    at lap 31+ are gone. Isolated cost +0.76% pinball. Inherent to the horizon under "no SQL
    changes"; a partial-window target with a scaled sum would recover them, and would be a new
    column rather than an edit. §25.
21. ~~**`_suggest`'s search space is binding, and on the trio it is rewarded.**~~ — **closed
    2026-08-26, and both halves of it were half right.** The space *was* truncating the
    optimum: widened, a 50-trial p50 search lands interior on all three widened axes
    (`max_depth` 9, `min_child_weight` 42, `n_estimators` 900) where the incumbent was pinned
    on two edges. But the truncation is worth **+0.0038 fold-paired, p=0.198, 4/5** — it does
    not clear its interval, so the bounds moved and the params did not. The session's finding
    is about instruments rather than hyperparameters: a coordinate probe past the bound says
    **no** on all five targets and a joint search says **maybe**, because stepping one axis
    cannot see a move that needs three at once. The space is data now and a search that stops
    on its own edge says so (`tune.boundary_params`). **It opens item 23.**

23. **Three of the five targets have never had the joint search.** p10, p90 and stint-life
    have the coordinate probe only, and item 21 is the demonstration that a coordinate probe
    is the weaker instrument — so their nulls are weaker than p50's was, not stronger. ~25
    minutes each, one command each, no new data. Opened 2026-08-26.

24. **`stint_life_regressor` sits on the *low* bound of `n_estimators` (200).** Found by the
    new detector rather than by a person reading JSON, which is the point of it. Probed
    downward the bound costs nothing (150 laps: +0.0115 at p=0.162, 4/5; 100: −0.0204; 50:
    −0.5896), so this is recorded, not actioned — but no search in the series has ever been
    able to ask for fewer than 200 trees, and stint-life is the one target that wants to.
    Opened 2026-08-26.
22. **§21/§22's attribution is stale in a second way.** It was measured on the 1-lap target, and
    §27 shows the group ablation inverts at h=5 — `compound` goes 1.3% → 19.1%. Re-running
    `make ml-attribution` against v8 would say whether the channel split moves with it.

### Where Series II goes next

Phase 6 is closed. The next phase is **not obviously Phase 7 any more**, and that is the one
decision worth making deliberately rather than by proceeding:

* **Phase 7 (retarget to 5 laps)** still has a real mechanical case — averaging five laps
  doubles the between-stint share, 0.0289 → 0.0645 — and it is still one constant plus a
  retune. But §18 shows the models are not bounded by that share at all, so doubling it may
  buy nothing, and §19 removed the "the 5-lap column shows a process" argument entirely.
  Phase 2 finding 1 (`tune.py` searches the quantile trio against the wrong estimator) is
  still unfixed and still blocks it.
* **Open item 15 (what *is* the within-stint signal)** is new, costs no new data, and is now
  the question with the most leverage: it decides whether the degradation family is modelling
  tyres or modelling traffic. The artefacts to answer it — ablation deltas, SHAP, the
  corrected ceiling — are already on disk from this session's evaluate.
* **Phase 8 (bound the cliff curve)** gained weight rather than losing it. The classifier is
  at 114% of its stint-level ceiling, so the ~0.40 macro-F1 is not a learner limit; it is set
  in SQL by a first-crossing scan over an unbounded polynomial. That is the single clearest
  "the ceiling is the label" result in the series.

**Superseded 2026-08-24.** Item 15 is done (§21), and it changed the ordering again. The
recommendation is now **item 16, then Phase 8, then Phase 7**:

* **Item 16 first** because it is the smallest measured win left in the series — one
  feature-set change, already quantified at +0.0178 macro-F1, no new data and no dependency on
  Phase 8's label repair. It is Phase 9 work that escaped Phase 9's ordering constraint, and it
  should be taken before anything that moves the label underneath it.
* **Phase 8 second**, unchanged and still the clearest "the ceiling is the label" result.
* **Phase 7 last**, and still blocked by Phase 2 finding 1 (`tune.py`). §21 weakens its case a
  third time: the degradation family's within-stint signal is ~48% driver push and traffic, so
  averaging over a 5-lap window will smooth *those* channels as much as the tyre signal, and
  the 2.1× gain in between-stint share was never the binding constraint anyway.

**Superseded again 2026-08-24, by taking it.** Item 16 was attempted, measured and **refused**
— §22. The ordering is now **Phase 8, then Phase 7**, with no item ahead of them:

* **Phase 8 first.** It was second on the old list only because item 16 was cheaper, and item
  16 no longer exists. Nothing else in the series has Phase 8's evidence behind it: the
  classifier scores 114% of its stint-level ceiling, so ~0.40 macro-F1 is not a learner limit
  — it is a first-crossing scan over an unbounded polynomial that emits 93 s/lap on laps that
  were actually run. §22 sharpens the case rather than weakening it. The one lever §21 offered
  for lifting the classifier without touching its label has now been shown not to exist, which
  leaves the label as the only thing left to move.
* **Phase 7 second**, unchanged, still blocked by Phase 2 finding 1 (`tune.py`), and with §21's
  three weakenings still standing.
* **Phase 9 is not next**, but it inherits a rule from §22: on a forward-looking target, no
  flatten result may be acted on without its causal arm, and the drop-based ablation the phase
  is written around does not have this problem at all (a drop removes information; it never
  invents an admissibility question).

**Superseded again 2026-08-25, by taking Phase 8.** The SQL repair landed and the re-tune
did not. The ordering is now **finish Phase 8 (tune the classifier), then Phase 2 finding 1,
then Phase 7**:

* **Phase 8's own last item first.** Everything measured this session is at hyperparameters
  tuned for the contaminated label, and the class balance moved 70.1% → 65.1% on the majority
  class. Until that search runs, "repairing the label does not lift the classifier" is a
  result about a refit, not about the label. It is one command and one target.
* **Phase 2 finding 1 (`tune.py`) next**, because it now blocks two things rather than one:
  Phase 7's retune, and any honest re-search of the quantile trio whose target Phase 8 has
  just moved on 9.05% of rows.
* **Phase 7 after that**, unchanged, with §21's three weakenings still standing and §23 adding
  a fourth consideration: the 5-lap column is built from the same residual, so Phase 8 has
  already moved it too. Re-measure before re-arguing the phase.

**Superseded again 2026-08-25, by closing Phase 8.** The re-tune ran and found nothing, so
Phase 8 has no remaining item. The ordering is now **Phase 2 finding 1, then Phase 7**, and
the list is two items shorter rather than reordered:

* **Phase 2 finding 1 (`tune.py`) first**, unchanged in substance and now unblocked by
  anything of Phase 8's. It still blocks Phase 7, and §23 has made it worse rather than
  older: the quantile trio's params were selected against the wrong estimator *and* on a
  target that has since moved on 9.05% of rows.
* **Phase 7 second**, unchanged, with §21's three weakenings and §23's fourth all standing.
* **A note the classifier now carries into any future phase.** Its ~0.40 macro-F1 has
  survived a label repair *and* a fresh hyperparameter search. Two of the three obvious
  explanations are now measured and gone. What has never been tested is the search space
  itself — both param sets pin `max_depth` and `n_estimators` at the top of their ranges —
  and that is a cheap test, not a phase.

**Superseded again 2026-08-25, by taking both.** Phase 2 finding 1 is closed (in two places,
§24) and Phase 7 has landed. Nothing on the old ordering remains. What is left, in order:

* **The search-space test first**, because it is now the cheapest open thing in the series and
  this session doubled the evidence for it. Phase 8 saw the classifier pin `max_depth` and
  `n_estimators` on a *flat* plateau and correctly refused to call it headroom. Phase 7's trio
  pinned `max_depth` **and** `min_child_weight` while **gaining 3%**, and Optuna ranks
  `max_depth` p50's most important parameter (0.3175). One edit to `_suggest`, one search.
  Open item 21.
* **Phase 9 second, and re-read before restarted.** Both its dependencies are done, so it is
  unblocked for the first time — but §27 inverts the ablation it is written around, and
  `compound`, the group its checklist singles out as contributing nothing, is now the largest
  at 19.1%. The phase's *rules* survive intact (drop on the interval, never the point estimate;
  never act on a flatten without its causal arm). Its *numbers* do not.
* **Phase 10 last and unchanged** — the only phase that adds information rather than repairing
  a number, and the only one whose headroom §14 does not rule out. Its precondition ("do not
  start before Phase 7 has proven the target") is now met.
* **Two SQL-shaped items that belong to whoever next opens the warehouse** — open items 19 and
  20, both consequences of the 5-lap horizon that Phase 7's own "no SQL changes" rule forbade
  it from fixing.

**Superseded again 2026-08-26, by taking the search-space test.** It is done: the bounds are
widened and the optimum inside them is interior, but it is not worth shipping (item 21). The
ordering is now **Phase 9, then Phase 10**, with two cheap measured items beside them:

* **Phase 9 first**, unchanged in substance and still to be **re-read against §27 before it is
  restarted** — its ablation ordering inverted on the 5-lap target and `compound`, the group
  its checklist queues for deletion, is now the largest contributor at 19.1%. Its rules
  survive; its numbers do not.
* **Phase 10 second**, unchanged — still the only phase that adds information rather than
  repairing a number.
* **Item 23 (the three unrun joint searches) whenever there is idle compute.** It is not on
  the critical path of either phase, it costs ~25 minutes per target, and item 21 is the
  argument for why the coordinate-probe nulls on p10, p90 and stint-life should not be
  treated as settled.
* **Item 22 (`make ml-attribution` against v8) before anything reads §21 as current.** It was
  already stale in one way and §27 makes it two.

The first command:

```
python -c "import json; d=json.load(open('ml/artefacts/evaluation_metrics.json')); \
  m=d['models']['degradation_regressor_p50']; \
  print(m['attainable']['metric_native']['fraction_of_attainable_in_sample']); \
  print([(a['group'], a['delta_vs_full']) for a in m['ablation']])"
```

2.84 is the proof-carrying multiple; the ablation deltas beside it are where item 15 started.
**Superseded 2026-08-24:** item 15 is closed and item 16 refused, so the first command is now
the one in the item-16 checkpoint — it reads the `causally_reachable` verdicts, which is where
§22 lives on disk. Phase 8 is next and it starts in SQL (`int_compound_cliff_predicted`), not
in `ml/`.
Do not start by touching `train.py`.

**Superseded again 2026-08-25.** Phase 8's SQL half is done, so neither command above is the
starting point any more — and the item-16 one **will not work**: `evaluation_metrics.json` is
now a v7 report written without `--attribution`, so it prints `None`. That is expected, not a
regression; §22's verdicts were measured on a target Phase 8 has since moved. **The first
command is the one in the Phase 8 checkpoint** — the two dbt tests that hold §23 and its price
on disk. Phase 8's remaining item is a re-tune of the classifier **only**.

**Superseded again 2026-08-25, by closing Phase 8.** The re-tune is done, so the two dbt tests
are no longer the *next* thing either — they remain the right sanity check that §23 is still on
disk, and they passed at the top of the closing session. **The first command is now the one in
the "Phase 8 closed" checkpoint**: `grep -n "meta is deliberately NOT passed" -A 6 ml/src/tune.py`,
which puts Phase 2 finding 1 on screen at the line where it bites. Phase 8 has no remaining
item. Still do not touch `train.py` first, and still do not tune the quantile trio until that
finding is fixed.

**Superseded again 2026-08-25, by fixing it and taking Phase 7.** That grep now finds nothing —
the comment it points at was the defect, and the defect is gone. **The first command is the one
in the Phase 7 checkpoint**: three fields out of the v8 report, which print `v8 100.72 0.473`
and are the phase's entire case. Then read §27 before opening Phase 9.

**Superseded again 2026-08-26, by closing item 21.** That command still works and still prints
`v8 100.72 0.473` — nothing this session touched an artefact. **The first command is now the
one that puts item 21's own result on screen**, because it is the thing most likely to be
mis-read next:

```
./.venv/bin/python -c "
from ml.src import tune as TU, schema as S
import json
for t in ['degradation_regressor_p10','degradation_regressor_p50','degradation_regressor_p90',
          'cliff_classifier','stint_life_regressor']:
    b = json.load(open(f'ml/models/{t}_best_params.json'))
    print(f'{t:32}', TU.boundary_params(b, S.TARGET_BY_NAME[t]))"
```

Four empty dicts and `{'n_estimators': 'low'}` for stint-life. The four are empty because the
bounds moved, **not** because anything was retuned — every one of those files still holds the
params Phase 7 shipped. The fifth is item 24. Then read the 2026-08-26 checkpoint's "two
instruments" section before running any probe, and **§27 before opening Phase 9**.

**Superseded again 2026-09-05, by closing Phase 9.** The 24-feature contract is fitted, shipped
and gated; see the 2026-09-05 checkpoint below for the numbers, including the two surprises
(the classifier and stint-life headlines moved more than any single group's floor predicted,
and `app/public/models/` grew rather than shrank — for a reason unrelated to the prune). The
ordering is now **Phase 10 last and unchanged** — the only phase still on the list, and the
only one that adds information rather than repairing a number. Its precondition (Phase 7's
target proven) has been met since the previous session; nothing this session did changes that.
Open items 19, 20 and 22's write-up remain unclaimed, exactly as the previous entry left them.

### Standing cautions (unchanged, still true)

* **The dev profile is not reproducible** — `threads: 4`, no `settings.threads`. Determinism
  holds only under `ci`.
* **`make transform-check` does not pass on `main`** — 8 pre-existing `sqlfluff` failures.
* **`npx tsc --noEmit` reports success while checking nothing** (`app/tsconfig.json` is
  solution-style with `"files": []`). Use `npm run typecheck`.
* **`ml/models/*_best_params.json` are tracked, and `make ml-retrain` refits production from
  them.** The trio's three now hold params searched against the **5-lap** target. `train.py`
  will refuse to overwrite a version fitted on a different column — but only for versions built
  since Phase 7, because older logs do not record the column. **v6 is one of those**: it warns
  and proceeds. Added 2026-08-25.
* **Nothing here is committed, and the agent does not commit.**

---

## Checkpoint 2026-09-05 (Phase 9 closed — the 24-feature set is fitted, shipped, and gated)

Phase 9's implementation pass. The decision (drop `powertrain`, `telemetry_cliff`,
`weather_air`, `track`, `context`; keep `stint_position`, `compound`, `cliff_prior`,
`thermal`, `dirty_air`) was already written into this file's Phase 9 section before this
session started, on the noise-floor ablation re-run against v8. Nothing in that decision was
re-derived here — this session's job was the four schema edits, the fit nobody had done yet,
and the full pipeline through to `app/public/models/`. All three of Phase 9's checklist items
are now checked; see that section above for the byte-size table and the guard-engagement
detail rather than repeating them here.

### What landed

* **`ml/src/schema.py`** — `FEATURE_GROUPS` drops the five groups (18 columns), `FEATURE_COLUMNS`
  follows automatically (42 → 24). `CATEGORICAL_COLUMNS` loses `constructor_id`/`anomaly_class`
  (now `(compound, air_state_dominant)`), `BOOLEAN_COLUMNS` loses `event_flag_any`/`is_rain_lap`
  (now `(cliff_onset_passed, cliff_candidate_flag)`), `AUDIT_FEATURES` loses `anomaly_class`
  (now `(cliff_candidate_flag,)`). `MODEL_VERSION_DEFAULT` is `"v10"`, with a new lineage
  comment above the v6/v5 history explaining what v10 actually is: the first artefact set that
  reflects Phase 7's 5-lap target and Phase 8's source-bounded cliff label *and* Phase 9's
  pruned contract, none of which had ever been shipped under a version bump before this session
  — `v6` was the stale label the whole time, and it stays the rollback floor because it is the
  last version actually exported to `app/public/models/` (v7/v8/v9 only ever existed as
  `ml/models/*.bst`, never copied out).
* **Five `_v10.bst` boosters, five `_v10.onnx` exports, `_smoke.bst` × 5 regenerated** — all
  gitignored, not in `git status`. `ml/models/manifest.json`, `encoders.json`,
  `model_card.json` (tracked) and `ml/model_card.yml` regenerated at v10.
* **`ml/src/attribution.py`** (untracked, new this series) — `CHANNELS`, a second taxonomy
  (item 15's physics hypotheses, independent of `FEATURE_GROUPS`) that still listed all 42
  columns, pruned to match: `tyre_thermal` 5→3, `driver_push` 10→1, `environment` 7→0 (kept as
  an explicit empty tuple with a comment, not deleted — `within_stint_ablation` skips empty
  units as a no-op, verified by reading it before relying on it).
* **`ml/tests/test_attribution.py`** (untracked) — three tests used `is_rain_lap` as their
  example boolean/discrete column; since it left `BOOLEAN_COLUMNS`, the functions under test
  silently fell through to the continuous branch and two of three assertions passed by
  coincidence (the mean of a 0/1 column and its mode agree unless there's a tie) rather than by
  testing what they claimed to. Swapped to `cliff_candidate_flag`, which is still boolean.
* **`scripts/dump_parity_rows.py`** — `np.clip(..., -10, 10)` was hardcoded to the 1-lap
  target's bound; Phase 7 moved the 5-lap target's to ±50 and nothing had run `app-parity`
  since to notice. Fixed to `-S.TARGET_BOUND, S.TARGET_BOUND`. This was a real, live bug, not
  a Phase-9 side effect — full detail under Gates below.
* **`scripts/ml_docs_facts.py`** — the ML-inventory card's body text hardcoded the ten group
  names in prose (`"Per-lap thermal, dirty-air, powertrain, ..."`); the title templates off
  `len(FEATURE_GROUPS)` correctly but the body did not. Rewritten to the five kept groups.
* **Hand-written docs corrected** (grepped for `42` and the five dropped group names across
  `docs/`, `README.md`, `ml/README.md`, then also found two more outside that grep by reading
  adjacent code): `docs/ml/overview.mdx`, `docs/ml/pipeline.mdx`, `docs/ml/models.mdx`,
  `docs/ml/feature-contract.mdx` (title/description/H2/CardGroup rewritten to 5 groups, a new
  note dated to the prune), `docs/ml/features-and-targets.mdx` (categoricals list; a note
  flagging that its two "measured and rejected" write-ups now reference dropped columns,
  historical numbers left untouched), `docs/ml/ci/leakage-spine.mdx` (two *current*-tense `42`s
  fixed to 24; one historical incident left as `42` deliberately — see Verified vs assumed),
  `docs/AGENTS.md`, `README.md` (three mentions, including the `v6`/`v5` version labels next to
  the feature counts — bumped to `v10`), `ml/README.md` (a Phase-7-era sentence saying the
  shipped version "disagrees" with the 5-lap target — no longer true now that v10 shipped it,
  rewritten rather than left stale), `app/src/features/model-metrics/methodology.tsx` (user-
  facing app copy, outside the grep's stated scope but found and fixed), `app/src/ml/verifyParity.ts`
  (two code comments, not logic — the logic was already manifest-driven).
* **`app/src/ml/featureVector.test.ts`** — one hardcoded `expect(vec.length).toBe(42)`, plus
  three tests keyed to now-dropped columns (`constructor_id`, `event_flag_any`, `is_rain_lap`)
  that would have failed or (in `is_rain_lap`'s case) silently stopped exercising the branch
  they claimed to. All four fixed against live columns; full failure detail under Gates.
* **`app/public/models/`** — v10 ONNX + manifest + encoders + card copied over v6.
  **`app/public/data/`** — re-exported; `_manifest.json` and `ml/mart_degradation_predictions/*`
  changed (both expected). **Three unrelated files also changed**:
  `app/public/data/marts/mart_corner_skill_driver/{2018,2019,2024}.parquet` moved by a handful
  of bytes each (4267→4260, 4261→4263, 4409→4390) — parquet re-serialization noise from
  re-running `app-data` against an unrelated table, not a content change this session caused.
  Noted so the next session doesn't chase it.
* **`data/marts/mart_degradation_predictions.parquet`** (the local warehouse copy `ml-predict`
  writes) — regenerated at v10, 137,447 rows.
* **`_improvements/ml_execution_plan.md`** (this file) — Phase 9's three remaining checklist
  items checked with real numbers; this checkpoint; a "Superseded again" line in "Where Series
  II goes next."

### What was verified vs assumed

**Verified — the before/after comparison is like-for-like.** v8's `evaluation_metrics.json`
was copied out before `ml-evaluate` overwrote it (`/tmp` scratch, not in the repo). Both reports
share `mode=cv_final_fold`, `eval_season=2024`, and identical `n` per family (13,896 / 19,145 /
20,272) — confirmed by reading both files' `models.*.n` rather than assuming the fold didn't
move under the new feature set.

**Verified — every gate that was supposed to catch a feature-count change did, with one
exception found and closed.** `test_feature_contract_subset_of_mart` and the manifest
`shape[1]` check are schema-derived and needed no edits (see Phase 9's checklist item above for
why that counts as "engaged," not "untested"). What was **not** schema-derived, and did need
editing, was found in three unrelated places by the same failure mode — a literal or a fixture
column that stopped tracking `FEATURE_GROUPS`/`BOOLEAN_COLUMNS` when those changed:
`attribution.py`'s `CHANNELS`, `dump_parity_rows.py`'s clip bound, and two JS test files. None
were weakened; all were corrected to the new ground truth, and each correction is recorded
above with the reasoning, per this doc's own rule against silently loosening a gate.

**Verified, and reported rather than smoothed over — the combined drop of five "noise-floor"
groups is not noise-floor for two of the five models.** Per-model, per-target headline,
v8 (42 features) → v10 (24 features), same eval fold:

| model | metric | v8 | v10 | Δ | % | vs. that family's single-group floor |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| `degradation_regressor_p10` | pinball ↓ | 0.510385 | 0.525219 | +0.014835 | **+2.91%** | no p10-specific floor exists (see below) |
| `degradation_regressor_p50` | pinball ↓ | 1.029103 | 1.034661 | +0.005558 | **+0.54%** | **0.36×** its own floor (0.015280) — inside noise |
| `degradation_regressor_p90` | pinball ↓ | 0.551656 | 0.564509 | +0.012853 | **+2.33%** | no p90-specific floor exists (see below) |
| `cliff_classifier` | macro-F1 ↑ | 0.397149 | 0.372960 | **−0.024189** | **−6.09%** | **3.50×** its own floor (0.006917) |
| `stint_life_regressor` | AFT NLL ↓ | 1.936635 | 1.956152 | +0.019517 | **+1.01%** | **2.59×** its own floor (0.007541) |

All five still `beats_baseline` and `beats_baseline_significant` after the drop — this is not a
claim the phase broke, and it is not a reason to re-tune (nothing here calls for that; it is an
open item for whoever opens Phase 10 or revisits this). But **p50 is the only family where "the
combined drop is inside the noise a single group would need to clear" turned out true.** The
classifier moved 3.5× its own single-group floor and stint life moved 2.6×, in the direction
that costs accuracy, even though the Phase 9 ablation table found no *individual* one of the
five dropped groups clearing that floor in *any* family. That is exactly the gap the Phase 9
section's own "Assumed" list already named — *"one eval fold generalises," "no group delta
carries a fold-paired interval"* — now measured rather than hedged. Read together with the
byte-size result below (the payload got bigger, not smaller), this session's honest summary is:
**the prune shipped as decided and the guards held, but its stated payoff did not land the way
either the checklist or the ablation table implied it would.** Neither number was recomputed a
second time or re-run at a different seed; both are single measurements on the one eval fold
this whole series uses, same as everything else in it.

**Assumed — same as the phase's own "Assumed, and it is the real gap" note, still true and
still not closed by this session:** `degradation_regressor_p10`/`_p90` were never scored by the
ablation (only the headline model per family is), so there is no single-group floor to compare
their +2.91%/+2.33% moves against, and this checkpoint does not manufacture one. They are
reported as raw deltas, not adjudicated.

**Not verified — whether the classifier's and stint-life's larger-than-floor moves are the
five groups acting jointly (an interaction the group-at-a-time ablation cannot see) or one
single group among the five actually mattering more than its own individual-drop delta
suggested on a different fold.** Distinguishing those would need re-adding groups one at a time
into the 24-feature set and re-fitting, which nobody has done. Flagged as the natural next
measurement, not attempted here — it is a re-tune-shaped question and the phase's own checklist
explicitly does not call for reacting by re-tuning.

### Gates run

| Gate | Result |
| :--- | :--- |
| `make ml-features` | **OK** — `[leakage guard] CLEAN (24 features)`, train rows=82,315 |
| `make ml-retrain` (`--all --tuned`, existing `*_best_params.json`, no new search) | **OK** — 5/5 fit at v10 |
| `make ml-evaluate` | **OK** — all 5 `beats_baseline` + `beats_baseline_significant`; headline table above |
| `make ml-predict` | **OK** — 137,447 rows, version=v10 |
| `make ml-onnx` | **OK** — ONNX parity 5/5 pass (`abs` ≤ 2.86e-05 on all); manifest 24 features, v10 |
| `make ml-card` | **OK** |
| `make ml-reference` | **OK** — `docs/reference/ml/degradation-model.mdx` regenerated, confirms "24 features in 5 ablation groups" |
| `make ml-test` (1st run, pre-fix) | **6 failed, 3 errors, 168 passed** — 3 `test_predict.py` errors (stale 42-feature `smoke` boosters), 4 `test_attribution.py` failures (stale `CHANNELS` + `is_rain_lap` fixtures), 2 expected `test_manifest_contract.py` failures (app-models not yet run) |
| `./.venv/bin/python -m ml.src.train --all --smoke` | **OK** — 5/5 smoke boosters refit at 24 features (guard correctly warned of the fingerprint change before proceeding) |
| `make ml-test` (2nd run, after fixes above) | **175 passed, 2 failed** — only the two app-models-pending failures remain |
| `./.venv/bin/python scripts/ml_docs_facts.py --write` (1st, then again after fixing the script's hardcoded group prose) | **OK both times** — 6 snippets written, idempotent on the 3rd (check-only) run |
| `./.venv/bin/python scripts/docs_facts.py` | **PASSED** — dbt models 68, dbt tests 577, ML models 5, ML tests 177, **ML features 24**, all consistent across README/overview/authority snippet |
| `make app-data` | **OK** — 37 tables, 423 MB total (unchanged); 3 incidental byte-level diffs on an unrelated mart, see above |
| `make app-models` | **OK** — v10 copied; `app/public/models/` 30,362,421 → 35,377,078 bytes (+16.5%), see Phase 9's checklist item for the per-model table and why |
| `make app-parity` (1st run) | **FAILED** — `maxAbs=11.995548248291016` vs tolerance `1e-3`; `cliffMismatches=0`. Root cause: `scripts/dump_parity_rows.py`'s hardcoded `±10` clip against a value the ONNX side correctly left unclipped at the manifest's `±50` bound |
| `make app-parity` (2nd run, after the fix) | **PASSED** — `maxAbs=3.325e-4`, `cliffMismatches=0` |
| `make ml-test` (3rd, final run) | **177 passed** — full green, including both manifest-contract tests now that `app/public/models/` is synced |
| `make app-build` | **OK** — `tsc -b && vite build` clean; pre-existing >500kB chunk-size advisory warnings, unrelated to this session |
| `cd app && pnpm exec vitest run` (full suite) | **First run: 4 failed** (1 hardcoded `42`, 3 fixtures on dropped columns in `featureVector.test.ts`) → **fixed → 347 passed, 1 skipped** (`parity.node.test.ts`, covered separately by `app-parity` above) |
| `make app-e2e` | **Deliberately skipped.** Reads `playwright.config.ts`: with no `E2E_BASE_URL` it serves the local build but fetches data + models from the **live GCS CDN**, which is still v6/42-features (nothing was published this session, and publishing is out of scope). Running it now would smoke the existing production deployment, not this session's changes — it would not exercise the 24-feature contract at all. Not run for that reason, not for lack of time. |
| `make app-bundle` | **Not run.** Checks the JS bundle against a size budget; the ONNX models load from the CDN, not the bundle, so it does not measure the claim this phase makes. Judged out of scope rather than skipped by omission. |

### Open decisions blocking the next phase

None of these block Phase 10 starting; they are open items this session found or left standing.

1. **The classifier's and stint-life's larger-than-single-group-floor regression (3.50× and
   2.59×) is unexplained.** Is it five groups' joint effect, or one group whose individual-drop
   delta undersold it on this fold? Whoever revisits Phase 9's evidence — or reads this before
   deciding whether the prune needs walking back for these two families specifically — should
   start here, not re-derive it.
2. **The ONNX-size payoff this phase was justified on did not materialise in the shipped
   total**, because the version bump also carried Phase 7/8's hyperparameter retune. If a
   future session wants the *isolated* Phase-9-only byte number for all five models (not just
   the two data points measured here — `cliff_classifier` and a same-hyperparameter `p10`
   side-export), it would need the pre-retune params refit at 24 features, which nobody has
   done and this session did not attempt.
3. **Open items 19, 20 and 22's write-up** (named in the previous checkpoint's "Where Series II
   goes next") are still unclaimed — nothing here touched them.
4. **Phase 10 is next**, unchanged from the previous session's ordering, and its precondition
   (Phase 7's target proven) has been met since before this session started.

### The first command the next session should run

```
python3 -c "
import json
before = json.load(open('ml/artefacts/evaluation_metrics.json'))
m = before['models']
for name in m:
    print(name, m[name]['headline'], m[name]['beats_baseline_significant'])
"
```

Confirms the v10 numbers in the table above are still what is on disk (this session did not
revert anything — unlike the Phase 8 closing checkpoint, nothing here needed to be). Then read
open decision 1 above before deciding whether the classifier/stint-life regression needs its
own investigation ahead of Phase 10, or whether it is recorded and carried forward as this
phase's honest cost.

---

## Checkpoint 2026-09-05 (Phase 10a closed — a new sensor, a real gain, and a reproducibility bug that nearly shipped)

Phase 10a end to end: SQL, the ablations that decide it, the contract change, a full refit of
all five models at **v11**, and the pipeline through to `app/public/models/`. **This is the
first phase in either series where a feature ADDITION moved a headline past its own noise
floor**, and the first whose feature comes from a different sensor rather than from a further
transform of lap times or the car channel — the specific thing the "Not recommended" list said
a 43rd feature would have to be.

Three of this phase's framing assumptions turned out to be wrong. All three are measured, not
argued, and all three are written into the checklist above as well as here:

1. **10c's ingest was never needed.** The position channel has been in bronze since the
   beginning of the project.
2. **10c's build-cost premise was wrong by roughly an order of magnitude.** The `pos` rows
   every build "wastes" cost ~0.36 s, not a painful scan.
3. **My own first build was not reproducible**, and only the byte-stability oracle could have
   caught it. That one is the most useful thing here and is written up in full below.

### What landed

All uncommitted, per this doc's convention. The working tree went 74 → 90 entries; the 16 new
entries are this session's. Nothing from Phases 6–9 was reverted or tidied.

**New SQL (6 files, untracked):**

* **`transform/models/staging/stg_telemetry_position.sql`** — the channel split. The only
  reader of `source_channel='pos'` in the project (58.8M of 118.7M telemetry rows), projecting
  `relative_distance`, `pos_x`, `pos_y`, `session_time_s` and FastF1's own
  `driver_ahead_number` / `distance_to_ahead_m`. Deliberately *not* `stg_telemetry` with a
  different `WHERE`: it drops the car-channel's `distance_m BETWEEN 0 AND 6500` guard, because
  its position column is a 0..1 lap fraction that carries its own bound and that guard would
  silently remove pit-lane and out-lap samples the proximity measure needs to see in order to
  exclude them *with a reason*. `pos_x`/`pos_y` have no consumer today; they are carried for 10b.
* **`transform/models/intermediate/int_lap_proximity.sql`** — the model. 162,729 rows, one per
  race lap, spine verified equal to `int_lap_air_state` and `int_stint_geometry`. Nine per-lap
  scalars reach the mart. Three guards, every one of them added because a test failed rather
  than because it was anticipated: a **self-match guard**, a **stoppage guard**
  (`proximity_max_gap_s`, 300 s, new var — exactly one lap in 162,729 exceeds it: 2023 São
  Paulo, VER lap 3, 1484.5 s, that race's red flag), and **two window tie-breaks** (below).
* **`transform/models/staging/stg_race_control.sql`** — **closes open item 13.** 12,814 rows
  across 149 races, ingested since the beginning and staged by nothing until now. Resolves
  `RacingNumber` (a car number) to `driver_id` (a three-letter code) via `stg_results`. All
  4,909 blue flags resolve.
* **`transform/tests/assert_proximity_crossing_total_order.sql`** — the reproducibility gate.
* **`transform/tests/assert_proximity_agrees_with_blue_flags.sql`** — the independent check.
* **`transform/tests/assert_proximity_train_subset_of_within1s.sql`** — a subset invariant
  between two independently-computed `AVG(CASE...)` columns; the same shape of defect Phase 8
  found in the cliff bound (two applications of one rule, one of them maintained).

**Modified:** `fct_cliff_prediction_features.sql` + `marts/schema.yml` (nine columns, carried
**alongside** the `air` block, not replacing it; five `not_null`, four deliberately nullable
because NULL means "no car within a full lap" and defaulting would invent a car);
`staging/src_formula1.yml` (new `raw_race_control` source); both layer `schema.yml`s;
`transform/tests/README.md`; `transform/tests/model_hashes.baseline.json`; `dbt_project.yml`;
`ml/src/schema.py` (`proximity` group, 24 → 33; `MODEL_VERSION_DEFAULT` v10 → **v11**);
`ml/src/attribution.py` (the nine join the existing **`traffic`** channel — same physics
hypothesis, different sensor — with the consequence named in-file: item 15's "traffic = 19.7%"
was measured over 4 columns and any re-run now measures 13, so the two are not comparable);
five `_v11.bst`/`_v11.onnx`/`_smoke.bst` (gitignored) plus the tracked manifest/encoders/card;
`app/public/models/` and `app/public/data/`; ten docs files; `app/src/ml/verifyParity.ts` and
`featureVector.test.ts` (a hardcoded `toBe(24)`); all ten generated inventory snippets;
`Makefile` (its `dbt-dev`/`dbt-test` help said "60 models"/"443 tests" — **both already wrong
before this session**, the real numbers were 68/577; now 71/594, and nothing gates them).

### The reproducibility bug, because it is the most transferable thing here

The p50 ablation arm scored **1.017496** against one build of the mart and **1.021648**
against the next, with no code change in between — a 0.28×-of-noise-floor swing from a
rebuild. The 24-column baseline arm was bit-identical across the same pair, which localised it
to the nine new columns.

**Cause: two `LAG`/`LEAD` windows ordered on keys that are not total orders.** Inside a tied
block the neighbour is arbitrary and the choice moves with DuckDB's scan parallelism.

| window | ordered on | ties | effect |
| :--- | :--- | ---: | :--- |
| `w` — who is the car ahead | `crossing_time_s` | **223,602 of 15,821,726** crossings (1.39%) | two cars enter the same ~50 m bin at the same recorded instant (e.g. 2024_4 bin 5 lap 44: NOR and SAI both at 9700.823) |
| `wd` — how long a bin took | `crossing_time_s` | 76 pairs | the **lap rollover**: FastF1 gives the transition sample to both laps, so bin 99 of lap N and bin 0 of lap N+1 share a time. `LEAD` could hand a bin a whole lap of duration |

Fixed with `ORDER BY crossing_time_s, driver_id` and
`ORDER BY crossing_time_s, lap_number, track_bin`. **Byte-identical across three consecutive
builds afterwards** (`1e6c7d22…`), and the mart with it (`253fbb7b…`).

Two things worth carrying forward:

* **`stg_telemetry` documents this exact defect one layer down** ("982,303 car-channel samples
  tied on distance_m… two builds of this identical SQL disagreed on ~500 laps"). The note was
  in the repo the whole time. I reproduced the bug anyway, in a model whose header I had
  already written. Reading the warning is not the same as applying it.
* **No gate in the repo except byte-stability could see it.** Row counts, null rates, ranges,
  the contract, and even the blue-flag agreement all passed on the broken build, because the
  values stayed individually plausible and only the *assignment* of neighbours moved. The
  `wd` bug in particular moved `time_within_1s` by up to **2.841 s (5.06%)** while
  `share_lap_within_1s`, computed over the same bin *set*, did not move at all.

A third, much smaller instability remained after both fixes — one row of 162,729 at
max |diff| **1.42e-14**, from a parallel float `SUM` — and is closed by `ROUND(..., 4)`, the
convention `int_lap_air_state` already uses. Rounded rather than tolerated: a model that is
*nearly* reproducible makes the byte-stability gate flake instead of work.

**Cost of finding it late:** the whole ML pipeline was run twice. Every number below is from
the final, deterministic mart. The rounding changed `time_within_1s` on 60,796 rows and moved
**no headline at all** — all five are identical to six decimals across that rebuild, which is
itself the evidence that the 1e-4 rounding is immaterial to the fits.

### The result, and the measurements that decide it

**Add-ablation**, run before the contract moved. Identical split, `evaluate.py`'s own
`_fit`/`_score`, each delta against that family's own 5-reseed floor (`2*sqrt(2)*sd`) — the
denominator Phase 9 used.

| family | metric | baseline (24) | **+proximity (33)** | Δ | vs. own floor | swap arm (drop `dirty_air`) |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `degradation_regressor_p50` | pinball ↓ | 1.034661 | **1.012128** | −0.022532 | **1.54× CLEARS** | +0.002189 (0.15×, inside) |
| `cliff_classifier` | macro-F1 ↑ | 0.372960 | **0.380950** | +0.007990 | **2.17× CLEARS** | −0.002487 (0.67×, and *worse* than baseline) |
| `stint_life_regressor` | AFT NLL ↓ | 1.956152 | **1.952005** | −0.004146 | 0.59× inside | −0.002712 (0.39×, inside) |

**All nine columns kept, because the gain is monotone in group size** — not on taste. p50 runs
0.40× (3 cols) → 0.91× (5) → **1.54×** (9); the classifier 1.44× → 2.07× → **2.17×**.

**Permutation-null arm — is it the traffic signal or nine extra split candidates?** Same
33-wide matrix, same params, proximity columns row-shuffled in train and eval, so capacity is
preserved exactly and the signal is destroyed. This was listed as "not verified" in the first
draft of this checkpoint and then run, because it is the cheapest thing that could falsify the
phase's headline:

| family | capacity effect (N−A) | information effect (B−N) | reading |
| :--- | ---: | ---: | :--- |
| `cliff_classifier` | −0.000416 (0.11×) | **+0.008406 (2.28× CLEARS)** | **the win is the traffic signal** |
| `degradation_regressor_p50` | −0.011286 (0.77×) | −0.011247 (0.77×) | **≈50/50, neither half clears alone** |
| `stint_life_regressor` | +0.001218 (0.17×) | −0.005365 (0.77×) | inside noise either way |

**So the classifier's gain is unambiguously information, and p50's is not cleanly
attributable.** Its total clears the floor, but it splits roughly evenly between information
and capacity and neither half clears on its own. That is recorded rather than rounded up, and
it is written into `schema.py` beside the group so the next reader meets it there too.

**Production refit, v10 → v11** — same `mode=cv_final_fold`, same `eval_season=2024`,
identical `n` per family, confirmed by reading both reports' `n_eval_rows` rather than
assuming the fold held. Nothing was re-tuned: v11 uses v10's `*_best_params.json` unchanged,
so the move is attributable to the nine columns and to nothing else.

| model | metric | v10 (24) | v11 (33) | Δ | % |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | pinball ↓ | 0.525219 | 0.520863 | −0.004356 | **−0.83%** |
| `degradation_regressor_p50` | pinball ↓ | 1.034661 | 1.012128 | −0.022532 | **−2.18%** |
| `degradation_regressor_p90` | pinball ↓ | 0.564509 | 0.559195 | −0.005314 | **−0.94%** |
| `cliff_classifier` | macro-F1 ↑ | 0.372960 | 0.380950 | +0.007990 | **+2.14%** |
| `stint_life_regressor` | AFT NLL ↓ | 1.956152 | 1.952005 | −0.004146 | **−0.21%** |

All five still `beats_baseline` **and** `beats_baseline_significant`, 5/5 folds on each.
Underperforming cohorts unchanged at 11. For scale: the classifier's +0.007990 recovers **33%**
of the −0.024189 that Phase 9's prune cost that family. It does not close it, and this phase
did not attempt to.

**Cost of the win:** `app/public/models/` 35,377,078 → 36,260,899 bytes (**+2.5%**). Phase 9
shrank the contract partly for payload and paid +16.5%; this phase grew it and paid 2.5%.

### What was verified vs assumed

**Verified — the position channel was already in bronze, across every season.** This is the
finding that took 10c's ingest off 10a's critical path, so it was checked deliberately rather
than generalised from the one race I first opened: one race per season for all 7 seasons plus
5 randomly-sampled races — `X`/`Y`/`RelativeDistance` 100% non-null in all 12,
`Source='pos'` present in all 12. Whole-bronze totals: 59,557,961 `car` / 58,831,651 `pos` /
318,995 `interpolation`. The plan's "~9M `pos` rows per season" is right (58.8M / 7 = 8.4M);
what was wrong was what scanning them costs.

**Verified — the new measure disagrees with the incumbent, and the disagreement favours the
new one.** Head-to-head at bin grain against FastF1's own `DriverAhead` (car number resolved to
code through `stg_results`): **87.05%** identity agreement across all seasons. Where they
agree the gaps are close; **where they disagree FastF1's own `DistanceToDriverAhead` is
roughly twice as large** (median 3.64 s vs 7.71 s on the race probed in detail) — it is naming
a car further away than the one actually ahead on track. Carried into the model as
`ff_ahead_identity_agreement` so this is re-checkable without re-deriving it.

**Verified — the blue-flag check is independent, and it holds per season, not just pooled.**
Median closest car, blue vs rest: 0.300/0.801, 0.300/0.600, 0.440/0.659, 0.220/0.860,
0.200/0.460, 0.201/0.441, 0.200/0.520 — **7 for 7**. The incumbent moves the **wrong way** on
the identical split (`dirty_air_share_lap` 0.2402 → 0.1327; `time_in_dirty_air_s` 30.08 →
19.17), which is not a rounding artefact but a structural blind spot: a car being lapped has
the fast car *behind* it, and `DistanceToDriverAhead` only looks forward.

**Verified — and reported rather than smoothed over — the 10c cost premise is wrong.** The
counterfactual was built, not argued: a full physical bronze split (column-projected, zstd,
sorted) compresses 6.48 GB → 1.80 GB and speeds the window-heavy path 7.91 s → 6.63 s. That is
~1.5 s of whole-warehouse build time for 1.8 GB of duplicated bronze and a regeneration seam
that must re-run after every ingest and can silently diverge. Rejected on those numbers, scratch
copy deleted, and the split that *did* land is a dbt staging model costing zero disk. Real
outcome: the three telemetry models together 77.3 s → 83.9 s (**+8.5%**), with
`int_lap_proximity` at 7.9 s standalone — cheaper than either model that predates it.

**Verified — four gates caught four real defects, none anticipated.** Named because "the gate
engaged" is a claim this doc requires evidence for. (1) The mart's **enforced dbt contract**
refused the first build, listing all nine columns as `missing in contract`. (2) A
**`dbt_expectations` range test** found the 1484.5 s red-flag gap; a **`not_null` test** found
246 NULLs in `is_blue_flag_event` from SQL three-valued logic (`NULL = 'BLUE' AND TRUE` is
NULL, not FALSE) — fixed at source with `COALESCE`, not by weakening the test. (3) The
**byte-stability oracle** found a fixture/production **type divergence** that a full green
`dbt build --target ci` had missed: `race_control.session_time_s` is `double` in all 149
production files and `timestamp[ns]` in all 3 fixture files. It slipped through CI because
`stg_race_control` is a **view** and nothing in the suite selected the column — *a green CI
build did not prove the model ran in CI*. (4) The same oracle is what exposed the
non-determinism above.

**Verified — the `int_pit_strategy_cost_curve` oracle warning is NOT this session's.** Traced
by reading its `ref()`s: `int_stint_geometry`, `stg_weather`, `race_to_track`,
`dim_compounds_season`, `circuit_reference`, `int_pit_loss_circuit`, `int_sc_hazard_history` —
no path to anything added or edited here (the three new models are leaves feeding only
`fct_cliff_prediction_features`). Comparing the working-tree baseline against HEAD's shows an
earlier phase re-snapshotted **15** models and missed this one, whose SQL it had edited.
Hash `23c691e16b46…` → `f871a2aeafd2…`. **Re-snapshotting for this phase absorbed that
pre-existing drift into the baseline.** It was a WARNING, never a FAILURE (the gate only fails
on `fct_*`), but it is recorded because nobody adjudicated whether that earlier change was
intended and after this snapshot the gate can no longer ask.

**Assumed — the same gap Phase 9 named, still open.** `degradation_regressor_p10`/`_p90` are
never scored by the ablation harness (only the headline model per family is), so their −0.83%
/ −0.94% have **no floor to compare against**. Reported as raw deltas, not adjudicated; no
floor was manufactured for them.

**Assumed — one eval fold, one seed, same as every number in this series.** The v10→v11 table
was not recomputed at a second seed. The ablation deltas *were* measured against a 5-reseed
floor, which is the stronger claim; the production table is not.

**Not verified — anything about `pos_x`/`pos_y` beyond their being present and non-null.**
They are staged for 10b and have no consumer, so nothing has checked whether the track frame is
stable across sessions at a venue, which 10b will need.

**Not verified — whether the blue-flag agreement holds on a *held-out* set.** It is a
descriptive check over all 149 races, not a train/test split. It establishes that the measure
tracks a physical event race control also saw; it is not a generalisation claim.

### Gates run

| Gate | Result |
| :--- | :--- |
| `dbt run --select int_lap_proximity` (first build) | **178 s** — profiled and fixed to **7.9 s**: `MODE()` over VARCHAR across 16,045,328 groups was 129 s of it. Replaced with `MIN()` (deterministic, unlike `ANY_VALUE`) |
| **3× rebuild, hash-compared** | **Byte-identical** (`1e6c7d22…`), mart `253fbb7b…`. Two earlier attempts were NOT — that is the finding above |
| `dbt run` (full dev) | **OK** — PASS=71 |
| `make dbt-test` | **OK — 594/594** (was 580; +14 from the new models and tests) |
| `dbt build --target ci` on fixtures | **OK — 672 PASS, 3 NO-OP.** Ran twice; the first pass was green *while hiding* the `TRY_CAST` defect |
| `assert_proximity_agrees_with_blue_flags` | **PASS on dev** (7 seasons). **Vacuous on CI** — stated in the test file, not silently |
| `assert_proximity_crossing_total_order` | **FAIL (76 rows) → fixed → PASS** |
| `sqlfluff lint` (my 4 SQL files) | **OK** after one `sqlfluff fix` pass |
| `make lint` (whole project) | **FAILS on 8 files, none mine** — 7 unmodified from HEAD (so they fail at HEAD too), 1 already modified at session start. Pre-existing; untouched |
| `data-profile-check` | **OK** — no drift, 15 tables |
| `lint-oracle-check` | **FAIL → re-snapshotted → OK**, 71 models incl. the 3 new. See the `int_pit_strategy_cost_curve` note |
| `make ml-features` | **OK** — `[forward-window audit] CLEAN`, `[leakage guard] CLEAN (33 features)`, 82,315 train rows |
| `make ml-retrain` (existing params, **no new search**) | **OK** — 5/5 at v11 |
| `make ml-evaluate` | **OK** — 5/5 `beats_baseline` + significant, 5/5 folds each |
| `make ml-predict` | **OK** — 137,447 rows, v11 |
| `make ml-onnx` | **OK** — parity 5/5 (`abs` ≤ 2.2e-04); manifest 33 features, v11 |
| `make ml-card` / `ml-reference` | **OK** — `all_claims_significant=True` |
| `make ml-test` | **177 passed** (after refitting the 5 stale smoke boosters and running `app-models`, both expected — same shape as Phase 9) |
| `make app-data` / `app-data-check` | **OK** — 37 tables, 348.59 MB; no manifest drift |
| `make app-models` | **OK** — v11 copied, 36,260,899 bytes (+2.5% vs v10) |
| `make app-parity` | **PASSED first run** — `maxAbs=7.764e-4` vs tol `1e-3`, `cliffMismatches=0` |
| `scripts/transform_docs_facts.py` | **FAIL → fixed → OK.** It raises on any uncategorised singular test and had been **failing since Phase 8** added `assert_compound_wear_bounded.sql` without a README row. Added that row plus the three new ones |
| `scripts/ml_docs_facts.py` / `docs_facts.py` | **FAIL ×3 → PASSED** — caught 24→33 in 18 hand-written places, then dbt 68→71 and 577→594 |
| `cd app && pnpm exec vitest run` | **347 passed, 1 skipped** (`parity.node.test.ts`, covered by `app-parity`) |
| `make app-build` | **OK** — clean; pre-existing >500 kB chunk advisories |
| `make app-e2e` | **Deliberately not run**, same reason as Phase 9: with no `E2E_BASE_URL` it fetches models from the live CDN, still v6. It would smoke production, not this session |
| `make app-bundle` | **Not run** — ONNX loads from the CDN, not the bundle, so it does not measure this phase's claim |

### Open decisions blocking the next phase

1. **10b is unblocked and undecided.** The Risks section made 10a's ablation the gate; it
   cleared on two of three families, with the classifier's gain surviving a permutation-null.
   `pos_x`/`pos_y` are already staged, so 10b needs no bronze work. The open question is no
   longer "is the channel worth it" — it is whether *racing-line deviation specifically* adds
   anything beyond what proximity already extracted from the same rows. Nothing measures that.
2. **p50's gain is not attributable to traffic** (0.77× information / 0.77× capacity). If the
   quantile trio can be improved by *any* nine extra columns, that is a statement about its
   hyperparameters — `colsample_bytree` is the obvious suspect — not about the sensor. A
   coordinate probe on that one axis is cheap and would settle it. **Do this before anyone
   cites −2.18% as a traffic result.**
3. **The oracle baseline now blesses `int_pit_strategy_cost_curve`'s pre-existing drift.**
   Hashes are recorded above. If that earlier change was unintended, this is the last
   checkpoint that can still point at it.
4. **Nothing is published to the CDN**, unchanged from Phase 9 and now one version further out
   of date: the app's committed state expects **v11**, prod serves **v6**. `make app-publish` /
   `app-deploy` is the user's call.
5. **The FP2/practice ingest (10c) is unstarted and unblocked** — FastF1's endpoints were
   reachable this session (livetiming.formula1.com 200, jolpi.ca 200), so nobody needs to
   re-test the network. It is the one remaining Phase 10 item needing new data rather than a
   new read of existing data.
6. **`make lint` is red on 8 pre-existing files** and `transform-check` runs it, so that
   composite gate cannot pass today for reasons that have nothing to do with this phase.
7. Phase 9's open decisions 1–3 are untouched and still stand.

### The first command the next session should run

```
cd transform && for i in 1 2; do \
  ../.venv/bin/dbt run --profiles-dir profiles --target dev --select int_lap_proximity >/dev/null 2>&1; \
  ../.venv/bin/python -c "import duckdb; print(duckdb.connect('../data/dev.duckdb', read_only=True).execute(\"SELECT md5(string_agg(rh,'' ORDER BY rh)) FROM (SELECT md5(CAST(t AS VARCHAR)) rh FROM int_lap_proximity t)\").fetchone()[0])"; \
done
```

Two identical hashes (`1e6c7d22630468494be51989d39e8201`). Not a formality: this phase's
central lesson is that a per-lap feature model can be plausible, well-tested, well-documented
and *silently non-reproducible*, and that the only instrument in this repo that can see it is
the one that compares a model's output to its own previous output. If those two lines differ,
stop and read the tie-break notes in `int_lap_proximity.sql` before trusting any number above.

**Re-verified independently, 2026-09-05, after this session was cut off mid-sentence by an
Opus rate limit** (its last line was "Let me verify the handoff command actually works as
written" — it hadn't run it yet). Ran the command above verbatim, twice: both hashes
`1e6c7d22630468494be51989d39e8201`, matching what this checkpoint claims. `dbt run` exited 0
both times. Nothing else in this checkpoint was re-checked — this closes only the one loop the
cut-off session flagged as open, not a re-audit of the rest of the phase.

**Handoff to a new session.** Everything above is real and gated; the working tree is
uncommitted exactly as described, and nothing further landed after the rate limit. The next
session should start at "Open decisions blocking the next phase" above (7 items) rather than
re-deriving state from git — 10b is unblocked and undecided (open decision 1), and p50's
information/capacity split (open decision 2) is flagged as needing resolution before anyone
cites the −2.18% as a traffic result.

---

## Checkpoint 2026-09-05 (two of Phase 10a's open decisions closed — measurement only, nothing shipped)

No code, SQL, model, or doc file touched. This session closed open decisions 2 and 3 from the
Phase 10a checkpoint above by measurement/archaeology and is reporting the result; nothing in
the working tree changed as a result (`git status` before and after this session is identical).

### What landed

Nothing in the repo. One throwaway script, `colsample_probe.py`, was written to a session-local
scratch directory outside the repo (not under version control, not guaranteed to survive to a
future session — the recipe to reproduce it is in "The first command" below). It opened
`data/dev.duckdb` read-only and read `ml/models/degradation_regressor_p50_best_params.json`
read-only; it wrote nothing to either.

### Open decision 3 — the `int_pit_strategy_cost_curve` drift, adjudicated

Traced by reading the actual uncommitted diff (`git diff HEAD -- transform/models/intermediate/
int_pit_strategy_cost_curve.sql`), which the prior checkpoint had not done — it only compared
hashes. **The change is intentional and already fully documented in-file**: it is Phase 8's
shared-bound fix, landing here as a rename from this model's own
`pit_strategy_max_wear_s_per_lap` var to the shared `compound_wear_max_s_per_lap`, so that
`int_pit_strategy_cost_curve` and `int_compound_cliff_predicted` cap the same wear tail at the
same bound. The in-file comment says so explicitly, dated to Phase 8, and names the consequence
("which is what shipped between Phase 5 and Phase 8, and is why both ML targets were still
standing on the 93 s/lap tail"). Not an accident, not drift from an unrelated change — a
cross-model consistency fix whose second half simply hadn't been snapshotted yet.

One small loose end this surfaced: `pit_strategy_max_wear_s_per_lap` is still declared in
`transform/dbt_project.yml` (`compound_wear_max_s_per_lap: 10.0` and
`pit_strategy_max_wear_s_per_lap: 10.0` sit side by side) but is no longer referenced by any
model — dead var left over from the rename. Cheap to delete, not urgent, not done here since
this session shipped nothing.

### Open decision 2 — is p50's capacity effect a `colsample_bytree` artifact? No.

Phase 10a's permutation-null test found `degradation_regressor_p50`'s −0.022532 pinball gain
from the 9 proximity columns splits ~50/50 between "capacity" (−0.011286, 0.77× floor) and
"information" (−0.011247, 0.77× floor) — neither half clears alone, unlike the classifier's
unambiguous 2.28×-floor information result. The open question: `colsample_bytree` is a *fixed
fraction* of column count (incumbent 0.6623), so adding 9 columns hands every tree ~6 more raw
split candidates at the same fraction, with no col added at all. If that mechanism alone
explains the capacity share, the ambiguity is a hyperparameter mismatch, not evidence about the
sensor.

**Method** — a coordinate probe, exactly the instrument item 21 already showed is right for a
single-axis question (a joint search is the wrong instrument here; nothing in this session
touched more than one axis). Reused the production code paths directly rather than
reimplementing them: `features.load_features` → `evaluate._evaluation_split` (resolves to
`cv_final_fold`: train 2018–2023, eval 2024 — the same "identical split" Phase 10a's ablation
used) → `evaluate._fit`/pinball scoring, with the IPW `survival_weight` carried as
`sample_weight` throughout. On the **original 24-column baseline only** (proximity columns
never added), `colsample_bytree` was stepped over 0.7, 0.8, 0.9106 (the value that samples the
same *absolute* column count on 24 columns that 0.6623 samples on 33 — the value the hypothesis
itself singles out), 0.95, and 1.0, holding every other hyperparameter at the incumbent's
tuned values.

**Instrument check, before trusting anything new** (this doc's own standing rule): the harness
reproduced both published Phase 10a numbers to the 6th decimal — 24-column baseline 1.034661
(measured 1.034661, 0.0000% off) and 33-column 1.012128 (measured 1.012128, 0.0000% off).

| colsample_bytree | pinball | Δ vs incumbent-24 (1.034661) | ×floor | verdict |
| :--- | ---: | ---: | ---: | :--- |
| 0.7000 | 1.032802 | +0.001859 | +0.13× | inside |
| 0.8000 | 1.033815 | +0.000845 | +0.06× | inside |
| 0.9106 (matched column count) | 1.032266 | +0.002395 | +0.16× | inside |
| **0.9500 (best)** | **1.031571** | **+0.003090** | **+0.21×** | **inside** |
| 1.0000 | 1.047995 | −0.013335 | −0.91× | inside (worse) |

Floor = `attribution.refit_noise_floor`'s `delta_noise_2sd`, computed at the incumbent 24-column
configuration over 5 reseeds (**Assumed** seed convention, not pinned by the doc:
`S.RANDOM_STATE + {0,1,2,3,4}` — the same pattern already used by `evaluate`'s within-stint
attribution call elsewhere in this codebase): `headline_by_seed` sd = 0.005178 →
**`delta_noise_2sd = 0.014647`**. Independent cross-check: back-solving Phase 10a's own three
reported ratios (`0.022532/1.54`, `0.011247/0.77`, `0.011286/0.77`) all imply a floor of
≈0.0146 — this session's independently-recomputed 0.014647 matches to 3 significant figures,
which is a second confirmation the instrument is calibrated correctly, on top of the exact
reproduction above.

**Verdict: ruled out.** No candidate clears the floor. The best (0.95) recovers **13.7%**
(0.003090 / 0.022532) of the proximity gain, and that 13.7% is itself statistically
indistinguishable from reseeding noise — nowhere near the 0.77×-floor capacity share the
permutation-null test found, let alone the full 1.54×-floor total. The specific value the
hypothesis singled out (0.9106, matched absolute column count) is unremarkable — it sits in the
middle of the five candidates, not at a standout optimum. Pushing to 1.0 (no subsampling) makes
p50 measurably *worse*. **The mechanism this session tested is not what produces the capacity
effect.** What does remains unidentified — this session answers the specific question asked
("is it this"), not the general one ("what is it") — and is not pursued further here since
nothing in the plan currently asks for that deeper hunt.

**The honest sentence for anyone citing this model going forward, unchanged from Phase 10a and
now reinforced rather than resolved:** p50's −2.18% / −0.022532 pinball gain from the proximity
group should not be cited as a pure traffic-signal result. It clears its own floor in total, but
the permutation-null test's ~50/50 information/capacity split stands, and this session closes
off one candidate explanation for the capacity half without finding what actually produces it.

### What was verified vs assumed

**Verified** — the drift adjudication above, by reading the actual diff rather than comparing
hashes (what the prior checkpoint had done).

**Verified** — the probe's instrument reproduces both Phase 10a headline numbers exactly (0.0000%
off, both arms), and its independently-computed noise floor (0.014647) matches Phase 10a's
implied floor (≈0.0146, back-solved three independent ways) to 3 significant figures.

**Verified** — no colsample_bytree value in the tested range, including the one the hypothesis
specifically predicts should matter, produces a pinball delta distinguishable from reseeding
noise on the 24-column baseline.

**Assumed** — the 5-reseed floor's seed values (`S.RANDOM_STATE + {0,1,2,3,4}`); the doc does
not pin these, and this choice is validated only by the floor it produces matching Phase 10a's
implied number, not by being stated anywhere as canonical.

**Not done** — no attempt was made to identify what *does* produce the capacity effect
(min_child_weight, subsample, or a generic more-split-candidates effect orthogonal to any one
hyperparameter). The question asked was narrower ("is it this") and is answered; the broader one
is now explicitly open rather than implicitly assumed-resolved.

### Gates run

| Gate | Result |
| :--- | :--- |
| Instrument check: reproduce Phase 10a's published 24-col / 33-col pinball | **PASS** — 0.0000% off both |
| Cross-check: recomputed noise floor vs Phase 10a's implied floor (back-solved 3 ways) | **PASS** — 0.014647 vs ≈0.0146 |
| `git status` before vs after this session | **identical** — nothing touched |
| `git diff` on `degradation_regressor_p50_best_params.json` | pre-existing (Phase 7, dated Aug 26), not touched this session — confirmed by file mtime and byte-identical content to what this session read |

### Open decisions blocking the next phase

Carried forward from Phase 10a, with 2 and 3 now closed:

1. **10b is unblocked and undecided** (unchanged) — whether racing-line deviation specifically
   (`pos_x`/`pos_y`, already staged) adds anything beyond what proximity already extracted.
2. ~~p50's gain is not attributable to traffic~~ — **closed this session.** Not a
   `colsample_bytree` artifact. The capacity/information split stands and −2.18% still should
   not be cited as a pure traffic result; what drives the capacity half is unidentified and not
   currently blocking anything.
3. ~~The oracle baseline now blesses `int_pit_strategy_cost_curve`'s pre-existing drift~~ —
   **closed this session.** It was Phase 8's intentional shared-bound rename, fully documented
   in-file. No action needed beyond the dead-var cleanup named above (optional, cheap).
4. **Nothing is published to the CDN** (unchanged) — the app's committed state expects v11, prod
   serves v6. `make app-publish`/`app-deploy` is the user's call.
5. **The FP2/practice ingest (10c) is unstarted and unblocked** (unchanged).
6. **`make lint` is red on 8 pre-existing files** (unchanged) — unrelated to this session.
7. Phase 9's open decisions 1–3 are untouched and still stand (unchanged).

### The first command the next session should run

The scratch script lives outside the repo and may not survive to a new session
(`/private/tmp/.../scratchpad/colsample_probe.py`, this session's temp dir). To re-verify the
table above, from the repo root with `.venv/bin/python`:

```python
from ml.src import attribution as AT, evaluate as E, features as F, schema as S, train as T
import json
from pathlib import Path

spec = S.TARGET_BY_NAME["degradation_regressor_p50"]
params = json.loads(Path("ml/models/degradation_regressor_p50_best_params.json").read_text())
baseline_cols = [c for c in S.FEATURE_COLUMNS if c not in S.FEATURE_GROUPS["proximity"]]

bundle = F.load_features(target="degradation_regressor_p50")
split = E._evaluation_split(bundle)                       # cv_final_fold: train 2018-23, eval 2024
X_tr, X_ev = split.X_tr[baseline_cols], split.X_ev[baseline_cols]

m = E._fit(spec, params, X_tr, split.y_tr, cens=None, w=split.w_tr)
pinball_24 = T.pinball_loss(split.y_ev, m.predict(X_ev), spec.quantile_alpha)
print(pinball_24)   # expect 1.034661 -- if this doesn't match, stop before trusting anything else
```

Two numbers to confirm first (1.034661 on `baseline_cols`, 1.012128 on the full 33), exactly as
this session's own protocol required, before re-running the `colsample_bytree` sweep or trusting
the table above.

---

## Checkpoint 2026-09-05 (Phase 10b measurement pass — one family clears cleanly, one is
ambiguous, one is flat; nothing shipped)

Open decision 1 from the checkpoint above ("10b is unblocked and undecided") answered by
measurement, following the same posture the plan used before committing to 10a: a cheap probe
first, shipping gated on what it finds. `git status` before and after this session is identical —
nothing in the repo was touched.

### What landed

Nothing in the repo. One throwaway script, `racing_line_probe.py`, written to a session-local
scratch directory (not under version control, not guaranteed to survive to a future session — the
recipe to reproduce it is in "The first command" below). It opened `data/dev.duckdb` read-only and
globbed the bronze telemetry parquet directly (read-only); it wrote nothing to either.

Two per-lap scalars were computed: the Euclidean offset of each lap's own position-channel path
from the driver's own clean-air early-stint reference line, per `dim_corners` corner window,
binned at 15m (close to the position channel's native ~13.5m average sample spacing).

* **`distance_m` confirmed 100% populated on `Source='pos'` bronze rows**, in the same range as
  `Source='car'` rows (one race, all 7 seasons of parquet globbed: pos 0–5565m, car 0–5556m) — so
  the probe reads `distance_m` straight off bronze the same way `stg_telemetry_position` already
  reads its other columns, needing no repo change and no assumed lap length to convert
  `relative_distance`.
* **Reference-lap definition, coverage checked before building anything**:
  `lap_in_stint BETWEEN 2 AND 5 AND NOT is_out_lap AND NOT is_in_lap`, excluding neutralised laps
  (`is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap`) and requiring `dirty_air_share_lap = 0`
  (Phase 10a's own traffic signal, so a lap driven in another car's wake never contaminates the
  reference). 15,236 of 137,447 laps qualify, across 2,635 (race, driver) groups, of which 2,490
  (94.5%) have ≥2 qualifying laps.
* **Final per-lap coverage**: 120,751 of 137,447 laps (87.9%) get a computed value; the rest are
  explicit NULL (no reference exists, or no corner-bin data), not defaulted — matching the
  project's missingness convention (`int_lap_proximity`'s four nullable columns, same reasoning).
  Where present, a lap touches a median of 300 corner-bins.
* **Cost, measured**: the full 7-season build (58.8M `Source='pos'` bronze rows, range-joined
  against `dim_corners`' ~30–40 corners/race) took **177.5 s** standalone in the unoptimized
  throwaway script — materially more than `int_lap_proximity`'s 7.9 s. A shipped dbt version would
  likely be cheaper (materializing the `Source='pos'` filter once via `stg_telemetry_position`
  rather than re-globbing raw bronze per run, the way this probe does), but the cost is not
  measured for that path since Stage 2 was not started.

### The result: three families, three different readings

Add-ablation, `evaluate.py`'s own `_fit`/`_score`, identical `cv_final_fold` split (train
2018–2023, eval 2024) for all three. **Instrument check passed first**: each family's 33-column
refit reproduced its published v11 headline to 6 decimal places (0.000000 diff, all three) before
anything built on top of it was trusted.

| family | headline (33) | **+racing_line (35)** | Δ | vs. own floor (2sd) | verdict |
| :--- | ---: | ---: | ---: | :--- | :--- |
| `degradation_regressor_p50` | 1.012128 | 1.024296 | +0.012167 (worse) | 0.87× | inside — no effect |
| `cliff_classifier` | 0.380950 | 0.387308 | +0.006358 (better) | **1.21× CLEARS** | see below |
| `stint_life_regressor` | 1.952005 | 1.942895 | −0.009110 (better) | **1.30× CLEARS** | see below |

**Permutation-null decomposition** (same method Phase 10a used: row-shuffle the new columns
independently in train and eval — capacity preserved, signal destroyed — capacity = shuffled-vs-
baseline, information = real-vs-shuffled):

| family | capacity (N−A) | information (B−N) | reading |
| :--- | ---: | ---: | :--- |
| `degradation_regressor_p50` | +0.005808 (0.42×) | +0.006359 (0.46×) | both inside; total also inside — nothing to decompose |
| `cliff_classifier` | +0.003397 (0.65×) | +0.002961 (0.56×) | **total clears, neither half does** |
| `stint_life_regressor` | +0.002259 (0.32×, wrong-signed) | **−0.011369 (1.62× CLEARS)** | **the win is information, not capacity** |

**Three different findings, none rounded up:**

1. **p50: nothing.** The total delta itself is inside the floor (0.87×). If Stage 2 ever ships,
   the racing-line group should not be pitched as helping the degradation quantile trio at all —
   not even the ambiguous "clears but can't attribute" reading proximity got here.
2. **`cliff_classifier`: the exact ambiguous pattern Phase 10a found for p50's proximity gain,
   mirrored onto a different family.** The total clears (1.21×), but capacity (0.65×) and
   information (0.56×) both sit inside the floor individually. A win that only appears once two
   numbers are added together, neither of which is itself distinguishable from noise, is not
   attributable to "the classifier reads the racing line" — it is recorded as clearing in total
   and left there, the same discipline Phase 10a applied to p50.
3. **`stint_life_regressor`: the clean case.** Total clears (1.30×) **and** the information half
   clears alone (1.62×), while the capacity half moves in the *wrong* direction (+0.32×, i.e. two
   literally-shuffled columns made the model slightly worse, not better) — ruling out "just two
   more split candidates" as the explanation. Structurally this is the same shape as Phase 10a's
   `cliff_classifier` result for `proximity` (2.28×, unambiguous information), just landing on a
   different family this time.

### What was verified vs assumed

**Verified** — all three instrument checks (33-column refit reproduces the published v11 headline
to 6 decimal places).

**Verified** — `distance_m` population on bronze `Source='pos'` rows, and reference-lap coverage,
both checked directly against `data/dev.duckdb` before any code was written (see "What landed").

**Assumed** — the 15m bin width and the mean/max scalar choice were picked by judgement to match
native sample spacing, not tuned or ablated against alternatives. A different bin width, a
corner-count-weighted aggregate, or a tail statistic (e.g. p90 offset instead of max) might read
differently on any of the three families — not tested.

**Not verified** — the Euclidean (not tangent/normal-decomposed) offset used here as a
simplification for "lateral deviation" (see this session's plan for the reasoning) against a true
signed-lateral measure. Not re-litigated here since the coarser version already produced a clean
result on one family; a refined version is a candidate improvement for Stage 2, not a prerequisite
for this measurement.

**Not verified** — whether the reference construction's within-stint look-ahead (laps 2–5 pooled
regardless of which lap is being scored) matters here beyond the precedent already accepted for
`int_lap_telemetry_aggregates`'s three existing early-stint-baseline features. Inherited, not
independently re-checked.

### Gates run

| Gate | Result |
| :--- | :--- |
| Instrument check: 3 families' 33-col refit vs published v11 | **PASS** — 0.0000% off, all three |
| `distance_m` population check on bronze `Source='pos'` rows | **PASS** — 100% non-null, range matches `Source='car'` |
| Reference-lap coverage check (≥2 qualifying laps per driver/race) | **PASS** — 94.5% of 2,635 groups |
| `git status` before vs after this session | **identical** — nothing touched |

### Open decisions blocking the next phase

1. **Stage 2 (shipping) was explicitly not started and needs its own go-ahead** — this session's
   plan gated it on Stage 1 clearing, and the result is genuine but narrower than Phase 10a's: one
   family clears cleanly (`stint_life_regressor`, 1.62× information), not two, and that margin is
   smaller than Phase 10a's own cleanest case (`cliff_classifier`/`proximity`, 2.28×). Whether a
   single clean family on a ~10-file production pass (contract change, 5-model refit, ONNX, docs)
   is worth it, or whether 10b should first get a refined (signed lateral) offset measure and be
   re-probed, is undecided.
2. **If shipped, the group's story is per-family, not uniform**: `stint_life_regressor` alone gets
   the clean "this is information" claim; `cliff_classifier` would carry the same
   clears-in-total-but-not-attributable caveat proximity's p50 result carries; `p50` gets nothing
   and should not be listed as a beneficiary.
3. All of Phase 10a's own open decisions (10c's FP2 ingest, nothing published to the CDN,
   `make lint` red on 8 pre-existing files) are untouched and still stand.

### The first command the next session should run

The scratch script lives outside the repo and may not survive to a new session
(`/private/tmp/.../scratchpad/racing_line_probe.py`, this session's temp dir). To rebuild it from
scratch, the SQL and harness are described in full above and in this session's plan file; the two
numbers to reproduce first, before trusting anything built on top, are the three instrument-check
values (1.012128 / 0.380950 / 1.952005 — the same three numbers Phase 10a's own checkpoint
published as the v11 headline).

## Checkpoint 2026-09-06 (Phase 10b re-probed with a signed lateral offset — Stage 2 closed, don't ship)

Open decision 1 from the checkpoint above, answered a second and final time: the previous probe's
own "Not verified" line flagged the raw Euclidean offset as a simplification that could be
contaminated by along-track (tangential) differences rather than pure side-to-side deviation. This
session built the refined version — a tangent/normal decomposition of the offset vector, keeping
only the normal (lateral) component — and re-ran the identical three-family harness. `git status`
before and after this session is identical — nothing in the repo was touched.

### What landed

Nothing in the repo. One throwaway script, `racing_line_probe_signed.py`, written to a
session-local scratch directory (not under version control) — same posture as the first 10b probe.
It opened `data/dev.duckdb` read-only and globbed the bronze telemetry parquet directly; wrote to
neither.

**The measurement change, precisely**: the first probe's per-(lap, corner-bin) scalar was
`||lap_point − ref_point||` (Euclidean). This one instead builds a local track frame at each
reference-line bin — a tangent from its neighbouring bins in the same (race, driver, corner_key),
ordered by distance, one-sided at either end of a corner window — and projects the offset vector
onto the tangent's normal: `lateral = (lap_point − ref_point) · normal`. The tangential component is
computed but deliberately never used (the whole point is to exclude it). Two columns, same shape as
before: `mean(|lateral|)` and `max(|lateral|)` per lap, aggregated over every corner-bin the lap
touches.

Reference-lap definition, corner windows, and bin width (15m) are unchanged from the first 10b
probe (same 15,236/137,447 reference-eligible laps, same `dim_corners` windows) — only the per-bin
scalar changed, so this is a like-for-like refinement, not a new measurement design.

**Coverage, better than the first probe, not worse**: 921,866 reference-line bins built; 921,844 of
them (99.997%) get a usable tangent (a corner window one bin wide has no neighbour to differ
against and is dropped — 22 bins, negligible). Final per-lap coverage: 126,424/137,447 (92.0%),
against the first probe's 87.9% — the pre-aggregated reference line (one row per race/driver/corner/
bin, built once) needs a plain equi-join per lap rather than a join against every individual
reference lap, which plausibly also explains the build cost: 15-17s standalone end to end, against
the first probe's reported 177.5s. **Not verified** — the cost gap was not profiled directly against
the old script (which no longer exists to compare against); recorded as an observation, not a
re-measured claim.

### The result: the refined measure moves all three families, and not in the flattering direction

Same instrument-check-first discipline as every prior probe: each family's 33-column refit
reproduced its published v11 headline to 6 decimal places before anything built on top was trusted.
Add-ablation and permutation-null decomposition, identical `cv_final_fold` split and `evaluate.py`
`_fit`/`_score` as the first probe.

| family | headline (33) | +racing_line_signed (35) | Δ | vs. own floor (2sd) | verdict |
| :--- | ---: | ---: | ---: | :--- | :--- |
| `degradation_regressor_p50` | 1.012128 | 1.020921 | +0.008793 (**worse**) | **2.03× CLEARS** | harmful |
| `cliff_classifier` | 0.380950 | 0.383062 | +0.002111 (better) | 0.38× | inside — no effect |
| `stint_life_regressor` | 1.952005 | 1.946169 | −0.005836 (better) | 0.63× | inside — no effect |

Permutation-null decomposition (same method as every prior phase: row-shuffle the two new columns
independently in train and eval):

| family | capacity (N−A) | information (B−N) | reading |
| :--- | ---: | ---: | :--- |
| `degradation_regressor_p50` | +0.008764 (**2.02× CLEARS**) | +0.0000289 (0.01×, nil) | **the harm is capacity, not information — two pure split candidates that overfit train and cost eval** |
| `cliff_classifier` | +0.000328 (0.06×) | +0.001783 (0.33×) | both inside; total also inside — nothing to decompose |
| `stint_life_regressor` | +0.002730 (0.29×, wrong-signed) | −0.008566 (**0.92×**, just short) | information carries the direction, same shape as the Euclidean version's clean case — but this time it does not clear |

**The finding, stated plainly**: purifying the offset to its lateral component only — the
refinement Open decision 1 asked for — does not strengthen any of the three families' cases. It
flips `degradation_regressor_p50` from "inside noise" to "clears, and it's harmful, and the harm is
unambiguously capacity" (the cleanest negative result any group in this plan has produced — 2.02×
and 2.03× essentially identical means the *entire* total delta is explained by two noise columns
giving the tree more places to (mis)split, not by anything the columns measure). It leaves
`cliff_classifier` exactly where it was, inside noise on every cut. And it takes
`stint_life_regressor` — the Euclidean version's one clean win, 1.30× total / 1.62× information —
down to 0.63× / 0.92×, both now inside the floor. The Euclidean measure's apparent stint-life signal
was, at least in significant part, the tangential/along-track contamination Open decision 1 named as
unverified: corner-cutting or arc-length differences correlated with stint life, not lateral
deviation from the racing line. Removing that contamination removed most of the effect.

### What was verified vs assumed

**Verified** — all three instrument checks (33-column refit reproduces the published v11 headline
to 6 decimal places: 1.012128 / 0.380950 / 1.952005, exactly as the first 10b probe and Phase 10a's
own checkpoint).

**Verified** — tangent validity (99.997% of reference-line bins) and final per-lap coverage (92.0%),
checked directly against `data/dev.duckdb` and the bronze parquet before any model was fitted.

**Fixed, not a finding** — the first run of this session's harness crashed inside the noise-floor
helper: `T._make_model` builds its sklearn kwargs via `dict(random_state=S.RANDOM_STATE, **params)`,
a function call, and Python's `dict()` raises on a duplicate keyword rather than letting the later
one win — unlike `AFTBooster.__init__`'s `{**p}` dict *literal*, which does allow the override. The
seed for a reseed-floor refit has to be set on the constructed object (`model.set_params
(random_state=seed)` for the two sklearn families, a direct `model.params["seed"] = seed` mutation
for `AFTBooster`, which has no `set_params`) rather than injected into `params` beforehand.

The same broken pattern (`m.set_params(random_state=seed)` unconditionally) is present in
production at `evaluate.py:858-865`, inside `within_stint_attribution` (**not** `ablation()` — those
are two different functions and this session's first draft of this checkpoint named the wrong one).
**Checked directly against the live `ml/artefacts/evaluation_metrics.json` this session, and it is
NOT live**: `within_stint_attribution` only runs when `RUN_ATTRIBUTION` is true (CLI `--attribution`,
default `False`, `evaluate.py:88`) *and* `target in ATTRIBUTION_TARGETS`
(`{"degradation_regressor_p50", "cliff_classifier"}`, `evaluate.py:86`) — `stint_life_regressor`,
the only survival-kind (`AFTBooster`) target, is not a member of that set on purpose (its own
comment: "its target is a deterministic ramp... within-stint variation is not a meaningful question
there"). Grepping the live metrics file for `refit_noise` and `error` inside it: neither key appears
anywhere in the file, consistent with the default gate never reaching this function at all. So the
bug is real and would crash the moment a survival target was ever added to `ATTRIBUTION_TARGETS` or
`--attribution` were run against one, but it is dead code today, not a silent production defect —
downgraded from the first draft's "plausibly silently absent or wrong today," which was an
un-rechecked generalisation of exactly the kind this doc's own conventions warn against.

**Assumed** — the 15m bin width, and mean/max as the two aggregate scalars, are unchanged from the
first probe and carry the same caveat: picked by judgement, not tuned or ablated.

**Not verified** — the tangent construction's neighbour-based direction estimate against a
higher-order (e.g. quadratic/spline) local direction fit; the coarser two-neighbour version already
produced a decisive result (moved every family's reading, two of them by a lot), so a smoother
tangent is a candidate refinement for a *third* pass only if Stage 2 is ever reopened, not a
prerequisite for closing this one.

### Gates run

| Gate | Result |
| :--- | :--- |
| Instrument check: 3 families' 33-col refit vs published v11 | **PASS** — 6 decimal places, all three |
| Reference-line tangent validity | **PASS** — 921,844/921,866 (99.997%) |
| Final per-lap coverage | **92.0%** (126,424/137,447; first probe was 87.9%) |
| `git status` before vs after this session | **identical** — nothing touched |

### Open decisions blocking the next phase

1. **Stage 2 for the racing-line group is closed: do not ship.** Two independent measurements now
   agree the group does not clear on a defensible signal: the Euclidean version's only clean win
   (`stint_life_regressor`) evaporates under the refined measure, and the refined measure's only
   result that clears at all is a harmful, purely-capacity effect on `degradation_regressor_p50`.
   Nothing here recommends building this into the dbt pipeline. This closes both of the prior
   checkpoint's open decisions (1 and 2) without qualification.
2. **The `evaluate.py` / `AFTBooster` seed-override bug in `within_stint_attribution` (see "What
   was verified vs assumed") is real but currently dead code, not a live defect** — verified
   against `ml/artefacts/evaluation_metrics.json` this session. Low priority: it only matters if
   `stint_life_regressor` (or any future survival target) is ever added to `ATTRIBUTION_TARGETS`.
   A one-line fix (branch on `spec.kind == "survival"` the same way this session's throwaway script
   does, instead of unconditional `m.set_params(random_state=seed)`) is cheap whenever someone is
   next in that function, but nothing is broken today and nothing forces this. Not fixed here on
   purpose — this session's mandate was measurement only and the repo is untouched.
3. All of Phase 10a's own leftover open decisions (10c's FP2 ingest, nothing published to the CDN,
   `make lint` red on 8 pre-existing files) are still untouched and still stand.

### The first command the next session should run

Nothing is blocking. Stage 2 for the racing-line group is closed (don't ship); item 2 is a
low-priority dead-code fix with no urgency. The next session should pick up whichever of Phase
10a's leftover items (10c's FP2 ingest, CDN publish, the 8 `make lint` failures) or a fresh
ideation pass it judges most valuable — see the open decisions above.

## Checkpoint 2026-09-06 (2022 regulation-era question closed — no split, no residual boundary effect)

Prompted by a question this session, not a plan phase: 2022 was F1's biggest regulation reset in
years (ground-effect floors, 18" tyres, a weight jump) — does pooling 2018-2024 into one model per
family blur two different physical regimes badly enough to justify splitting the degradation/cliff/
stint-life models pre/post-2022, or building explicit era features? Answered by a cheap diagnostic
rather than by argument. `git status` before and after this session is identical — nothing touched.

### What landed

Nothing in the repo. Two things, both read-only:

1. **A codebase check, no script needed.** The tyre-wear parameters the degradation/cliff models
   actually consume (`compound_grip_peak`, `compound_wear_gradient`, sourced from
   `compound_cliff_params.csv` / `dim_compounds_season`) are already refit **per season and
   circuit**, so whatever physical shift 2022 caused in a given compound's wear curve is already a
   season-specific number, not a global constant blurred across the boundary. Separately, this
   codebase already has precedent for an explicit 2022 era split where it's needed —
   `int_era_normalized_driver_rating.sql` splits driver-skill rating pre/post-2022 (2018-2021 /
   2022-2024) with a bridge-driver calibration — but driver-skill columns are barred from the ML
   feature set as causal leakage (`EXCLUDED_LEAKAGE_COLUMNS`), so that precedent doesn't reach the
   three families in question either way.
2. **A throwaway script, `era_diagnostic.py`** (session-local scratch, not under version control).
   Reused `train._season_folds` (the same 5-season-fold TimeSeriesSplit `train.py`/`tune.py` already
   run), `evaluate.py`'s own `_fit`/`_score`/`baseline_predictions`/`load_cohort_dims`, and each
   family's tuned production params — no new code path, no re-tuning. For each of the 5 folds
   (validating 2020, 2021, 2022, 2023, 2024 in turn — `TimeSeriesSplit` never validates the first 2
   of 7 seasons), fit on the honest expanding-window train side, score the model AND its own cohort
   baseline on the held-out season, record the margin (model's improvement over baseline, sign
   corrected so positive always means "model ahead"). This is the same `beats_baseline` question the
   production gate already asks — just asked every season, not only the single 2024 fold the
   standard eval split can see.

### The result: five point of a season each, and no cliff at the boundary

| target | 2020 | 2021 | 2022 | 2023 | 2024 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p50` margin | +0.935 | +1.066 | +1.308 | +1.059 | +1.166 |
| `cliff_classifier` margin | +0.144 | +0.198 | +0.168 | +0.160 | +0.162 |
| `stint_life_regressor` margin | +0.121 | +0.092 | +0.167 | +0.102 | +0.235 |

All three families beat their own cohort baseline in all five seasons, pre- and post-2022 alike.
Pre/post-2022 means (2 pre-era points vs 3 post-era points):

| target | pre_2022 mean | post_2022 mean |
| :--- | ---: | ---: |
| `degradation_regressor_p50` | 1.000 | 1.178 |
| `cliff_classifier` | 0.171 | 0.163 |
| `stint_life_regressor` | 0.107 | 0.168 |

No family shows a dip right at the boundary — `cliff_classifier` is essentially flat across all
five seasons (0.144-0.198, no era pattern); the other two are, if anything, slightly higher
post-2022, the opposite of what "the regulation change hurt the model" would predict. That
"slightly higher" reading is not trusted as an era effect either — the expanding-window design
means later folds mechanically have more training rows, which independently improves fit quality,
and the pre/post buckets are too thin (2 vs 3 points) to separate the two explanations.

### What was verified vs assumed

**Verified** — `compound_grip_peak`/`compound_wear_gradient` are season-scoped at the source
(`compound_cliff_params.csv` columns include `season`; `dim_compounds_season` is built from it),
checked by reading the seed/model files directly, not inferred from naming.

**Verified** — the per-season margin table above, from a direct out-of-fold refit using the
production fit/score/baseline functions unmodified.

**Assumed / explicitly not claimed** — that the slightly higher post-2022 margins reflect a real
era effect rather than the expanding-window CV's confound with training-set size. Stated as
ambiguous rather than rounded into either "the model improved after 2022" or "eras don't matter at
all" — the honest reading is narrower: no penalty is visible, which is enough to answer the question
that was actually asked (does pooling hurt us), not the broader one (would era-aware features help
us further).

**Not tested** — whether a *new*, ground-effect-specific signal (e.g. floor-sensitivity to ride
height, porpoising-adjacent telemetry, 18"-tyre thermal characteristics) would add anything. This
diagnostic only answers "does the CURRENT feature set's pooling across the boundary cost anything"
(no) — it says nothing about whether a differently-designed feature could still find something
regulation-specific. That would be new ideation, not a re-ask of this question.

### Gates run

| Gate | Result |
| :--- | :--- |
| Out-of-fold refit across 5 season-folds, 3 families, production params | **completed**, all 15 fits beat their own cohort baseline |
| `git status` before vs after this session | **identical** — nothing touched |

### Open decisions blocking the next phase

1. **Closed: do not split the models by regulation era, and do not add an explicit era feature.**
   No evidence supports it, and the one architectural piece that plausibly needed it (compound wear
   physics) already has it via per-season refitting.
2. **Still open, and now the more interesting question**: is there a *new* signal specific to the
   2022+ generation of car (ground-effect floor sensitivity, 18" tyre thermal behaviour) worth
   ideating from scratch, independent of the pooling question this session closed? Not scoped or
   started.
3. Item 2 from the checkpoint above (the dead-code `within_stint_attribution` seed bug) and Phase
   10a's own leftovers (10c's FP2 ingest, CDN publish, 8 `make lint` failures) are all still
   untouched and still stand.

### The first command the next session should run

Nothing is blocking. If open decision 2 above is picked up, it starts from a blank page — this
session deliberately did not scope what a ground-effect-era-specific feature would look like, only
closed the narrower pooling question.

## Checkpoint 2026-09-06 (two leftover open items closed: `make lint` is green, and the
`within_stint_attribution` seed bug is fixed)

Picked up two items that had stood untouched across every checkpoint since Phase 10a: `make lint`
red on 8 pre-existing files, and the dead-code seed-override bug the 2026-09-06 signed-lateral-offset
checkpoint identified in `evaluate.py:858-865`. Both closed this session; ground-effect-era ideation
(the other open item) was explicitly declined by the user for this session.

### What landed

**`make lint` (8 pre-existing files, all cosmetic — no model logic changed):**
- `int_compound_cliff_predicted.sql`, `int_track_evolution.sql`: the `weather` CTE's
  `DISTINCT ON (race_year, race_id, lap_number)` tiebreak `ORDER BY` had only one of five columns
  with an explicit direction (AM03). Made all five explicit (`... ASC, ..., weather_session_time_s
  DESC, driver_id ASC`) — same tiebreak DuckDB was already applying (unspecified defaults to ASC),
  now just spelled out.
- `int_stint_geometry.sql`, `int_driver_circuit_affinity.sql`, `fct_ghost_car_pace.sql`: comment/line
  rewraps for LT05 (line > 80 chars). No SQL tokens changed.
- `int_track_geometry.sql`: `t.X AS x` / `t.Y AS y` / `t.Z AS z` renamed to bare `t.x`/`t.y`/`t.z`
  (AL09 self-alias + CP02 capitalisation) — DuckDB identifiers are case-insensitive unquoted, so this
  is a no-op against the source column.
- `int_driver_circuit_era_affinity.sql`: collapsed multi-space `END    AS x` to single-space (LT01).
- `int_driver_circuit_affinity.sql`: the final `SELECT`'s `n_obs`/`seasons_observed_n`/
  `raw_affinity_s`/`shrunk_affinity_s`/`posterior_var_s2`/`affinity_confidence` were unqualified
  against a two-table join (RF02) — qualified all to `ws.` (they all come from the `with_shrinkage`
  CTE, never `circuit_name_map`).
- `mart_corner_skill_driver.sql`: three `CASE WHEN ... THEN x / NULLIF(...)` blocks had bad
  indent+line-length (LT02/LT05) — ran `sqlfluff fix` on this file only (not the other 7, done by
  hand) after confirming by inspection its diff was a pure reformat of the same three expressions.

**`evaluate.py`'s `within_stint_attribution.fit_seeded`** (lines ~858-869): branched the seed-override
on `spec.kind == "survival"` — `AFTBooster` has no `set_params`, so its seed is now mutated on
`m.params["seed"]` directly (matching `AFTBooster.__init__`'s dict-literal override semantics) and
`is_censored=cens_tr` is now passed to `m.fit(...)` for that branch, which the pre-fix code never did
either (masked because the `set_params` crash always fired first). The two sklearn families keep
`m.set_params(random_state=seed)` unchanged.

### What was verified vs assumed

**Verified** — `make lint` is green top to bottom (`sqlfluff lint models/` and `make lint` both exit
0), and a full `dbt build --target ci` (675 nodes: 54 table models, 17 views, 594 tests, 3 exposures,
7 seeds) completes with PASS=672 ERROR=0 on the post-fix code — no test regressions from any of the
8 files.

**Verified** — the 8 lint fixes are byte-stable, not just test-green. Stashed just the 8 edited SQL
files back to HEAD, rebuilt `fct_ghost_car_pace` and `mart_corner_skill_driver` (the two with the
least-trivial diffs: a qualified-reference rename and a `sqlfluff fix`-driven reformat) on
`ci.duckdb`, and hashed both with the oracle's own `hash_relation` (order-independent, excluding
`VOLATILE_COLS`) against the post-fix hashes — identical on both counts (`16d2e6ac...` for
`fct_ghost_car_pace`, `5ba24af9...` for `mart_corner_skill_driver`, pre- and post-fix alike). Then
restored the 8 files with `git stash pop`.

**Verified, and explicitly not this session's problem** — running the repo's own
`scripts/snapshot_model_hashes.py --check` (the full 675-model oracle gate) hit
`_duckdb.OutOfMemoryException: failed to allocate 4.0 GiB` on this machine, unrelated to any content
here (a single relation's row-hash query exceeding available memory). Working around it with a
lower `memory_limit` for the two models above surfaced a real thing worth flagging: **both models'
current hashes already differ from what `transform/tests/model_hashes.baseline.json` has recorded**,
identically whether the 8 lint fixes are applied or reverted to HEAD. This proves the drift predates
and is independent of this session's changes — most likely the baseline file (itself sitting
uncommitted, modified by whichever prior session last ran the snapshot after Phase 9/10a's feature
additions) is stale against the current warehouse/model state. **Not investigated further** — root-
causing or regenerating the baseline is a separate, deliberate decision (the oracle script's own
docstring: "regenerate + commit it when model logic changes intentionally"), and doing so was not
in scope for a lint pass. Flagged here so the next session does not mistake it for something these
two fixes caused.

**Verified** — the survival-target seed fix actually works, not just that it type-checks. Wrote a
throwaway script (session-local scratch, not committed) that calls `within_stint_attribution`
directly for `stint_life_regressor` (bypassing the `ATTRIBUTION_TARGETS` gate that excludes it in
production), reusing `F.load_features`, `E._evaluation_split`, `E._fit`, `E._params_for`,
`E.load_cohort_dims` unmodified. Pre-fix this path raised `AttributeError` inside
`refit_noise_floor`'s `fit_seeded` (swallowed by `within_stint_attribution`'s own try/except into
`out["refit_noise"]["error"]`); post-fix it returns a real floor (`n_seeds=5, headline_mean=1.9543,
headline_sd=0.00248, delta_noise_2sd=0.00700`), no error key.

**Verified** — full `ml/tests` suite (177 tests) passes unchanged after the `evaluate.py` edit.

### Gates run

| Gate | Result |
| :--- | :--- |
| `sqlfluff lint models/` / `make lint` | **PASS** (was: 8 files failing) |
| `dbt build --target ci` (full, 675 nodes) | **PASS** — 672/675 (3 no-op), 0 errors |
| Oracle hash, `fct_ghost_car_pace` + `mart_corner_skill_driver`, post-fix vs pre-fix (HEAD) code | **IDENTICAL** — lint fixes are byte-stable |
| Oracle hash, same two models, vs `tests/model_hashes.baseline.json` | **DRIFT on both — pre-existing, not caused by this session** |
| `scripts/snapshot_model_hashes.py --check` (full, default memory settings) | **OOM on this machine** (4 GiB alloc, unrelated to content) |
| `within_stint_attribution` for `stint_life_regressor`, direct call (throwaway harness) | **PASS** — no error, real noise floor returned |
| `pytest ml/tests` (full suite) | **PASS** — 177 passed |
| `git status` | Only the 8 lint files + `ml/src/evaluate.py` newly modified; nothing else touched |

### Open decisions blocking the next phase

1. **The stale oracle baseline** (see "What was verified vs assumed") is real and unresolved:
   `fct_ghost_car_pace` and `mart_corner_skill_driver` both hash-drift against
   `tests/model_hashes.baseline.json` independent of anything this session did. Whoever next runs
   `make lint-oracle-check` (or `transform-check`) should expect it to fail on more than these two,
   and should treat that as "the baseline needs regenerating against current HEAD-plus-uncommitted
   state," not as new breakage.
2. **`scripts/snapshot_model_hashes.py` OOMs on this machine at default settings** (4 GiB single
   allocation). Not fixed here (out of scope for a lint pass) — a future run either needs a
   lower-memory rewrite of `hash_relation` (chunked hashing, or `SET memory_limit`/
   `preserve_insertion_order=false` added to the script's own `duckdb.connect`) or a machine with
   more headroom.
3. 10c's FP2/practice ingest, CDN publish, and everything else from Phase 10a's leftovers —
   unchanged, still stand.

**Closed without investigation (2026-09-06, user call):** ground-effect-era feature ideation
(prior checkpoint's open decision 2, carried forward above as item 3 until now) — the user's
explicit judgment is that the models are already well normalised per-season (per-season compound
refitting, per the "2022 regulation-era question closed" checkpoint earlier this same date), so a
separate ground-effect-era feature axis is not worth pursuing. Removed as an open item; do not
resurface it as a leftover in a future checkpoint.

### The first command the next session should run

Nothing is blocking. If the stale-baseline item (1 above) is picked up: regenerate
`transform/tests/model_hashes.baseline.json` via `.venv/bin/python scripts/snapshot_model_hashes.py`
(no `--check`) against a freshly-built `ci.duckdb`, review the diff to confirm every drifted model's
change is an intentional, already-known one (Phase 9/10a's feature additions, the era-affinity model,
etc.) rather than a surprise, and only then let it get committed alongside those other changes
whenever they are committed.

## Checkpoint 2026-09-06 (oracle OOM fixed; the "stale baseline" item turned out to be a false
alarm caused by a stale warehouse file, not real drift; one genuine bug found and fixed along the
way)

Picked up open item 1 (stale oracle baseline) and item 2 (OOM) from the prior checkpoint, per the
user's explicit direction to fix the OOM and to drop ground-effect-era ideation entirely (already
closed above, at the user's call, without investigation — the per-season compound refit already
absorbs it).

### What landed

**`transform/scripts/snapshot_model_hashes.py` — `hash_relation` rewritten to fix a real OOM, not
just a slow query.** The old implementation combined per-row hashes with
`string_agg(md5(...) ORDER BY ...)` — order-independent, but it requires sorting and concatenating
every row's hash into one string, an O(n) intermediate. On `stg_telemetry` this failed with
`OutOfMemoryException: failed to allocate 4.0 GiB (4.0 GiB/6.3 GiB used)` on this 8 GB machine.
Replaced with `bit_xor(md5_number(CAST(t AS VARCHAR)))`: `md5_number` returns a 128-bit
(`UHUGEINT`) hash instead of a 32-char string, and `bit_xor` is commutative and associative, so it
combines as a single O(1)-memory running accumulator with no sort and no concatenation — order-
independence falls out of the operator itself rather than an explicit `ORDER BY`. Also added
rowcount comparison to `do_check()` alongside the hash comparison: `bit_xor` has a known blind spot
the old algorithm didn't (adding or removing an *even* number of byte-identical duplicate rows
cancels out and leaves the combined hash unchanged), and the rowcount is already computed and
stored in the baseline, so checking both closes that gap at negligible cost.

**The "stale baseline" from the prior checkpoint was misdiagnosed — not new drift, a wrong-scale
warehouse.** `data/ci.duckdb` on disk already had `stg_telemetry` at 118,036,558 rows and
`stg_track_status` at 1,729 — both far larger than the project's own canonical CI scale. Every gate
that actually builds its own warehouse first (`make test-all`, `make transform-check`) does so via
`dbt build --target ci --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'`, which
produces `stg_telemetry` at 2,360,678 rows and `stg_track_status` at 52 — the file sitting on disk
had, at some earlier point, been built without that fixtures override (against the full bronze
lake) and never rebuilt since. That stale file is what the prior checkpoint's OOM reproduction and
"drift" finding both ran against. Rebuilt `ci.duckdb` correctly (see below) before regenerating
anything.

**`transform/models/staging/stg_track_status.sql` — a genuine, previously-unknown non-determinism
bug, found only because the OOM fix let the oracle reach this relation for the first time.** Hashed
this view 4 times back-to-back against identical underlying data and got 3 different results —
confirmed non-deterministic, not a fluke. Root cause: `renamed` had literal duplicate rows from the
bronze source (e.g. race `2024_17` had the exact same `all_clear` event logged 4 times and the exact
same `yellow` event logged 4 times, both at `session_time_s = 819.841`), and the final
`LEAD(session_time_s) OVER (PARTITION BY race_year, race_id ORDER BY session_time_s)` had no
secondary tiebreak, so ties (both the literal duplicates and, after dedup, two distinct status codes
genuinely stamped at the same instant in 5 races) resolved to an arbitrary, engine-dependent order.
Fixed with two changes: `SELECT DISTINCT` in the `renamed` CTE (removes the literal duplicates —
this model's own header declares the grain as "one row per track-status change event," so identical
duplicate rows were already a grain violation independent of the determinism question), and
`status_code` added as a secondary `ORDER BY` key in the `LEAD()` window (makes the choice of which
simultaneous event is treated as "first" stable and reproducible — the comment in the file is
explicit that this does not claim the ordering is domain-meaningful, only that it is deterministic).

**`transform/tests/model_hashes.baseline.json` regenerated** against the correctly-rebuilt,
track-status-fixed `ci.duckdb` (69 models, 0 missing).

### What was verified vs assumed

**Verified** — the OOM is fixed at the scale that actually caused it, not just at canonical scale:
re-ran the new `bit_xor`-based hash directly against the *stale* 118M-row `stg_telemetry` (before
touching anything else) and it completed in ~33s with no memory error, versus the old algorithm's
hard OOM on the identical relation.

**Verified** — the `stg_track_status` fix actually eliminates the non-determinism, not just
plausibly should: hashed the rebuilt view 6 times back-to-back post-fix, all 6 identical
(`092c849c8fa55c02e63271e2931fd2d4`); rowcount dropped from 1,729 (stale-scale, pre-fix) to 52
(correct scale, post-dedup) with zero remaining `(race_year, race_id, session_time_s)` ties.

**Verified, not assumed — the "stale baseline drift" claim from the prior checkpoint was a false
alarm.** Re-implemented the *old* `string_agg`-based algorithm standalone and ran it against the
correctly-rebuilt `ci.duckdb` for every model, then diffed against `git show
HEAD:transform/tests/model_hashes.baseline.json`. Result: 53 models byte-identical to HEAD, 3
legitimately new (`int_lap_proximity`, `stg_race_control`, `stg_telemetry_position` — Phase 9/10a's
already-known additions), and 15 changed. Checked the 15 two ways: (a) for `fct_ghost_car_pace`,
`fct_cliff_prediction_features`, `fct_driver_skill_features`, `fct_ghost_race_finish`,
`fct_lap_residuals`, and `fct_stint_features`, the old-algorithm hash against the *correct-scale* DB
matched **exactly** the value already sitting in this session's starting (uncommitted)
`model_hashes.baseline.json` — i.e. the value an earlier session had already correctly captured, and
the prior checkpoint's claim that `fct_ghost_car_pace` "drifted" was purely an artifact of testing
against the stale 118M-row warehouse, not real drift; (b) for the other 8
(`int_constructor_deg_sensitivity`, `int_lap_anomaly_flags`, `int_lap_residual_decomposed`,
`int_lap_residual_stint_detrend`, `int_qualifying_decomposed`, `int_sector_residual_decomposed`,
`int_synthetic_teammate`, `int_tyre_surface_vs_bulk_decoupling`) — none of which have a `.sql` diff
in this session — reran the old algorithm 3x each to rule out them being *another* latent
non-determinism bug (all stable across repeats), then confirmed each value also matches what was
already sitting in the pre-session working tree exactly. All 15 are pre-existing, already-correct,
already-uncommitted Phase 9/10a state, not new drift from anything done this session.

**Assumed, flagged, not fixed** — `stg_track_status`'s surrogate key
(`track_status_id = {race_id}_{session_time_s}`) collides for the two-distinct-events-same-instant
case (both `all_clear` and `yellow` at `819.841` in `2024_17` now get the same ID), which violates
its own schema.yml description ("Surrogate key"). Not touched: `track_status_id` is not joined
anywhere in `models/` (grepped), so this doesn't break anything currently, and there is no `unique`
test on the column today (only `not_null`) so nothing is silently passing that should fail. Fixing
it (e.g. appending `status_code` to the key) is a small, separate, deliberate change — flagged here
rather than bundled into a session that was fixing a different bug.

**Assumed** — `int_pit_strategy_cost_curve` showing as a `WARNING` (non-mandatory drift) on every
fresh `--check` run is expected, not new: this is the same model the 2026-09-05 checkpoint titled
"two of Phase 10a's open decisions closed" already investigated and adjudicated under "Open decision
3." Not re-investigated here.

### Gates run

| Gate | Result |
| :--- | :--- |
| New `bit_xor` hash vs old `string_agg` hash, stale 118M-row `stg_telemetry` | **Old: OOM. New: completes in ~33s** |
| `stg_track_status` hashed 6x post-fix (identical underlying data) | **PASS** — all 6 identical |
| Remaining `(race_year, race_id, session_time_s)` ties post-dedup | **0** |
| `make transform-check` (parse → lint → build → 56 singular tests → oracle → pytest) | **PASS** — 0 lint errors, dbt build 672/675 (3 no-op) 0 errors, 56/56 singular tests, oracle 0 fct_* drift, 66/66 coefficient pytest |
| Old-algorithm cross-check, correct-scale DB vs `git show HEAD:...baseline.json` | 53 unchanged, 3 new (known), 15 changed — all 15 traced to pre-existing uncommitted Phase 9/10a state, not new drift |
| `git status` | Only `transform/scripts/snapshot_model_hashes.py`, `transform/models/staging/stg_track_status.sql`, `transform/tests/model_hashes.baseline.json`, and this doc newly touched this session |

### Open decisions blocking the next phase

1. **`stg_track_status.track_status_id` surrogate-key collision** (see "Assumed, flagged, not
   fixed" above) — real but low-severity (not joined anywhere, no `unique` test relying on it).
   Fixing it means deciding the right key shape (e.g. append `status_code`) and is a separate,
   deliberate change from this session's determinism fix.
2. 10c's FP2/practice ingest, CDN publish, and everything else from Phase 10a's leftovers —
   unchanged, still stand.

### The first command the next session should run

Nothing is blocking. `transform/tests/model_hashes.baseline.json` is current and gate-verified —
`make transform-check` passes clean. If item 1 above (the `track_status_id` collision) is picked
up, start by deciding the key shape with the user before changing it, since nothing downstream
currently depends on the column's exact format.

## Checkpoint 2026-09-06 (`track_status_id` collision closed — same session, user picked it up
immediately after the OOM/determinism checkpoint above)

### What landed

`transform/models/staging/stg_track_status.sql` — `track_status_id` changed from
`{race_id}_{session_time_s}` to `{race_id}_{session_time_s}_{status_code}`. Verified first, not
assumed: queried the corrected-scale `ci.duckdb` for remaining `(race_year, race_id,
session_time_s, status_code)` duplicates post-dedup — zero — before picking this key shape, so
`status_code` is confirmed sufficient to disambiguate every case that motivated the change (the
same-instant, two-distinct-status-codes races found in the prior checkpoint). `schema.yml`
updated to match (`Surrogate key   {race_id}_{session_time_s}_{status_code}`) and given a `unique`
test alongside the existing `not_null` — previously there was no `unique` test on this column at
all, so this also closes the gap where nothing would have caught a future regression.
`transform/tests/model_hashes.baseline.json` regenerated once more to absorb the new ID format
(only `stg_track_status`'s own hash changes; nothing joins `track_status_id` downstream, confirmed
by grep in the prior checkpoint).

### What was verified vs assumed

**Verified** — `make transform-check` full gate clean after the change: `unique_stg_track_status_
track_status_id` and `not_null_stg_track_status_track_status_id` both PASS (676 nodes now, was
675 — the new generic test adds one), dbt build 673/676 (3 no-op) 0 errors, 56/56 singular tests,
66/66 coefficient pytest.

**Verified** — oracle `--check` now reports zero warnings at all (`OK: all 7 fct_* models
byte-stable vs baseline.`, no non-mandatory drift line), closing out the `stg_track_status`
warning that appeared on every run since the determinism fix landed.

### Gates run

| Gate | Result |
| :--- | :--- |
| Remaining `(race, time, status_code)` duplicates before applying the key change | **0** — confirmed the key shape is sufficient before committing to it |
| `make transform-check` | **PASS** — 673/676 (3 no-op) 0 errors, including the new `unique` test |
| `snapshot_model_hashes.py --check` | **OK, zero warnings** (previously: 1 non-mandatory warning for `stg_track_status`) |

### Open decisions blocking the next phase

1. 10c's FP2/practice ingest, CDN publish (app-deploy — v11 committed, prod still serves v6, "the
   user's call" per Phase 10a's own checkpoint), and everything else from Phase 10a's leftovers —
   unchanged, still stand. These are the only items left open across the whole Phase 9/10 arc as
   of this checkpoint.

### The first command the next session should run

Nothing is blocking and nothing is gate-red. The only remaining open items are the two above —
both need a user decision before any code changes (10c needs a go-ahead to pull new data; the CDN
publish is explicitly the user's call), so there is no default "next command" to hand off — ask
the user which (if either) they want to start, same as this session did.

## Checkpoint 2026-09-07 (Phase 10c closed — not viable, no data pulled)

Asked the user which of the two remaining open items to start. Before agreeing to pull FP2 data,
the user raised the objection that FP2 sessions have unknown engine modes and unknown fuel
programs — no code was written to investigate this, it was a methodological challenge to 10c's own
premise, checked against the code that already exists rather than argued in the abstract.

### What landed

Nothing shipped — this is a closure decision, not a feature. `ingest.py` is untouched; no FP2 data
was pulled.

### The finding: 10c's premise had it backwards

The plan's own case for 10c (§16/§14, restated at the top of this checkpoint's parent sections)
was that FP2 long runs are "long, in clean air and free of strategy contamination" — trading
race-strategy confounds (pit stops, traffic, tyre management calls) for a cleaner degradation
signal. Checked against the two fuel-correction models that already exist in this codebase, that
framing is backwards: FP2 has confounds of its own that neither one can handle.

* **`int_lap_fuel_state.sql`** (race laps) estimates starting fuel as `race_lap_count ×
  fuel_consumption_rate_kg_per_lap` — sound only because a race car's fuel load is sized to a
  *known* race distance. An FP2 long run has no equivalent anchor: a team picks an arbitrary
  starting fuel for whatever program it is running, unrelated to how many laps it happens to do
  that day. The formula has no FP2 analogue.
* **`int_lap_fuel_state_qualifying.sql`** sidesteps the same problem by assuming a flat 12 kg —
  defensible only because quali fuel is low and burn-off over one push lap is negligible
  (~0.006 s). FP2 long runs are the opposite case: many laps, high starting load, meaningful
  burn-off — exactly where the flat-constant trick stops working.

Between the two, there is no existing method, and no available data source, for estimating FP2
fuel load. Fuel burn-off over a long run is comparable in magnitude to the tyre-degradation signal
itself, so an uncorrected long run would corrupt exactly the thing 10c was meant to sharpen, not
add clean rows to it.

**Engine mode is worse, not just similarly bad.** Fuel load at least has a race-side estimation
method that fails to transfer; engine/power-unit deployment mode has no telemetry channel in
FastF1 at all, for any session type. There is nothing to even attempt a correction against.

### What was verified vs assumed

**Verified** — read both `int_lap_fuel_state.sql` and `int_lap_fuel_state_qualifying.sql` in full;
the `race_lap_count`-dependent formula and the flat-12kg constant are both real, current code, not
a memory of how they used to work.

**Assumed** — that no public data source (team radio, press fuel-load estimates, etc.) is reliable
enough to substitute. Not investigated in depth; the user chose "close as not viable" over
"investigate a proxy first" when asked, on the reasoning that even a successful proxy would be a
noisy estimate of a confound already comparable in size to the signal of interest, undermining the
original "raise SNR" rationale for 10c in the first place.

### Gates run

None — no code changed.

### Open decisions blocking the next phase

1. **CDN publish / app-deploy** — v11 committed, prod still serves v6. Unchanged from every prior
   checkpoint back to Phase 9. Explicitly the user's call, not a default next action.

Phase 10c (FP2/practice ingestion) is removed from the open-items list as of this checkpoint. Do
not resurface it as a leftover in a future checkpoint without a genuine fuel-load or engine-mode
proxy in hand — re-raising it without one would be re-litigating a closed, reasoned decision, the
same failure mode this doc warns about at the top of the "Handoff protocol" section.

### The first command the next session should run

Nothing is blocking. The only open item left across the entire Phase 9/10 arc is the CDN
publish/deploy decision, and it is explicitly not a default action — ask the user before doing
anything toward it.

## Checkpoint 2026-09-07 (research program §3 probed before it was built — the method was
disproven, redesigned, and nothing shipped)

Second session of 2026-09-07, immediately after the Phase 10c closure above. With this plan's
last work item closed, `_improvements/ml_research_program.md` opened. Its §3 ("build a ceiling
that binds") was to be the first thing built. It was probed first, and the probe killed the
method as specified.

### What landed

No code, no model, no contract, no artefact. Two documents changed:

* `_improvements/ml_research_program.md` — §3 rewritten: the original matching sketch is
  retained but marked superseded, a new §3a records the feasibility probe and its two failure
  modes, and a new §3b specifies the replacement design. §4 (FP ingest) restated as **CLOSED,
  NOT VIABLE** with a do-not-restart banner pointing at the checkpoint above. §5's denominator
  corrected 17 → 21 checkpoints. Status header, §1d, §6 and §7 updated for a three-item ladder.
* This file — the checkpoint you are reading.

### The finding: the §3 method would have retired the program on an instrument artefact

§3's sketch was to match near-identical rows across different races on hand-picked keys
(driver, compound, circuit, tyre-age band, fuel, track state) and read the within-group spread
as irreducible noise. Probed read-only against `data/dev.duckdb`,
`fct_cliff_prediction_features`, `is_training_eligible AND next_5_lap_cumulative_jump_s IS NOT
NULL` — 82,315 rows / 6,200 stints / 147 races / 2018–2024, marginal target SD 6.083:

**Failure mode 1 — the keys do not resolve anything.** One row per stint per group, ladder from
three keys to seven: within-group SD moves 5.470 → 5.674 → 5.757 → 5.521 → 5.305 against a
marginal 6.083. Flat, and non-monotone because each level survives on a different row
population (26,336 / 16,977 / 10,360 / 22,183 / 15,990 rows — so the levels are not comparable
to each other either). At its strictest the match explains ~24% of variance, so the floor would
have reported ~87% of the target's SD as irreducible and concluded the campaign was finished.
That is §3's own named risk — "match on too few → wrongly retire the whole program" —
realised, not hypothesised.

**Failure mode 2 — strict matching cannot support a quantile floor.** At the strictest level
(15,511 rows, 7,177 groups, avg m = 2.16), the leave-one-out group-quantile floor comes out at
2.4175 / 2.5138 / 2.3770 for p10/p50/p90 — **above the stint-blind constant-predictor floor**
(1.2911 / 2.0094 / 0.8972) at every quantile, and 2.5–4.6× the v11 model. A floor above the
floor is estimator variance, not a bound: LOO at m ≈ 2 estimates a p10 from one point.

The two failure modes trade off along the same axis the planned sweep was going to traverse,
so there is no good point on that line.

### What was verified vs assumed

**Verified** — all five ladder rows and both floor tables are computed numbers from
`data/dev.duckdb`, read-only, this session. Thinning to one row per stint per group was applied
throughout (the target is a 5-lap forward window; consecutive rows share 4 of 5 terms).

**Verified** — the probe's pinball arithmetic matches `evaluate.py`'s. Its constant-predictor
floors are 1.2911 / 2.0094 / 0.8972 against `evaluation_metrics.json`'s 1.2512 / 1.9536 /
0.7859. **These are two different protocols and the 2–4% gap is population, not disagreement**
— the probe pools 2018–2024, the artefact is `cv_final_fold` on `eval_season` 2024. The
agreement was used only to confirm the arithmetic. No probe number is diffed against an
artefact number anywhere in the write-up, and §3a says so on the page.

**Assumed** — that k-NN in the scaled 24-feature space (the §3b replacement) resolves failure
mode 1. It is the right space in principle, being the space the model conditions on, but it is
untested and 24 dimensions at 82k rows is where nearest-neighbour methods get thin. This is why
§3b mandates a synthetic recovery test before the instrument is trusted on real data.

**Assumed** — that pooling centred within-group residuals fixes failure mode 2. It removes the
m ≈ 2 estimation problem by construction, but it substitutes a homoscedasticity assumption that
is probably false (noise is likely wider near the cliff and in traffic). §3b carries the caveat
and requires stratified pooling rather than a single scalar.

### Gates run

| Gate | Result |
| :--- | :--- |
| Probe writes to warehouse / models / git | **None** — read-only connection, throwaway scratchpad scripts, nothing committed |
| Probe pinball arithmetic vs `evaluate.py`'s floors | **Agrees** within 2–4%, fully explained by population (all-seasons vs `cv_final_fold` 2024) |
| Falsification gate (floor ≤ model's achieved loss) applied to the *old* §3 method | **FAILS** — 2.5138 vs 1.0121 at p50. This is what disqualified the method |
| Model refits / contract changes / artefact writes | **None** |

### Open decisions blocking the next phase

1. **CDN publish / app-deploy** — v11 committed, prod still serves v6. Unchanged, still the
   user's call, still not a default action.
2. **§3b is designed but unbuilt.** No decision blocks it; it is simply the next piece of work,
   and it is now the only thing gating §5 and §6.

### The first command the next session should run

Read `_improvements/ml_research_program.md` §3a and §3b in full before writing any code — §3a
is the reason §3's original method must not be built, and a session that skips it will rebuild
the disproven instrument. Then build §3b's estimator: the first artefact is a curve of
estimated irreducible **pinball loss** (p10/p50/p90, headline units, not variance) against
**mean k-NN distance in the scaled 24-feature space**, for `next_5_lap_cumulative_jump_s`, on
`data/dev.duckdb` read-only, with the d→0 extrapolated intercept reported alongside the curve
rather than instead of it. Build the synthetic recovery test first, and apply the falsification
gate to every point on the curve — a point where the estimated floor exceeds the model's
achieved loss is an instrument failure and gets reported as one, not dropped from the plot.
