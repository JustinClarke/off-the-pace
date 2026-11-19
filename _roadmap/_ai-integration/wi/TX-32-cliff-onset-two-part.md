# TX-32 — Constructor cliff onset: split into timing (laps) and post-cliff cost (rate)

**Group:** 1 transform · **Depends on:** TX-30, TX-29, DM-05 · **Model / cost:** `sonnet-5`, 6.5d (+0.5d if the stopgap is chosen)
**Owner decisions (OPEN, none ruled):** HD29, HD30, HD31, HD32, HD33, HD34. Nothing below is built until they are ruled.

**How to run:** own scratch folder, copy named `dev.duckdb`, 1 thread. Never write `data/dev.duckdb`, `data/bronze/`, `data/fits/` or `app/public/data/`. Nothing staged or committed by an agent. No re-export without the owner's yes (rule 7).
**Class:** transform class (ghost chain, held behind HD20 via DM-05). ML use is a separate, later step (see "ML as-of rule").
**Evidence:** `_evidence/cliff-onset-downstream.md` (Opus read-only review, 2026-11-18). Line numbers below were re-checked on the working tree on 2026-11-18.

**This doc is a plan, not a ruling.** Each "recommended" choice is the planner's recommendation. The six marked decisions are the owner's. Any other method choice in this doc that the owner disagrees with becomes a seventh decision before the build starts (rule 10).

---

## Problem

`int_constructor_deg_sensitivity.cliff_onset_shift_laps` (`:560-581`) is meant to say how many laps earlier or later a constructor's tyre cliff arrives than the field's. It is computed as `-hinge_dev_shrunk * ref_depth / severity_used`. The numerator is in seconds and the divisor `severity_used` is a step height in seconds, so the result has no units. It is 1/2.5 of a lap count, because the intended divisor was the ramp slope `plateau / 2.5`. The shape is also wrong. The hinge coefficient measures an extra post-onset *slope*, and the field curve has been a saturating ramp since CO-02 (flat 2.5 laps past onset). At `ref_depth` (5 to 8 laps, on the plateau), moving the onset changes the penalty by zero, so the matching rule has no solution. The one number is used both as a timing (shifting stint age inside the ramp in `fct_ghost_car_pace`) and as an uncertainty exposure (`fct_ghost_race_finish`). It is right for neither use. In addition, 0 means two things ("thin cell" and "no cell"), its SE is the raw hinge SE rather than a posterior sd, and the SE exposure counts plateau laps (about 26.5% of published rows) as active. The KNOWN DEFECT note at `:440-472` records this and leaves it unfixed.

## Consumers (complete)

Only `fct_ghost_car_pace` reads the source model. Nothing in `ml/src`, `app/src` or `scripts` reads any `*cliff_shift*` or `*cliff_active*` column (grep, 2026-11-18).

| Consumer | Where | Use today |
|---|---|---|
| `fct_ghost_car_pace` CTE `deg_sensitivity` | `:165-176` | source read of shift and SE |
| `cliff_interaction_s` | `:245-281` | shift subtracted from stint age inside `cliff_ramp_frac`, times the plateau, clip +/-2 s, added to the predicted lap |
| `host/ego_cliff_shift_laps` | `:243-244` | output column, COALESCE 0 |
| `host/ego_cliff_shift_se_laps` | `:295-296` | passthrough, NULL when no estimate (TX-18) |
| `host/ego_cliff_active` | `:304-319` | 1 when past the shifted onset; SE exposure |
| `fct_ghost_race_finish` | `:85-89`, `:198-203`, `:230-234` | `se_laps * mean_severity * frac_active` in the host term and in `var_self` |
| Tests | `assert_cliff_hinge_centering.sql:19`, `assert_low_sample_cliff_cells_unshifted.sql`, `intermediate/schema.yml:1524-1567`, `marts/schema.yml:1036-1091`, `tests/data_profile.baseline.json` | |

---

## Method A — cliff timing, in laps

**Estimand.** For each (constructor, compound, season) cell: how much later (+) or earlier (-) this car's cliff starts than the field's, in tyre-age laps, with a posterior sd.

