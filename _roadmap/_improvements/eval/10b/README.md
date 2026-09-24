# 10b Evaluation — the cause-specific arm: non-green endings treated as censored

## Status

**MEASURED and REJECTED — 2026-09-18, on the `v12`/`08m` substrate.** Gate steps 1, 2 (substituted),
3, 5 and 7 run; step 4 is inapplicable and substituted. 24 refits through `evaluate.py`'s own
`_fit`/`_score`, plus a 200-draw paired race-level cluster bootstrap. Nothing committed; nothing
written to `ml/models/`, to the warehouse or to `ml/artefacts/evaluation_metrics.json`.

**Ruling:** the `10b` label construction is **rejected**. `standard` — the realised stint ending,
which `D5` already chose on product grounds — is better on **both** pre-registered metrics by 4–6
times the arm's own reseed floor, and the result is resolved at **95%** on the instrument `10d` ruled
authoritative. Nothing to land: production already ships `standard`.

**This closes `10d`'s follow-up (b)** — "rule on 10b with A3's numbers in hand" — and confirms `D5`
on independent statistical evidence rather than only the product argument.

## The question

`schema.py` frames remaining stint life as single-event right-censored survival, but a stint ends for
several reasons and only one is a statement about the tyre. `10a` built the label; `10b` asks whether
**training** on it helps: refit `survival:aft` with every non-green ending recoded to censored, so the
fit estimates the *tyre-limit* distribution rather than the marginal mixture.

## Why it was measured a third time

Twice measured, ruled on neither time, and both prior numbers are now explained:

| the number | what it actually was |
| :--- | :--- |
| **+0.179** (original) | the incumbent scored under `standard` labels against the arm scored under `10b` labels — two different scoring populations. Withdrawn at the time as "92.6% a scoring artefact"; reproduced here at **+0.182** in-sample as exactly that |
| **−0.028** (rerun) | matched scoring, but fitted on 2018–2024 and scored on 2024 — in-sample, the same gate-1 defect `10d` later found in `10c`. Reproduced here at **+0.027** in the same mode |

And the substrate moved under all of it: `08m` rebuilt the warehouse and `08n` shipped v12 on
2026-09-16, so the eval fold is **19,973** laps today against the **20,272** that `10b`, `10c`, `10d`
and `10e` all scored. No figure those four published is reproducible to six decimals, which is stated
rather than worked around.

## The design

    A0 = `standard` labels -- the realised stint ending. Production's shipped v12 variant, D5's choice.
    A1 = `10b` labels     -- every non-green ending recoded to censored.

Same 32-column matrix, same v12 tuned params, same split, same rows. The **only** difference is the
censoring flag on 9,135 of 99,849 training rows (`sc_pit` 5,710 + `vsc_pit` 2,575 + `red` 850) and
1,185 of 19,973 eval rows. Capacity is identical **by construction** — unlike `10e`'s hyperparameter
re-search, where capacity *was* the arm.

## The methodological content: which labels to score under

AFT NLL is computed *against* the censoring flags, so "which labels to score under" is not a detail —
it is how `+0.179` happened. Both arms are therefore scored on the **green-pit stratum only**, where
the two constructions are identical row for row: `green_pit` is uncensored under both, `y` matches
exactly (verified array-for-array on all 9,149 rows), and both metrics derive their horizon grid from
that same `y`. The stratum is also the tyre-limit set the reframing exists to isolate, and it carries
**no censoring at all**, so it is the least IPCW-exposed quantity `10c` measured.

**The full-fold NLL is not a neutral instrument here, and this is the item's most reusable finding.**
On the full fold the `10b` arm has the *lower* NLL under either construction (+0.0215 under
`standard`, +0.0392 under `10b`) — and the decomposition says why: on rows with an observed ending it
is worse by 0.100, on censored rows it is better by 0.152. A censored row scores through
`log S(t) = log P(T > t)`, which improves monotonically the longer the prediction, and the `10b` arm
predicts **25.996** laps of mean remaining life against the incumbent's **20.680**. On the ~half of
the fold that is censored it collects that reward without having to be right about anything. Any
label change that reclassifies rows as censored buys full-fold NLL for free.

## Method

Gates in `gates.md` numbering. Steps 1–3 are this item's acceptance set.

1. **Instrument check** — `E._fit`/`_score` reproduces the published v12 headline
   `aft_nloglik` **1.9913358778933028** exactly; plus the substrate-drift table, plus the
   in-sample/honest optimism gap for both label constructions, plus the 2×2 scoring table that makes
   the original artefact visible in one place.
2. **Add-ablation** — inapplicable, nothing is added. Substituted requirement (same split for every
   family, through `evaluate.py`'s own `_fit`/`_score`) met and verified array-for-array.
3. **Floor** — each arm's **own** 5-reseed floor, seeds 20260528–20260532 with XGBoost's `seed`
   genuinely varied, `2*sqrt(2)*sd`, cross-checked against
   `attribution.py::refit_noise_floor` to 1e-12. Delta quoted against A1's floor (the arm's own
   family) with A0's beside it; neither borrowed.
4. **Permutation null** — inapplicable, no new columns. Substitute is the paired reseed null of
   step 3. Capacity is identical between the arms by construction, not by assumption.
5. **Forward-window / label adjacency** — `stint_end_cause`, `is_censored_stint`, `end_regime` and
   `end_cause_confidence` all asserted absent from `FEATURE_COLUMNS`.
