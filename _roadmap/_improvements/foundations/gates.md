# The standing gate

Every change to the feature contract or to a model passes this, in order. It is not
negotiable per item, and an item that skips a step is `MEASURED`, never `GATED`.

The gate exists because the programme has already shipped on a number that did not survive
its own decomposition — see step 4.

## 1. Instrument check, first

The N-column refit must reproduce the published v11 headline **to six decimal places** before
anything built on top of it is trusted. Phase 10b did this; it is what makes its numbers
comparable to Phase 10a's.

A refit that does not reproduce the headline means the harness moved, and every delta
measured against it is meaningless.

## 2. Add-ablation on the identical split

`cv_final_fold`, train 2018–2023, eval 2024, using `evaluate.py`'s own `_fit`/`_score` — not
a reimplementation. Same split for every family in the comparison.

## 3. Delta against that family's own reseed floor

`2*sqrt(2)*sd` over 5 reseeds, from `ml/src/attribution.py::refit_noise_floor`. Each family
has its own floor; do not borrow one family's floor for another.

**Never against a floor computed under `intervals.py`'s paired-t protocol.** See
[`epistemics.md`](epistemics.md).

## 4. Permutation-null arm

Row-shuffle the new columns in train *and* eval, so capacity is preserved exactly and the
signal is destroyed. Report capacity (`shuffled − baseline`) and information
(`real − shuffled`) separately.

This step is not optional and it is not a formality. Phase 10a found a group whose **total
cleared at 1.54× while neither half cleared alone** — without this arm that would have
shipped as a clean information win. It is recorded in `schema.py` beside the group so the
next reader meets it there too.

## 5. Forward-window audit

For anything label-adjacent, plus the per-item leakage checks named in the leaf docs. Two
shapes to watch for, each of which has had a live instance in the current backlog:

- **A centred window reaches forward.** Work item `02a` exists because
  `int_corner_skill_residuals` computes residuals against "5-lap-bucket field medians" and
  nobody has checked whether that bucket is centred.
- **A pooled historical rate leaks the future into the past.** Work item `02d` must rebuild
  `int_sc_hazard_history` as a season-lagged expanding rate, because as built it puts 2024
  races into what a 2018 row sees.
  **CLOSED 2026-09-21 by `02d`.** The model is rebuilt as a season-lagged expanding rate
  keyed `(circuit_slug, season)`, with the empirical-Bayes prior lagged alongside it;
  `assert_sc_hazard_no_forward_leakage` re-derives the window with an inequality join rather
  than a frame, so a frame ending at `CURRENT ROW` surfaces as a count mismatch; 22/22 dbt
  tests pass, and `python3 -m ml.src.features --check` is clean on the forward-window,
  aggregation-scope and leakage audits with the model inside the audited lineage. The closure
  is independent of the feature's own ablation, which came back **negative** — see
  `work/02-feature-expansion.md`, "Verdict — `02d`". Four other models still carry the
  all-time-pooled shape (`int_driver_circuit_affinity`, `int_driver_circuit_era_affinity`,
  `int_era_normalized_driver_rating`, `int_pit_loss_circuit`); none feeds a feature today, and
  each enters `audit_aggregation_scope` automatically if ever wired in.

## 6. Pre-register the arms before running them

`reference/ml_research_program.md` §5 documents an uncorrected multiplicity problem across 22
checkpoints. Adding four tiers of feature tests without pre-registration makes it worse, and
pre-registration costs nothing.

Write the arms into the leaf doc, then run them. This is why work item `04` sits ahead of
`01` and `02` in the build order rather than after them.

## 7. Declare the e-value construction before running the arm

Step 6 says *what* you will test. This says *how the result will be scored for multiplicity*, and
it has to be written down before the arm runs or it is worth nothing afterwards.

Name the null as the information contrast step 4 already isolates (real vs row-shuffled, not
arm vs baseline — capacity is a nuisance), then declare the construction, its parameters and the
seeds. [`reference/e_value_construction.md`](../reference/e_value_construction.md) carries three
worked constructions for the reseed-floor setting and a fill-in block; take one, substitute your
numbers, paste it into the leaf doc.

**Before you fix `n` and `g`, check the construction's ceiling against the declared family size.**
Construction B is bounded: `E_max(n, g) = (1 + n*g)^((n-1)/2)` (`e_value_construction.md` §4). A
construction whose ceiling sits below `20 * (m + 1)`, where `m` is the campaign's current declared
family size, cannot produce a lone rejection whatever the data show — that is arithmetic, not
evidence, and it is `09c`'s finding. Look up `m` before choosing `n` and `g`, size the construction
so its ceiling clears that bar, and record which `m` you sized against beside the pre-registration
block. This check does not apply retroactively — arms already declared keep the `E` they were
given under the parameters declared at the time.

Report `E` whatever it comes out as, `E < 1` included, and count the arm in the campaign family
either way. The family is the set of *declared* hypotheses; dropping the ones that failed is the
selection problem this step exists to remove. Campaign-level decisions run **e-BH**, which holds
under arbitrary dependence and at any stopping time — the two properties `04b` closed on and
retrospective BH does not have.

## What "clears" means

A delta that clears its own family's floor, in the direction of improvement, **with the
permutation-null arm attributing it to information rather than capacity**. A total that
clears while neither half does is recorded as exactly that — ambiguous — and never rounded up.

Clearing the floor and returning a large `E` are **two instruments, not one**. A delta below the
floor can still return `E > 1`, and a delta well above it can still fail e-BH once the family is
counted. Step 3 rules on whether the arm beat its own noise; step 7 rules on what that is worth
across the campaign. Report both numbers and let them disagree in public.
