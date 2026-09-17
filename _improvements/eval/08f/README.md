# 08f-2 Evaluation — Does the circuit×constructor rebuild move the model's labels?

## Status
Preliminary probe, not a gate run. Scoped per the orchestrating session's instructions: measure
one thing, write it up, stop. No `GATED`/`MEASURED` verdict is claimed here and `build-log.json`
is untouched — the orchestrating session rules on what this means for 08f's status.

## The Question
`08f-2` (already built and shipped — `int_circuit_x_constructor_interaction.sql` rebuilt from
season-pooled `GROUP BY`s to point-in-time expanding windows) was originally meant to be gated by
testing `cliff_candidate_flag`. That measurement found the flag carries nothing (`08g`, `08j`) and
is now pruned from the model entirely — **that path is closed, not reopened here.**

The actual open question: `driver_skill_residual_s` is barred from ever being a model **input**
(`ml/src/schema.py::EXCLUDED_LEAKAGE_COLUMNS`, "causal leakage"), but it IS consumed inside
`fct_cliff_prediction_features.sql` to **construct** several of the model's actual **targets** —
`next_5_lap_cumulative_jump_s` (`DEGRADATION_TARGET`), `next_3_lap_cumulative_jump_s`,
`drift_s_per_lap`, and `laps_until_cliff_class` (`CLIFF_TARGET`). Nobody had measured how much
`08f-2` moves *those*.

## Method
Isolated-warehouse copy, same shape as `08g`'s `gate_before` target: bronze `external_location`
sources rebuilt into a scratch `data/gate_before.duckdb`, `dev.duckdb` never opened for write.
Built the full 39-model ancestor lineage of `fct_cliff_prediction_features` twice —
once as-shipped (AFTER), once with **only** `int_circuit_x_constructor_interaction.sql` reverted
to its pre-08f-2 content (BEFORE) — and diffed, row-matched on the mart's PK (`lap_id`) and the
interaction model's own grain (`race_year, race_id, constructor_id`).

**The revert commit needed independent verification.** `08g`'s note names `c7c8509` for a
*different*, combined `08e`+`08f-2` revert across two files. Checked directly with `git log
--follow` on this file alone: `c7c8509` predates an unrelated fix to this same file (pooling on
physical `circuit_id` rather than the event-slug `circuit_key`), so using it here would have
silently reverted that too. The commit that actually introduced 08f-2 in this file is `bbe3e48`
(2026-09-09, despite an unrelated commit message); its immediate parent in the file's own history,
`e5bcd35`, is the correct pre-fix content — confirmed with `git diff e5bcd35 bbe3e48 -- <path>`
showing exactly the `GROUP BY` → window-function rewrite and nothing else.

Cleanup done: `data/gate_before.duckdb` deleted, the `gate_before` profile block removed from
`transform/profiles/profiles.yml`, the SQL file restored via `git checkout HEAD --`. `git status`
confirms nothing persists.

## Headline

**`08f-2` moves the barred quantity it feeds substantially, and moves every actual model target
by exactly zero (float noise only), for a provable algebraic reason — not a small-sample
coincidence.**