**Data.** One row per race stint on a slick compound, from the stint/lap spine on the TX-30 build.
- **Event:** the stint's cliff lap. Which detector is HD29. The recommendation is the field's own detector, `transform/tasks/coefficients/survival.py::detect_cliff_lap`. It is keyed on `age_in_stint`, which is the same odometer as `compound_cliff_onset_laps` and the ghost recombination. The field KM onset is fitted from it. Using a different event for the constructor than for the field would make "relative to the field" compare two definitions. `fct_stint_features.cliff_lap_in_stint` (from `cliff_candidate_flag`) is keyed on `lap_in_stint` and was pruned as an ML feature in 08j, so its quality as an event is unmeasured. Step 0 measures the agreement between the two.
- **Duration:** the age at the event; else the age at the stint's last lap.
- **Censoring (right):** the stint ends without an event (voluntary pit, safety-car stop, non-tyre DNF, chequered flag). A tyre-failure DNF counts as an event, as `build_survival_dataset` does. Stints that pit *before* the cliff are kept as censored rows, which is the main gain over the hinge regression (that regression cannot see them).
- **Covariate carried, not filtered:** `is_fresh_tyre` (scrubbed sets), as the field fitter does.

**Model.** Log-normal AFT, the same family as `ml/src/survival.py`, fitted in Python under `transform/tasks/coefficients/` (a new `fit_constructor_cliff_timing.py`). It is not SQL.
- `log T = mu[season, compound] + gamma[circuit] + delta * is_fresh_tyre + b[constructor, compound, season] + sigma * eps`.
- Fixed effects: season x compound, and circuit. These absorb the field onset level, so `b` is relative to the field.
- **Shrinkage (two-stage, matching the current SQL machinery).**
  - Stage 1: fit `b` per cell as a fixed effect with a small ridge penalty, read `b_raw` and `se_b` from the observed information.
  - Field-centre `b_raw` per (compound, season), with a precision-weighted mean of 0.
  - Stage 2: DerSimonian-Laird `tau2` per (compound, season), then `b_shrunk = b * tau2 / (tau2 + se_b^2)` and `sd_post = sqrt(1 / (1/se_b^2 + 1/tau2))`. This is the same form as `deg_slope_posterior_sd_s_per_lap` (`:545-550`).
  - A full random-effects AFT (frailty) is possible but heavier. The recommendation is two-stage, for consistency with the deg slope and the hinge.

**Output (per cell, new columns in `int_constructor_deg_sensitivity`, or a new `int_constructor_cliff_timing` it joins):**
- `cliff_time_ratio = exp(b_shrunk)` and `cliff_time_ratio_sd` (delta method: `exp(b_shrunk) * sd_post`).
- `cliff_onset_shift_laps = field_onset * (exp(b_shrunk) - 1)`, where `field_onset` is the cell's (compound, season) `compound_cliff_onset_laps` median, for display. Its sd is `field_onset * exp(b_shrunk) * sd_post`.
- `cliff_onset_shift_sd_laps` (posterior sd, the replacement for `cliff_onset_shift_se_laps`), `n_events`, `n_censored`, `is_low_sample_cliff`.
- **The ghost applies the ratio, not the cell-level lap count.** On each ego lap it uses `A = onset_lap * (ratio - 1)` with that lap's own circuit onset, so a 0.9 ratio is about 2 laps at a short-onset circuit and 4 at a long one. This is a recommendation. If the owner prefers a single lap count per cell, it becomes a decision.

**Clip.** HD32. The recommendation is to drop the +/-3 clip, because shrinkage is the regulariser. A schema range test at +/-8 laps would stay as an alarm only.

## Method B — post-cliff extra cost, as a rate

**Estimand.** The extra seconds per lap, per lap past onset, that this car loses once past its cliff, compared with the field: `cliff_post_slope_dev_s_per_lap2`.

- Keep the existing hinge regression (`cliff_beta` / `cliff_centered` / `cliff_tau`, `:352-436`) and its EB shrinkage. Re-centre the hinge at the **constructor-shifted onset from A**, `hinge = GREATEST(0, age - onset - A)`, so that timing and post-onset cost are not counted twice.
- Publish `hinge_dev_shrunk` **as the rate**, with its posterior sd (same form as the deg slope; `tau` for thin cells per HD31).
- **The divisor is deleted, not replaced.** `severity_used`, `cliff_sev` and the 0.30 floor have no role in B. The KNOWN DEFECT note at `:440-472` is closed by removal: no rate-scale floor is needed because nothing is divided.
- **Capped exposure:** `capped_depth = LEAST(laps_past_onset, H)`, where H is HD34. The recommendation is H = `compound_wear_hold_after_onset_laps` (5.0, `dbt_project.yml:134`). The cap keeps the term bounded and outlier-robust without a clip.

