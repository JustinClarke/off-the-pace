# 10 — Competing risks in the stint-life target

**Group:** 10 · **Depends on:** `10a` before `10b` before `10c` · **Shares its label with `02d`**

Opened 2026-09-07 out of research round R1. The strongest finding of that round, and the only one
where a settled statistical framework maps onto a **measured** defect in a shipped model.

Full evidence: [`../research/R3-competing-risks.md`](../research/R3-competing-risks.md).
Do not re-derive it.

**The claim in one line.** `schema.py` frames remaining stint life as single-event right-censored
survival. But "uncensored" is not one event — a stint ends for several reasons, and only one of
them is a statement about the tyre.

**Verified.** Of 5,360 uncensored stints, **1,543 (28.8%) end under safety car, VSC or red flag.**
They run **11.14 / 17.04 / 5.34 laps** respectively against green's **19.44**. Present in every
season (19.2–38.9% non-green). The AFT fit is therefore a mixture of a tyre-wear process and an
exogenous-interruption process, with a circuit- and season-varying mixture weight.

**Corrected by `10a`:** 325 of those 5,360 are not stints at all but 2018 laps FastF1 never
assigned a stint number, and 127 of them are non-green. On real stints the share is **1,416 /
5,037 = 28.1%**, and 2018 drops from 26.0% to 17.4%. The claim stands; the 2018 row did not.
See `10a`'s correction table below.

**Corroboration, Assumed rather than Verified.** In `ml/model_card.yml`'s `dual_importance`,
`age_in_stint` is in **neither** top-5 for `stint_life_regressor`, while the two models predicting
pace and cliff state both carry it prominently. What sits at the top instead is `fuel_mass_kg` and
`lap_number` — near-collinear, i.e. the **race clock**. That is the fingerprint a mixture of
tyre-limit and deployment-timing events predicts. Importance rankings are not causal and
`lap_number` correlates with tyre age by construction; carry both caveats whenever it is quoted.

**And the input is not the problem.** `age_in_stint` is FastF1's `TyreLife` passed through
untouched, 0.21% missing, and every within-stint step is exactly +1 across 154,378 transitions.
See [`../notes/tyre-life-provenance.md`](../notes/tyre-life-provenance.md). This is a **target**
problem. Nobody should re-open the data question.

---

## 10a — The end-regime label — **LANDED 2026-09-08**

**Objective.** One column: why did this stint end?

**Method.** Classify each stint's final lap from `int_stint_geometry`'s `is_red_flag_lap` /
`is_safety_car_lap` / `is_vsc_lap`, crossed with `is_censored_stint`, into
{green-pit, sc-pit, vsc-pit, red, race-end, retirement}. Precedence must be declared, not
inherited from whatever order the CASE happens to be written in — red before SC before VSC is what
the R3 measurement used.

**`02d` needs the same label.** Build it once, use it twice; sequence the two together.

**Acceptance.** The label exists at stint grain, its precedence rule is written down, and its
distribution reproduces R3's table.

**Definition of done.** A later reader can tell, for any stint, why it ended and how confidently.

### What landed

`transform/models/intermediate/int_stint_end_regime.sql`, one row per `stint_id`, 8,333 rows.
`fct_stint_features` now carries `end_regime`, `stint_end_cause` and `end_cause_confidence`
alongside `is_censored_stint`, so `10b` is a change to label construction in `ml/src` and nothing
else. Guarded by 19 schema tests on the model and 5 on the mart's passthrough columns, plus
`transform/tests/assert_stint_end_cause_partition.sql`, which re-derives the label independently
of the model's own CTEs — a different route to the final lap, the censoring window and the
running-at-the-flag test rebuilt from staging — so it fails on drift rather than moving with it.

**Two facets, not one, and they are not redundant.**

- `end_regime` ∈ {green, safety_car, vsc, red_flag} — the track regime in force on the stint's
  final lap, emitted for **every** stint including censored ones. Crossed with
  `is_censored_stint` it reproduces R3's 2×4 table exactly, cell for cell, counts and mean
  lengths both.
- `stint_end_cause` — the six-class answer, which folds the regime into the censoring split.

Splitting them is what lets the cause label do the honest thing on a censored stint without
losing the measurement R3 rests on.

### The precedence rule, as declared

1. **Censoring outranks regime.** A censored stint is the driver's last of the race, so it did not
   end in a tyre change whatever was flying at the time; its causes are `race_end` and
   `retirement`. The regime is still recorded in `end_regime`, so nothing is lost. The 2021
   Belgian GP — stopped and abandoned under red flag, 20 drivers classified after 3 laps — comes
   out `race_end` with `end_regime = 'red_flag'`, which is the true pair of facts. This is what
   makes the taxonomy's own shape work: four uncensored causes, two censored ones, six.
2. **Within an uncensored stint, severity decides:** `red_flag` > `safety_car` > `vsc` > green.
   Not academic — `TrackStatus` is a concatenated digit string, and **346 final laps carry more
   than one code**: 276 red+SC, 53 SC+VSC, 17 red+VSC. Reorder the CASE and those 276 change
   class with nothing else failing, which is what the singular test exists to catch.
3. **Within a censored stint, the classified result decides.** Running at the flag →
   `race_end`, else `retirement`. The test is on `status` ('Finished', '+N Lap(s)', 'Lapped'),
   not on `is_classified`: 23 'Retired' rows *are* classified because the driver covered 90% of
   the distance, and they stopped. Disqualification is the one status that hides the answer — a
   post-race ruling, not a reason a stint ended, landing on drivers who ran to the flag and on
   drivers who did not — so it is resolved on distance instead, and marked `inferred`.

### How confidently — `end_cause_confidence`

| value | n | what it means |
| :--- | ---: | :--- |
| `observed` | 7,593 | every input read, nothing chosen |
| `inferred` | 415 | severity precedence had to choose (346), the pit marker is missing on an uncensored stint (328, overlapping), or disqualification hid the answer |
| `unassigned_stint` | 325 | not a stint — see below. `stint_end_cause` is NULL here |

### Correction to R3's numbers — the artefact stints

**Verified.** 325 of the 8,333 "stints" are built from the 343 laps FastF1 never assigned a stint
number, all in 2018, mean length 1.06 laps. `fct_stint_features` already sorted them below every
real stint so they come out *uncensored*, and R3 counted them: **127 of them are non-green**.
They are not stints and their ending has no cause, so `stint_end_cause` is NULL on them and they
are excluded from any share.

That moves two of R3's numbers and leaves the finding standing:

| | R3, as written | corrected | note |
| :--- | :--- | :--- | :--- |
| non-green share of uncensored | 1,543 / 5,360 = **28.8%** | 1,416 / 5,037 = **28.1%** | headline barely moves |
| 2018 non-green share | 818 stints, **26.0%** | 495 stints, **17.4%** | entirely artefact |
| 2018 mean length, green | 16.6 | **24.0** | 1-lap artefacts were dragging it |
| 2018 mean length, non-green | 6.9 | **15.5** | same |

No other season contains an unassigned-stint row, so 2019–2024 are unchanged and 2018 stops being
the outlier it appeared to be. R3's headline claim — that the AFT fit is a mixture of a tyre-wear
process and an exogenous-interruption process, present in every season — survives intact.

### Deviations from this doc, logged

- **The label is not built inside `fct_stint_features`.** The method above said "crossed with
  `fct_stint_features.is_censored_stint`". Instead `int_stint_end_regime` **owns**
  `is_censored_stint` — the definition moved down out of the mart, which now reads it back — and
  the mart's output is bit-identical on that column (8,333/8,333 against an independent
  recomputation; 2,973 censored, unchanged). "Build it once, use it twice" applied to the
  censoring window too, rather than leaving `02d` a second copy to drift from. This doc's method
  paragraph is corrected above.
- **Two extra columns beyond the six-class label**: `end_regime` (so R3's table stays
  reproducible) and `end_cause_confidence` (the "how confidently" the definition of done asks
  for). Plus provenance — `end_lap_id`, `end_lap_number`, `end_lap_in_stint`,
  `is_multi_regime_end`, `ended_on_pit_lap`, `was_running_at_flag`.
- **The family is `strategy`, not a new `survival` family.** `transform_docs_facts.py` fixes the
  intermediate vocabulary at five families, and `int_sc_hazard_history` — the model `02d` rebuilds
  — already sits in `strategy`.

### What `10b` reads

`stint_end_cause = 'green_pit'` is the tyre-limit set: 3,621 stints, mean 20.44 laps. Everything
else uncensored — `sc_pit` (806, 12.48), `vsc_pit` (223, 18.47), `red` (387, 5.34) — is what
`10b` recodes to censored.

---

## 10b — The cause-specific arm

**Objective.** Test whether separating the causes buys anything, cheaply, before anything
expensive is built.

**Method.** Keep `survival:aft`. Refit with **non-green endings treated as censored** — the
interval label already supports it; this is a change to label construction, not to the model
class. That fit estimates the *tyre-limit* distribution, which is the quantity the app's gauge
claims to show. Compare against the incumbent under
[`../foundations/gates.md`](../foundations/gates.md), delta against the family's **own** reseed
floor.

**This is a genuine test, both ways.** If the recoded fit does not move NLL beyond the floor, the
reframing closes on a measurement and `10c` never runs.

**Declare the e-value construction before running** (`09b`).

**Acceptance.** Gate steps 1–3 run in full; the delta is quoted with its floor ratio.

**Definition of done.** A written verdict: does splitting the causes move the family, or not.

### Pre-registration — arms, instruments and e-value (gates 6 and 7)

Written 2026-09-18, **before the `10b` arm was fitted on this substrate.** The only fit that preceded
this block is `A0` as the gate-1 instrument anchor (§1 below), which is the incumbent and not an arm.

**Why this is being measured again rather than read off the record.** Two reasons, both gate 1.

1. **The recorded −0.028 is in-sample.** It was measured with 2024 inside the scored booster's own
   training set — the same defect `10d` found in `10c`, and it is why the number was never ruled on.
2. **The substrate moved.** `08m` rebuilt the warehouse and `08n` shipped **v12** on 2026-09-16.
   The `cv_final_fold` eval fold is **19,973** laps today against the **20,272** that `10b`, `10c`,
   `10d` and `10e` all scored, and the green-pit stratum is **9,149** against **9,270**. Gate 1's
   literal requirement — reproduce the published headline to six decimal places — **cannot be met
   against any figure those four items published**, because the rows are not the same rows. What is
   anchored instead is *today's* published v12 headline, and the drift is reported rather than
   papered over.

**The headline instrument, and why comparing NLL across two label constructions needs one.** The
AFT NLL is computed *against* the censoring flags, so "which labels to score under" is not a detail
— it is exactly how the original `+0.179` became a 92.6% scoring artefact. Both arms are therefore
scored on the **green-pit stratum only**, where the two label constructions are **identical row for
row**: `green_pit` is uncensored under both, `y` matches exactly, and the metrics' horizon grid
(deciles of uncensored `y`) is therefore the same grid for both arms. That stratum is also the
tyre-limit set the whole reframing exists to isolate, and it carries no censoring at all, so it is
the least IPCW-exposed quantity `10c` measured. Verified array-for-array before anything was fitted.

**Arms.** Both refit on the training side only (2018–2023) through `evaluate.py`'s own
`_evaluation_split` → `_fit`, scored on 2024. Identical 32-column matrix, identical v12 tuned
params, identical rows. The only thing that differs is the censoring flag on **9,135 training rows**
(`sc_pit` 5,710 + `vsc_pit` 2,575 + `red` 850) and 1,185 eval rows.

| arm | label construction |
| :--- | :--- |
| **A0** | `standard` — the realised stint ending; production's shipped v12 variant, and `D5`'s ruling |
| **A1** | `10b` — non-green endings treated as censored |

**Declared hypotheses — two.**

- **H1 — green-pit AFT NLL.** `delta = NLL(A0) − NLL(A1)`, positive = `10b` improves. The metric
  this item's method names.
- **H2 — green-pit IPCW-Brier.** `delta = Brier(A0) − Brier(A1)`, positive = `10b` improves. The
  metric `10c` chose as its headline, on which `10d`'s A3 arm already ruled against `10b` on the old
  substrate (0.190 vs 0.206). Declared so that ruling is either reproduced or overturned on v12
  rather than inherited.

**Reported as diagnostics, not hypotheses:** full-fold NLL under *each* label construction for
*each* arm — the 2×2 scoring table that makes the original artefact visible — plus green-pit
time-dependent AUC, calibration slope, mean log-scale bias, the 5-bin predicted→observed table, and
the in-sample counterparts so the optimism gap is printed rather than assumed.

**Gate 3 floor.** Five seeds **20260528–20260532**, varying XGBoost's `seed` so `subsample` and
`colsample_bytree` genuinely redraw. `10b`'s original reseed table was zero-variance because the
seed was never varied, which is what produced its "∞× floor" — that is the defect being repaired
here, not a detail. Each arm gets its **own** floor per `gates.md`; the delta is quoted against
**A1's** (the arm's own family) with A0's printed beside it, and neither is borrowed. Floor =
`2*sqrt(2)*sd` through `attribution.py::refit_noise_floor`, in the same metric as the delta.

**Gate 2, substituted and stated.** The add-ablation is inapplicable in its literal form: nothing is
added. The substituted requirement — the same split for every family in the comparison, through
`evaluate.py`'s own `_fit`/`_score` rather than a reimplementation — is met exactly and verified by
comparing `X`, `y` and `lap_ids` array-for-array between the two bundles.

**Gate 4, stated rather than skipped** (outside the acceptance set, recorded because acceptance stops
at 3). The permutation null row-shuffles *new columns* and there are none. Unlike `10e`'s re-search,
capacity here genuinely **is** identical by construction: same matrix, same params, same tree
budget, and only the label bounds move. The substitute is the paired reseed null of gate 3.

**Gate 5, one check.** The label is label-adjacent, so `stint_end_cause` and `is_censored_stint` are
asserted absent from `FEATURE_COLUMNS` in both bundles before either arm is fitted.

**The bootstrap.** Paired **race-level cluster** bootstrap, 200 draws, seed 20260910, races the
resampling unit, 24 eval races — both arms scored on the *same* resampled races so the shared
race-draw noise cancels. `10d` §4 ruled this the instrument to believe where the three disagree, and
this item does not get to re-litigate that after seeing its own numbers. The standing limit applies
and is stated before the numbers exist: 24 races could not establish `10d`'s 0.17 slope move and
will not establish a small NLL move either.

**E-value — Construction B, declared now.** From
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) §4, the default, which
removes the plug-in-scale hole `10d`'s Construction A fell into.

- **Null.** H₀: the label change carries no information about green-pit fit, so the five paired
  reseed deltas are mean-zero.
- **Deltas.** `d_i = m(A0, seed_i) − m(A1, seed_i)` for `m` ∈ {green-pit NLL, green-pit IPCW-Brier},
  arm and incumbent refit at the **same** five seeds so the shared seed noise cancels.
- **Statistic.** `t = sqrt(5) * mean(d) / sd(d)` (ddof=1), `g = 1`,
  `E = (1+5g)^(-1/2) * [(1 + t²/4) / (1 + t²/(4(1+5g)))]^(5/2)`.
- **Verified before use**, as §4 requires: 100k simulated draws of five i.i.d. `N(0, σ)` deltas at
  several σ must return mean `E` = 1 to Monte Carlo error, and the reference's worked example must
  return 17.0.
- **Direction is carried beside the number, never folded into it.** The formula is symmetric in `t`,
  so a consistently *negative* delta also returns a large `E` — evidence against exchangeability in
  the wrong direction, which is a different statement from evidence for the arm.
- **Family.** Two declared hypotheses, added to the campaign family, both reported with their `E`,
  `E < 1` included. Campaign-level decisions run e-BH per gate 7.

**What would make this a pass, declared now so it cannot be decided afterwards.** `10b` clears if
the green-pit NLL delta is **positive**, **exceeds A1's own reseed floor**, and the paired bootstrap
puts `P(improves) ≥ 0.95`, with H2 not contradicting it. A delta inside the floor, or a positive
delta on one declared metric against a negative on the other, is recorded as **the reframing closing
on a measurement** — which this item's method names as a genuine outcome, not a failure to find one.

**One thing the method paragraph can no longer mean.** "If the recoded fit does not move NLL beyond
the floor … `10c` never runs" is retrospective: `10c`, `10d` and `10e` all ran on the `10b` label
before this ruling was made, and `D5` then chose `standard` anyway. So this item's job is no longer
to gate them. It is to settle the follow-up `10d` left open as **(b)** — whether the `10b` label was
ever the right family — and to say so in writing.

### Verdict — MEASURED 2026-09-18

**Splitting the causes does not move the family. It moves it backwards — by 6.2 times the arm's own
noise floor on the metric this item's method names, in all five reseeds, and in 200 of 200 paired
bootstrap draws.** `10d`'s A3 finding is reproduced on a rebuilt substrate and sharpened from "worth
revisiting" into a ruling: **`standard` is the label, `10b` is not.** The reframing closes on a
measurement, which this item's own method named as a legitimate outcome rather than a failure.

Artefact: [`../eval/10b/`](../eval/10b/) — script, JSON, log. 920s, 24 refits, nothing written to
`ml/models/`, the warehouse or `evaluation_metrics.json`.

#### 1. Gate 1 — the instrument, and three things it found

**(a) The harness reproduces today's published headline exactly.** `E._fit`/`_score` under the
`standard` label returns `aft_nloglik` **1.9913358778933028** against `evaluation_metrics.json`'s
published v12 **1.9913358778933028** — every digit stored, not merely six places.

**(b) No figure published by `10b`, `10c`, `10d` or `10e` can be reproduced to six decimals, because
the rows moved.** `08m` rebuilt the warehouse and `08n` shipped v12 on 2026-09-16, after all four ran:

| | published by 10b–10e | today |
| :--- | ---: | ---: |
| eval-fold laps | 20,272 | **19,973** |
| green-pit laps | 9,270 | **9,149** |
| eval races | 24 | 24 |

Gate 1's literal requirement is unmeetable against the record, and that is stated rather than quietly
satisfied against a number that no longer exists. What *does* reproduce is the **defect** — §2.

**(c) Both of this item's withdrawn numbers are now accounted for, mechanically.**

| the number | what it actually was | reproduced here |
| :--- | :--- | ---: |
| the original **+0.179** | the incumbent scored under `standard` labels against the arm scored under `10b` labels — two different scoring populations | **+0.182** in-sample, **+0.202** honest |
| the recorded **−0.028** | matched scoring, but fitted 2018–2024 and scored on 2024, i.e. in-sample, on the full mixture fold | **+0.027** in this item's orientation (10b better), in-sample, full fold, 10b-scored |

Neither was a fluke and neither was signal. The first is a scoring mismatch worth ~0.18 NLL on its
own; the second is an in-sample reading of a full-fold instrument that §5 shows is not neutral
between these two arms.

#### 2. The optimism gap — `10d`'s finding, independently reproduced on a rebuilt substrate

Same arm (`10b` labels), same eval rows, fitted two ways. `in_sample` fits every training season
2018–2024 exactly as `train.py` does, then scores the 2024 rows that sit inside that fit:

| green-pit, `10b` label | honest | in-sample | optimism | `10d` published |
| :--- | ---: | ---: | ---: | ---: |
| time-dependent AUC | 0.6987 | 0.8396 | +0.1409 | +0.1429 |
| IPCW-Brier | 0.2031 | 0.1430 | −0.0601 | −0.0652 |
| calibration slope | 0.6993 | 1.2192 | **+0.5198** | +0.5682 |

The slope crosses 1.0 across that gap, on a warehouse rebuilt eight days later, on rows that are not
the same rows. **`10d`'s gate-1 finding is not an artefact of its substrate** — and that is worth
more than any number this item produces.