- `circuit_constructor_interaction_s` changes on **all 1,456/1,456** (race, constructor) cells.
  Mean |Δ| = 0.086s (matches `08g`'s own scale estimate of ~0.08–0.11s), median 0.068s, max 0.514s.
  Largest in 2018 (mean 0.101s), smallest in 2024 (mean 0.063s) — the old pooled version leaned
  hardest on future seasons for the earliest data.
- `driver_skill_residual_s` (barred input) moves 1:1 with it on **99.7% of the 137,447 mart rows**
  (all of 2020/2023, 99.4–100% every other season). Mean |Δ| 0.084s, median 0.068s, max 0.514s.
- But `next_5_lap_cumulative_jump_s` (`DEGRADATION_TARGET`), `next_3_lap_cumulative_jump_s`,
  `drift_s_per_lap`, `laps_until_cliff_class` (`CLIFF_TARGET`), and even the legacy 1-lap targets
  are **unchanged to floating-point noise** (max |Δ| 1.8e-15 to 2.5e-14; **0 of 137,447 rows**
  cross a `laps_until_cliff_class` bucket boundary; **0 of 7,064 stints'** `drift_s_per_lap`
  moves beyond float error).

**Why, verified rather than assumed.** `circuit_constructor_interaction_s` has grain
(race_year, race_id, constructor_id) — one value per constructor per race, the same for every lap
of every stint that constructor ran. Because `driver_skill_residual_s` is `... −
constructor_component_s − ...` and `constructor_component_s = constructor_structural_pace_s +
circuit_constructor_interaction_s`, the 08f-2 shift is an **exact constant within every
(race_year, race_id, constructor_id) group** — measured directly: the largest within-group
standard deviation of the per-lap diff, over all 1,456 groups, is 6.7e-16. Every target this probe
checked is built from **within-stint** differences or an OLS slope of `driver_skill_residual_s`
against `lap_in_stint`, and a stint never spans more than one such group — so the constant cancels
out exactly, algebraically, not approximately. `anomaly_class` / `is_training_eligible` cancel the
same way (the trailing-MAD window in `int_lap_anomaly_flags.sql` is partitioned by
`race_year, race_id, driver_id`, which nests inside the same constant-shift group) — 0 rows flip
either. This is stated as a mechanism check, not a re-test of whether `cliff_candidate_flag`
carries information; that question stays closed.

**Instrument check passes.** Row/grain counts match production exactly on both builds
(137,447 mart rows, 1,456 interaction rows, 7,064 stints). Three columns with no path to the
08f-2 lineage — `push_residual` (family T, independent sibling), `fuel_mass_kg`,
`expected_compound_pace_s` — are bit-identical (max |Δ| = 0.0) between both scratch builds and
production `data/dev.duckdb` (read-only, never touched).

**`remaining_stint_life_laps` is out of the 08f-2 lineage, confirmed by trace, not rebuilt.**
Its source, `int_stint_end_regime.sql`, refs only `int_stint_geometry` and `stg_results`;
`int_stint_geometry` refs only `stg_laps`. No path to `int_circuit_x_constructor_interaction` or
`int_lap_residual_decomposed` exists, so it was not included in the isolated rebuild — there was
nothing to measure.

## Recommendation

**Negligible — in fact exactly zero, to float precision, for every target the model is trained or
evaluated against. No further target-integrity test (of the `08l`/`08m` kind) is warranted on this
question; 08f-2 can be signed off on this measurement alone, from the label-construction-integrity
angle.**

Plain-language version: 08f-2 does change a number that used to leak future seasons into the past
(`circuit_constructor_interaction_s`, and the barred `driver_skill_residual_s` it feeds) — that
part of the original defect story is real and was already worth fixing. But when the model builds
its "correct answers" from that number, it always does so by comparing one lap in a stint to
another lap in the *same* stint, and 08f-2's whole effect on a stint is to nudge every lap in it by
the *same* amount. Comparing two things that both moved by the same amount gives back the original
difference — so the labels the model is actually scored against come out identical. This is not a
sampling result that could look different with more data; it is an arithmetic identity, checked
over the entire 137,447-row population with nothing excluded.

**Scope note.** This probe answers only the label-construction question it was asked. It does not
re-examine whether `circuit_constructor_interaction_s` / `constructor_component_s` matter as
*features* rather than as label-construction inputs — a different question, and the one live
feature that chain reaches (`cliff_candidate_flag`, via `int_lap_anomaly_flags`) is already ruled
dead by `08g`/`08j` and stays closed here too.

## Files in This Folder (08f-2)
- `README.md` — this file
- `MEASUREMENTS.md` — full tables (season breakdown, percentile distributions, instrument check,
  mechanism check)
- Script: `scripts/measure_08f2_label_impact.py` (the read-only analysis half; its docstring
  carries the exact manual dbt steps used to build the two scratch snapshots — not run automatically
  since the scratch warehouse and profile block are deliberately not left on disk or in git)

---

# 08f-1 Evaluation — Gating the survival-weight season-lag, in isolation

## Status
**GATED, 2026-09-17.** This is the one piece of 08f that had never been gated in isolation (the
2026-09-09 run reverted `08e`+`08f-1`+`08f-2` together in one combined A/B, on a target `08m` has
since superseded — see the STALE banner at the head of `work/08-foundations-repair.md`'s `08f`
section). This run isolates 08f-1 alone, on the current v12/08m substrate, with 08e and 08f-2 left
exactly as shipped on both sides.

## The Question
`fct_cliff_prediction_features.sql` builds the quantile trio's IPW sample weight
(`survival_weight`) from `total_per_compound` / `stints_reaching`. Before 08f-1 (commit `bbe3e48`,
2026-09-09), both were pooled over every ingested season with no season key — a 2018 training
row's weight was partly estimated from 2024 (the eval season). 08f-1 rebuilt them as an expanding
sum over seasons strictly before the row's own. `survival_weight` is never a `FEATURE_COLUMNS`
member, so no column ablation can see it — it reaches the model only through `train.py`'s sample
weight for the quantile trio. Never gated on its own until this run.

**A correction surfaced while designing this gate, logged in `work/08-foundations-repair.md`'s
`08f` section.** The leaf doc describes the defect as reaching "both the fit and the metric"
(`evaluate.py:613` supposedly weighting the eval score too). Traced directly: `EvalSplit` carries
`w_tr` only (no `w_ev`), and `_score`'s quantile branch calls `T._headline(spec, y_true, pred)`
with no `meta`, so `pinball_loss` is unweighted at eval time in the code as it stands today (exactly
two call sites, `grep -n "pinball_loss(" ml/src/*.py`, neither weighted). The channel is fit-only.
This does not change the defect or the fix — a 2018 row's *training* weight was still partly
estimated from 2024 — it only narrows how that defect could reach the headline, which matters for
how this gate is designed (see Method).

## Method
Isolated-warehouse copy, same `gate_before` pattern as `08g` and this session's 08f-2 probe: bronze
`external_location` sources rebuilt into scratch `data/gate_before.duckdb`, `dev.duckdb` never
opened for write. Built the mart's ancestor lineage (`fct_cliff_prediction_features` +
`fct_stint_features`, 40 + 26 models) twice — AFTER (as-shipped, season-lagged) and BEFORE (only
`total_per_compound`/`stints_reaching`/`stint_survival` hand-reverted to their season-pooled,
pre-08f-1 form; `baseline_observations_n`, corner-inputs, qualifying and everything else left
exactly as shipped) — via `scripts/gate_08f1_survival_weight.py`.