## Recombination in `fct_ghost_car_pace`

`cliff_interaction_s = plateau * [ramp(age - onset - A_h) - ramp(age - onset - A_e)] + (B_h - B_e) * LEAST(lpc, H)`

- `ramp` = existing `cliff_ramp_frac`, `plateau` = existing `cliff_plateau_s`.
- When ego == host the result is exactly 0. This is the test that must keep holding.
- The +/-2 s clip: the first term stays bounded by the plateau. The second term is bounded by `|B_h - B_e| * H`. Keep the clip as an inert guardrail plus a test that it never binds. Whether to keep it is covered by HD32, which applies to both clips.

**Columns changed** (marts/schema.yml updated to match):
- `host/ego_cliff_shift_laps` become true laps (A). Add `host/ego_cliff_post_slope_dev_s_per_lap2` (B).
- `host/ego_cliff_shift_se_laps` are replaced by `*_cliff_shift_sd_laps` and `*_cliff_post_slope_sd` (posterior sds).
- `host/ego_cliff_active` are **removed** and replaced by two exposures per car:
  - `*_cliff_in_ramp_s_per_lap = (plateau / ramp_span) * 1[0 < age - onset - A < ramp_span]`
  - `*_cliff_capped_depth_laps = LEAST(GREATEST(age - onset - A, 0), H)`
- Add `*_cliff_is_low_sample` (from the source) alongside the existing `*_deg_slope_is_prior`, so "thin, shrunk to field" and "no cell, filled" stay distinguishable.

## Changes in `fct_ghost_race_finish`

- `race_totals` (`:80-90`): drop `host/ego_cliff_se`, `mean_severity` (for this term) and `frac_*_active`. Add `AVG` of both shift sds, both B sds, `in_ramp_s` and `capped_depth` per car.
- Variance (`:198-203`):
  - host term: `host_cliff_A_term = sd_A_h * mean(in_ramp_s_h)` and `host_cliff_B_term = sd_B_h * mean(capped_depth_h)`, kept separate for the pairwise step exactly as `host_slope_term` is.
  - `var_self` gets `(sd_A_e * mean(in_ramp_s_e))^2 + (sd_B_e * mean(capped_depth_e))^2`.
- The downstream pairwise `sd_diff`, `p_beats_next` and `finish_pos_se` structure is unchanged. Under HD31 = tau, a thin cell no longer turns the whole scenario's `finish_pos_se` NULL. Only a missing cell does that, and HD20 rules on missing cells.

## Stopgap (x2.5) — ship first or not (HD30)

- **What it is:** divide by `plateau / 2.5` instead of `severity`, which makes the stored value 2.5 times larger. To keep the finish SE from also growing 2.5x, `fct_ghost_race_finish` must at the same time change `mean_severity` in the cliff term to `mean(plateau) / 2.5`. So it is a two-file change, not one line.
- **What it does not fix:** the value is still a slope presented as a timing, has no fitted ramp-window basis, still mixes "thin" and "missing" as 0, and still counts plateau laps in the exposure.
- **Cost:** 0.5d plus a full diff, and it moves the published numbers twice (now, then again at A/B).
- **Planner's recommendation (not a ruling):** do not ship it. Go straight to A/B. Until then, the ghost method note should say the cliff-timing term is an interim value under repair. The term is small (mean |cliff_interaction_s| 0.089 s on 5.1% of rows; scenario mean 0.004 s against 0.147 s for the deg term), so a second move of published numbers costs more than the gain. If the owner wants it, it belongs in TX-30's single diff review (step k), so that the re-export count stays at one.

## Thin-cell and missing-cell rules

| Case | Point | sd | Flag | Ghost mart |
|---|---|---|---|---|
| Qualifying cell | shrunk A, shrunk B | posterior sd | — | used as is |
| Thin cell (below the minimum events / stints) | 0 (field-timed by prior) | prior `tau` (HD31 rec.) or NULL | `is_low_sample_cliff = TRUE` | used; flag carried as `*_cliff_is_low_sample` |
| No cell (constructor never ran the compound that season) | NULL | NULL | — | per HD20 (via DM-05): today a 0 fill with `*_deg_slope_is_prior` |