#### 3. Gate 2, substituted — the arms differ in the label and in nothing else

Verified array-for-array rather than asserted: `X_tr`, `X_ev`, `y_tr`, `y_ev`, `lap_ids_tr` and
`lap_ids_ev` are all identical between the two bundles. Split `cv_final_fold`, train 2018–2023, eval
2024, through `evaluate.py`'s own `_evaluation_split`/`_fit`/`_score`. What differs is the censoring
flag on **9,135 of 99,849 training rows** (`sc_pit` 5,710 + `vsc_pit` 2,575 + `red` 850) and **1,185
of 19,973 eval rows**. Capacity is identical by construction: same 32 columns, same v12 params, same
tree budget.

**The green-pit stratum is matched, which is what makes the headline legitimate.** 9,149 laps over 24
races, **0.000 censored under both** constructions, `y` identical row for row — so both metrics derive
their horizon grid from the same `y` and score both arms on the same grid.

The cause label also covers every row on both sides of the split (train 45,022 + 42,458 + 5,710 +
3,234 + 2,575 + 850 = 99,849; eval 9,385 + 9,149 + 884 + 282 + 254 + 19 = 19,973), so `10a`'s 325
NULL-cause artefact stints never reach the training-eligible rows and `features.py`'s NULL fallback
in the `10b` branch is never exercised here. The recode is clean on this substrate.

**Gate 5**, the one check the label's adjacency calls for: `stint_end_cause`, `is_censored_stint`,
`end_regime` and `end_cause_confidence` are all absent from `FEATURE_COLUMNS`. The cause label is
meta and stays meta.

#### 4. Gate 3 — the delta, with its floor ratio

| arm | green-pit NLL | Brier | AUC | slope | intercept | mean log bias | margin sd |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **A0** `standard` | **3.4377** | **0.1904** | 0.6896 | 0.6736 | +0.2319 | **−0.2741** | 0.5818 |
| **A1** `10b` | 3.5361 | 0.2031 | 0.6987 | 0.6993 | +0.2601 | −0.4329 | 0.6306 |

Each arm's own 5-reseed floor, seeds 20260528–20260532 with XGBoost's `seed` genuinely varied.
**The floors are non-zero this time, and that is the repair:** `10b`'s original reseed table was
identical across all five seeds because the seed never reached the booster, so `subsample` and
`colsample_bytree` redrew identically — which is where its "∞× floor" came from.

| metric | A0 sd / floor | A1 sd / floor (of record) |
| :--- | ---: | ---: |
| green-pit NLL | 0.002943 / 0.008325 | 0.005986 / **0.016932** |
| green-pit Brier | 0.000736 / 0.002082 | 0.001212 / **0.003429** |
| green-pit AUC | 0.002126 / 0.006012 | 0.003079 / **0.008709** |
| calibration slope | 0.008848 / 0.025025 | 0.013892 / **0.039291** |

`attribution.py::refit_noise_floor` agrees with this arithmetic to 1e-12 on A1's NLL floor — the
helper was run as a cross-check rather than reimplemented and trusted.

**The delta, quoted against the arm's own family's floor, as the acceptance requires** (positive =
`10b` improves):

| | delta | × A1's own floor | × A0's floor | clears |
| :--- | ---: | ---: | ---: | :--- |
| **H1 declared** — green-pit AFT NLL | **−0.1053** | **−6.22×** | −12.65× | **no** |
| **H2 declared** — green-pit IPCW-Brier | **−0.0140** | **−4.07×** | −6.70× | **no** |
| H1 diagnostic — green-pit AUC | +0.0052 | +0.60× | +0.87× | no |
| H2 diagnostic — \|slope − 1\| | +0.0164 | +0.42× | +0.66× | no |

**And it is not a mean hiding a spread.** Every one of the five paired reseeds is negative, tightly:
NLL −0.0984, −0.1062, −0.1070, −0.1050, −0.1100; Brier −0.0127, −0.0135, −0.0142, −0.0140, −0.0152.

`10b` is worse than the incumbent by 6.2 of its own noise floors on the metric its method names and
4.1 on the metric `10c` chose. There is no reading of the gate under which that is a pass.

**A methodological note that extends `gates.md` rather than applying it.** The rule is that a floor
is not borrowed across families. This item adds: **nor across substrates.** A1's slope floor is
0.0393 here against `10d`'s 0.0176 under the *same* label and the *same* params — a 2.2× change
produced by a warehouse rebuild alone. Note also that A1's floor is roughly **twice** A0's on every
one of the four metrics: the `10b` label does not merely score worse, it makes the fit measurably
less stable under reseeding.

#### 5. Why the full-fold NLL says the opposite, and why it is the wrong instrument

This is the part that explains the whole history of the item, so it is measured rather than argued.
On the **full** eval fold the `10b` arm has the *lower* NLL under either label construction:

| full-fold `aft_nloglik` | A0 `standard` | A1 `10b` | delta (positive = 10b better) |
| :--- | ---: | ---: | ---: |
| scored under `standard` labels (48.3% censored) | 1.9913 | 1.9698 | **+0.0215** |
| scored under `10b` labels (54.2% censored) | 1.8285 | 1.7893 | **+0.0392** |

Decomposed into the two populations that make up that fold:

| scored under | delta on rows with an observed ending | delta on censored rows |
| :--- | ---: | ---: |
| `standard` labels | **−0.1004** | **+0.1522** |
| `10b` labels | **−0.0984** | **+0.1554** |

**The mechanism in one line.** An uncensored row scores through the log-density at the observed life;
a censored row scores through `log S(t) = log P(T > t)`, which improves *monotonically* the longer the
prediction. The `10b` arm predicts **25.996 laps** of mean remaining life against the incumbent's
**20.680** — 26% longer, because it has been told that every short non-green ending was a censoring
event rather than an ending. On the ~half of the fold that is censored it collects that reward without
having to be right about anything; on the rows where an ending was actually observed it pays 0.10 NLL
for the same over-prediction. Half the fold at +0.15 beats half the fold at −0.10, and the aggregate
flips sign.

So the full-fold NLL is **not a neutral instrument between these two arms**: any label change that
reclassifies rows as censored buys NLL on those rows for free. That is `10c`'s mixture artefact
appearing in the NLL itself, it is why the headline was pre-registered on the stratum with no
censoring in it, and it retroactively explains why the original measurement looked like a 9% win.
The uncensored-row delta (−0.1004) and the green-pit delta (−0.0984) nearly coincide, as they must:
green-pit is 9,149 of the 10,334 uncensored eval rows under `standard`, i.e. **88.5%**.

#### 6. The bootstrap — the instrument `10d` ruled authoritative, and it resolves this one

Paired race-level cluster bootstrap, 200 draws, seed 20260910, 24 races, both arms scored on the
*same* resampled races so the shared race-draw noise cancels (positive = `10b` improves):

| | paired delta | 95% | P(10b improves) |
| :--- | ---: | :--- | ---: |
| **H1 green-pit NLL** | **−0.1004** | **[−0.1556, −0.0536]** | **0.000** |
| **H2 green-pit Brier** | **−0.0131** | **[−0.0219, −0.0053]** | **0.005** |
| green-pit AUC | +0.0105 | [−0.0063, +0.0266] | 0.905 |
| \|slope − 1\| | +0.0312 | [−0.0285, +0.0947] | 0.815 |

**Both declared hypotheses are resolved at 95% — against the arm.** The intervals exclude zero on the
losing side; 0 of 200 draws and 1 of 200 draws respectively favour `10b`. This item does not inherit
the standing 24-race ceiling that `10d` and `10e` both hit, and the reason is the one `10e` already
identified: a proper score evaluated **per row** has far less sampling variance than a slope fitted
through five binned points, so the same 24 races that cannot resolve a slope *can* resolve an NLL and
a Brier. `10e`'s Brier cleared at 95% for the same reason. **This is the rare case in this campaign
where the authoritative instrument settles the question rather than declining to.**

And the two diagnostics straddle zero, consistent with both sitting inside their own reseed floors
(§4). They agree with the floor, which is the outcome to hope for when two instruments are asked the
same question.

#### 7. Gate 7 — the e-values, and a direction that must be read before the number

Construction B as declared, five paired reseed deltas, `g = 1`. **Verified before use:** 100k
simulated draws of five i.i.d. `N(0, σ)` deltas return mean `E` = 0.994–1.011 at every σ from 1e-4
to 1, and the reference's own worked example returns **17.05** against its published 17.0.

| declared hypothesis | delta | t | E | direction is improvement |
| :--- | ---: | ---: | ---: | :--- |
| H1 green-pit NLL | −0.1053 | **−54.99** | **35.41** | **no** |
| H2 green-pit Brier | −0.0140 | **−34.07** | **34.50** | **no** |

**Those are large e-values against the arm, not for it, and the construction cannot tell the
difference.** The safe-t statistic is symmetric in `t`, so a consistently negative delta returns the
same `E` as a consistently positive one; direction is carried beside the number because applying a
one-sided transform after seeing the data is the one thing that voids an e-value. Read correctly: H₀
was "the label change carries no information about green-pit fit", and it is decisively rejected —
the change carries information, and the information is that it makes the fit worse.

**e-BH at α = 0.05 over the two declared hypotheses rejects both**, `k* = 2`: the joint bar is
`n/(αk)` = 2/(0.05×2) = **20**, and both clear it. **One limit of the instrument, which was true
before the run rather than discovered after it:** at `n = 5`, `g = 1` the maximum attainable `E` is
`(1+ng)^((n-1)/2)` = **36**, below the **40** a lone rejection in a family of two needs. A
single-hypothesis rejection was unreachable here by construction; the joint one was not.

#### 8. What looked like `10b` doing better is inside the noise

Two things pointed the other way and neither survives its own floor:

- **Time-dependent AUC** +0.0052 over five paired seeds, **0.60× A1's floor**, bootstrap
  [−0.0063, +0.0266]. What a rank-based metric does with a wider spread of the same ordering: A1's
  margin sd is 0.6306 against 0.5818.
- **Calibration slope closer to 1.0**, `|slope − 1|` better by 0.0164, **0.42× floor**, bootstrap
  [−0.0285, +0.0947]. Both arms remain far below 1.0 and nothing here moves that.

**And the slope ordering contradicts `10d`, which is itself the finding.** On the old substrate `10d`
measured `standard` 0.700 against `10b` 0.666 and called them indistinguishable. Today the ordering
is **reversed** — `standard` 0.6736 against `10b` 0.6993 — on a rebuilt warehouse with 299 fewer eval
laps and the same params. Neither ordering survived a substrate change, and per-seed the two arms
overlap outright (A0 0.674/0.652/0.665/0.672/0.670 against A1 0.699/0.674/0.696/0.675/0.669). That is
a third independent confirmation of the standing limit `10d` and `10e` both recorded: a slope
estimated from 24 races is not a quantity this campaign can rank models on.

**The level bias, however, reproduces almost exactly.** Mean log bias **−0.4329** under `10b` against
**−0.2741** under `standard`, where `10d` measured −0.434 and −0.285. Under a framing whose entire
content is "the tyre would have lasted longer" that bias is not a bug — it *is* the framing. Per `D5`
it is also the wrong quantity for the gauge.

#### 9. Answering the definition of done

**Does splitting the causes move the family, or not? It does not.** It moves it backwards on the
metric this item's method names (green-pit AFT NLL, −6.22× the arm's own floor, bootstrap 0 of 200
draws favourable), backwards on the metric `10c` chose (green-pit IPCW-Brier, −4.07×, 1 of 200), and
its two apparent gains are inside their floors. The pre-registered pass criterion — positive delta,
above the floor, bootstrap `P ≥ 0.95`, H2 not contradicting — **fails on every clause.**

**R3's claim is untouched and this item does not dispute it.** The uncensored population really is a
mixture of a tyre-wear process and an exogenous-interruption process, 28.1% non-green, in every
season. What is now measured is that **recoding the interruptions to censored is not the repair.**
Telling the model that 9,135 short endings were merely censoring events teaches it that tyres last
26% longer than they do, and that is worse precisely where the app reads it.

**And `10a` is not collateral damage.** `stint_end_cause` remains load-bearing: it defines the
green-pit stratum that every honest number in `10c`, `10d`, `10e` and this item is computed on, and
`02d` shares it. The cause label's value is as an **instrument**, not as a training label. That
distinction is the durable result of group 10.

#### 10. What this settles downstream

- **`10d`'s follow-up (b) is closed.** "Rule on 10b with A3's numbers in hand" — A3's ruling
  reproduces and strengthens: `standard` beats `10b` on green-pit Brier out of sample, now by 0.0140
  at 4.1× the floor, with all five reseeds and a 95% bootstrap interval agreeing.
- **`D5` is confirmed on independent evidence.** It was settled as a product question with A3 as
  supporting evidence; the label it chose now also wins the statistical comparison on the arm's own
  declared metric, at 6.2× the floor and at 95%.
- **`10c`'s headline is doubly superseded and must not be quoted.** Its AUC 0.844 / Brier 0.141 were
  in-sample (`10d`) *and* measured on the label this item rejects. Its durable contribution is the
  three metric repairs and their 26 regression tests, which are untouched and pass.
- **`10e`'s S1x is unaffected** — it was tuned under `standard`, the surviving label.
- **A live trap, flagged and deliberately not fixed:** `ml/src/evaluate_10c.py` still defaults to
  `--variant 10b`, so anyone re-running 10c's evaluation with defaults measures the rejected label.
  Changing that default changes what the 10c artefact reproduces, so it belongs to whoever lands this
  ruling rather than being done silently here.

#### 11. Deviations, and one bug in this item's own instrument, logged

- **Gate 1's six-decimal requirement was met against today's published v12 headline, not against the
  record**, whose rows no longer exist. §1(b).
- **Gates 2 and 4 are substituted, not run.** Nothing is added, so neither the add-ablation nor the
  permutation null is defined; `gates.md` is explicit that an item which skips a step is `MEASURED`,
  never `GATED`. Nothing is landed either way — the arm is rejected.
- **An e-BH bug in this item's own script, found and fixed before any number was used.** The first
  pass tested only the lone-rejection bar `n/α` = 40 and reported "rejects nothing"; the `k*` rule is
  the whole point of e-BH — several hypotheses clearing together is cheaper than one alone — and the
  corrected implementation rejects both at the joint bar of 20. Recorded because it was live in the
  code that produced the first set of numbers.
- **The diagnostics were promoted to floored-and-bootstrapped mid-item, before the bootstrap ran.**
  The first design carried only the two declared hypotheses per seed, which would have left §8's AUC
  and slope gains quoted with no floor under them. They are floored and bootstrapped, and remain
  **diagnostics** — not declared hypotheses, and not counted in the e-value family, because promoting
  a diagnostic after seeing its value is what gate 6 exists to prevent.
- **The in-sample arm is a refit, not the shipped booster.** `stint_life_regressor_v12.bst` was never
  loaded or touched; the in-sample mode refits on 2018–2024 exactly as `train.py` does, so the
  optimism gap is measured under this item's own params rather than inheriting whatever last wrote the
  artefact — the provenance failure `10d` found in `10c`.

---

## 10c — Evaluation that fits the framing

**Objective.** Stop quoting AFT NLL on a mixture as though it were a headline.

**Method.** Cause-specific IPCW-Brier and time-dependent AUC, plus a calibration check
(D-calibration, or the 2025 A-calibration variant which handles censoring less conservatively).

**And state the dependent-censoring caveat rather than assuming it away.** SC arrival correlates
with race state, which correlates with tyre state, so censoring is **not** independent — under
which IPCW-weighted Brier and the concordance index are themselves biased. The literature's
recommended treatment is a copula-based sensitivity analysis: bracket it across a band of
dependence strengths rather than claiming to have fixed it. That is the same bracketing house
style `ceiling.py` already uses for its oracle.

**Acceptance.** Cause-specific metrics reported with the dependence band, never as a point.

**Definition of done.** The stint-life headline says which cause it is about.

### Pre-registration — the framings, the dependence grid and the decision rule (gates 6 and 7)

Written 2026-09-18, **before anything was fitted or scored on this substrate**, and before the
copula estimator existed in the tree.