**The commit, independently verified, not trusted from the leaf doc.** `git log --follow` on
`fct_cliff_prediction_features.sql`'s own history names `bbe3e48` (2026-09-09) as the commit that
introduced the season-lag rewrite; `git diff c7de693 bbe3e48 -- <path>` (its immediate predecessor
in the file's history) shows exactly that rewrite plus one unrelated bundled addition —
`baseline_observations_n`, 08e's companion column, from the same squashed commit. So the pre-08f-1
form is **not** `git show c7de693:<path>` wholesale (that would also strip `baseline_observations_n`
and the later 02b/02c columns) — it is a hand revert of exactly the three CTEs, applied on top of
HEAD. `bbe3e48` is the same commit that introduced 08f-2 in the interaction model — both halves of
08f landed in one squashed commit with an unrelated message ("Add SQL test for stint_end_cause
partitioning logic").

**Because `survival_weight` is a sample weight, not a feature, gates.md's add/drop-a-column
framework does not apply literally — translated, and declared before the arms ran (gates.md step
6; this is the pre-registration, written into `scripts/gate_08f1_survival_weight.py`'s docstring
before it ran):**

- Baseline arm `A` = **uniform weights** (w=1 for every row) — the zero point a weight-scheme
  ablation drops *to*, the direct analogue of "contract minus the family" for a column ablation.
- Arm `BEFORE` = the season-**pooled** IPW (what shipped pre-08f-1).
- Arm `AFTER` = the season-**lagged** IPW (current, shipped, what this gate is for).
- **Step 1 (instrument check)** = (a) AFTER refit reproduces the published v12 headline to 6dp on
  every target; (b) row-level diff of all 32 `FEATURE_COLUMNS`, every target, and the censoring
  flag between the AFTER and BEFORE snapshots — must be exactly zero, which licenses treating
  `cliff_classifier`/`stint_life_regressor` as structurally invariant without refitting them under
  BEFORE weights (they never consume `survival_weight` — `train.py::_sample_weight`'s
  classification arm computes balanced class weights from `y`, its survival arm returns `None` by
  design).
- **Step 2 (the gate's own question)** = AFTER vs BEFORE, both refit at the canonical seed via
  `evaluate.py::_fit`, scored via `evaluate.py::_score` (unweighted at eval time — a training-time
  effect only, per the correction above). Oriented positive = AFTER improves on BEFORE.
- **Step 3 (floor)** = `attribution.refit_noise_floor`, 5 reseeds, computed on both arms, quoted
  against the larger — identical convention to every other item in this tree.
- **Step 4 (permutation null, translated)** = row-shuffle the weight *vector* across training rows
  (there is no column to shuffle) — preserves the exact multiset of weight values (capacity)
  while destroying the (compound, lap_in_stint, season) alignment (information). Run for both
  AFTER and BEFORE.
- **Step 5 (feature-contract check)** = this change touches zero `FEATURE_COLUMNS` members (never
  one to begin with); `features.py --check` re-run this session against the untouched `dev.duckdb`.
- **Step 7 (e-value)** = Construction B (paired safe-t, same `g=1.0` as every other item), 5 seeds,
  on the information contrast gates.md always names — real AFTER vs its own row-shuffle, not
  AFTER-vs-BEFORE (that is step 2's question).

Cleanup done immediately after both builds: `fct_cliff_prediction_features.sql` restored via
`git checkout HEAD --` (confirmed clean diff), `data/gate_before.duckdb` deleted, the `gate_before`
profile block removed from `transform/profiles/profiles.yml`. `git status` confirms nothing
persists.

## Headline

**Every one of the five headline deltas (AFTER vs BEFORE) is inside its own reseed noise floor.
08f-1 is a real, substantial correctness fix whose effect on model performance is not
distinguishable from refit noise, on this substrate, at this sample size — a clean null, not a
failure to fix.**

| target | metric | AFTER (=published v12) | BEFORE (pooled) | delta | floor (2√2·sd) | ratio | clears? |
|:---|:---|---:|---:|---:|---:|---:|:---:|
| `degradation_regressor_p10` | pinball | 0.4764640778 | 0.4802231706 | **+0.00375909** | 0.00763075 | 0.49× | inside |
| `degradation_regressor_p50` | pinball | 0.9823587336 | 0.9840438286 | **+0.00168510** | 0.01115092 | 0.15× | inside |
| `degradation_regressor_p90` | pinball | 0.5128462338 | 0.5122840197 | **−0.00056221** | 0.00839541 | −0.07× | inside |
| `cliff_classifier` | macro F1 | 0.3524660979 | = AFTER (0 by construction) | 0.0 | n/a | n/a | structurally invariant |
| `stint_life_regressor` | AFT nloglik | 1.9913358779 | = AFTER (0 by construction) | 0.0 | n/a | n/a | structurally invariant |

AFTER's three quantile headlines reproduce `08e`'s own independent v12 re-read
(`08e_thermal_family_arms.json`'s `A+T` cell) to the digits shown — cross-validates both isolated
builds against a second, independently-run refit.

**Verified, not assumed.** `cliff_classifier`/`stint_life_regressor` invariance rests on two
independent checks: the code trace above (no path for `survival_weight` to reach either kind's
sample weight), and the row-level warehouse diff (0 of 32 `FEATURE_COLUMNS` differ, and the target
columns differ by exactly 0.0 — not float noise — between the AFTER and BEFORE snapshots for these
two targets). The quantile trio's targets carry float noise only (max |Δ| 8.62e-14 train / 6.75e-14
eval), the same order of magnitude as the threading non-associativity artifact `08e`/`08g` already
named (8.17e-14) and structurally unrelated to the CTE revert (no shared computation) — not a leak
in the isolation.

**The weight vector itself moves substantially — the null is not for lack of a real change to
weigh.** 93.3% of training rows (63,344 / 67,907) get a different `survival_weight` under AFTER vs
BEFORE; mean shifts 1.711 → 1.970, max per-row |Δ| 2.97 (against the [0.25, 4] clip range). So 08f-1
does what it is supposed to do — it substantially changes which rows the quantile trio is trained
to fit hardest — and that substantial reweighting still does not move any of the three quantile
headlines past their own noise floor on `eval_season` 2024.

**Secondary finding, out of 08f-1's own scope, recorded because it turned up in the same arms.**
Both weighting schemes underperform **uniform (no IPW at all)** on all three quantile heads:
AFTER-vs-uniform is −0.00534 / −0.00065 / −0.00345 (p10/p50/p90), BEFORE-vs-uniform is −0.00910 /
−0.00233 / −0.00289. AFTER is closer to uniform than BEFORE on p10 and p50 (smaller loss), fractionally
further on p90. This bears on whether IPW reweighting earns its place *at all*, not on whether the
season-lag improves it — a different, pre-existing question this tree has not gated, named here so
it is not lost. The permutation null adds a second observation in the same direction: on p10, the
*specific* row-to-weight alignment clears its floor as a real, information-attributed cost, for
**both** schemes alike (AFTER −1.30×, BEFORE −1.06×) — i.e. whichever weighting scheme is used,
its exact alignment (not just its aggregate distribution of values) makes p10 worse, at 2024. p50
and p90's permutation terms stay inside floor for both arms. None of this is a defect in 08f-1's own
season-lag rewrite — the sign and magnitude are similar whichever scheme is used — so it is recorded
as an open question about the IPW mechanism generally, not ruled on here.

**e-values (step 7), on the information contrast (real AFTER vs its own row-shuffle, 5 seeds,
Construction B, g=1.0 — the same construction and parameters as `08e`).** MC validity check passes
(mean E ≈ 1.00 ± 0.01 at four sigmas, matching `08e`'s own check). p10: E=2.11 (direction: shuffling
helps, i.e. AFTER's alignment costs pinball, matching the permutation-null finding above). p50:
E=2.00 (same direction, weaker). p90: E=1.78 (opposite direction — AFTER's alignment helps here).
Max attainable at n=5, g=1 is 36.0; none of these are close to it, and none would survive even a
single-item e-BH test. Negative controls (shuffle vs shuffle, H0 true by construction): p10 E=0.47,
p90 E=0.93 (unremarkable); **p50 E=8.76** is the largest number in this whole table and is recorded
rather than rounded away, exactly as `08e` recorded its own largest control (3.28 on p10) — it is a
control, not a headline finding, but it is the single largest E anywhere in this gate.

## Definition of Done
- No `known_leak` entry with `fixed_by: 08f` remains anywhere (already true, unaffected by this
  gate — verified: zero real entries in either `schema.yml`).
- Instrument check re-run and reported (step 1): AFTER exactly reproduces published v12 on all
  five targets; BEFORE differs from AFTER by 0 (structural targets) or float noise only (targets'
  own float-threading artifact, quantile trio).
- The three aggregations carry a season key (08f-1's own build, unchanged by this gate) and the
  re-measured headline is recorded here as the reference, with BEFORE named beside it — both
  requirements from the leaf doc's `08f` Definition of Done.
- Working tree restored to the AFTER (shipped) substrate; `git status` confirms nothing persists
  from the probe.

**Gates run.** 1 (instrument check, all five + row-level diff), 2 (the weight-scheme A/B, at the
canonical seed), 3 (each arm's own 5-reseed floor, larger quoted), 4 (permutation null, translated
to a weight-vector shuffle, capacity/information separated, both arms), 5 (`features.py --check`
this session — 32 features unaffected by this change), 6 (design pre-registered in the script's
docstring before it ran), 7 (e-value declared and computed on the information contrast, with its MC
validity check and negative controls). All seven steps addressed; none silently skipped.

## Overall 08f Verdict (both halves)

**08f is GATED on the current v12/08m substrate, both halves complete:**
- **08f-2** (circuit×constructor season-pooling): closed by the 2026-09-17 probe above — proven,
  over the full 137,447-row population, to move every actual model target by exactly zero (float
  noise), because its effect is a per-(race_year, race_id, constructor_id) constant that every
  target's within-stint construction cancels exactly. No add-ablation gate is meaningful for a
  change that provably touches zero live features and zero targets; this is not re-measured here,
  per the orchestrating session's scoping.
- **08f-1** (survival-weight season-lag): gated in isolation above. A real, substantial fix
  (93.3% of training-row weights change) whose effect on all five headline metrics is inside noise
  — a clean null.

Both halves resolve `known_leak`/pooling defects that `08b`'s audit found real. Neither buys nor
costs detectable headline performance on the current substrate — which is a different outcome from
`08e` (family T clears its floor as a genuine win) and from the original combined `08e`+`08f`
step-1 re-baseline (removing the leakage cost headline performance on the old, pre-08m target).
08f's own fixes, measured cleanly in isolation on the current target, cost nothing and win nothing
detectable — they are simply correct.

## Files in This Folder (08f-1)
- `08f1_gate_arms.json` — every fit's headline, per seed, weight-vector summaries, permutation-null
  and e-value detail for all five targets
- `08f1_gate_arms.log` — generation log
- Script: `scripts/gate_08f1_survival_weight.py` (three-stage: `export-after` / `export-before`
  against the isolated warehouse, `analyze` — pure pandas/numpy — from the two snapshots; its
  docstring carries the exact manual dbt steps and the full pre-registered design)