- **Thin-cell threshold for A.** The planner proposes, for the owner to confirm, `n_events >= 5 AND n_stints >= 8` per cell. The value is set from the step-0 count, which reports how many cells each threshold leaves thin. B keeps today's `cliff_qualifies` rule (`:386-392`: `n_post >= 30`, `n_deep >= 15`, `n_stints_cliff >= 5`).
- **`tau2 <= 0`** (no between-constructor spread): the shrunk point is 0, and the posterior sd should be the stage-1 `se_b`, not 0. AUD-13 records the existing deg-slope case at `:548` as an SE fill. Do not copy that 0 here. HD27 covers the existing site.
- A thin cell is never treated as "known field-timed". The app shows it as a wide band.

## App pictures to support (data contract only; page work is a later AP item)

1. **Cliff timing per team.** For each compound and season, one dot per constructor with its interval, on an axis relative to the field onset at 0 laps. Needs per cell: `cliff_onset_shift_laps`, `cliff_onset_shift_sd_laps` (band = +/- 1.96 sd, or quantiles of the log-normal ratio), `is_low_sample_cliff`, `n_events`, `n_censored`. Thin cells must draw a wide band, not a confident dot.
2. **Predicted lap-time curve per team with the cliff marked.** The field curve (wear + ramp + plateau), the team's curve shifted by A, a vertical onset line with a band for A's interval, and B drawn as the widening gap after the plateau. Needs: field `compound_cliff_onset_laps`, `cliff_plateau_s`, wear gradient, the cell's ratio and sd, B and its sd, and H. It plugs into `features/tyre-cliff-survival` (field KM onset per compound already) and `routes/ghost-car/lap-chart.tsx` (stub).

`int_constructor_deg_sensitivity` is not exported today. Picture 1 needs either a small new mart (`mart_constructor_cliff_timing`) or an export of the cell table. That is a new published artifact, so it waits for the owner's export yes. This item builds the columns and stops there.

## ML as-of rule (HD33)

- No ML model reads this value today. Its natural user is `cliff_classifier` (`ml/src/schema.py:298, 367, 403`; target `laps_until_cliff_class`). That model's features carry only the field cliff (`compound_cliff_onset_laps`, `laps_past_cliff`, `schema.py:142-146`).
- **The in-season A must never enter ML.** It is fitted on the same season's stints, including the post-onset laps of the stints being predicted, which is target leakage for a cliff classifier.
- If HD33 admits it, the feature is an **as-of A**: for race r, fitted only on races strictly before r (the T48 rule the isolation marts follow). It is published as two columns, the point in laps plus `sd`, with the thin flag as its own column rather than a bare 0. It passes `holdout_guard.py` (TX-29: nothing reads 2025+ for a fit). Admission goes through the usual ablation gate on the retrained models.
- That is ML-track work after ML-01 (held behind AX-20), not part of this item. This item only writes the fitter so that an `as_of_race` cut-off is a parameter.

## Published numbers that move

Every option, including the stopgap, moves these.

- **`fct_ghost_car_pace`** (exported): `host/ego_cliff_shift_laps`, the SE columns (renamed), `cliff_interaction_s` (non-zero on 70,426 of 1,384,558 rows on the Nov-8 export; mean |.| 0.089 s, max 0.86 s), `predicted_lap_time_s`, `predicted_residual_pace_s`, `delta_vs_actual_lap_s`. `*_cliff_active` is removed and new columns are added.
- **`fct_ghost_race_finish`:** `predicted_mean_lap_s`, `predicted_mean_residual_pace_s`, `predicted_total_race_time_s`, `predicted_mean_lap_se_s`, `p_beats_next`, `finish_pos_se` (every row, because the exposure changes), and `predicted_finish_position` where a rank flips. Under B (rate x depth up to 5) flips can be larger than under x2.5. Count them.
- **App:** `hidden-performance` (`predicted_finish_position`, `finish_pos_se`) and `counterfactual-championship` (`predicted_mean_lap_s`).
- **Tests and baselines:** `data_profile.baseline.json`, `assert_cliff_hinge_centering.sql`, `assert_low_sample_cliff_cells_unshifted.sql`, both schema.yml blocks, `model_hashes*.baseline.json` (re-taken only after the owner accepts the diff).

## Test plan