**Why this item is being measured again.** Its 2026-09-10 verdict is doubly superseded and `10b`
§10 says so in writing: the AUC 0.844 / Brier 0.141 headline was in-sample (`10d`'s gate-1 finding)
*and* measured under the `10b` label, which `10b` has now rejected. Two of the three things the
method paragraph asks for were also never delivered — there was no per-cause comparison, and the
dependence band was stated but not quantified. This refresh exists to deliver both on the v12
substrate `08m`/`08n` rebuilt on 2026-09-16.

**What is evaluated, and what is not.** The shipped v12 configuration under the `standard` label —
`D5`'s ruling, since confirmed by `10b` on the arm's own declared metric — refit on the training
side of `cv_final_fold` (2018–2023) through `evaluate.py`'s own `_evaluation_split`/`_fit` and
scored on 2024. **There is no arm and no model change.** This item produces an instrument; it does
not propose to move anything.

**Three framings, each declared with the estimand it answers.** The whole content of this item is
that these are different questions and the difference is measurable.

| | rows | events | censored | estimand |
| :--- | :--- | :--- | :--- | :--- |
| **F1 stratum** (complete-case) | `stint_end_cause = green_pit` only | all | none | the **realised** green-pit ending, conditional on the ending having been green-pit |
| **F2 cause-specific** (competing risks) | the whole eval fold | endings of cause `c` | every other ending, including `race_end` and `retirement`, censored at its observed time | the **latent** cause-`c` limit |
| **F3 mixture** | the whole eval fold | whatever `standard` calls uncensored | the rest | nothing the app asks for — diagnostic, labelled as one |

F1 is what `10b`, `10d` and `10e` all scored and what the gauge means. F2 is the textbook
cause-specific construction and is **the only framing in which IPCW does any work**, so it is where
the dependent-censoring caveat bites and where the band has to be computed. F3's ruling from
2026-09-10 stands and is not re-litigated. F2 is run for every cause with **≥ 100 eval events**.

**Metrics.** IPCW-Brier (Graf), time-dependent AUC, the binned calibration slope / intercept /
5-bin table and mean log bias — the last four exactly as `10b`, `10d` and `10e` reported them, so
the numbers stay comparable — plus **D-calibration**, newly implemented: Haider et al.'s
censoring-aware Pearson goodness-of-fit on the transformed survival times, which is what `R3`
named. `survival.py::d_calibration` is a **binned calibration slope wearing that name** and it is
not the same test; the name is left alone for continuity and the real one lands beside it.

**The dependence grid, fixed now.** A Clayton copula between the latent cause time `T` and the
censoring time `C`, through the Rivest & Wells closed-form Archimedean copula-graphic estimator of
the censoring marginal (Zheng & Klein 1995). Kendall's **τ ∈ {−0.50, −0.25, 0, +0.25, +0.50}**,
`θ = 2τ/(1−τ)`. Both signs, because the direction of the dependence is not known and asserting one
would be the thing this item exists not to do. **The grid does not move after the data are seen.**

**The anchor, reported beside the grid and not allowed to move it.** Kendall's τ between the
model's predicted median life — a function of `X` alone — and the observed censoring time on the
censored rows. Under independent censoring it is 0. It says which part of the declared grid is
plausible; it does **not** select the band, and the band is reported across the full grid whatever
the anchor says.

**Gate 1 — three anchors, and this is the first item in group 10 that can meet the literal
requirement.** (a) today's published v12 `aft_nloglik` to every stored digit; (b) `10b` §4's A0
green-pit row, measured on **this same substrate on 2026-09-18**, to six decimals — the rows have
not moved since, so unlike `10b` this item has a published figure it can actually reproduce;
(c) the new estimator against the incumbent one: the copula-graphic estimator at τ = 0 must return
Kaplan–Meier, and the new vectorised IPCW-Brier must return `survival.py::ipcw_brier`, both to
machine precision, **before either is used**.

**Gate 2, substituted.** Nothing is added. Every framing scores rows drawn from one
`_evaluation_split`, through `evaluate.py`'s own `_fit`, and the framings are verified to partition
the same eval rows.

**Gate 3.** Five seeds **20260528–20260532**, varying XGBoost's `seed` so `subsample` and
`colsample_bytree` genuinely redraw. Floor = `2*sqrt(2)*sd` per metric per framing, cross-checked
against `attribution.py::refit_noise_floor` rather than reimplemented and trusted.

**The decision rule, declared before the numbers exist.** Every reported metric carries **three
widths**, which measure three different things and are allowed to disagree in public:

1. the **reseed floor** — refit noise, gate 3;
2. the **dependence band**, max − min across the declared τ grid — identification uncertainty;
3. the **200-draw race-level cluster bootstrap 95% interval** — sampling noise on 24 races.

A metric is reported **as a band** whenever the dependence band exceeds the reseed floor. If the
band sits inside the floor, the caveat is still stated and priced as immaterial *at this sample
size*, never silently dropped. **No cause-specific number is quoted as a point in any case** — the
acceptance clause is a reporting rule, not a threshold to pass.

**Gate 4 — inapplicable, stated rather than skipped.** The permutation null row-shuffles new
columns; there are none, and there is no arm whose capacity could be the nuisance. The reseed
spread is the only noise model this item has, and it is gate 3's.

**Gate 5.** Re-run: the cause label *defines* the framings here, so `stint_end_cause`,
`is_censored_stint`, `end_regime` and `end_cause_confidence` are asserted absent from
`FEATURE_COLUMNS` before anything is fitted.

**Gate 7 — declared, and the declaration is that there is nothing to declare.** This item states
**no comparative hypothesis** and therefore **adds nothing to the campaign e-value family.** There
is no arm to bank: it measures an instrument and reports widths. Recorded explicitly, because an
item that quietly declines to enter the family and then quotes a win is exactly what gate 7 exists
to prevent.

**The bootstrap.** 200 draws, seed **20260910**, races the resampling unit, 24 eval races — the
instrument `10d` §4 ruled authoritative. **Unpaired**, because there is one model: the interval is
on the level, not on a delta. The standing limit is restated before the numbers exist — 24 races
could not establish `10d`'s 0.17 slope move and will not put a tight interval on a slope here
either.

### Verdict — MEASURED 2026-09-18

> **THE CONFIGURATION THIS VERDICT SCORES WAS RETIRED THE NEXT DAY. Added 2026-09-19 by the
> build-order audit.** Everything below scores *"the shipped `v12` configuration"* — `v12` carrying
> `v11`'s stint-life hyperparameters. On **2026-09-19** `10e` landed `S1x`, and
> `ml/artefacts/evaluation_metrics.json` (`evaluated_at 2026-09-19T08:41:44Z`) now describes a
> different booster. `10e`'s own post-landing check, on the config that actually ships:
>
> | on the green-pit stratum | this verdict (`A0`, retired) | shipped since 2026-09-19 (`S1x`) |
> | :--- | ---: | ---: |
> | IPCW-Brier | **0.1904** | **0.1689** |
> | time-dependent AUC | **0.6896** | **0.7096** |
> | calibration slope | 0.6736 | 0.8754 |
> | mean log bias | **−0.2741** | **+0.0680** |
>
> Three specific consequences, so they are not rediscovered:
>
> 1. **The headline two numbers below (`0.1904` / `0.6896`) are no longer the gauge's accuracy.**
>    `reference/10c_evaluation_framework.md` line 20 repeats them and carries no banner.
> 2. **Product limitation (2) has inverted for the shipped model.** It reads *"it over-predicts in
>    the dangerous direction under the estimand the user reads (mean log bias −0.2741)"*. `S1x`
>    moves that to **+0.0680** — the gauge now slightly *under*-predicts. This section anticipated
>    the possibility (*"`10e`'s S1x flips the sign of the level error rather than removing it"*) but
>    states the limitation unconditionally, and `ml/model_card.yml`'s own limitations entry now says
>    the opposite: *"the gauge stops over-predicting remaining tyre life … and starts
>    under-predicting it slightly."*
> 3. **The framing arithmetic in the next paragraph moves.** *"The framing choice is worth 0.045
>    Brier … the largest model improvement this campaign has ever measured — `10e`'s S1x — was
>    0.023"* was computed against `A0`. Against the model that ships, the realised-vs-latent gap is
>    `0.1689 − 0.1452` on the old latent figure, and the latent leg, the dependence band
>    (`0.0362`), the F1/F2 tables and every D-calibration row below were all computed on the
>    retired booster and have not been recomputed.
>
> **The rulings are not retracted.** F1-not-F3 as the estimand, F1's `0.6896`-not-F2's `0.7882` as
> the discrimination reading, "independence is the optimistic end", the copula-graphic/KM
> equivalence checks and the `d_calibration_chisq` implementation are all structural and survive a
> hyperparameter change. **The levels have not been re-measured.** Re-running this item against the
> shipped config is cheap — `evaluate_10c --variant standard`, 64 s and 6 refits by this item's own
> accounting — and is the only way the band and the D-calibration tables become statements about
> the model in production.

**The stint-life headline is `0.1904` IPCW-Brier and `0.6896` time-dependent AUC on the
realised green-pit ending — and the same model, on the same rows, scores `0.1452` against the
latent green-pit limit, somewhere in `[0.1367, 0.1729]` depending on a dependence parameter
nobody can identify.** The framing choice is worth **0.045** Brier and the dependence band a
further **0.036**. The largest model improvement this campaign has ever measured — `10e`'s S1x —
was **0.023**. **Both of the choices this item exists to make explicit move the headline by more
than any model change group 10 produced**, which is the answer to why AFT NLL on a mixture was
never a headline and why nothing here may be quoted as a point.

Artefact: [`../eval/10c/`](../eval/10c/) — script, JSON, log. 64s, 6 refits, nothing written to
`ml/models/`, the warehouse or `evaluation_metrics.json`.

#### 1. Gate 1 — three anchors, and this time the literal requirement is met

**(a) Today's published v12 headline, to every stored digit.** `E._fit`/`_score` under `standard`
returns `aft_nloglik` **1.9913358778933028** against `evaluation_metrics.json`'s
**1.9913358778933028**.

**(b) `10b` §4's A0 row reproduces *exactly* — all eight figures, every digit.** `10b` had to
explain gate 1 away because `08m` moved the rows out from under the record. Eight days on the rows
have not moved, so this item has a published figure it can actually reproduce, and it does:

| | `10b` §4 published | reproduced here |
| :--- | ---: | ---: |
| green-pit NLL | 3.4376675618143007 | **identical** |
| green-pit IPCW-Brier | 0.1903917717687864 | **identical** |
| green-pit AUC | 0.6895774514309989 | **identical** |
| calibration slope / intercept | 0.6735936337052354 / 0.23187910000373496 | **identical** |
| mean log bias / margin sd | −0.27413700814322794 / 0.5818239268804684 | **identical** |

And so do all four of `10b`'s A0 **reseed floors**, independently recomputed: Brier 0.002082, AUC
0.006012, slope 0.025025, NLL 0.008325. The instrument is reproduced, not merely the point.

**(c) The new estimator against the incumbent one, before either was used.** The copula-graphic
estimator at τ = 0 must *be* Kaplan–Meier or the band has no centre. Over every distinct observed
time in the eval fold the maximum absolute gap is **2.4 × 10⁻¹⁵**, and `ipcw_brier_dependent` at
τ = 0 returns `survival.py::ipcw_brier` to **2.2 × 10⁻¹⁶**. The hard part is ties — laps are
integers — and the estimator handles them by ordering events ahead of censorings inside a tie
group, which is what makes the Rivest & Wells sum telescope to KM's own `(n_j − d_j)/n_j` factor.
Pinned in `ml/tests/test_survival.py`, not hoped for.

#### 2. Gate 2, substituted — three framings, one split, and they partition the same rows

Nothing is added, so the substituted requirement is the same split for everything in the
comparison, through `evaluate.py`'s own `_evaluation_split`/`_fit`. Train 2018–2023, eval 2024,
**19,973 laps over 24 races**, cause labels covering all 19,973 with no NULLs. **F1's rows are
exactly F2's green-pit event set**, verified index-for-index, and both derive their horizon grid
from the same uncensored times — `[2, 4, 5, 7, 9, 11, 14, 17, 22]` laps — so the band is measured
on the same grid as its own centre.

**Gate 5** re-run because the cause label *defines* the framings here: `stint_end_cause`,
`is_censored_stint`, `end_regime` and `end_cause_confidence` are all absent from `FEATURE_COLUMNS`.

#### 3. The headline, and it names its cause

**F1 — the realised green-pit ending, which is what `D5` says the gauge means.** 9,149 laps, 24
races, **zero censoring**, so IPCW does nothing and the dependence band is **exactly zero by
construction**. That is not the caveat being absent; it is the caveat having been paid for in a
different currency — F1 conditions on the outcome it is scoring.

| | point | reseed floor | bootstrap 95% (24 races) |
| :--- | ---: | ---: | :--- |
| IPCW-Brier | **0.1904** | 0.002082 | [0.1748, 0.2079] |
| time-dependent AUC | **0.6896** | 0.006012 | [0.6394, 0.7342] |
| calibration slope | 0.6736 | 0.025025 | [0.4310, 0.9106] |
| AFT NLL | 3.4377 | 0.008325 | — |

**Its IPCW AUC equals its unweighted AUC to 10⁻¹²**, which is the structural check that the
stratum really carries no censoring: every weight is exactly 1.

#### 4. The cause-specific framings, each with its band — the acceptance clause

**F2 — for cause `c`, endings of cause `c` are events and every other ending, `race_end` and
`retirement` included, is censored at its observed time.** This is the textbook competing-risks
construction and the only framing in which IPCW does any work, so it is the only one that can
carry a band. Clayton copula, Kendall's τ across the grid declared before the run:

| cause | events | censoring | τ = −0.50 | −0.25 | **0** | +0.25 | +0.50 | band width |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **green_pit** IPCW-Brier | 9,149 | 54.2% | 0.1367 | 0.1398 | **0.1452** | 0.1555 | 0.1729 | **0.0362** |
| **green_pit** Uno AUC | | | 0.7892 | 0.7888 | **0.7882** | 0.7871 | 0.7855 | 0.0037 |
| `sc_pit` IPCW-Brier | 884 | 95.6% | 0.1358 | 0.1381 | **0.1408** | 0.1436 | 0.1461 | 0.0104 |
| `sc_pit` Uno AUC | | | 0.7704 | 0.7703 | **0.7703** | 0.7703 | 0.7702 | 0.0002 |
| `vsc_pit` IPCW-Brier | 282 | 98.6% | 0.1686 | 0.1714 | **0.1739** | 0.1758 | 0.1771 | 0.0085 |
| `vsc_pit` Uno AUC | | | 0.8197 | 0.8196 | **0.8195** | 0.8194 | 0.8193 | 0.0003 |

`red` has **19** eval events against the declared floor of 100 and is not run — recorded rather
than quietly dropped. `race_end` and `retirement` are censored under `standard` and have no
cause-specific framing by construction.

**This closes the first of the three things `10c` said it did not deliver.** Under the `10b` label
green-pit was the only uncensored cause and the other five strata had no events; under `standard`
three causes carry one, and the per-cause comparison exists.

**But the comparison is weaker than it looks, and the reason is this item's own ruling turned on
itself.** F2 removes the mixture from the *event* definition and **not from the at-risk pool** —
green-pit cases are ranked against controls of every cause, and the causes differ in length by
construction. So F2's AUC inherits a diluted form of the same cause-membership artefact that got
F3 ruled out, which is why **F1's 0.6896, not F2's 0.7882, remains the discrimination headline.**
F2 is where the band lives; F1 is where the ranking is clean.

#### 5. The three widths — what the dependence assumption is actually worth

Declared before the numbers existed: refit noise, identification uncertainty, sampling noise.

| | point | **dependence band** | reseed floor | bootstrap 95% width | band ÷ floor | band ÷ boot |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **F2 green-pit IPCW-Brier** | 0.1452 | **0.0362** | 0.001839 | 0.0313 | **19.7×** | **1.16×** |
| F2 green-pit Uno AUC | 0.7882 | 0.0037 | 0.004633 | 0.0786 | 0.80× | 0.05× |
| F1 Brier / AUC / slope | — | **0** | 0.0021 / 0.0060 / 0.0250 | 0.0331 / 0.0948 / 0.4796 | 0 | 0 |

**The level is dominated by the dependence assumption and the ranking is not.** The Brier band is
**twenty times** the refit noise and wider than the sampling noise on 24 races — the instrument
this campaign otherwise treats as its binding constraint. The Uno AUC band sits *inside* its own
reseed floor, so discrimination is robust to the whole ±0.5 sweep. Per the declared rule the Brier
is reported as a band and the AUC's band is stated and priced as immaterial at this sample size,
not dropped.

**And the band is not itself refit noise wearing a band's clothes:** recomputed at all five seeds
it is 0.0362, 0.0361, 0.0360, 0.0356, 0.0356.

#### 6. The dependent-censoring caveat, measured rather than asserted

`R3` claimed SC arrival correlates with race state which correlates with tyre state. That is
observable, and it is true:

| censoring population | n | Kendall's τ (predicted life vs observed censoring time) |
| :--- | ---: | ---: |
| all censoring | 10,824 | **+0.1905** |
| **`sc_pit` / `vsc_pit` only** | 1,166 | **+0.2615** |
| administrative (`race_end` / `retirement`) | 9,639 | +0.2034 |

**Safety-car censoring is more associated with predicted tyre state than administrative censoring
is**, which is the caveat's own claim, in a number. Two things it is not: it is an *observable*
rank association, not the latent `T`–`C` dependence the copula parameterises — that is not
identifiable from this data at all, which is the entire reason for a band rather than a
correction — and it is contaminated by both quantities depending on the race clock, so it is an
upper read rather than an estimate.

**What it is good for is direction, and the direction matters.** It is positive and lands nearest
the **+0.25** node, and the Brier *rises* monotonically with τ. So **the independence assumption
is the optimistic end of the plausible range**: a green-pit Brier quoted at τ = 0 as 0.1452 is
plausibly 0.1555, and the honest reading of the band is asymmetric — `[0.1452, 0.1729]` is the
half of it the anchor points at. Declared in advance as a diagnostic that would not move the grid,
and it has not: the full grid is reported above.

#### 7. D-calibration proper — and the sign of the error depends on which cause you ask about

`survival.py::d_calibration` is a **binned calibration slope wearing that name**; `R3` asked for a
Pearson goodness-of-fit on the transformed survival times. That now exists as
`d_calibration_chisq` — Haider et al.'s test, with a censored row's unit mass spread over `[0, p_i]`
— beside the old one, which keeps its name so `10b`/`10d`/`10e`'s slopes stay comparable.

Bin counts as a ratio to expected, over 10 bins. A high bin means the observed ending came *early*
in the predicted survival curve, i.e. the model predicted more life than the tyre had:

| framing | χ²(9) | mean \|dev\|/exp | bin 1 → bin 10, as a ratio to expected |
| :--- | ---: | ---: | :--- |
| **F1** realised green-pit | 1066.6 | **0.252** | 0.22 · 0.89 · 0.90 · 0.87 · 0.92 · 0.95 · 1.09 · 1.30 · 1.33 · **1.55** |
| **F2** latent green-pit (τ = 0) | 246.9 | 0.095 | **1.16** · 1.21 · 1.10 · 1.00 · 0.96 · 0.91 · 0.91 · 0.96 · 0.91 · 0.87 |
| F3 mixture *(diagnostic)* | 89.3 | 0.051 | 1.01 · 1.14 · 1.11 · 1.00 · 0.98 · 0.93 · 0.94 · 0.99 · 0.96 · 0.96 |

**The tilt reverses sign between the two framings.** Against the realised ending the model
over-predicts life — 1.55× too many stints in the bin meaning "finished far earlier than
predicted", and barely a fifth of the stints that should have outlived their prediction. Against
the latent limit it **under**-predicts, gently. Both are the same model and the same predictions.
**That is the definition of done demonstrated in a number rather than argued: a stint-life headline
that does not name its cause has not stated which sign its error has.**

**And the mixture is the flattest of the three, which is the original claim in a new metric.** The
two errors point opposite ways and partly cancel when the causes are pooled, so F3 looks best
calibrated while answering a question nobody asked. `10c`'s 2026-09-10 ruling against the `overall`
row stands, now with a mechanism under it.

Read with the same caveat as everything else in F2: the censored-mass spreading assumes
independence, and a τ-aware D-calibration is **not** implemented — §11.

#### 8. What the framing choice is worth, against what any model change bought

Same model, same rows, same per-row predictions, two estimands:

| | IPCW-Brier |
| :--- | ---: |
| F1 — realised green-pit ending (`D5`'s estimand) | 0.1904 |
| F2 — latent green-pit limit, τ = 0 | 0.1452 |
| **the framing gap** | **+0.0451** (across the band: +0.0175 to +0.0537) |
| *for scale:* `10e` S1x, the best model improvement this campaign has measured | +0.0229 |

Neither framing is wrong and this item does not rank them — they are different questions and are
not on a common scale, F2's at-risk pool being both larger and easier. The gap is the **size of the
choice**, and it is twice the best result the campaign has produced by changing the model.

#### 9. Answering the definition of done

**The stint-life headline, saying which cause it is about:**

> **On the tyre-limit set — stints that ended in a green-flag pit stop — the shipped v12
> configuration predicts the *realised* stint ending with IPCW-Brier 0.1904 and time-dependent AUC
> 0.6896, 95% [0.639, 0.734] over 24 eval races. Read instead as the *latent* tyre limit, the same
> model scores 0.1452 Brier, bracketed at [0.1367, 0.1729] across Kendall's τ ∈ [−0.5, +0.5] of
> dependence between safety-car arrival and tyre state, with the observable evidence pointing at
> the upper half of that bracket.**

**The product limitation, stated:**

1. **The gauge answers one cause and does not say so.** It shows the realised ending under
   `standard`, and the number above is conditioned on the stint having ended in a green-flag stop.
   **28.1% of real stints do not** (`10a`: 1,416 of 5,037; 11.5% of uncensored *laps* in this eval
   fold). For those, the gauge was never answering the question the user was asking.
2. **It over-predicts, in the dangerous direction, under the estimand the user reads.** §7's F1
   tilt and the mean log bias of −0.2741 agree. `10d` and `10e` both measured this and neither
   closed it; `10e`'s S1x flips the sign of the level error rather than removing it, which is
   `D4`'s open question.
3. **It cannot tell the user which cause is coming.** The app has no safety-car term, so it cannot
   convert the tyre-limit answer into the realised one for the 28.1%. `int_sc_hazard_history` is
   exactly that term and currently feeds nothing; `02d` rebuilds it and `07a` is building the
   instrument the anchor in §6 stands in for.
4. **The dependence caveat is not fixable at this data.** It is bracketed, and the bracket is wider
   than the sampling noise this campaign treats as binding. Any future cause-specific claim on this
   substrate inherits the band.

#### 10. What this settles, and what it does not

- **`10c`'s three admitted gaps: two closed, one narrowed.** The per-cause comparison exists (§4).
  The dependence band is quantified (§4, §5) and the withdrawn "1.2× dependence strength" is
  replaced by a declared grid plus an observable anchor. The third — that quantifying the true
  dependence needs an instrument for SC arrival — is **still open**, and §6 says precisely why: the
  anchor is observable association, not latent dependence.
- **The evaluation framework that gates `10d` and `10e` is now what those items assumed it was.**
  Both selected on green-pit IPCW-Brier; this item shows that metric's value depends on a framing
  choice worth 0.045 and an unidentifiable parameter worth 0.036. Neither item's *comparison* is
  invalidated — both compared arms under one fixed framing, where the band is common-mode and
  cancels — but neither item's *level* should be quoted without the framing named.
- **`10b`'s live trap is closed.** `ml/src/evaluate_10c.py` defaulted to `--variant 10b`, so anyone
  re-running it with defaults measured the rejected label. `10b` §10 left that to whoever landed
  this ruling; the default is now `standard`, in the CLI and in both function signatures, with the
  history in the module docstring.
- **Not delivered, and not claimed:** a cause-specific *model*. Every number here scores the
  marginal `standard` fit against cause-specific estimands. A model that actually targets the
  cause-specific hazard — `R3`'s option 1 — has never been built, and `10b` established only that
  recoding the label is not the way to it.

#### 11. Deviations, and the limits of this item's own instruments, logged

- **Gate 7 is declared empty.** No comparative hypothesis, so nothing enters the campaign e-value
  family. Stated rather than skipped, because an item that quietly declines to enter the family and
  then quotes a win is what gate 7 exists to prevent. Gate 4 is inapplicable — no new columns, no
  arm — and the reseed spread is the only noise model, which is gate 3's.
- **A-calibration is not implemented.** The method paragraph offers it as an alternative to
  D-calibration; its 2025 definition could not be verified from inside this run, and implementing a
  calibration test from a half-remembered description is worse than not implementing it.
  D-calibration is the one `R3` describes in enough detail to build, and it is the one that landed.
- **The τ-aware D-calibration does not exist.** F2's censored rows spread their mass over `[0, p_i]`
  under independence, so §7's F2 row is a τ = 0 reading and carries no band. The Brier and the AUC
  carry theirs; the calibration test does not, and that is a hole, not a choice.
- **The cause-specific calibration slope is unassessable for the rare causes.** At 95.6% and 98.6%
  censoring the KM curve inside each risk bin barely falls, so `sc_pit` returns 0.115 and `vsc_pit`
  0.044 — those are the estimator failing, not the model. Reported in the JSON, not quoted here.
  F2 green-pit's 0.892 is estimable.
- **The level diagnostics in F2 do not vary by cause.** Mean log bias and margin sd are computed
  over the whole fold, where the cause enters only through the event definition, so all three F2
  rows return −0.5374. Present in the JSON; it would be a mistake to read them per cause.
- **The Clayton family is one assumption inside another.** Bracketing across τ within one
  Archimedean family is not bracketing across copula families. Frank and Gumbel would give a
  different band of the same order; nothing here tests that, and "the band" means "the Clayton
  band".
- **`survival.py` gained three functions and 13 tests** (36 total in `test_survival.py`, all
  passing): `copula_graphic_survival` + `step_eval`, `ipcw_brier_dependent`,
  `time_dependent_auc_ipcw` and `d_calibration_chisq`. The existing `d_calibration`,
  `ipcw_brier` and `time_dependent_auc` are **untouched**, so every figure `10b`, `10d` and `10e`
  published is still produced by the code that produced it.

### Verdict — 2026-09-10 — **SUPERSEDED 2026-09-18**, see the refreshed verdict above

Full results and the per-horizon tables: [`../reference/10c_evaluation_framework.md`](../reference/10c_evaluation_framework.md).

**The headline, and it names its cause:** tyre-limit survival on green-pit endings is predicted
with **time-dependent AUC 0.844** and **IPCW-Brier 0.141** (9,270 eval-fold laps, 2024).

**The finding worth acting on is the calibration, not the discrimination.** Green-pit calibration
slope is **1.23** — observed risk exceeds predicted in 4 of 5 risk bins and the gap widens as risk
rises (at the top bin, predicted 0.78 against observed 0.95). The model **over-predicts stint
life, and is worst on the stints it already flags as fragile**. That is a live defect in the
quantity the app's gauge shows, and it is a better lead than 10b's -0.028 NLL.

**Three things this item did not deliver, stated plainly:**

1. **No per-cause comparison.** Under the 10b variant green-pit is the only uncensored cause, so
   the other five strata have no events to score and their metrics are undefined. 10c produced one
   clean stratum and five empty ones. Comparing survival *across* causes needs a cause-specific
   hazard treating each cause as its own event in turn — which 10b did not train.
2. **The dependence band is not quantified.** Only stated. An earlier draft's "dependence strength
   1.2×" is **withdrawn**: cause determines censoring status under 10b, so cause-specific censoring
   rates are 0/1 by construction and their spread measures the definition, not the dependence.
   Quantifying it needs an instrument for SC arrival — which is what `07a` is building.
3. **The `overall` row is not a headline and must not be quoted** (Brier 0.093, AUC 0.924). It
   scores green-pit events against an at-risk pool that is 54% non-green, and the causes differ in
   length by construction (`race_end` 26.4 laps mean, `green_pit` 20.4, `red` 5.3). A model scores
   well there by separating *cause membership* — the same mixture artefact this item exists to
   remove, in a new metric. It is kept as a diagnostic and labelled as one in the artefact.

**Metric repairs were needed first.** Three of the metrics did not measure what they claimed;
`d_calibration` was a tautology returning 0.5 for every row, `ipcw_brier` ignored the horizon in
its weights, and `time_dependent_auc` counted ties as discordant. All fixed in `ml/src/survival.py`
and the item re-run before any number was used downstream. Superseded figures: green-pit AUC 0.829,
overall Brier 0.116, overall AUC 0.916, and the unsupported "calibration slope ≈1 (unbiased)".
Detail in the reference doc's § Metric corrections.

---

---

## 10d — Fix the stint-life calibration defect

**Objective.** The model over-predicts how long tyres last. Fix that, in the model.

**Depends on** [`10c`](#10c--evaluation-that-fits-the-framing) for the finding, and
[`08k`](08-foundations-repair.md#08k--rebuild-the-model-artefacts-against-the-post-08j-32-feature-contract)
because this item retrains and re-exports `stint_life_regressor` and that cannot be validated
against a red ONNX-parity and manifest-contract suite.

**The finding.** Green-pit calibration slope **1.232**. Observed risk exceeds predicted in 4 of 5
risk bins and the gap widens as risk rises:

| model says stint is this likely to be over | it actually is, this often |
| ---: | ---: |
| 0.110 | 0.169 |
| 0.282 | 0.237 |
| 0.442 | 0.490 |
| 0.603 | 0.737 |
| **0.781** | **0.946** |

The bottom row is the problem. On stints the model has already flagged as fragile it is wrong in
the dangerous direction — it reports life left in a tyre that is essentially finished. This is the
quantity the app's gauge shows, so the defect is user-visible.

**It is the model's, not the sample's.** This had to be settled first, because green-pit is a
*filtered* stratum — a stint only becomes green-pit if no safety car diverted it — and
recalibrating a model to match a filtered sample would bake that filter's bias in permanently.
Races with **zero SC/VSC endings** had no diversion, so green-pit within them is unfiltered. The
slope does not move:

| stratum | n (laps) | slope | AUC |
| :--- | ---: | ---: | ---: |
| Zero-SC races (no diversion possible) | 6,822 | **1.224** | 0.845 |
| SC races (diversion occurred) | 2,448 | 1.267 | 0.844 |
| All races | 9,270 | 1.232 | 0.844 |

Race-level cluster bootstrap on the zero-SC stratum (200 draws, per `05c`'s gate-3 substitute):
mean 1.222, sd 0.0714, 95% interval **[1.098, 1.363]**, 0 of 200 draws below 1.0. That stratum
holds only **14 races** and cluster bootstraps on so few clusters run anti-conservative, so treat
the interval as indicative — the finding rests on the point estimate being unmoved across a split
that would have to move it if selection were the cause.

**Method — the constraint, not the recipe.** Fix the fit. Do **not** post-hoc recalibrate against
the green-pit evaluation sample, for the reason above. Candidate directions, none of them ruled on
yet: the AFT scale parameter, the label construction 10b introduced, or a distributional
assumption that does not fit a target with skewness −0.829 and excess kurtosis 5.218 (`R2`).
Re-measure with `ml/src/evaluate_10c.py`, whose metrics are now under regression test.

**Acceptance.** Gates 1–7 per [`../foundations/gates.md`](../foundations/gates.md). The 1.23 is a
**measurement** and has not been gated; the fix that follows from it must be. Report the slope with
its bootstrap interval, not as a point.

**Definition of done.** A written verdict on whether the slope moves toward 1.0 without costing
discrimination (AUC 0.844 is the incumbent), and either a landed fix or a recorded reason the
defect is not addressable at this model class.

**Note for [`02b`](02-feature-expansion.md).** Its pre-flight requires 5-reseed noise floors for
`stint_life_regressor`. Those must be measured **after** this lands, or they are measured against a
model that is about to change.

### Pre-registration — arms and e-value (gates 6 and 7)

Written 2026-09-10, before any arm was scored on the 2024 eval fold.

**The instrument, first (gate 1).** `evaluate_10c.py` as written loads the *shipped*
`stint_life_regressor_v11.bst`, which `train.py` refits on **every** training season — 2018–2024 —
and scores it on the `cv_final_fold` eval rows, which are 2024. The eval fold is inside that
booster's training set, so every 10c number is in-sample. The honest instrument refits on the
training side of the split only (`EV._evaluation_split` → `EV._fit` on `split.X_tr`, exactly as
`evaluate.py::evaluate_target` already does) and scores 2024 out of sample. Both are measured below;
the honest one is the baseline every arm is compared against.

**Headline for this item.** Green-pit calibration slope on the 2024 eval fold, out of sample, with a
200-draw race-level cluster bootstrap interval (`05c`'s gate-3 substitute). Secondary: green-pit
time-dependent AUC and IPCW-Brier. "Toward 1.0" is scored as a decrease in `|slope − 1|`.

**Arms.** Every arm is selected on the **training side only** — expanding season folds inside
2018–2023. Nothing is selected on the 2024 rows; that is the constraint the method section sets, and
it is what keeps this a fit change rather than a post-hoc recalibration against the eval sample.

| arm | what moves | selection signal (train-side inner CV) |
| :--- | :--- | :--- |
| **A0** | nothing — the incumbent, refit honestly | — (baseline) |
| **A1** | `aft_loss_distribution_scale` ∈ [0.30, 1.40] | inner-fold green-pit \|slope − 1\|, ties broken on inner-fold AFT NLL |
| **A2** | `aft_loss_distribution` ∈ {normal, logistic, extreme} | XGBoost's own `aft-nloglik` on the inner folds, each distribution at its own A1 scale |
| **A3** | label construction ∈ {standard, 10b} | inner-fold green-pit \|slope − 1\| |
| **A4** | capacity: `max_depth` ∈ {3,4,5,6,8} × `n_estimators` ∈ {200,400} | inner-fold green-pit \|slope − 1\| |

**Gate 4 is inapplicable in its literal form and the substitute is stated rather than skipped.** The
permutation null row-shuffles *new columns*. No arm here adds a column: A1, A2 and A4 change how the
same feature matrix is fitted, and A3 changes only the label bounds. Capacity is therefore identical
between every arm and A0 — the nuisance parameter gate 4 exists to remove is exactly zero by
construction, not by assumption. The substitute null is the **reseed null**: arm and incumbent refit
at the same five seeds, under H₀ ("the change carries no information about calibration") the paired
delta is mean-zero.

**Gate 3 floor.** Five seeds, 20260528–20260532, varying XGBoost's `seed` (which drives `subsample`
and `colsample_bytree`, so the refits genuinely differ — 10b's zero-variance reseed table came from
not varying it). Floor = `2*sqrt(2)*sd` of the green-pit calibration slope across those five,
measured on the incumbent family, per `attribution.py::refit_noise_floor`.

**E-value — Construction A, declared now.** From
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) §3.

- **Null.** H₀: the arm's change carries no information about green-pit calibration, so the paired
  reseed delta below is mean-zero.
- **Delta, oriented so positive is improvement.**
  `delta = |slope(A0) − 1| − |slope(arm) − 1|`, both measured on the 2024 green-pit stratum.
- **Scale.** `s = c * sqrt(2) * sd` with **`c = 1.5`**, `sd` the gate-3 reseed sd above. `c = 1.5`
  and not 1.0 because `sd` is a five-seed plug-in and §3's stated hole applies: validity is
  **conditional on σ ≤ s** and that condition is stated here rather than hidden.
- **Betting fraction.** `lambda = 2 / c = 1.333`, growth-rate optimal against `delta* = F`.
- **Result.** `E = exp((2 / c^2) * (z − 1))` with `z = delta / (sqrt(2) * sd)`, i.e.
  `E = exp(0.8889 * (z − 1))`.
- **Family.** Four declared arms (A1–A4). All four are counted in the campaign family and reported
  with their `E`, `E < 1` included. Campaign-level decisions run e-BH per gate 7.

**Seeds.** 20260528, 20260529, 20260530, 20260531, 20260532. Bootstrap seed 20260910, 200 draws,
races as the resampling unit.

### Pre-registration addendum — the 2026-09-18 re-run

Written 2026-09-18, after gate 1's anchors were checked and **before any arm was fitted**. Four
things moved under the 2026-09-10 verdict; this records what changes and what carries forward, so
the re-run is a re-run and not a fresh search dressed as one.

**1. The substrate moved, and six-decimal reproduction of this item's own 2026-09-10 figures is
impossible.** `08m` repaired the compound wear curve and `08n` shipped v12 on 2026-09-16. The
`cv_final_fold` eval fold is **19,973 laps / 9,149 green-pit** today against the **20,272 / 9,270**
every figure in the verdict below was measured on. Gate 1 is anchored on what *can* be reproduced,
exactly as `10b` and `10c` were re-anchored: today's published v12 headline, and `10b` §4's A0 row.
Both were checked before this paragraph was written and both reproduce to every stored digit —
headline `1.9913358778933028`; green-pit NLL `3.4376675618143007`, Brier `0.1903917717687864`, AUC
`0.6895774514309989`, slope `0.6735936337052354`, intercept `0.23187910000373496`, mean log bias
`−0.27413700814322794`, margin sd `0.5818239268804684`.

**2. A0 changes label, which flips A3's direction.** The verdict below made A0 the **`10b`** label.
`D5` has since settled on the realised stint ending and `10b`'s 2026-09-18 ruling rejected its own
label, so **A0 is now `standard`** — the shipped v12 variant. A3 therefore tests `10b` *against* a
`standard` incumbent rather than the reverse, and its pre-registered expectation, stated now, is
that it **selects the incumbent**. An arm whose expected answer is "no change" is still run and
still counted in the family.

**3. A4x — `max_depth` 2 — is promoted from post-hoc extension to declared arm.** It was an
undeclared extension in the run below, added after the monotone depth trend was visible. Carrying a
post-hoc finding forward by *declaring it in advance on fresh rows* is the only honest way to use
it, and this is that. The old `C2` cross (`standard` + depth 2) is **not** a separate arm any more:
under A0 = `standard` it *is* A4x.

**The family is therefore five declared arms — A1, A2, A3, A4, A4x** — all five counted, all five
reported with their `E`, `E < 1` included.

**4. Gate 7 gains a second construction, declared now rather than chosen after.** Construction A is
reported exactly as declared above, because that is what was pre-registered and gate 7 does not
allow quietly swapping an instrument that returned an inconvenient number. But §4 of the verdict
below established *why* it is wrong here — its scale is refit noise where the estimand's uncertainty
is sampling noise 16–30× larger — so **Construction B (the paired safe-t of
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) §4, `g = 1.0`, `n = 5`
paired reseed deltas)** is run beside it, on the same deltas, and validated against 100k null draws
before use exactly as `10b` did. Both are reported. Neither is dropped.

**The declared pass criterion, stated as a bar this run expects to miss.** An arm *fixes the
calibration defect* if all three hold: (i) `|slope − 1|` decreases against A0; (ii) the **paired**
race-cluster bootstrap returns `P(improves) ≥ 0.95`; (iii) the AUC cost is no larger than the AUC
reseed floor. Leg (ii) is the one this run expects to fail — the verdict below and `10e` both hit
the same 24-race ceiling at P = 0.945 and P = 0.930 — and it is written down in advance so that
missing it cannot be reinterpreted afterwards as a pass.

**Secondary, declared, and not a hypothesis.** §6 below found that every arm fixed the *dispersion*
of the risk score and left the *level* where it was. Mean log bias and the calibration intercept are
carried for every arm to test whether that survives the substrate change. They are **diagnostics**:
floored and bootstrapped so no gain is quoted bare, and **not** counted in the e-value family.

Everything not listed here carries forward unchanged — the arms and their selection signals, the
train-side-only selection constraint, `|slope − 1|` as the scoring rule, the five seeds, and
bootstrap seed 20260910 over 200 draws with races as the unit.

### Verdict — MEASURED 2026-09-18

**No arm fixes the calibration defect at 95% confidence.** On the v12 substrate with the honest split, the incumbent slope is **0.674** [0.431, 0.911]. Five declared arms were tested: A1 (AFT scale 1.3, delta +0.079 slope, P = 0.825), A2 (normal dist, delta −0.036, P = 0.02), A3 (standard label, delta +0.016, P = 0.815), A4 (depth 3, delta +0.190, P = 0.92), A4x (depth 2, delta +0.328, P = 0.855). All five fail leg (ii) of the declared pass criterion: paired race-cluster bootstrap P(improves) ≥ 0.95. The pre-registration flagged this bar as "the one this run expects to miss", matching 10c's finding that 24 eval races inherits a 0.945 ceiling from sampling noise.

**Construction A e-values (refit-noise scale) report large improvements; Construction B (paired safe-t on reseed deltas) reports modest improvements; the paired race-cluster bootstrap disagrees with both.** For A4x: Construction A E = 5.4 × 10⁹; Construction B E = 35.7; paired bootstrap P = 0.855, interval straddling 1.0. Gate 7's rule stands: where the three disagree, the bootstrap is authoritative because it measures what actually governs the estimand — sampling noise on 24 races, not refit noise on 5 seeds.

**A4x clears on closeness (depth 2, slope 0.993 ≈ 1.0) but not on resolution.** The depth finding from 2026-09-10 reproduces: inner-fold slope improves monotonically as depth falls. On 2024 out-of-sample, A4x reaches slope 0.993 [0.589, 1.410], the closest to 1.0 of any arm. The calibration intercept also improves (A0 +0.232 → A4x +0.162), the magnitude of level bias halves. But the 95% interval straddles 1.0 and the two-tailed bootstrap P(improves on slope) is 0.855, below 0.95. A4x is not landed here for the same reason the 2026-09-10 verdict declined it: "overwriting the shipped booster on a 0.945-probability result is exactly the kind of move `04a`'s multiplicity finding exists to discourage."

**What carries forward.** The gates ran clean (1–3, 5 pass; 4 inapplicable; 6–7 declared and reported). The honest instrument refits on 2018–2023 and scores 2024, invulnerable to in-sample artefacts. The substrate-drift addendum (§1.c) showed that 10d's 2026-09-10 finding — in-sample slope crosses 1.0 honest — reproduces to every digit on v12, eight days and a warehouse rebuild later. Both label constructions are tested (A3 on `10b`, selected `10b` on inner CV but A0=`standard` passes it on eval). All artefacts in [`../eval/10d/`](../eval/10d/); nothing written to `ml/models/`, the warehouse or `evaluation_metrics.json`.

### Verdict — MEASURED 2026-09-10

**The defect this item was created to fix does not exist as described. The 1.232 is an in-sample
number, and out of sample the slope is 0.666 — on the other side of 1.0.** The instrument was
scoring a booster on rows that were inside its own training set. Gate 1 caught it, which is what
gate 1 is for.

#### 1. Gate 1 — the instrument, and what it was actually measuring

`evaluate_10c.py` loaded `ml/models/stint_life_regressor_v11.bst` and scored it on the
`cv_final_fold` eval rows. `train.py` refits the shipped booster on **every** training season and
`training_seasons` is 2018–2024; the eval fold **is** 2024. Every 10c number was in-sample.

Reproduced exactly, which is how the provenance was settled. Refitting on all seasons under the 10b
label and scoring the 2024 rows returns green-pit **Brier 0.141216, AUC 0.844167, slope 1.231641**
against 10c's published 0.1412159702194419 / 0.8441673881692147 / 1.2316409494909957 — six decimal
places, and the 5-bin table lands on 10c's `0.110 0.282 0.442 0.603 0.781` → `0.169 0.237 0.490
0.737 0.946` row for row.

Two further facts fell out of that check:

- **`evaluate_10c.py` no longer scored the model 10c reported.** The `.bst` was rewritten by a
  `standard`-variant retrain (training log `stint_life_regressor_v11_20260910T092333.json`,
  `censoring_variant: "standard"`) *after* 10c ran, so re-running the script today returned
  0.834378 / 1.234564 — the *standard*-variant in-sample refit, to six decimals. 10c's own
  description of the artefact as "the 10b-trained model" was already false by the time it was read.
- **The hyperparameters were never fitted for this problem.** `tune.py` calls
  `F.load_features(target=target)` with the default `censoring_variant="standard"`, and folds over
  `bundle.training_seasons` = 2018–2024, so `max_depth: 8` and `aft_loss_distribution_scale: 0.8`
  were selected against the *other* label construction, on the mixture NLL 10c said not to use as a
  headline, with 2024 in the validation set.

The honest instrument refits on the training side only (`EV._evaluation_split` → `EV._fit` on
`split.X_tr`, the path `evaluate.py::evaluate_target` already uses) and scores 2024 out of sample.
The optimism it was hiding, on identical eval rows, is not a rounding error:

| green-pit | honest | in-sample | optimism |
| :--- | ---: | ---: | ---: |
| time-dependent AUC | **0.6914** | 0.8344 | +0.1429 |
| IPCW-Brier | **0.2059** | 0.1407 | −0.0652 |
| calibration slope | **0.6664** | 1.2346 | +0.5682 |

The slope does not merely shrink across that gap — it **crosses 1.0**, so the in-sample run reported
the miscalibration with the wrong sign. Every downstream statement built on it inherits that.
**`AUC 0.844` is not the incumbent. `0.691` is.**

**10c's selection check has to be re-run, and it survives.** The zero-SC / SC split was the evidence
that the miscalibration was the model's and not the sample's, and it was measured in-sample like
everything else. Out of sample it still holds, in the new direction: zero-SC races slope 0.6555
(n=7,588, 16 races), SC races 0.7823 (n=1,682, 8 races), all races 0.6664. Both strata sit well
below 1.0. Selection does not explain the defect — that conclusion of 10c's is unaffected, only its
sign is.

#### 2. The honest baseline, with its interval

Refit 2018–2023, scored on 2024, 10b labels, tuned v11 params. Race-level cluster bootstrap, 200
draws, 24 eval races:

> **Green-pit calibration slope 0.666, 95% [0.463, 0.906]** — 99.5% of draws below 1.0.
> Time-dependent AUC 0.691. IPCW-Brier 0.206.

Gate-3 reseed floor, five seeds with XGBoost's `seed` genuinely varied (10b's zero-variance reseed
table came from not varying it, so `subsample` and `colsample_bytree` drew identically every time):
slope sd **0.006208**, floor `2*sqrt(2)*sd` = **0.017559**; AUC sd 0.001256, floor 0.003554.

#### 3. The arms

Every arm selected on the training side only. `delta = |slope(A0) − 1| − |slope(arm) − 1|`.

| arm | slope | boot 95% | delta | × floor | AUC | ΔAUC | × AUC floor | Brier |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **A0** incumbent | 0.6664 | [0.463, 0.906] | — | — | 0.6914 | — | — | 0.2059 |
| **A1** scale 0.90 | 0.6883 | [0.465, 0.947] | +0.0219 | 1.25× | 0.6843 | −0.0071 | 1.99× | 0.2084 |
| **A2** normal | *selected the incumbent* | | 0 | 0 | | | | |
| **A3** standard labels | 0.7000 | [0.444, 0.933] | +0.0336 | 1.91× | 0.6935 | +0.0021 | 0.60× | **0.1903** |
| **A4** depth 3 / 200 | 0.8791 | [0.584, 1.220] | +0.2127 | 12.11× | 0.6871 | −0.0043 | 1.21× | 0.2100 |
| A4x depth 2 / 200 † | **1.0735** | [0.704, 1.446] | +0.2601 | 14.81× | 0.6826 | −0.0088 | 2.47× | 0.2150 |
| C2 standard + depth 2 † | 1.0476 | [0.669, 1.448] | +0.2860 | 16.29× | 0.6739 | −0.0175 | 4.94× | 0.1993 |

† **Undeclared.** The pre-registered A4 grid was `max_depth ∈ {3,4,5,6,8}`; depth 2 and the
cross with the `standard` label are extensions added after seeing the monotone trend, logged here
rather than folded into the declared arm. They are counted in the family and reported, but the
declared A4 winner is depth 3.

**A1 — the AFT scale is not the lever, and this is the clearest negative of the four.** Across
0.30→1.40, a 4.6× range, the train-side inner-fold green-pit slope moves only 0.537→0.622 and never
reaches 0.63. On 2024 the best scale buys +0.022 of slope for −0.007 of AUC (2.0× the AUC floor) —
it pays more in discrimination than it returns in calibration. The inner-CV NLL optimum under the
10b label is 0.90, not the shipped 0.80, so the scale *is* mis-set; it just does not matter here.

**A2 — the distributional assumption is not the lever either, and R2's skew statistic was measured
on the wrong quantity.** Screened on XGBoost's own `aft-nloglik` over the inner folds, each
distribution at its own swept scale: **normal 1.8364** (scale 0.90) beats extreme 1.8650 (0.90) and
logistic 1.8876 (0.70). The arm selects the incumbent, so nothing needs plumbing through
`laps_from_margin`, the ONNX export and `app/src/ml/survival.ts` — which is worth knowing, because
`extreme` would have needed all three (its standardised median is `log(log 2) = −0.3665`, not 0, so
`exp(margin)` stops being the median). The reason the direction fails: skewness −0.829 and excess
kurtosis 5.218 are properties of the **target in laps**, and the AFT does not assume that quantity is
normal — it assumes the *log-scale residual* is. Measured, that residual has skew **−0.443** and
excess kurtosis **−0.063**. It is already close to normal on the scale the model actually uses.

**A3 — the label construction is worth revisiting, but not for the slope.** `standard` and `10b` are
indistinguishable on slope (0.700 vs 0.666, delta 1.9× floor, paired interval straddling zero), but
`standard` is **better on green-pit Brier, 0.190 vs 0.206**, better on the level bias (mean log
residual −0.285 vs −0.434) and costs no AUC. 10b's label change, whose original +0.179 NLL was
already withdrawn as a 92.6% scoring artefact and restated as −0.028, makes green-pit *worse* out of
sample on the metric 10c chose as its headline. That is a finding about 10b, not about 10d, and it
is recorded here for whoever rules on 10b.

**A4 — capacity is the lever, and the relationship is monotone.** Train-side inner CV, 10b labels,
scale 0.90:

| max_depth | 2 | 3 | 4 | 5 | 6 | 8 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| inner-fold slope | 0.794 | 0.708 | 0.680 | 0.669 | 0.656 | 0.622 |
| inner-fold NLL | 1.8171 | 1.8090 | 1.8078 | 1.8130 | 1.8188 | 1.8364 |

The slope rises as depth falls, and inner-CV NLL **also** improves — the shipped `max_depth: 8` is
worse on the training folds' own headline metric, which is what you expect from hyperparameters
selected under a different label construction. The mechanism is visible in the fit: the standard
deviation of the margin over the green-pit eval rows falls 0.642 → 0.509 → 0.418 as depth goes
8 → 3 → 2. The incumbent's risk score was over-dispersed relative to its real skill, which is
exactly what a slope below 1.0 means.

#### 4. Gate 7 — the e-values, and why they should not be believed at face value

Construction A as declared, `c = 1.5`, `lambda = 4/3`, `sd = 0.006208`, `E = exp(0.8889*(z−1))`:

| arm | delta | z | E |
| :--- | ---: | ---: | ---: |
| A1 scale 0.90 | +0.0219 | 2.50 | 3.78 |
| A2 normal | 0 | 0.00 | **0.41** |
| A3 standard | +0.0336 | 3.83 | 12.4 |
| A4 depth 3 | +0.2127 | 24.2 | 9.3 × 10⁸ |
| A4x depth 2 † | +0.2601 | 29.6 | 1.1 × 10¹¹ |
| C2 standard + depth 2 † | +0.2860 | 32.6 | 1.5 × 10¹² |

**Those last three are not evidence at that strength and the construction is what is wrong, not the
arithmetic.** The pre-registered scale is the reseed sd, which measures **refit** noise — how much
the slope moves when only XGBoost's seed changes. The uncertainty that actually governs a slope
estimated from 24 races is **sampling** noise, and the cluster bootstrap puts that at sd ≈ 0.10–0.19,
**16–30× larger**. Feeding a scale 25× too small into `exp()` is how you get 10¹¹. Reported as
declared, per gate 7, and then read correctly: on the instrument that matches the estimand, the
paired race-cluster bootstrap — both arms scored on the *same* resampled races, so the shared
race-draw noise cancels — the deltas straddle zero:

| arm | paired delta | 95% | P(improves) |
| :--- | ---: | :--- | ---: |
| A1 scale 0.90 | +0.0211 | [−0.0101, +0.0549] | 0.870 |
| A3 standard | +0.0212 | [−0.0721, +0.1334] | 0.630 |
| A4 depth 3 | +0.1726 | [−0.1389, +0.3103] | **0.945** |
| A4x depth 2 † | +0.1695 | [−0.3081, +0.4029] | 0.855 |

`gates.md` already says the floor and the e-value are two instruments and must be allowed to
disagree in public. Here a third disagrees with both, and it is the one to believe: **the capacity
fix clears the reseed floor by 12×, returns E ≈ 10⁹, and still cannot be established at 95% on 24
races.** The floor is not wrong about refit noise; it is being asked a question it does not answer.

#### 5. Gate 4 — inapplicable, and stated rather than skipped

No arm adds a column. A1, A2 and A4 change how the same 32-feature matrix is fitted; A3 moves only
the label bounds. Capacity is identical between every arm and A0, so the nuisance parameter the
permutation null exists to remove is exactly zero **by construction**, not by assumption. The
substitute declared in the pre-registration — the five-seed reseed null — was run and is §2's floor.

#### 6. The trade-off that was not anticipated: the slope moves, the bias does not

This is the part that matters for the gauge, and it is the reason this item does not close as a win.

| | predicted risk → observed risk, 5 bins | mean log bias | intercept |
| :--- | :--- | ---: | ---: |
| A0 depth 8 | 0.058→0.330 · 0.186→0.386 · 0.345→0.492 · 0.512→0.590 · 0.732→0.780 | −0.434 | +0.271 |
| A4 depth 3 | 0.096→0.303 · 0.210→0.407 · 0.320→0.523 · 0.434→0.588 · 0.604→0.757 | −0.524 | +0.192 |
| A4x depth 2 | 0.115→0.279 · 0.218→0.447 · 0.301→0.509 · 0.397→0.595 · 0.533→0.749 | −0.560 | +0.180 |

Reducing capacity fixes the **dispersion** of the risk score and leaves the **level** where it was —
the calibration intercept only moves +0.271 → +0.180, and the mean log-scale bias gets *worse*,
−0.434 → −0.560. Observed risk still exceeds predicted in all five bins at every depth. Restated in
the brief's own terms: the original complaint was "the model says 0.781 and the tyre is finished
0.946 of the time". Honestly measured that reads "the model says **0.533** and the tyre is finished
**0.749** of the time" — a ~22-point gap in the same dangerous direction, and **none of the four
declared arms closes it.**

That residual bias is not obviously a defect at all. Under the 10b label the model estimates the
**latent tyre limit**, and green-pit endings are realisations that stopped at or before it, so a
median above the observed green-pit ending is what the framing *predicts*. The app's gauge reads
that latent quantity to a user who interprets it as a realised stint — which is precisely the
product question the closing section of this doc raises and does not settle. It is also why A3's
Brier is better: `standard` targets the realised ending, which is what the gauge claims to show.

#### 7. Answering the item's definition of done

**Does the slope move toward 1.0?** Yes, and materially: 0.666 → **1.074** at depth 2 (declared
winner depth 3: **0.879**), a 78% reduction in `|slope − 1|`, and both bootstrap intervals now
contain 1.0 where the incumbent's excluded it in 99.5% of draws.

**Without costing discrimination?** Nearly. Against the honest incumbent AUC of 0.691 — not the
in-sample 0.844 — depth 3 costs 0.0043 (1.2× the AUC reseed floor) and depth 2 costs 0.0088 (2.5×).
Small, real, and priced.

**Landed?** No, deliberately, and this is a judgment call that should be reviewed:

1. The paired bootstrap cannot establish the improvement at 95% on 24 eval races. Overwriting the
   shipped booster on a 0.945-probability result is exactly the kind of move `04a`'s multiplicity
   finding exists to discourage.
2. The right fix is not a hand-picked `max_depth`. §1 shows the whole tuned parameter set was
   searched under the `standard` label, on the mixture NLL, with 2024 in the validation folds. Depth
   is the symptom the calibration slope happened to expose; a re-search under the honest split and a
   metric that is not the mixture NLL is the actual repair, and it is a separate item.
3. §6 says the level bias — the part that is dangerous for the gauge — survives every arm. Shipping
   a slope fix while that stands would move a number the app shows without fixing what it shows.

**Landed instead:** the instrument. `ml/src/evaluate_10c.py` now refits on the training side by
default and keeps the shipped-booster path only as an explicitly labelled `in_sample` diagnostic,
printed beside the headline as an optimism gap so the failure cannot recur silently. The 26
`ml/tests/test_survival.py` regression tests are untouched and pass — the metrics were never the
problem, the model being scored was.

**Follow-ups this opens.** (a) Re-run `tune.py` for `stint_life_regressor` under the honest split
and the chosen label, on a metric that is not the mixture NLL. (b) Rule on 10b with A3's numbers in
hand: `standard` beats `10b` on green-pit Brier out of sample. (c) Settle the product question in
§6 before any recalibration of the level — it is a question about what the gauge should mean, not a
statistical one. (d) `02b`'s note still stands and is now sharper: its `stint_life_regressor` noise
floors must not be measured until (a) resolves.

**Recorded 2026-09-10, on close-out.** Follow-up (a) is now item [`10e`](#10e--re-tune-stint_life_regressor-under-the-honest-split) below, and `02b` waits on it in the log. (b) is appended to `10b`'s note in `build-log.json`, where whoever rules on that item will read it. (c) is decision **D5**; whether to ship the depth fix in the meantime is decision **D4**. 10d is staged `MEASURED`, not `GATED` — gate 4 was substituted rather than run, and `gates.md` is explicit that an item which skips a step is `MEASURED`, never `GATED`.

---

## 10e — Re-tune `stint_life_regressor` under the honest split

**Objective.** The hyperparameters were never fitted for this problem. Fit them.

**Depends on** [`10d`](#10d--fix-the-stint-life-calibration-defect) for the finding and for the
repaired instrument. **Blocks** [`02b`](02-feature-expansion.md)'s noise-floor pre-flight.

**The defect in the search, as `10d` established it.** `tune.py` calls
`F.load_features(target=target)` with the default `censoring_variant="standard"` and folds over
`bundle.training_seasons` = 2018–2024. So the shipped `max_depth: 8` and
`aft_loss_distribution_scale: 0.8` were selected

1. under the **other** label construction,
2. on the **mixture AFT NLL** that `10c` ruled out as a headline, and
3. with **2024 inside the validation folds** — the season everything downstream evaluates on.

All three are wrong for the quantity the app's gauge shows. This is the repair `10d`'s verdict
names as the real one; depth was only the symptom its calibration slope happened to expose.

**What the search will find, already measured.** Capacity is the lever and the relationship is
monotone — and the shipped setting loses on the training folds' *own* metric, which is the
signature of a search run under the wrong label:

| `max_depth` | 2 | 3 | 4 | 5 | 6 | 8 (shipped) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| inner-fold green-pit slope | 0.794 | 0.708 | 0.680 | 0.669 | 0.656 | 0.622 |
| inner-fold NLL | 1.8171 | 1.8090 | 1.8078 | 1.8130 | 1.8188 | **1.8364** |

The AFT scale is mis-set too (inner-CV optimum 0.90 under the 10b label against the shipped 0.80),
though `10d` priced that as not mattering for calibration.

**Method — the constraint, not the recipe.** Re-run `tune.py` for `stint_life_regressor` with the
folds confined to the **training side** of `cv_final_fold` so 2024 stays out, the censoring variant
chosen deliberately rather than by default, and a selection metric that is **not** the mixture NLL —
green-pit IPCW-Brier and `|calibration slope − 1|` are the two `10d` used. Re-measure with
`ml/src/evaluate_10c.py`, whose honest mode is now the default and whose metrics carry 26
regression tests.

**Do not hand-pick a depth.** That is exactly what `10d` declined to land, and for the reason in its
§7: a single parameter chosen by eye on 24 eval races is not a repair to a search that was run
wrongly. If the re-search lands on depth 3 by itself, that is a result; asserting it is not.

**Settle [D5](../status/build-log.json) first if you can.** It decides which label this tunes
against, and it is a product question, not a statistical one. `10d`'s A3 arm is the evidence in
hand: out of sample `standard` beats `10b` on green-pit Brier, **0.190 vs 0.206**, with no AUC cost.

**Watch the level bias.** `10d` §6 found that capacity fixes the **dispersion** of the risk score
and leaves the **level** — intercept +0.271 → +0.180, mean log bias *worsening* −0.434 → −0.560,
observed risk above predicted in all five bins at every depth. A re-search that optimises the slope
alone will reproduce that, and the level is the half that is dangerous for the gauge.

**Acceptance.** Gates 1–7 per [`../foundations/gates.md`](../foundations/gates.md). Report the slope
with its race-level cluster bootstrap interval, never as a point — and note the standing limit:
24 eval races could not establish `10d`'s 0.17 slope improvement at 95%, so a result resting on the
same 24 races inherits the same ceiling.

**Definition of done.** A tuned parameter set selected under a split and a metric that both match
the estimand, with a written verdict on what it costs and buys against the honest incumbent
(green-pit slope 0.666, AUC 0.691, Brier 0.206) — or a recorded reason the search does not move it.

### D5 is settled, and it sets the label — recorded 2026-09-10

**The realised stint ending**, i.e. the `standard` censoring/label construction, not `10b`'s latent
tyre limit. The gauge says "remaining stint life: N laps" and a user reads that as the realised
answer, deployments included; that is also the pit wall's own decision quantity. It is the side the
numbers already favour — `10d`'s A3 arm scored `standard` better than `10b` on out-of-sample
green-pit Brier (0.190 vs 0.206) at no AUC cost, and the latent framing's level bias *worsens*
as the slope is fixed (−0.434 → −0.560). "Show both" was considered and set aside: it roughly
doubles this item and adds app work. **10e tunes against `standard`.**

One consequence for the numbers below. The incumbent named in the definition of done — slope 0.666,
AUC 0.691, Brier 0.206 — is the incumbent *under the `10b` label*. The like-for-like baseline for a
`standard`-label re-search is `10d`'s A3 row, reproduced here as **A0**: slope 0.700, AUC 0.694,
Brier 0.190. Both are reported; A0 is the one the arms are scored against.

### Pre-registration — arms, space and e-value (gates 6 and 7)

Written 2026-09-10, **before any trial ran**. Everything below is selected on the training side of
`cv_final_fold` (seasons 2018–2023); nothing is selected on 2024.

**The split, exactly.** `EV._evaluation_split` puts train on 2018–2023 and eval on 2024. The
re-search's inner CV is `train._season_folds` over the **training side only**, `n_splits=4` on six
seasons — expanding whole-season windows, first train 2018–2019 validating 2020, last train
2018–2022 validating 2023. Four folds and not five because five over six seasons opens with a fold
trained on 2018 alone; four reproduces production's own shape (first train = two seasons) inside the
shorter window. The eval season never enters a fold. This is the defect `10d` named: today's
`tune.py` folds over `bundle.training_seasons`, which is 2018–**2024**.

**The label, explicitly.** `censoring_variant="standard"`, passed rather than defaulted. It happens
to equal `load_features`' current default; the point is that it is now a stated choice and appears in
the run's own record, because `10d` showed the default is what made the shipped search wrong for
`10b` and right for `standard` by accident rather than by decision.

**The space.** `tune.SEARCH_SPACE ∪ tune.SURVIVAL_SPACE` as widened for open item 21, with **one
declared change: `max_depth` low bound 3 → 2.** `10d` measured inner-fold slope rising monotonically
as depth falls and its best arm sat at depth 2, outside the shipped space — a search that cannot
propose the value its own predecessor found best is a search stopped on its edge before it starts.
The bound moves in `tune.py` (the same file the item 21 widening moved) rather than being patched per
run. Every other range is untouched.

**Arms.** Two searches, differing only in what they select on. Both run 60 TPE trials seeded with
`S.RANDOM_STATE`, MedianPruner as production, over the identical folds.

| arm | selection objective (mean over the four inner folds) | why it is declared |
| :--- | :--- | :--- |
| **A0** | — (baseline: shipped v11 params, refit honestly under `standard`) | the incumbent |
| **S1** | green-pit **IPCW-Brier** ↓ | a proper scoring rule; scores level *and* dispersion, and it is the metric on which `standard` already beat `10b` |
| **S2** | green-pit **\|calibration slope − 1\|** ↓ | the metric `10d`'s winning arm used — declared separately precisely to test this doc's own warning that optimising the slope alone leaves the level where it is |

Neither objective is the mixture AFT NLL. It is reported per selected config as a diagnostic only,
so the shipped `max_depth: 8` can be checked against the training folds' own former headline.

**Boundary handling, declared in advance.** `tune.boundary_params` names any parameter that comes back
on an edge. If either search stops on one, the probe past that bound is run and reported **as a
declared extension of that arm**, not folded into it — `10d`'s A4x/C2 were added after seeing the
trend and had to be marked undeclared, and this is the cheap way not to repeat that.

**What is reported for every arm.** Green-pit calibration slope with a 200-draw **race-level cluster
bootstrap** interval (seed 20260910, races the resampling unit, 24 eval races), time-dependent AUC,
IPCW-Brier, and — because this is the half `10d` found survives every fix — the **level**
diagnostics: calibration intercept, mean log-scale bias, the 5-bin predicted→observed table, and the
sd of the log-scale prediction. A slope that improves while the mean log bias worsens is reported as
exactly that.

**Gate 3 floor.** Five seeds, 20260528–20260532, varying XGBoost's `seed` (which drives `subsample`
and `colsample_bytree`, so the refits genuinely differ), measured on **this family's own** label
construction — `standard`, not `10b`. `10d`'s floor was measured under `10b` and `gates.md` is
explicit that a floor is not borrowed across families. Floor = `2*sqrt(2)*sd` per
`attribution.py::refit_noise_floor`.

**Gate 4, and an honest correction to how `10d` stated it.** The permutation null row-shuffles *new
columns*; no arm here adds one, so it is inapplicable in its literal form and the declared substitute
is the paired reseed null. But `10d` also wrote that "capacity is identical between every arm and A0
… by construction". For a hyperparameter re-search that is **false**: `max_depth` and `n_estimators`
*are* capacity, and capacity is the entire content of the arm. So there is no information/capacity
decomposition to run here, and the e-value's null below is stated as what it actually is — "no
difference beyond refit noise" — rather than as an information null it cannot be.

**E-value — Construction B, declared now.** From
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) §4, which that
document calls the default and which removes the plug-in-scale hole that `10d` fell into (its
Construction A fed a refit-noise sd into `exp()` and returned 10¹¹).

- **Null.** H₀: the re-searched parameter set performs no better than the incumbent beyond refit
  noise, so the five paired reseed deltas are mean-zero.
- **Deltas, oriented so positive is improvement,** both pre-registered:
  `d_B(i) = Brier(A0, seed_i) − Brier(arm, seed_i)` and
  `d_S(i) = |slope(A0, seed_i) − 1| − |slope(arm, seed_i) − 1|`, all on the 2024 green-pit stratum,
  arm and incumbent refit at the **same** five seeds so the shared seed noise cancels.
- **Statistic.** `t = sqrt(5) * mean(d) / sd(d)` (ddof=1), `g = 1`,
  `E = (1+5g)^(-1/2) * [(1 + t²/4) / (1 + t²/(4(1+5g)))]^(5/2)`.
- **Verified before use**, as §4 requires: 100k simulated draws of five i.i.d. `N(0, σ)` deltas at
  several σ, mean `E` = 1 to Monte Carlo error.
- **Reported alongside:** Construction A at `c = 1.5` on the same deltas, purely so this item's
  numbers sit beside `10d`'s table on the same scale, and **the paired race-cluster bootstrap**,
  which is the instrument that matches the estimand. `10d` §4 already ruled that where the three
  disagree the bootstrap is the one to believe, and this item does not get to re-litigate that
  after seeing its own numbers.
- **Family.** Both declared searches (S1, S2) plus any declared boundary extension. All are counted
  and reported with their `E`, `E < 1` included. Campaign-level decisions run e-BH per gate 7.

**The standing limit, restated before the numbers exist.** 24 eval races could not establish `10d`'s
0.17 slope improvement at 95%. Anything measured here rests on the same 24 races and inherits the
same ceiling; a result inside it is reported as inside it.

### Pre-registration addendum — the 2026-09-19 re-run

Written 2026-09-19, after gate 1's anchors were checked and the tuning path smoke-tested, and
**before any search trial or any arm was fitted**. Three things moved under the 2026-09-10 verdict
below; this records what changes and what carries forward, so the re-run is a re-run and not a
fresh search dressed as one. It is the same shape of addendum `10d` wrote on 2026-09-18, for the
same reason.

**1. The substrate moved, and six-decimal reproduction of this item's own 2026-09-10 figures is
impossible.** `08m` repaired the compound wear curve and `08n` shipped v12 on 2026-09-16. The
`cv_final_fold` eval fold is **19,973 laps / 9,149 green-pit** today against the **20,272 / 9,270**
every figure in the verdict below was measured on. Gate 1 is anchored on what *can* be reproduced,
exactly as `10b`, `10c` and `10d` were re-anchored: today's published v12 headline, and `10b` §4's
A0 row. Both were checked before this paragraph was written.

**2. The space this item widened is now the space, so there is no pinned/unpinned pair to report.**
The 2026-09-10 boundary extension landed in `tune.py` — `n_estimators` low 200 → 50 (step 100 → 50),
`max_depth` low 3 → 2, both with their rationale in the module and both pinned by
`test_search_space.py`. S1 and S2 below therefore search the space S1x and S2x searched, and the
four-arm family the old run needed collapses to two searches. The declared boundary rule carries
forward unchanged and still binds: **any parameter that comes back on an edge is probed past that
bound and the probe is reported as a declared extension of that arm, never folded into it.**

**3. A third declared arm, X1 — the 2026-09-10 winner, re-scored on v12.** S1x's exact parameter set
is promoted from "the previous run's winner" to a declared arm of this one. This is the move `10d`
made with A4x and it is made for the same reason: carrying a finding forward **by declaring it in
advance on fresh rows** is the only honest way to use it. It is also required rather than optional
here — [D4](../status/build-log.json) was resolved on 2026-09-11 in favour of shipping S1x, the
landing never executed, `08n` then shipped v12 carrying v11's hyperparameters, and **S1x has never
been scored on this substrate**. The log's own audit note of 2026-09-18 says to re-score it before
anything is landed on it. That note predates this run and is the landing rule stated below.

**The family is therefore three declared arms — S1, S2, X1** — all three counted, all three
reported with their `E`, `E < 1` included. A0 is the baseline and not a member.

| arm | what it is | selected on |
| :--- | :--- | :--- |
| **A0** | incumbent: v12 shipped params, `standard` label, honest refit | — |
| **S1** | fresh search, 50 TPE trials, current space | green-pit **IPCW-Brier** ↓ |
| **S2** | fresh search, 50 TPE trials, current space | green-pit **\|calibration slope − 1\|** ↓ |
| **X1** | the 2026-09-10 S1x parameter set, unchanged | nothing — declared, not searched |

**The searches, exactly.** `python -m ml.src.tune --target stint_life_regressor --trials 50
--folds 4 --honest-split --censoring-variant standard --objective {green_pit_brier,
green_pit_calibration} --no-refit`, studies and best-params written to a scratch directory so no
shipped artefact moves. Four inner folds over the training side only (2018–2023, expanding whole
seasons, first train 2018–2019 validating 2020, last train 2018–2022 validating 2023), TPE seeded
with `S.RANDOM_STATE`, MedianPruner as production. The eval season never enters a fold. Neither
objective is the mixture AFT NLL; it is reported per selected config as a diagnostic only.

**What is reported for every arm**, unchanged from the pre-registration above: green-pit calibration
slope with a 200-draw race-level cluster bootstrap interval (seed 20260910, races the unit, 24 eval
races), time-dependent AUC, IPCW-Brier, and the level diagnostics — calibration intercept, mean log
bias, the 5-bin predicted→observed table, and the sd of the log-scale prediction.

**Gate 3 floor.** Five seeds, 20260528–20260532, varying XGBoost's `seed`, each arm measured against
**its own** floor under `standard`. `2*sqrt(2)*sd` per `attribution.py::refit_noise_floor`.

**Gate 7 — Construction B as before, with its ceiling stated in advance.** `g = 1`, `n = 5` paired
reseed deltas, verified against 100k simulated null draws before use; Construction A at `c = 1.5`
reported beside it for comparability with `10d`'s table and not believed, per `10d` §4. The family
is three, so e-BH at α = 0.05 needs `E ≥ 60` for a lone rejection, `≥ 30` for two, `≥ 20` for all
three. **Construction B's ceiling at `n = 5, g = 1` is `(1+ng)^((n-1)/2) = 36`**, so a lone
rejection is arithmetically unreachable before the data are seen and only a joint two- or
three-arm rejection can fire. That is [`09c`](09-scoring-instruments.md)'s finding, restated here
because it constrains what this item can conclude, and `g` is **not** moved to dodge it — moving it
after seeing the numbers is exactly what gate 7 forbids.

**The declared pass criterion, three legs.** An arm **improves the shipped model** if all of:

1. green-pit IPCW-Brier improves against A0 — the metric the primary objective selects on and the
   one `10d` could resolve;
2. the **paired** race-cluster bootstrap on that Brier delta returns `P(improves) ≥ 0.95` **and** a
   95% interval excluding zero;
3. neither `|slope − 1|` nor AUC worsens by more than that arm's own gate-3 reseed floor.

**And the leg that is expected to miss, written down before it does.** The calibration *slope*
improvement is reported with its own paired-bootstrap `P` and is **not** a leg of the criterion.
24 eval races could not establish `10d`'s slope gain at 95% on 2026-09-10 (P = 0.945), could not on
2026-09-18 (P = 0.855 at its best arm), and could not establish this item's own on 2026-09-10
(P = 0.930). A third failure is the standing ceiling, not a new finding, and it cannot be
reinterpreted afterwards as a pass.

**The boundary probe, declared when the pin appeared and before it was run.** S2 came back on
`n_estimators = 50 (low)` — the same axis and the same side its 2026-09-10 counterpart pinned on,
one widening later. The declared probe is a **coordinate ladder in `n_estimators` at S2's other
selected parameters**, over {10, 25, 50, 100, 200, 400, 800}, on the same four inner folds and
through `tune._green_pit_objective`, reported as **S2p**, a declared extension of S2 and not folded
into it. What it can settle is `boundary_params`' own distinction: a ladder that improves below 50
means the learner wants a weaker fit than the space allows and the bound must move again; a ladder
that worsens below 50 means the optimum lives at the edge and the bound is not binding. It is a
**coordinate** probe and cannot see a joint move ([`../foundations/epistemics.md`](../foundations/epistemics.md));
it is read for one axis only, which is the question a pin asks. S2p enters the e-value family if
and only if it is scored on 2024 as an arm — if the ladder says the bound is not binding, it is a
diagnostic and the family stays at three.

**The landing rule, which is not this session's to invent.** D4 is resolved: ship S1x, flagged
rather than presented as an established fix. The log's audit note of 2026-09-18 makes that
conditional on exactly one thing — that S1x still improves green-pit Brier on v12 **with the paired
interval excluding zero**. So: if X1 meets legs 1–3, D4's landing executes as ruled, with D4's
caveat wording. If it does not, nothing ships and the question goes back to the user, because D4
rested on a measurement that no longer holds. **A fresh arm (S1 or S2) that beats X1 is reported and
raised, not shipped** — D4 ruled on S1x, and a different parameter set is a different decision.

### Verdict — MEASURED 2026-09-19

**The parameter set this item found on 2026-09-10 survives a warehouse rebuild, a target repair and
a fresh independent search — and the fresh search cannot beat it.** Re-scored on v12, S1x (here the
declared arm **X1**) improves green-pit IPCW-Brier by **+0.0226**, paired race-cluster bootstrap 95%
**[+0.0073, +0.0353]**, **200 of 200 draws improving**, ~15× its own reseed floor. A 50-trial search
run from scratch on this substrate, against the same objective and the same folds, returns a
configuration whose **own inner-fold objective is worse than X1's** (0.1805 against 0.1780) and
which is worse out of sample on both Brier and slope. The re-search reproduces the 2026-09-10
finding without improving on it, which is a stronger result than finding something new.

**And the slope lands on P = 0.945 for the third time.** `10d` measured +0.173 at P = 0.945 on
2026-09-10, 0.855 at its best arm on 2026-09-18, and this item measured +0.173 at P = 0.930 on
2026-09-10. X1 on v12 returns **+0.179 at P = 0.945**. Four attempts, four numbers below 0.95, on
the same 24 races. That is the ceiling, not the model, and it was written down before this run.

#### 1. Gate 1 — the instrument

Anchored on what can be reproduced. The 2026-09-10 figures cannot be: `08m` rebuilt the warehouse
and `08n` shipped v12 on 2026-09-16, so the eval fold is **19,973 laps / 9,149 green-pit / 24
races** against the 20,272 / 9,270 / 24 that verdict was measured on.

| gate | anchor | result |
| :--- | :--- | :--- |
| 1a | today's published v12 headline, through `E._fit`/`E._score` | `1.9913358778933028` — **exact** |
| 1b | `10b` §4's A0 row, all 7 stored figures | **exact, every digit** |
| 1c | substrate drift against 2026-09-10 | reproduction impossible, and stated as such |
| 1d | the optimism gap, re-measured | slope **0.674 honest / 1.229 in-sample** |

Gate 1d is `10d`'s original finding, alive on v12 eight days and a rebuild later: the shipped
booster's eval rows sit inside its own training set, and across that gap the calibration slope does
not merely shrink — it crosses 1.0, so an in-sample reading reports the miscalibration with the
wrong **sign**. Green-pit AUC reads 0.831 in-sample against 0.690 honest.

The green-pit stratum carries **zero censoring** under `standard`, so every IPCW weight in it is 1
and the Brier is an ordinary proper score on realised endings.

#### 2. What the searches did, and where one of them stopped

| arm | objective | selected | inner-fold value | boundary |
| :--- | :--- | :--- | ---: | :--- |
| **S1** | green-pit IPCW-Brier ↓ | depth **11**, **100** trees, lr 0.0265, scale 0.524, `min_child_weight` 6, subsample 0.835, colsample 0.625 | 0.1805 | **interior on every axis** |
| **S2** | \|slope − 1\| ↓ | depth 6, **50** trees, lr 0.0318, scale 0.748, `gamma` 0.898, `min_child_weight` 14 | 0.1057 | **pinned** `n_estimators` low |

**Both searches cut shrinkage, and neither reached for depth.** `n_estimators × learning_rate` runs
5.26 at the incumbent, **2.65** at S1 and **1.59** at S2. That is the same axis the 2026-09-10 run
moved (to 2.19) and it is now the third independent search to move it. `10d`'s prediction that the
search would land on low depth is wrong again: S1 went to depth **11**, one step below the ceiling.

**S2 pinned, so the pin was probed and not read.** The declared coordinate ladder in `n_estimators`
at S2's other selected parameters, on the same four inner folds:

| `n_estimators` | 10 | 25 | **50** | 100 | 200 | 400 | 800 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective \|slope−1\| | 183.48 | 3.82 | **0.106** | 0.392 | 0.414 | 0.456 | 0.485 |
| pooled slope | 189.26 | 4.75 | 0.915 | 0.562 | 0.534 | 0.504 | 0.475 |
| inner Brier | 0.450 | 0.324 | 0.190 | 0.194 | 0.210 | 0.213 | 0.217 |
| pooled margin sd | 0.105 | 0.218 | 0.353 | 0.498 | 0.587 | 0.652 | 0.702 |

**The optimum lives at the edge and the bound is not binding on it.** One step below 50 the
objective is 36× worse, because the risk score becomes under-dispersed and the slope overshoots to
4.75 and then 189. That is `boundary_params`' own distinction — "the learner wants more" versus
"the optimum sits at the edge" — settled the only way it can be, by the probe. It is a
**coordinate** probe and cannot see a joint move ([`../foundations/epistemics.md`](../foundations/epistemics.md));
it is read for one axis, which is the question a pin asks. The 2026-09-10 ladder reached the same
verdict on different rows. **S2p is therefore a diagnostic, not an arm, and the family stays at
three** — as the addendum declared it would if the ladder came back this way.

**The inner folds rank X1 first, and that is the finding.** Fold-mean over the four training-side
folds, nothing here having seen a 2024 row:

| | A0 | S1 | S2 | **X1** |
| :--- | ---: | ---: | ---: | ---: |
| green-pit Brier (S1's objective) | 0.2098 | 0.1805 | 0.1899 | **0.1780** |
| \|slope − 1\| (S2's objective) | 0.4155 | 0.3760 | **0.1057** | 0.2745 |
| mixture AFT NLL (selected on by nobody here) | **2.1852** | 2.2674 | 2.4320 | 2.2663 |

S1 is the winner of a 50-trial search against green-pit Brier and **X1 beats it on that search's own
objective**, on that search's own folds, having been selected on a different substrate eight days
earlier. Either 50 TPE trials under-explore this space, or X1 sits in a basin robust to a target
repair; the two are not exclusive and this item does not have to choose between them to report the
fact.

#### 3. The arms, on the 2024 eval fold

Green-pit stratum, n = 9,149, 24 races, zero censoring. Every configuration refit on 2018–2023
through `evaluate._fit` on the identical split; only the hyperparameters differ. Canonical seed
20260528.

| arm | slope | boot 95% | AUC | Brier | boot 95% | mean log bias | intercept | margin sd |
| :--- | ---: | :--- | ---: | ---: | :--- | ---: | ---: | ---: |
| **A0** incumbent v12 | 0.6736 | [0.431, 0.911] | 0.6896 | 0.1904 | [0.174, 0.211] | −0.2741 | +0.2319 | 0.5818 |
| S1 brier | 0.6280 | [0.453, 0.824] | 0.7120 | 0.1756 | [0.161, 0.193] | −0.0305 | +0.1897 | 0.4730 |
| S2 slope | 1.1919 | [0.866, 1.589] | 0.7095 | 0.1838 | [0.169, 0.200] | +0.3402 | −0.3064 | 0.3488 |
| **X1** = S1x | **0.8754** | **[0.619, 1.147]** | 0.7096 | **0.1689** | **[0.159, 0.184]** | +0.0680 | +0.0229 | 0.4363 |

Gate 3, five seeds 20260528–20260532 with XGBoost's `seed` varied, **each arm against its own
floor** (`2*sqrt(2)*sd`), never a borrowed one:

| arm | Δ\|slope−1\| | × floor | ΔBrier | × floor | ΔAUC | × floor |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| S1 | **−0.0283** | −0.94× | +0.0168 | 6.66× | +0.0272 | 2.90× |
| S2 | +0.1235 | 2.33× | +0.0080 | 6.70× | +0.0217 | 7.00× |
| **X1** | **+0.2118** | **6.52×** | **+0.0226** | **14.98×** | +0.0209 | 3.27× |

A0's own floors, which `02b` needs and which are measured here under `standard`, this family's own
label: slope sd 0.008848 (floor 0.025025), Brier sd 0.000736 (floor 0.002082), AUC floor 0.006012.

#### 4. The paired race-cluster bootstrap — the instrument that matches the estimand

200 draws, seed 20260910, races the resampling unit, both arms scored on the **same** resampled
races so the shared race-draw noise cancels. `10d` §4 ruled this authoritative where the floor, the
e-value and the bootstrap disagree; this item does not re-litigate that after seeing its numbers.

| arm | ΔBrier | 95% | P | Δ\|slope−1\| | 95% | P |
| :--- | ---: | :--- | ---: | ---: | :--- | ---: |
| S1 | +0.0150 | [+0.0040, +0.0246] | **1.000** | −0.0362 | [−0.107, +0.049] | 0.175 |
| S2 | +0.0088 | [−0.0166, +0.0313] | 0.730 | +0.0962 | [−0.450, +0.478] | 0.650 |
| **X1** | **+0.0226** | **[+0.0073, +0.0353]** | **1.000** | +0.1792 | [−0.040, +0.270] | **0.945** |

**Against the declared three-leg criterion: S1 and X1 pass, S2 fails on leg 2.** X1 passes with the
larger margin on every leg it is judged by.

**The slope is where it has always been.** +0.179, interval straddling zero, P = 0.945 — the fourth
measurement of this quantity in this campaign and the fourth below the bar. A proper score evaluated
per row has far less sampling variance than a slope fitted through five binned points, which is why
the same 24 races resolve the Brier and cannot resolve the slope. Nothing here is a new limit.

**S2 is the arm that shows what the two objectives are worth.** It is selected on \|slope − 1\| and
it buys the best slope of the three on the training folds (0.106) — then lands at **1.19** out of
sample, overshooting past 1.0, with the widest interval of any arm [0.866, 1.589] and a Brier gain
the bootstrap cannot resolve (P = 0.730). Optimising the slope alone selects a configuration whose
slope is unstable, because the quantity being optimised is itself the noisiest thing measured here.

#### 5. The level bias — the prediction, and where it broke, again

The 2026-09-10 verdict predicted that a slope-only search leaves the level where it is, and found
that Brier selection breaks the pattern. **Both halves reproduce on v12, and the slope-only arm is
worse than "unchanged" — it overshoots.**

| | 5 bins, predicted risk → observed risk | mean log bias | intercept |
| :--- | :--- | ---: | ---: |
| A0 | 0.108→0.287 · 0.250→0.410 · 0.409→0.535 · 0.566→0.597 · 0.766→0.744 | −0.2741 | +0.2319 |
| S2 | 0.460→0.225 · 0.604→0.445 · 0.706→0.565 · 0.789→0.563 · 0.885→0.776 | **+0.3402** | −0.3064 |
| S1 | 0.133→0.200 · 0.319→0.444 · 0.517→0.598 · 0.714→0.596 · 0.905→0.735 | **−0.0305** | +0.1897 |
| **X1** | 0.266→0.223 · 0.433→0.450 · 0.579→0.540 · 0.697→0.607 · 0.834→0.753 | +0.0680 | +0.0229 |

A0 predicts **below** observed risk in all five bins — the gauge says a tyre has life it does not
have. S2 predicts **above** it in all five and by more than the incumbent was wrong the other way:
\|mean log bias\| 0.274 → 0.340. X1 flips the sign and cuts the magnitude **75%**, to +0.068. And
the arm that gets closest to zero on the level is **S1**, at −0.0305, an 89% reduction that keeps
the incumbent's sign — the only arm here that reduces the level error without inverting it.

That matters for the product question and it is worth stating plainly, because it is the one axis on
which the fresh search beats X1: **S1 errs conservatively-by-almost-nothing, X1 errs conservatively
by a little, A0 errs dangerously by a lot.** S1's price for it is the worst calibration slope of the
four (0.628, below even the incumbent) and a Brier gain a third smaller than X1's.

#### 6. Gates 2 and 4 — inapplicable in their literal form, stated rather than skipped

**Gate 2** is an add-ablation and nothing is added: all four arms are the same 32-column matrix
under the same `standard` label, fitted differently. The substituted requirement — one split, one
label construction, one set of eval rows for every arm, through `evaluate.py`'s own `_fit` — is met
exactly.

**Gate 4** row-shuffles new columns and there are none. The reseed null is the declared substitute
and its floors are in §3. The correction this item made to `10d`'s phrasing on 2026-09-10 stands and
is repeated because it is easy to lose: for a hyperparameter re-search, **capacity is not a
nuisance held constant — it is the entire content of the arm**, so there is no
information-versus-capacity decomposition available and the e-value's null below is stated as what
it is, "no difference beyond refit noise", not as an information null it cannot be. Both
substitutions are why this item is **MEASURED, never GATED**.

#### 7. Gate 7 — the e-values, the family, and an instrument that must be read with its sign

Construction B as declared (`g = 1`, `n = 5` paired reseed deltas), **verified before use**: 100k
simulated draws of five i.i.d. `N(0, σ)` deltas return mean `E` = 0.999–1.011 at every σ tested, and
the reference's own worked example returns **17.05** against its published 17.0.

| arm | Δ\|slope−1\| | `E_B` slope | `E_A` slope | ΔBrier | `E_B` Brier | `E_A` Brier |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| S1 | −0.0283 | 13.74 *(wrong direction)* | 0.055 | +0.0168 | 34.25 | 7.1 × 10⁵ |
| S2 | +0.1235 | 25.64 | 2.7 × 10³ | +0.0080 | 31.77 | 3.7 × 10² |
| X1 | +0.2118 | **34.38** | 1.4 × 10⁶ | +0.0226 | **35.57** | 9.8 × 10⁷ |

**e-BH at α = 0.05 over the three declared arms rejects all three on Brier, and none on slope.** The
family is three, so the ladder is `E ≥ 60` for a lone rejection, `≥ 30` for two, `≥ 20` for all
three; the Brier column clears the three-arm rung and the slope column clears no rung. This is, as
far as this tree records, **the first e-BH rejection in the campaign** — and it happens not because
the evidence is stronger than `10e`'s was on 2026-09-10 but because **the family is three instead of
four**. The best arm's `E` is 35.57 against 35.9 then. That is the honest reading and it is
uncomfortable: the multiplicity verdict here turned on how many hypotheses were declared, which is
what multiplicity correction is, and it is also why `09c` exists.

**Three things must be read alongside that number, none of them flattering.**

1. **Construction B's ceiling is 36 and the winner is at 35.57.** `E` is pinned against the
   arithmetic limit of the construction, so it is not measuring how strong this evidence is any
   more — it is measuring that the evidence is strong enough to saturate a bounded instrument.
   Declared in advance (addendum, gate 7) precisely so this could not be discovered afterwards.
2. **The e-value's null is refit noise; the estimand's uncertainty is sampling noise.** e-BH rejects
   **S2** on Brier at `E_B` = 31.77 while the paired bootstrap on the same arm returns
   **P = 0.730** with an interval straddling zero. Two declared instruments, one public
   disagreement, and `10d` §4's standing ruling decides it: **the bootstrap is the one to believe**,
   so S2's Brier gain is not established whatever e-BH says about it.
3. **Construction B as implemented here is two-sided in `t`**, so it scores "there is a difference",
   not "there is an improvement". S1's slope `E_B` = 13.74 comes from `t = −6.21` — a delta in the
   **wrong** direction — and is marked as such in the table rather than being quietly counted as
   evidence for S1. No rejection depends on it (the slope column rejects nothing at any rung), so
   the two-sidedness changes no conclusion here, but an `E` from this harness must never be quoted
   without the sign of its delta. The 2026-09-10 run declared a one-sided truncation and this one
   did not; that is a difference between the two runs' instruments and it is logged in §10 rather
   than smoothed over.

Construction A is inflated again — 9.8 × 10⁷ for X1 — for the reason `10d` diagnosed and this item
confirmed: its scale is five-seed refit noise where the bootstrap puts sampling noise an order of
magnitude higher. Reported because it was declared. Not believed.

#### 8. The metric the incumbent was tuned on

On the training folds' own mixture AFT NLL — the objective that selected the shipped parameters —
the incumbent is **best** (2.1852, against 2.2663–2.4320 for the three arms). On the green-pit
stratum it is **worst** (eval-fold green-pit NLL 3.4377, against X1's 3.2922). The two metrics rank
these four models in opposite orders, and the mixture is the one the app does not care about. That
is `10c`'s ruling restated in this item's own numbers, for the second time and on a rebuilt
substrate.

#### 9. Answering the definition of done, and D4

**A tuned parameter set selected under a split and a metric that both match the estimand:** yes, and
it is the one this item already had. **X1 = S1x** — `censoring_variant=standard` (D5's realised
stint ending), folds confined to 2018–2023, green-pit IPCW-Brier as the objective. Against the
honest incumbent on v12 (slope 0.674 / AUC 0.690 / Brier 0.190): slope → **0.875**, \|slope−1\| −62%
at 6.5× floor; Brier → **0.169**, 15.0× floor and the only gain any instrument here resolves at 95%;
AUC → **0.710**, +0.021 at 3.3× floor, an increase; mean log bias −0.274 → **+0.068**.

**What it costs:** the level error changes sign rather than closing, and the calibration-slope gain
remains unresolved at 95% on 24 races for the fourth time.

**D4's landing condition is met.** D4 was resolved on 2026-09-11 — ship S1x, flagged clearly rather
than presented as an established fix — and the landing never executed; the session hit a usage
limit, and `08n` then shipped v12 on 2026-09-16 carrying v11's hyperparameters, so production is
**not** S1x. The log's audit note of 2026-09-18 made the landing conditional on exactly one thing:
that S1x still improves green-pit Brier on v12 with the paired interval excluding zero. It does —
**+0.0226 [+0.0073, +0.0353]**. The condition was written before this run and this run met it.

**The fresh search did not produce a better candidate, so no new decision is raised.** The
addendum's branch for that case — report and raise, never ship — does not fire. S1 loses to X1 on
Brier (0.1756 vs 0.1689), loses on slope (0.628 vs 0.875, and 0.628 is worse than the incumbent's
0.674), and wins only on \|mean log bias\| (0.031 vs 0.068) and by 0.0024 of AUC, which is inside
the AUC floor. **S1's level advantage is recorded here as the one thing the fresh search found that
X1 does not have**, so that whoever reopens the level-direction product question has it in hand.

#### 10. Deviations from the declared method, logged

- **The e-value instrument differs from the 2026-09-10 run's.** That run declared and applied a
  one-sided truncation to Construction B (validated at null mean `E` = 0.70); this run reused
  `10d`'s harness, which is two-sided (validated at null mean `E` = 1.00). Both are valid
  e-values against their own nulls. The difference is stated in §7, the direction is printed beside
  every `E`, and no rejection here turns on it. It was not noticed at declaration time, which is
  why it is a deviation and not a design choice.
- **The harness was dry-run once before the real arms**, on placeholder parameter files (the
  incumbent's own params, and the incumbent at depth 3) with the bootstrap skipped, to catch a
  crash before an hour of compute rather than after. Its outputs were deleted, no figure from it
  appears anywhere, and the run is named here rather than left out.
- **S2p, the declared boundary ladder, was run as a diagnostic and not scored on 2024.** The
  addendum said it would enter the family if and only if it became an arm, and the ladder's answer —
  the bound is not binding — is what kept it out. Had the ladder gone the other way the family
  would be four and the e-BH rungs 80/40/26.7.
- **Trial count 50, not the 60 the 2026-09-10 pre-registration named.** 50 is what that run's own
  recorded command used and what this addendum declared before running. Named because the two
  numbers are both in this document.
- **The mixture AFT NLL is reported on the inner folds and on the green-pit stratum, not as a
  whole-eval-fold headline per arm.** That number exists only for A0 (gate 1a, 1.9913) because
  producing it for the arms means a fit whose only purpose is a metric `10c` ruled out. §8 makes its
  point with the two figures that were already computed.

### Landing note — LANDED 2026-09-19, on D4's ruling

**What shipped.** `ml/models/stint_life_regressor_best_params.json` now carries X1/S1x, and
`stint_life_regressor_v12.bst` is retrained on it. `max_depth` stays at **8** — the shipped value —
and the fit is bought back on the shrinkage axis: `n_estimators` 200 → **100**, `learning_rate`
0.02631 → **0.02192**, `aft_loss_distribution_scale` 0.80 → **0.754**, with `reg_alpha`,
`min_child_weight`, `subsample` and `colsample_bytree` moving too. `n_estimators × learning_rate`
falls 5.26 → 2.19.

**Why it is a landing and not a gate pass.** [D4](../status/build-log.json) was resolved on
2026-09-11 — ship S1x, flagged clearly rather than presented as an established fix — as a deliberate
human override of the normal `GATED` prerequisite, logged then and logged again here. The landing
did not execute that day (the session hit a usage limit) and `08n` shipped v12 on 2026-09-16
carrying v11's hyperparameters, so production was never S1x. The log's audit of 2026-09-18 made
re-execution conditional on one measurement, which §9 above reports as met.

**The verification D4 asked for, run after the landing.** `evaluate_10c --variant standard` on the
shipped configuration returns green-pit **AUC 0.7096, Brier 0.1689, slope 0.8754** — X1's row above,
to four decimals. The landing landed the parameter set it was supposed to land.

**One thing the landing improved that nothing predicted.** The optimism gap — gate 1d, the defect
`10d` found — **shrinks by more than half**: AUC optimism +0.1415 → **+0.0834**, Brier +0.0484 →
**+0.0056**, slope +0.5557 → **+0.3066**. Less shrinkage means less memorisation of the training
seasons, which is the mechanism, and it means an in-sample reading of this model is now much less
wrong than an in-sample reading of the old one. It still crosses 1.0 in sample (1.182 against 0.875
honest), so the rule that produced `10c`'s original error stands: **never read this model's
calibration in sample.**

**The cost, which D4 did not have in front of it.** This family's *published headline* is the
mixture AFT NLL, and landing S1x makes it worse: **1.99134 → 2.15315**, against a baseline that also
moves (2.18868 → 2.20099, because the AFT baseline is computed at the model's own fitted scale).
`beats_baseline` stays **True**; `beats_baseline_significant` flips **True → False**, and
`evaluation_metrics.json` now lists `stint_life_regressor` under `claims_inside_noise`. This is the
expected direction — `10c` ruled the mixture the wrong headline for this target, and §8 above shows
the two metrics ranking these models in opposite orders — but it is a real consequence that was not
weighed when D4 was ruled, and it is recorded here, on the model card (deviation `E4` and its
limitations entry) and in the log rather than left for someone to discover. On the green-pit
stratum's own NLL the new parameters win, 3.4377 → 3.2922.

**The ceiling-capture trade — recorded 2026-09-21 by `01c`.** The `fraction_of_attainable` on the v12 substrate fell from pre-`10e` 0.6152 to post-`10e` 0.1820 — a decline of **43.3 percentage points**, or **70.4% of prior capture**. The trade was `01c`'s job to record and is documented there with full traceability; this note links it: landing S1x bought the green-pit Brier gain (`+0.0226, 95% [+0.0073, +0.0353]`) and paid ~70% of this family's attainable ceiling capture, measured on the same v12 substrate and same two timestamps (pre-`10e`: commit `fb546b4`; post-`10e`: commit `44bb0ba`).

**What else moved, and what did not.** `evaluate --all` was re-run so the published metrics match
the shipped artefacts — a step D4's recorded nine-step sequence omits, and without it every future
gate 1a would reproduce a headline no artefact carries. The other four families reproduce **to
every digit** across that re-run, which is its own small instrument check. ONNX parity passes for
all five (stint-life abs 2.98e-05). `ml/models/encoders.json` is unchanged. The warehouse was not
touched.

**Test suite: 209 passed, 1 failed, and the failure is not this item's.**
`test_aggregation_survey_still_names_the_outstanding_instance` asserts that
`int_sc_hazard_history` still appears in the aggregation survey with the wording "pools every
ingested season". It appears, but `02d`'s rebuild changed what it pools, so the survey now says
"pools the laps of one race" and "pools the races of one season". Both the SQL and the test are
unmodified against `HEAD`, and nothing in this landing can reach `survey_aggregation_scope` — so
this is red at `HEAD`, it belongs to `02d`, and it is reported rather than fixed here because
re-wording another item's advance notice is that item's call.

**Reverting, if D4 is reconsidered.** `ml/models/stint_life_regressor_best_params.json`,
`ml/models/manifest.json`, `ml/models/model_card.json`, `ml/model_card.yml`, `ml/src/card.py` and
`app/public/models/{manifest,model_card}.json` are tracked and revert with `git checkout`. The
`.bst`/`.onnx` artefacts and `ml/artefacts/evaluation_metrics.json` are gitignored; the pre-landing
copies were kept for the session and the durable route back is `make ml-retrain ml-evaluate ml-onnx
ml-card app-models` once the params file is reverted. Nothing was committed.

> **CORRECTION 2026-09-19 (build-order audit): the last sentence and the `git checkout` route are
> both out of date.** All seven of those files were committed later the same day in **`44bb0ba`**
> ("Add log for re-tuning stint_life_regressor under honest split for v12 evaluation",
> 2026-09-19 15:46), which is the commit the log's own next history entry records as *"S1x
> hyperparameters and model card deployed to production."* `git status` is clean on every one of
> them, so **`git checkout <path>` now restores S1x, not the pre-landing state** — the instruction
> is inverted. The route back is `git checkout 44bb0ba~1 -- <paths>` (or `git revert 44bb0ba`),
> then the `make ml-retrain ml-evaluate ml-onnx ml-card app-models` chain, which is unchanged and
> is still the durable part.
>
> **Also worth recording, because nothing else in the tree does.** `stint_life_regressor_v12.bst`
> was retrained **in place** (mtime 2026-09-19 12:32, `aft_scale 0.753792882` in
> `ml/models/manifest.json`). The booster `08n` shipped as v12 on 2026-09-16 no longer exists on
> disk under any name. It is reconstructible — the refit is deterministic from the reverted params
> — but until it is reconstructed, `"the published v12 headline"` names **two different stint-life
> numbers** depending on date, and the gate-1a anchor `1.9913358778933028` recorded by `08e`
> (2026-09-17), `08h` (2026-09-17), `08i` (2026-09-18) and `10c` (2026-09-18) reproduces against
> **no** artefact now on disk. Three of those four are terminal; **`08i` is not** — it is `GATED`
> behind `D10`, and its stint-life column across all four thermal floors was measured on the
> retired booster.

### Verdict — MEASURED 2026-09-10 — **superseded on the v12 substrate**, see the verdict above

Every figure below was measured on the pre-`08m` warehouse (eval fold 20,272 laps / 9,270 green-pit)
and none of them reproduces today. The finding did survive: the 2026-09-19 re-run re-scored this
verdict's winner on v12 and it still wins. Read this section for its reasoning, never for its
numbers.

**The search moves the numbers, and it moves the half `10d` said would not move.** Re-run under the
`standard` label, on the training side only, selecting on green-pit IPCW-Brier, the search returns a
parameter set that is better than the incumbent on **calibration slope, on Brier, on AUC, and on the
level bias at the same time** — no trade. That was not the expected shape and the reason it happened
is not the one this doc predicted.

#### 1. Gate 1 — the instrument

Every honest baseline `10d` published was reproduced before anything was built on it, to every digit
`10d` printed, through `evaluate_10c.evaluate_mode` and again through this item's own harness:

| | reproduced | `10d` published |
| :--- | :--- | :--- |
| `10b` honest — Brier / AUC / slope | 0.205929 / 0.691432 / 0.666397 | 0.2059 / 0.6914 / 0.6664 |
| `standard` honest (`10d`'s A3) | 0.190290 / 0.693548 / 0.700013 | 0.190 / 0.6935 / 0.700 |
| `standard` in-sample (the shipped `.bst`) | 0.834378 AUC / 1.234564 slope | 0.834378 / 1.234564 |
| `10b` level diagnostics | intercept +0.2713, mean log bias −0.4342 | +0.271, −0.434 |
| `10b` 5-bin table | 0.058→0.330 · 0.186→0.386 · 0.345→0.492 · 0.512→0.590 · 0.732→0.780 | row for row |

**And one of `10d`'s own arms turned out to be under-described.** Its `C2` row —
"standard + depth 2", slope 1.0476 / AUC 0.6739 / Brier 0.1993 — does not reproduce from the shipped
params with `max_depth` set to 2, which return **1.0295 / 0.6833 / 0.1975**. It reproduces exactly at
`aft_loss_distribution_scale = 0.90`, A1's inner-CV optimum: **1.0476 / 0.6739 / 0.1993**. So `10d`'s
capacity arms were run at scale 0.90 and its table says only "depth 2". Recorded here because
[D4](../status/build-log.json) is a decision about that exact configuration.

The eval fold is unchanged: 20,272 laps, **9,270 green-pit**, **24 races**, no censoring inside the
green-pit stratum under either label construction.

#### 2. What the search did, including where it stopped

**Both declared searches stopped on `n_estimators = 200 (low)`** — with `learning_rate` at 0.0205
against a bound of 0.02. Those two axes multiply, so a search pinned on both is asking for a weaker
fit than the space can express. Per the pre-registration the bound was probed rather than read: the
low bound moved 200 → 50 (step 100 → 50, a strict superset of the old grid) and both searches re-ran
as **S1x** and **S2x**. It mattered — inner-fold Brier 0.1981 → **0.1764**, inner-fold `|slope − 1|`
0.3454 → **0.0915**.

| arm | space | selected | inner-fold value | boundary |
| :--- | :--- | :--- | ---: | :--- |
| S1 | as shipped | depth 10, 200 trees, lr 0.0205, scale 0.552, heavy `gamma`/`reg_lambda` | Brier 0.1981 | **pinned** `n_estimators` low |
| **S1x** | widened | **depth 8, 100 trees, lr 0.0219, scale 0.754, `reg_alpha` 2.64, `min_child_weight` 3, subsample 0.674, colsample 0.702** | **Brier 0.1764** | **interior on every axis** |
| S2 | as shipped | depth 3, 200 trees, lr 0.0255, scale 0.839 | \|slope−1\| 0.3454 | **pinned** `n_estimators` low |
| S2x | widened | depth 7, 50 trees, lr 0.0314, scale 0.953 | \|slope−1\| 0.0915 | **pinned again**, at 50 |

**S1x in full**, so the result outlives the scratchpad it was written to:

```json
{"aft_loss_distribution_scale": 0.7537929016487691, "colsample_bytree": 0.7022777269179408,
 "gamma": 0.00526088099298953, "learning_rate": 0.021917329940077092, "max_depth": 8,
 "min_child_weight": 3, "n_estimators": 100, "reg_alpha": 2.6396744208969904,
 "reg_lambda": 0.016254068532870026, "subsample": 0.6740434973007393}
```

Reproduce with:
`python -m ml.src.tune --target stint_life_regressor --trials 50 --folds 4 --honest-split
--censoring-variant standard --objective green_pit_brier --no-refit --version 10e_S1x
--studies-dir <scratch>/studies --best-params-out <scratch>/S1x_best_params.json`

**`10d` predicted the search would land on low depth. It did not.** S1x chose `max_depth` **8** — the
shipped value — and bought its fit reduction on the *shrinkage* axis instead: `n_estimators ×
learning_rate` falls **5.26 → 2.19**. Depth was the axis `10d` happened to be holding when it found
the effect; it is not the axis the search picks when allowed to choose freely. S2's declared winner
*was* depth 3, independently reproducing `10d`'s A4 pick from a different objective — so the depth
finding is real, it is just not the cheapest route to the same place.

**S2x pinned twice, so the pin was probed rather than reported.** A coordinate ladder in
`n_estimators` at S2x's other parameters, on the same inner folds and through the same
`tune._green_pit_objective`:

| `n_estimators` | 10 | 25 | **50** | 100 | 200 | 400 | 800 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| objective \|slope−1\| | 40.80 | 2.37 | **0.09** | 0.33 | 0.38 | 0.44 | 0.48 |
| slope | 41.80 | 3.37 | 1.016 | 0.672 | 0.619 | 0.563 | 0.521 |
| green-pit AUC | 0.684 | 0.679 | 0.668 | 0.655 | 0.652 | 0.647 | 0.640 |
| green-pit Brier | 0.427 | 0.296 | 0.186 | 0.194 | 0.210 | 0.216 | 0.223 |
| margin sd | 0.111 | 0.242 | 0.386 | 0.545 | 0.658 | 0.741 | 0.821 |

The optimum is **genuinely interior and happens to sit on the bound**: one step further down and the
objective is 26× worse, because the risk score becomes *under*-dispersed and the slope overshoots to
3.37 and then 41.8. That is `boundary_params`' own distinction — "the learner wants more" versus "the
optimum lives at the edge" — settled by the probe it says is the only way to settle it. It is a
**coordinate** probe and cannot see a joint move ([`epistemics.md`](../foundations/epistemics.md)); it
is used only to read one axis, which is the question the pin asks.

#### 3. The arms, on the 2024 eval fold

Green-pit stratum, n = 9,270, 24 races. Every configuration refit on 2018–2023 through
`evaluate._fit` on the identical split; only the hyperparameters differ. Bootstrap = 200 draws,
races the resampling unit, seed 20260910.

| arm | slope | boot 95% | AUC | Brier | mean log bias | intercept |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: |
| **A0** incumbent v11 | 0.7000 | [0.444, 0.933] | 0.6935 | 0.1903 | −0.2848 | +0.2234 |
| S1 brier (pinned) | 0.5803 | [0.394, 0.772] | 0.7071 | 0.1892 | −0.2087 | +0.2663 |
| **S1x brier** | **0.9034** | **[0.643, 1.190]** | **0.7154** | **0.1674** | **+0.0681** | **+0.0068** |
| S2 slope (pinned) | 0.8667 | [0.562, 1.266] | 0.6836 | 0.1934 | −0.3570 | +0.1835 |
| S2x slope | 1.2877 | [0.927, 1.720] | 0.7032 | 0.1803 | +0.3203 | −0.3206 |
| *ref:* `10d` C2 depth 2 | 1.0295 | [0.677, 1.420] | 0.6833 | 0.1975 | −0.3966 | +0.1489 |

Against A0's **own** gate-3 floor — measured under `standard`, this family's own label, five seeds
20260528–20260532 with XGBoost's `seed` varied: slope sd 0.011786 (floor 0.033337), AUC sd 0.001855
(floor 0.005247), Brier sd 0.000731 (floor 0.002066). **Note it is nearly twice `10d`'s 0.006208**,
which was measured under `10b` — `gates.md`'s rule against borrowing a floor across families earns
its keep here.

| arm | Δ\|slope−1\| | × floor | ΔBrier | × floor | ΔAUC | × floor |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| S1 | −0.1197 | −3.59× | +0.0011 | 0.54× | +0.0135 | 2.58× |
| **S1x** | **+0.2034** | **6.10×** | **+0.0229** | **11.06×** | **+0.0219** | **4.17×** |
| S2 | +0.1667 | 5.00× | −0.0031 | −1.49× | −0.0099 | −1.89× |
| S2x | +0.0123 | 0.37× | +0.0100 | 4.85× | +0.0096 | 1.83× |
| *ref:* C2 depth 2 | +0.2705 | 8.12× | −0.0072 | −3.50× | −0.0103 | −1.96× |

**Paired race-cluster bootstrap** — both arms scored on the same resampled races, which is the
instrument `10d` §4 ruled is the one to believe:

| arm | Δ\|slope−1\| | 95% | P | ΔBrier | 95% | P |
| :--- | ---: | :--- | ---: | ---: | :--- | ---: |
| S1 | −0.1144 | [−0.176, −0.038] | 0.005 | +0.0007 | [−0.005, +0.006] | 0.610 |
| **S1x** | +0.1731 | [−0.117, +0.273] | 0.930 | **+0.0237** | **[+0.0067, +0.0368]** | **1.000** |
| S2 | +0.1414 | [−0.177, +0.266] | 0.930 | −0.0027 | [−0.010, +0.004] | 0.265 |
| S2x | −0.0039 | [−0.636, +0.495] | 0.465 | +0.0119 | [−0.010, +0.034] | 0.830 |
| *ref:* C2 | +0.1492 | [−0.326, +0.378] | 0.835 | −0.0067 | [−0.016, +0.001] | 0.070 |

**The slope improvement inherits exactly the ceiling this doc warned it would**: +0.173 at P = 0.930,
an interval straddling zero, indistinguishable from `10d`'s +0.173 at P = 0.945. Twenty-four races
could not establish that then and cannot now.

**The Brier improvement does not.** +0.0237, 95% [+0.0067, +0.0368], **200 of 200 draws improve**. A
proper score evaluated per row has far less sampling variance than a slope fitted through five binned
points, so the same 24 races *can* resolve it. That is the one number in this item that clears its
own instrument at 95%, and it is the number the selection metric was.

#### 4. The level bias — the prediction, and where it broke

This doc predicted that a re-search optimising the slope would leave the level where it was. **For
the slope-selected arm that is exactly what happened**, and the reproduction is close to literal:
S2's mean log bias is **−0.3570** against A0's −0.2848, i.e. *worse*, matching `10d`'s
−0.434 → −0.560 on the `10b` label. Optimising `|slope − 1|` alone buys dispersion and pays for it in
level, twice, under both label constructions.

**The Brier-selected arm breaks the pattern, and the mechanism is that Brier prices the level and
`|slope − 1|` does not.**

| | 5 bins, predicted risk → observed risk | mean log bias | intercept |
| :--- | :--- | ---: | ---: |
| A0 | 0.105→0.296 · 0.249→0.403 · 0.409→0.513 · 0.566→0.603 · 0.759→0.763 | −0.2848 | +0.2234 |
| S2 | 0.136→0.299 · 0.272→0.403 · 0.377→0.539 · 0.484→0.597 · 0.647→0.739 | −0.3570 | +0.1835 |
| **S1x** | 0.274→0.238 · 0.431→0.423 · 0.576→0.526 · 0.700→0.627 · 0.836→0.764 | **+0.0681** | **+0.0068** |

A0 predicts **below** observed risk in all five bins; S1x predicts **above** it in all five. The bias
is not removed — it is **reduced 76% in magnitude and flipped in sign**, and the sign it flips to is
the conservative one: the gauge now says a tyre is slightly closer to finished than it turns out to
be, where the incumbent said it had life it did not have. For a number a pit wall reads as safe laps
remaining, those two errors are not equivalent, and this item does not get to call the flip a free
win — it is a smaller error in a better direction, which is a product judgment as much as a
statistical one.

Two-thirds of that came from the label, not the search: `10d` already measured the level bias at
−0.434 under `10b` against −0.285 under `standard`. D5 bought most of it before this item ran.

#### 5. Gates 2 and 4 — inapplicable in their literal form, and stated rather than skipped

**Gate 2** is an add-ablation. Nothing is added here: every arm is the same 32-column matrix under the
same label, fitted differently. The substituted requirement — "same split for every family in the
comparison", through `evaluate.py`'s own `_fit` — is met exactly; all six configurations share one
`_evaluation_split` and one set of eval rows.

**Gate 4** row-shuffles new columns, and there are none. `10d` declared the reseed null as the
substitute and it was run again here (§3's floor). But `10d` also wrote that "capacity is identical
between every arm and A0 … by construction", and **for a hyperparameter re-search that is false**:
`max_depth`, `n_estimators` and `learning_rate` *are* capacity, and capacity is the whole content of
the arm. There is therefore no information-versus-capacity decomposition available here, and the
e-value's null below is stated as what it is — "no difference beyond refit noise" — not as an
information null it cannot be. This is a correction to how `10d` phrased its own gate-4 substitution,
not a new hole.

#### 6. Gate 7 — the e-values, and the family they belong to

Construction B as declared, on five paired reseed deltas, `g = 1`. **Verified before use** per §4 of
the reference: 100k simulated draws of five i.i.d. `N(0, σ)` deltas return mean `E` = **0.999–1.000**
two-sided at every σ, and **0.70** with the one-sided truncation this item declared (a delta in the
wrong direction pays the minimum). `E[E] ≤ 1` holds; the construction is conservative by ~30%, which
is the price of orienting it. The reference's own worked example returns **17.05** against its
published 17.0.

| arm | Δ\|slope−1\| | `E_B` (slope) | ΔBrier | `E_B` (Brier) | `E_A` (slope, c = 1.5) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| S1 | −0.1197 | 0.408 | +0.0011 | 14.22 | 0.0007 |
| S1x | +0.2034 | 34.28 | +0.0229 | **35.88** | 2.1 × 10⁴ |
| S2 | +0.1667 | 34.31 | −0.0031 | 0.408 | 3.0 × 10³ |
| S2x | +0.0123 | 5.57 | +0.0100 | 34.64 | 0.79 |

**e-BH at α = 0.05 over the four declared arms rejects nothing.** The threshold for a lone rejection
in a family of four is `n/(αk)` = **80**, and the largest `E` is 35.9. Reported as declared, and it is
the right answer: an item that re-searched a parameter set on two objectives, then probed a boundary
and re-ran both, has spent four hypotheses and does not get to bank the best one at face value.

Construction A is again inflated — 2.1 × 10⁴ for S1x — for exactly the reason `10d` diagnosed: the
reseed sd measures refit noise, the cluster bootstrap puts sampling noise 8–16× higher. It is
reported because gate 7 says report what you declared, and it is not believed. **Three instruments,
and they disagree in public: S1x clears the reseed floor 6–11×, returns `E_B` ≈ 35, fails e-BH, and
is significant at 95% on Brier but not on slope.** All four statements are true and they are about
different questions.

#### 7. The metric the incumbent was tuned on, for completeness

`aft_nloglik` on the eval fold — the objective `tune.py` used to select the shipped params:

| | A0 | S1x | S2 | S2x | C2 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| all eval rows (the mixture) | **1.9878** | 2.1512 | 1.9783 | 2.3045 | 1.9966 |
| green-pit rows only | 3.4356 | **3.2837** | 3.4318 | 3.4163 | 3.4360 |

The incumbent is at or near the top on the mixture and last on the stratum. That is the cleanest
statement of what `10c` ruled and this item acted on: the two metrics rank the models differently, and
the mixture is the one the app does not care about.

#### 8. Answering the definition of done

**A tuned parameter set selected under a split and a metric that both match the estimand:** yes —
**S1x**, `censoring_variant=standard` (D5's realised stint ending), folds confined to 2018–2023, and
green-pit IPCW-Brier as the objective. Interior on every axis of the space that produced it.

**What it costs and buys against the honest incumbent:** it buys, and does not appear to cost.
Against A0 under the same label (slope 0.700 / AUC 0.694 / Brier 0.190): slope → **0.903**
(|slope−1| −68%, 6.1× floor), Brier → **0.167** (11.1× floor, and the only 95%-significant result
here), AUC → **0.715** (+0.022, 4.2× floor — an *increase*), mean log bias −0.285 → **+0.068**. Against
the definition-of-done's `10b`-label incumbent (0.666 / 0.691 / 0.206) the gaps are larger, but that
is not the like-for-like comparison and is not claimed as one.

**Landed? No — and unlike `10d`, not because the result is weak.** Three reasons, and only the third
is about the numbers:

1. **Landing is not this item's call.** `10e` is staged `SPEC` and the build order puts overwriting a
   shipped artefact behind a human decision. Nothing in `ml/models/` was touched: the search ran with
   `--no-refit` and wrote its params to the scratchpad.
2. **e-BH rejects nothing at α = 0.05.** The strongest arm returns `E` = 35.9 against a threshold of
   80. `04a`'s multiplicity finding exists to stop exactly the move of banking the best of four
   declared arms.
3. **The level bias flipped sign rather than closing**, and which side of zero a stint-life gauge
   should err on is the product question D5 answered for the *label* and did not answer for the
   *level*. A model that tells a pit wall the tyre is more finished than it is will be wrong in a way
   users notice differently from the incumbent's error, and that is worth a decision rather than a
   default.

**What this item does close.** The search defect `10d` named is fixed in the production path, not
worked around: `tune.py` now takes `--censoring-variant`, `--objective` and `--honest-split`, warns
when a survival search runs with the eval season inside its folds, and `--no-refit` lets a search be
read without republishing an artefact. The two bounds that were truncating this problem — `max_depth`
low and `n_estimators` low — are widened with the pins that moved them recorded in
`test_search_space.py`. `02b`'s noise floors can now be measured, and §3 already carries them for
both the incumbent and S1x.

#### 9. Deviations from the method above, logged

- **The pre-registered space was widened mid-item, once, under the declared boundary rule.**
  `n_estimators` low 200 → 50. The rule was written before any trial ran and the probe is reported as
  the extension it is (S1x/S2x), not folded into S1/S2. `max_depth` low 3 → 2 was declared up front.
- **Four arms, not two.** The boundary extensions are counted in the e-value family, which is why the
  e-BH threshold is 80 rather than 40.
- **The shrinkage ladder in §2 is post-hoc**, added after S2x pinned a second time, to answer a
  question the pre-registration named ("probe past the bound") but could not have specified a shape
  for in advance. It is a coordinate probe and is read as one.
- **`ml/models/encoders.json` was rewritten** by running gate 5 through its production entry point
  (`python -m ml.src.features --check` calls `load_features(persist_encoders=True)`). The content is
  byte-identical to `HEAD` — `git diff` is empty — but the ad-hoc-probe rule says not to touch
  `ml/models/*.json` and this is disclosed rather than buried.
- **Not run: a second widening below `n_estimators = 50`.** The ladder shows the objective 26× worse
  one step down, so the bound is no longer binding on the optimum and a third search would be
  chasing a question already answered.

---

## The product question this does not settle

From the app's point of view the pit wall's decision *is* arguably the thing to predict — a user
reading "remaining stint life: 11 laps" may want the realised answer, deployments included. That
is a genuine product call and it is the user's, not a statistical one.

It does not rescue the incumbent, because the incumbent answers **neither** question cleanly. It
answers the marginal mixture: a tyre limit contaminated by a deployment process it cannot see
coming, and a deployment process degraded by tyre variation. Splitting the causes lets the app
choose — and lets it show both. `int_sc_hazard_history` is exactly the term that recombines them.
