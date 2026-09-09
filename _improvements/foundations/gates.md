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
shapes to watch for, both of which have live instances in the current backlog:

- **A centred window reaches forward.** Work item `02a` exists because
  `int_corner_skill_residuals` computes residuals against "5-lap-bucket field medians" and
  nobody has checked whether that bucket is centred.
- **A pooled historical rate leaks the future into the past.** Work item `02d` must rebuild
  `int_sc_hazard_history` as a season-lagged expanding rate, because as built it puts 2024
  races into what a 2018 row sees.

## 6. Pre-register the arms before running them

`reference/ml_research_program.md` §5 documents an uncorrected multiplicity problem across 22
checkpoints. Adding four tiers of feature tests without pre-registration makes it worse, and
pre-registration costs nothing.

Write the arms into the leaf doc, then run them. This is why work item `04` sits ahead of
`01` and `02` in the build order rather than after them.

## What "clears" means

A delta that clears its own family's floor, in the direction of improvement, **with the
permutation-null arm attributing it to information rather than capacity**. A total that
clears while neither half does is recorded as exactly that — ambiguous — and never rounded up.