**Python (fitter, `transform/tasks/coefficients/tests/`):**
1. Synthetic stints with a known per-constructor time ratio, about 50% censored. `b` is recovered within 2 se, and a fit that drops the censored rows is visibly biased (regression guard).
2. A thin cell gives point 0, sd = `tau`, flag TRUE. A `tau2 = 0` cell gives sd = `se_b`, not 0.
3. Field-centring: the precision-weighted mean of `b` per (compound, season) is 0 within 1e-9.
4. The as-of cut-off: a fit for race r reads no stint from race >= r. `holdout_guard` refuses 2025+ input.
5. Provenance columns are written like the other seeds (`test_seed_param_provenance.py` pattern).

**dbt (scratch build only):**
6. When ego == host, `cliff_interaction_s = 0` exactly (keep or extend the existing check).
7. Range alarms: `cliff_onset_shift_laps` within +/-8, `cliff_time_ratio` within (0.5, 2), B within a band set from step 0, every sd >= 0.
8. sd is NOT NULL wherever a cell exists (if HD31 = tau). NULL only where the cell is missing.
9. `assert_low_sample_cliff_cells_unshifted.sql` is rewritten: point = 0 and sd = tau (not NULL).
10. `assert_cliff_hinge_centering.sql` is rewritten for B: no severity, the weight is `1/se^2` of the rate.
11. Exposures: `in_ramp_s_per_lap` within [0, plateau/2.5] and 0 on every plateau lap; `capped_depth_laps` within [0, H].
12. The +/-2 s clip never binds (count = 0), if the clip is kept.
13. `fct_ghost_race_finish`: `finish_pos_se` is non-NULL on every scenario whose cells all exist (counts against the TX-30 baseline).

**Diff (scratch vs the TX-30 accepted build):** rows moved and size of move for every column in "Published numbers that move", rank flips per season, and the share of thin cells per compound-season. These go to the owner as one diff review.

## Sequence

0. **Measure (read-only, 0.5d), on the TX-30 accepted scratch build.**
   - Per (constructor, compound, season), count stints, `detect_cliff_lap` events and `cliff_candidate_flag` events.
   - Measure the agreement between the two events (same stint, lag in laps).
   - Count how many cells each candidate threshold leaves thin.
   - The result feeds HD29 and the thin threshold. **Recommended first step.**
1. Owner rules HD29 to HD34 (and confirms the thin threshold and the per-lap ratio application).
2. If HD30 says stopgap: do it inside TX-30's step k, not here.
3. Write `fit_constructor_cliff_timing.py` and its Python tests (A, two-stage, with `as_of_race` as a parameter). Output: a seed or a table under the scratch folder only (3d).
4. Join A into `int_constructor_deg_sensitivity`. Rewrite the hinge at the A-shifted onset. Publish B as a rate. Delete `cliff_sev`, the divisor and the clip as ruled. Update `intermediate/schema.yml` (1d).
5. `fct_ghost_car_pace`: new recombination, two exposures, flags. `fct_ghost_race_finish`: new variance terms. Update `marts/schema.yml` (1d).
6. Rewrite and add the dbt tests above. Re-take `data_profile.baseline.json` on scratch only (0.5d).
7. Full scratch build, diff, rank-flip count. One owner diff review (0.5d).
8. Re-export and hash baselines only on the owner's yes. App pictures and the ML as-of feature are filed as follow-up items when the owner schedules them.

## Effort

| Step | Days |
|---|---|
| 0 measure | 0.5 |
| 3 fitter A + tests | 3.0 |
| 4 source model (A join, B rate) | 1.0 |
| 5 ghost marts | 1.0 |
| 6 tests and baselines | 0.5 |
| 7 build, diff, review pack | 0.5 |
| **Total** | **6.5d** (+0.5d if the HD30 stopgap is chosen, in TX-30) |

## Done when

- `cliff_onset_shift_laps` is a lap count with a posterior sd.
- B is published as a rate with no severity divisor.
- `*_cliff_active` is replaced by the two exposures.
- Thin and missing cells are distinguishable in both ghost marts.
- Every test above passes on scratch.
- The owner has reviewed the one diff.

## Sources

`transform/models/intermediate/int_constructor_deg_sensitivity.sql`, `transform/models/marts/fct_ghost_car_pace.sql`, `transform/models/marts/fct_ghost_race_finish.sql`, `transform/tasks/coefficients/survival.py`, `transform/tasks/coefficients/fit_compound_cliff.py`, `transform/tasks/coefficients/holdout_guard.py`, `transform/macros/compound_cliff_wear.sql`, `transform/models/marts/fct_stint_features.sql`, `ml/src/survival.py`, `ml/src/schema.py`, `_evidence/cliff-onset-downstream.md`.