7. **E-value** — Construction B (paired safe-t), `n = 5`, `g = 1.0`, on the two declared
   hypotheses, declared in the leaf doc before the arm was fitted. Validity checked first: 100k
   i.i.d. normal draws return mean `E` = 0.994–1.011 at five sigmas, and the reference's worked
   example returns 17.05 against its published 17.0.

Plus a **paired race-level cluster bootstrap**, 200 draws, seed 20260910, 24 races, both arms scored
on the same resampled races — the instrument `10d` §4 ruled authoritative where the three disagree.

Deltas are oriented so **positive always means `10b` improves**, on every metric.

### Declared hypotheses, and what is only a diagnostic

- **H1** green-pit AFT NLL — the metric this item's method names.
- **H2** green-pit IPCW-Brier — the metric `10c` chose, on which `10d`'s A3 already ruled against
  `10b` on the old substrate (0.190 vs 0.206). Declared so that ruling is reproduced or overturned
  rather than inherited.

Green-pit AUC and the calibration slope are **floored and bootstrapped but not declared** and not
counted in the e-value family. They are reported so no gain is quoted without a floor under it;
promoting a diagnostic to a hypothesis after seeing its value is what gate 6 exists to prevent.

## Result

**The delta, with its floor ratio** (positive = `10b` improves):

| | delta | × A1's own floor | bootstrap 95% | P(10b improves) |
| :--- | ---: | ---: | :--- | ---: |
| **H1** green-pit NLL | **−0.1053** | **−6.22×** | [−0.1556, −0.0536] | **0.000** |
| **H2** green-pit Brier | **−0.0140** | **−4.07×** | [−0.0219, −0.0053] | **0.005** |
| green-pit AUC (diag) | +0.0052 | +0.60× | [−0.0063, +0.0266] | 0.905 |
| \|slope − 1\| (diag) | +0.0164 | +0.42× | [−0.0285, +0.0947] | 0.815 |

All five paired reseeds are negative on both declared metrics, tightly. The two apparent gains sit
**inside** their own floors and their bootstrap intervals straddle zero — so there is no trade-off to
weigh: `10b` loses on what was declared and does not measurably win anything else.

**This item is resolved at 95%, unlike `10d` and `10e`.** Those both hit the 24-race ceiling on a
calibration slope; a proper score evaluated per row has far less sampling variance than a slope
fitted through five binned points, so the same 24 races that cannot rank a slope *can* rank an NLL
and a Brier. `10e`'s Brier cleared for the same reason.

**Gate 7:** `E` = 35.41 (H1) and 34.50 (H2), and e-BH rejects both at the joint bar of 20 (`k* = 2`)
— but **in the wrong direction**: `t` is −54.99 and −34.07. The safe-t statistic is symmetric in `t`,
so direction is carried beside the number, never folded in. H₀ "the label change carries no
information about green-pit fit" is decisively rejected; the information is that it makes the fit
worse. A *lone* rejection was unreachable by construction — max attainable `E` at `n=5, g=1` is 36,
below the 40 a family of two requires.

## What reproduces from `10d`, and what does not

| `10d` finding | here |
| :--- | :--- |
| the in-sample optimism gap (AUC +0.143, Brier −0.065, slope +0.568 crossing 1.0) | **reproduces** (+0.141, −0.060, +0.520) on a rebuilt substrate and different rows |
| level bias −0.434 under `10b` vs −0.285 under `standard` | **reproduces** (−0.4329 vs −0.2741) |
| A3: `standard` better on green-pit Brier | **reproduces and strengthens** — now 4.1× floor and 95% |
| slope: `standard` 0.700 *better than* `10b` 0.666 | **reverses** — today `standard` 0.6736 against `10b` 0.6993, per-seed overlapping. Neither ordering survives a substrate change |

That last row is a third independent confirmation of the standing limit `10d` and `10e` both
recorded: a calibration slope estimated from 24 races is not a quantity this campaign can rank models
on.

## Two notes that outlive this item

1. **A floor is not borrowed across substrates either.** `gates.md` says not across families. A1's
   slope floor is 0.0393 here against `10d`'s 0.0176 under the *same* label and *same* params — 2.2×,
   from a warehouse rebuild alone. A1's floor is also ~2× A0's on all four metrics: the `10b` label
   does not only score worse, it makes the fit less stable under reseeding.
2. **`10a` is not collateral damage.** `stint_end_cause` remains load-bearing — it defines the
   green-pit stratum every honest number in `10c`, `10d`, `10e` and this item is computed on, and
   `02d` shares it. The cause label's value is as an **instrument**, not as a training label.

## Contents

- `README.md` — this file: status, question, design, method, ruling
- `MEASUREMENTS.md` — every table, gate by gate, with the per-seed values
- `arms_10b_cause_specific_censoring.json` — the full artefact: all 24 fits, floors, e-values,
  bootstrap draws, provenance
- `arms_10b_cause_specific_censoring.log` — generation log

Script: [`scripts/arms_10b_cause_specific_censoring.py`](../../../scripts/arms_10b_cause_specific_censoring.py).
Reproduce with `PYTHONPATH=. python3 scripts/arms_10b_cause_specific_censoring.py` (~15 min, the
bootstrap is the slow part; `--skip-boot` for the gates alone).

## Decision required

**None.** The arm is rejected and production already ships the surviving label (`standard`, per `D5`).
The one loose end is a documented trap rather than a decision: `ml/src/evaluate_10c.py` still defaults
to `--variant 10b`, so re-running 10c's evaluation with defaults measures the rejected label. Changing
that default changes what the 10c artefact reproduces, so it is left to whoever lands this ruling.
