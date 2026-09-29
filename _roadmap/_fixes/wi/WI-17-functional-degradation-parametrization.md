# WI-17 — Functional degradation parametrization: power-law tyre curves for the Degradation Simulator

**Group:** 06 publication (the browser simulator) · **Depends on:** nothing on this board ·
**Blocker:** none. W49 (success criteria) is RULED -- Option A, graded on fan-facing accuracy
(see *Success criteria*).

**Findings:** none from the audit. This is a new capability, requested 2026-09-28. It is **not** F40:
F40 is "equal-car rating compares P20 vs teammate median" (`WI-14b`, gated by `FD5`), and it has
nothing to do with tyres. The nearest board context is W25 (do not re-export
`fct_cliff_prediction_features` before a retrain) and W26 (the simulator sends NaN for a contract
feature it cannot supply). This item's design is constrained by both.

**Cost:** 2-3d · **Model:** `fable-5.1`. The failure mode here is a plausible-looking number, not an
error. Per-stint power-law parameters are poorly identified (see *Read first*), and an R² against
noisy targets reads fine while meaning nothing. That is the vocabulary's case for `fable-5.1`.

---

## What this builds

The simulator's tyre term is replaced by a two-number curve, `Δt(age) = α · age^β` seconds over the
fresh-tyre pace, where `α` and `β` come from a small model fed by track, conditions and a
**compound hardness rank**, not a compound name. The pieces:

1. **Fits in dbt.** Power-law fits of every historical stint's degradation, in SQL.
2. **A predictor.** An XGBoost model that predicts `(α, β)` from features the simulator can actually
   supply.
3. **An ONNX export under 500 KB**, with a TypeScript curve function the simulator can call.

Compound identity enters only as the hardness rank (and an era flag), so a renamed or reformulated
compound is a new row of data rather than a new feature contract.

### What it solves, and what is actually true about each claim

| Requested claim | What holds | What does not |
| :-- | :-- | :-- |
| Handles 2018 legacy names through 2025 C6 without retraining | 2018 laps already carry absolute compound names (HYPERSOFT…HARD), so they map onto one declared hardness scale without the seed. 2019+ come from `compound_code`. | Trees do not extrapolate. A model that has not seen rank 6 predicts C6 exactly as C5. C6 is 59 laps in the whole warehouse (2025, three races). "Without retraining" means "gives C5's curve", and T54 measures how wrong that is. |
| A compound formula change means new `(α, β)`, not a model rebuild | The dbt fits re-run on new stints with no code change. The feature contract (hardness rank, era, track, conditions) does not move. | The predictor still needs a **retrain** (minutes, not a rebuild) for a new compound to move its predictions. Nothing learns from data it has not been trained on. |
| Tiny ONNX footprint | Two small tree ensembles. Size is set by trees × depth, and a few hundred KB is realistic. | — |

Today the coupling this removes is real. `inputs.ts` hard-codes `COMPOUND_DEFAULTS` by compound
**name** (HARD…HYPERSOFT, no C-codes), and `mart_degradation_history_envelope` keys its cells on the
**relative** label (SOFT at Monaco and SOFT at Bahrain are different rubber, in one cell each).

---

## Read first: pre-flight probe (2026-09-28)

The requested success criteria were checked before anything was specced, against `data/dev.duckdb`
(read-only), with throwaway scripts in the session scratchpad.

**Lap set.** Laps come from `int_lap_residual_decomposed` with the envelope mart's filters:
`correction_weight = 1`, no SC/VSC/red, not a major outlier, slicks only. The target is
`y = weight_corrected_lap_time − rubber_component_s`, fit as `y = c + α · age^β` with β profiled on a
grid of 0.20–3.00 in steps of 0.05.

**Per stint** (6,390 stints with ≥ 8 clean laps and an age span of at least 7):

| Quantity | Value |
| :-- | :-- |
| Per-stint R², p10 / p25 / **p50** / p75 / p90 | 0.07 / 0.22 / **0.50** / 0.74 / 0.87 |
| Share of stints with R² ≥ 0.85 | **11.6 %** (8-15 laps 12.4 %, 15-25 laps 12.7 %, 25+ laps 9.4 %) |
| Median R² gain of the power law over a straight line | 0.041 |
| β at the grid edge (0.2 or 3.0), 1,500-stint subsample | **58.5 %**. β is not identified per stint |
| Reliability ceiling¹ for predicting per-stint β / α | **0.49** / **< 0**, the best R² *any* feature set could reach |

**Pooled per (race, compound) cell** (388 cells, each with stint intercepts and a shared `(α, β)`):
median within-cell R² is 0.30, 28 % of cells land β on the grid edge, and the reliability ceiling¹
is α < 0, β 0.42, and 0.20 for the curve value at age 15.

¹ `1 − mean(bootstrap sampling variance) / cross-unit variance of the estimates`: residual bootstrap
for stints, stint-cluster bootstrap for cells, 40 reps each. This is rough, but the direction is not
in doubt.

**What it means.** Over 8-30 laps of real F1 lap times, `α` and `β` trade off against each other and
cannot be told apart, and the curvature the power law adds is small (R² +0.04 over a line). The fuel
correction is linear in lap number, and so is tyre age within a stint, so any error in the fuel
model lands directly on the degradation fit. Two of the four requested criteria therefore cannot pass
as written:

- **"Fit explains ≥ 85 % of variance per stint"** fails on 88 % of stints, and it measures lap-time
  noise rather than curve adequacy.
- **"(α, β) prediction R² ≥ 0.70"** sits above the measured ceiling for both parameters. No model
  can reach it against those targets.

The decision (W49, ruled 2026-09-28: Option A) is recorded under *Success criteria*. The build's own
Step 0 re-measures the ceiling properly, on the final target definition, before any training.

---

## Inputs and what must not be read

**Reads:**

- `int_stint_geometry`: stint identity, `age_in_stint` (which is tyre life, so used sets are handled),
  `compound_in_stint`, `compound_code`.
- `int_lap_residual_decomposed`: `weight_corrected_lap_time`, `rubber_component_s` and the lap
  filters. `fct_cliff_prediction_features` does not carry lap time.
- `fct_cliff_prediction_features`: track and condition features, **allowlist only** (below).
- `race_to_track` and `dim_circuits`, to join the P3 accuracy basket.

**Must not read (the F2/FD3 guard).** This is what keeps the item off `FD3`. `FD3` is open on whether
the compound seed may be fitted on the race it scores. Nothing here may consume that seed, or
anything priced from it:

- `compound_cliff_params` and every `compound_*` column it feeds (grip peak, wear gradient, optimal
  temps, cliff onset, cliff severity);
- `int_compound_cliff_predicted` and its outputs: `expected_compound_pace_s`,
  `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`;
- `compound_component_s`, and anything net of it (`driver_skill_residual_s`, `pace_delta_s`, the label).

Filtering "pre-cliff" laps with `cliff_onset_passed` is out for the same reason. The power law's
β > 1 carries acceleration, and the cliff stays the cliff classifier's job.

**The compound seed had a live defect in the working tree (W50, RESOLVED 2026-09-28).** The
working-tree `tyre_allocations.csv` edit had added 2018 rows with legacy names in the relative
hard/medium/soft columns. But 2018 laps carry **absolute** names, so `int_stint_geometry`'s join
(`LOWER(compound) = compound_label`) would have mislabelled them. Of the 20,664 slick 2018 laps:

- **901** would have been coded correctly;
- **8,967** would have been coded wrong: 6,594 real SOFT laps as Ultrasoft, Supersoft or Hypersoft,
  and 2,373 MEDIUM laps as Soft;
- **10,796** would have been NULL.

The fix: the 2018 rows and the unverified 2025 rows were dropped from the seed (128 rows,
2019-2024, unchanged), and `compound_hardness_scale` (with its `era` column) now carries the
cross-era ordinal instead of forcing legacy names onto C-code positions. `dev` still needs a
rebuild to pick this up. This item therefore:

- takes 2018 compound identity from the lap's own name, never from the seed (which has no 2018
  rows at all, by design);
- takes 2019+ from `compound_code` once dev is rebuilt on the corrected seed;
- the 2025 rows are out of scope until they are re-added and checked against their source URLs.

---

## Method

### Step 0: identification check (before any training)

Re-run the scratchpad probe on the final lap set as `ml/src/powerlaw_ceiling.py` (read-only), and
report the reliability ceiling for α, β and the curve values at ages 5, 10, 15 and 20, for both fit
grains below. Add one variant: the pooled fit with a **(race, lap) fixed effect** alongside the stint
intercepts. Cars on different tyre ages on the same lap identify it, and it absorbs fuel-model error,
rubber and ambient, which are all per-(race, lap), as `WI-16`'s field-centring argument shows. Adopt
the variant if it raises the curve-value ceiling materially. It needs alternating projections, so it
would move into a `transform/tasks/coefficients/` fitter writing to `data/fits/`, following
`fit_car_fe`'s pattern, with dbt reading the result. **If every ceiling stays below 0.3, stop and
report.** The item then becomes a measured "no" rather than a shipped curve.

### Step 1: fits in dbt

- **`int_stint_power_law_fit`** (grain: `stint_id`), as requested. Cross-join a β grid (0.20–3.00,
  step 0.05) and fit per `(stint, β)` with `REGR_SLOPE`, `REGR_INTERCEPT` and `REGR_R2` on
  `(POW(age, β), y)`, keeping the β with the highest R².
  - Columns: `alpha_s`, `beta`, `intercept_s`, `r2`, `r2_linear` (β = 1), `n_laps`,
    `beta_at_grid_edge`, `fit_eligible` (≥ 8 laps and an age span ≥ 7).
  - Lap set and `y` exactly as in *Read first*, so the fit and the P3 truth use one lap set.
  - Age runs from 1 to 50.
- **`int_cell_power_law_fit`** (grain: race × compound hardness rank). This is the pooled target:
  within-stint demeaning removes each stint's intercept, β is profiled on the same grid, and α is fit
  by OLS through the origin. Carry `n_stints`, `n_laps`, `r2_within` and `beta_at_grid_edge`.
- **`compound_hardness_scale`** (new seed). A declared cross-era ordinal:
  - 2019+: C1…C6 → 1…6.
  - 2018: absolute names mapped onto the same scale by a stated correspondence (HARD, MEDIUM, SOFT,
    SUPERSOFT, ULTRASOFT, HYPERSOFT, SUPERHARD).
  - The seed carries a `provenance` column and is flagged **non-quotable**, like `tyre_allocations`.
    The mapping is an assumption, and T55 tests it.
- **`fct_power_law_training`** (grain: cell). Targets from `int_cell_power_law_fit`, plus the
  allowlisted features.

### Step 2: features (an allowlist of what the simulator can supply)

W26 is the lesson here. A feature the browser cannot fill arrives as NaN, which is a feature the model
never saw. So the feature set is exactly what `SimulatorControls` and `dim_circuits` can provide at
inference time:

- `compound_hardness_rank`, `era` (2018 / 2019-21 / 2022+);
- `track_energy_index`, `circuit_abrasiveness_index`;
- `ambient_temp_delta`, track temperature (circuit-season median);
- `fuel_mass_kg` at stint start, `dirty_air_share_lap` (the stint mean);
- constructor structural pace.

**"Car setup" is not observed in this warehouse**, and the WI does not pretend otherwise:
constructor pace is a team-level proxy, and nothing here sees setup.

Add a monotone constraint on `compound_hardness_rank`: softer means α goes up. That keeps ordering
honest inside the seen range, but it does not buy extrapolation past rank 5 (see T54).

### Step 3: model, split, export

- **`ml/src/powerlaw.py`.** A separate module, so the v14 contract, `train.py` and `export_onnx.py`'s
  targets are untouched. It fits two XGBoost regressors, one for `α` and one for `β`, at a few hundred
  trees and depth ≤ 4, sample-weighted by `n_laps`. As a fallback that keeps the `(α, β)` export,
  predict the curve at two anchor ages instead and recover the parameters with
  `β = ln(Δ20/Δ5)/ln 4`, `α = Δ5 / 5^β`. Use it if Step 0 shows the curve values are identified and
  the raw parameters are not.
- **Split.** `FD4` is open, so there is no clean holdout season. The primary split is **GroupKFold by
  race**. A season-forward fold (train ≤ 2024, test 2025) is reported and labelled *not a holdout
  claim*, because 2025 was spent as a selection fold. Pinning a holdout is `WI-03`'s job, not this one.
- **Export.** Use `onnxmltools.convert_xgboost`, as `export_onnx.py` does, to
  `ml/models/powerlaw_{alpha,beta}_v1.onnx`. Add parity against `onnxruntime` on the test fold and a
  manifest entry with its own `feature_order`, one vector per model (the WI-04 contract).
  - Do **not** bump or publish the v14 manifest.
  - Do **not** re-export `fct_cliff_prediction_features` (W25).
  - Publishing to the CDN is the user's call.

### Step 4: the simulator side

- **`app/src/features/degradation-simulator/powerLaw.ts`.** A pure `tyreCurve(alpha, beta, laps)`
  plus the ONNX call.
- **`powerLaw.test.ts`.** Runs the existing P3.1-P3.3 gates (`accuracy.ts`,
  `__fixtures__/fitted_basket.json`) against the power-law tyre term.
- Wire it in as the headline tyre term **only if** it beats the current isotonic term on the basket.
  Otherwise it ships as code plus tests and nothing user-visible changes.

---

## Success criteria

**The user's four, as requested, and the restatement W49 ruled in.** W49 is RULED: **Option A**,
graded on fan-facing accuracy. The restated column is the definition of done.

| # | As requested | Probe verdict | Restated (RULED -- Option A) |
| :-- | :-- | :-- | :-- |
| 1 | Power-law fit explains ≥ 85 % of variance per stint | Fails on 88 % of stints, and it grades noise, not the curve | **Form adequacy:** on every P3 accuracy-basket cell, the power-law curve fitted to that cell passes P3.1 (MAE ≤ 0.5 s against observed deg-from-fresh p50). This is the bar the current curve already meets. The per-stint R² distribution is reported, not gated. |
| 2 | `(α, β)` predictions R² ≥ 0.70 | Above the measured ceiling for both (β ≈ 0.4-0.5, α < 0) | **Held-out curve error:** on GroupKFold-by-race held-out cells, the predicted curve's MAE at ages 5, 10, 15 and 20 beats both (i) the compound-rank median curve (the no-model baseline) and (ii) the current simulator tyre term on the same cells. R² for α and β is reported next to its Step 0 ceiling, as a fraction of the achievable. |
| 3 | ONNX < 500 KB | Feasible | Unchanged: both files together under 500 KB, **plus** ONNX-to-XGBoost parity with max abs diff ≤ 1e-5 on the test fold. |
| 4 | Simulator matches live prediction on test races | "Live prediction" is undefined | **(a)** Browser `tyreCurve` from ONNX equals the Python prediction (≤ 1e-5) for every held-out race. **(b)** On those races the power-law tyre term passes P3.1-P3.3: MAE ≤ 0.5 s, zero monotone violations, and the sign and sanity checks. |

**The ruling (W49, resolved 2026-09-28): Option A.** The numbers originally requested assume each
stint's wear curve can be pinned down precisely. It can't: over 8-30 laps, lap-time noise is bigger
than the curve's bend, so "how steep" (α) and "how curved" (β) blur into each other. Graded the
original way, the item fails even if the simulator gets better. The user chose to grade it on what
fans see instead: is the curve close to what really happened on races the model never saw, and
better than today's curve -- criterion 2's **held-out curve MAE beating the current simulator** is
the headline bar. The alternatives were not chosen: **B** (keep the original thresholds and ship a
documented "fails 1 and 2") and **C** (simplify first -- fix β per hardness rank, predict only α).

---

## Tests

T-ids continue the board's series (T1-T49 are taken).

| Id | What it asserts | Where |
| :-- | :-- | :-- |
| **T50** | `int_stint_power_law_fit`: one row per eligible stint. `beta` is in [0.2, 3.0], `r2` is in [0, 1], and `r2 ≥ r2_linear − 1e-9` (the grid contains β = 1, so the profile can never do worse than a line). | `transform/tests/assert_power_law_fit_bounds.sql` |
| **T51** | The F2/FD3 guard: `fct_power_law_training` and the feature allowlist in `powerlaw.py` contain no `compound_*` seed column, no `expected_*` column, no `cliff_onset_passed` / `laps_past_cliff`, and nothing net of `compound_component_s`. | dbt test plus a pytest on the allowlist |
| **T52** | 2018 hardness rank comes from the lap's own compound name: every 2018 slick lap with a name resolves, and no 2018 rank comes from `tyre_allocations`. | `transform/tests/assert_hardness_rank_2018_from_lap_name.sql` |
| **T53** | ONNX: combined size < 500 KB, and parity with XGBoost ≤ 1e-5 on the test fold. | `ml/tests/test_powerlaw_export.py` |
| **T54** | C6 leave-out. Train without rank 6, then report error on the C6 cells against C5 at the same races. Reported, not gated: 59 laps cannot carry a threshold. | `ml/src/powerlaw.py --leave-out-rank 6` |
| **T55** | Cross-era mapping. Leave out 2018, predict it under the declared `compound_hardness_scale`, and compare against the alternative mapping and against era-flag-only. Report which one wins. | `ml/src/powerlaw.py --leave-out-era 2018` |

P3.1-P3.3 run unchanged on the power-law term through `powerLaw.test.ts`.

---

## Definition of done

1. Step 0's ceiling report exists, with the chosen fit grain and the reason for choosing it recorded
   in *As built*. If every ceiling is below 0.3, the item closes as a measured "no" and the report is
   the deliverable.
2. `dbt build -s int_stint_power_law_fit int_cell_power_law_fit fct_power_law_training
   compound_hardness_scale` passes on dev, with T50-T52 passing. W50 is cleared (the seed rewrite
   landed 2026-09-28; `tyre_allocations` is back to 2019-2024/128 rows and `compound_hardness_scale`
   exists), so the 2019+ codes are right once dev is rebuilt.
3. `python -m ml.src.powerlaw` trains, reports the restated (RULED, Option A: fan-facing) criteria,
   writes both ONNX files, and passes T53. T54 and T55 are reported.
4. `npm test` passes, including `powerLaw.test.ts` running P3.1-P3.3 on the power-law term.
5. Not run: `ml.src.features --check`, and any re-export of `fct_cliff_prediction_features` (W25).
   No manifest publish.
6. `python3 _roadmap/_fixes/status/board.py --check` is clean, and the `landed` history entry names
   what was rebuilt.

## Board registration

Added 2026-09-28 as item `WI-17` (group 06, SPEC, `fable-5.1`, 2-3d, no dependencies), with the
pointer moved to it at the user's request. Watch entries were raised with it:

- **W49** (raised pending-ruling; RESOLVED 2026-09-28): success criteria A / B / C, above -- ruled A.
- **W50** (raised hazard; RESOLVED 2026-09-28): the uncommitted `tyre_allocations.csv` 2018 rows
  mislabelled 2018 laps -- cleared by the seed rewrite (2018 and 2025 rows dropped, 128 rows
  2019-2024 unchanged, `compound_hardness_scale` added).

## As built

**2026-09-28, stage MEASURED** (the orchestrator has not re-run the definition of done yet).

**In plain terms.** It works, with two caveats. On races the model never saw, the predicted
curve is about 11 % closer to what really happened than a simple "typical curve for this
hardness" baseline, and about 2.3 times closer than today's simulator method rebuilt without
that race. But it explains only about a tenth of the race-to-race differences it could in
principle explain. Almost all of its skill is in how *much* the tyre fades by lap 20; the
*shape* of the curve is close to unpredictable from these inputs. It passes the simulator's own
accuracy gate on three of the four dry basket cells. It fails at Monza, where even each race's
own fitted curve fails, because the gate's "truth" rises faster than any single car's tyres do.
It is not wired into the page.

### Step 0: identification (DoD 1)

`python -m ml.src.powerlaw_ceiling` (read-only; report in `ml/artefacts/powerlaw_ceiling.json`,
40 bootstrap reps, seed `RANDOM_STATE`). Reliability ceiling = the best R² any feature set
could reach against these targets. `incr_a` is the curve over the fresh-tyre pace at age 2 (the
simulator's anchor, see below). `delta_a` is the WI's `α·a^β`, over the extrapolated age-0 pace.

| Quantity | stint | **cell** (race × rank) | cell + (race, lap) FE |
| :-- | --: | --: | --: |
| α | −0.01 | 0.07 | −10.3 |
| β | 0.46 | 0.51 | 0.26 |
| delta 5 / 10 / 15 / 20 | 0.13 / 0.27 / 0.43 / 0.55 | 0.24 / 0.38 / 0.49 / 0.59 | −68 … −232 |
| **incr 5 / 10 / 15 / 20** | 0.41 / 0.58 / 0.69 / 0.64 | **0.58 / 0.69 / 0.76 / 0.76** | −289 … −468 |

- **Grain chosen: the cell, without the (race, lap) fixed effect.** It has the highest curve
  ceilings.
- **The (race, lap) FE variant is not identified, and no fitter was written.** Within a stint,
  tyre age and lap number rise together one for one. So a straight-line age term lies exactly in
  the span of the stint and (race, lap) fixed effects (the age-period-cohort problem). Only
  curvature, and differences between a race's ranks, survive. The bootstrap variance runs
  10-470× the cross-cell variance, and the median `incr_20` drops from 0.53 to 0.35 s as the FE
  soaks up the common slope. The WI's premise that same-lap cars at different ages identify it
  holds for the ranks' *difference* only.
- **Not every ceiling is below 0.3, so the item continues.** α is not identified (0.07) and the
  curve is, so the WI's fallback applies: predict curve values and recover the parameters. The
  anchors are taken over the **age-2** pace, not age 0. The age-0 level is an extrapolation
  below the data (the first clean lap on a set is age 2; 6 of 139,855 lap-set laps are age 1),
  which is why `delta` trails `incr` everywhere.
- **Target: `y = weight_corrected_lap_time`, not `− rubber_component_s`.** There are two
  reasons.
  - `rubber_component_s` is fitted from `int_field_pace_curve`, which subtracts the compound
    seed's `expected_compound_pace_s` from every lap. That makes it priced from the seed the
    F2/FD3 guard fences off.
  - The P3 truth (the envelope's `obs_deg_from_fresh`) and the simulator (`net = ref + fuel +
    tyre`, with no track-evolution term) are both built on `weight_corrected_lap_time`.

  With rubber subtracted, the `incr` ceilings are 0.51-0.72. The per-stint R² then reproduces
  the pre-flight probe exactly (median 0.503, 11.5 % ≥ 0.85, 6,390 stints), which cross-checks
  this implementation against the probe.
- **Per-stint R² on the final target (reported, not gated).** p10/p25/p50/p75/p90 are
  0.05/0.16/0.42/0.67/0.83. 8.2 % of stints are ≥ 0.85, β sits on the grid edge in 65 %, and
  the gain over a straight line is 0.041.

### What was built

- **dbt.**
  - `int_power_law_lap` (new): the shared lap set, 139,855 laps. The DoD's `-s` list does not
    name it; build it first, or select `+fct_power_law_training`.
  - `int_stint_power_law_fit`: 7,320 stints, 6,390 eligible.
  - `int_cell_power_law_fit`: 390 cells, 339 eligible.
  - `fct_power_law_training`: 339 cells, 141 races, 117,845 laps, 2018-2024.
  - Macro `power_law_beta_grid`.
  - Tests T50 `assert_power_law_fit_bounds`, T51 `assert_power_law_no_seed_columns` and T52
    `assert_hardness_rank_2018_from_lap_name`. T51 and T52 were mutation-checked: pointed at
    `int_lap_residual_decomposed`, T51 flags 12 guarded columns and the direct
    `int_compound_cliff_predicted` read. Given a W50-style `compound_code` on 2018 SOFT laps,
    T52 flags 5,494 laps.
- **ML.** `ml/src/powerlaw_fit.py` holds the shared math; the numpy cell fit equals the dbt fit
  on all 390 cells. `ml/src/powerlaw_ceiling.py` is Step 0. `ml/src/powerlaw.py` trains,
  grades and exports to `ml/models/powerlaw_{deg20,beta}_v1.onnx` (plus `.bst`) and
  `ml/models/powerlaw_manifest_v1.json`. The manifest is separate and per-model; the v14
  `manifest.json` is untouched. Tests are in `ml/tests/test_powerlaw_export.py` (T51 on the
  Python side, T53, and fit parity).
- **App.** `powerLaw.ts` (`tyreCurve`, the ONNX call, `fitPowerLaw`) and `powerLaw.test.ts`,
  with fixtures `powerlaw_parity.json` and `powerlaw_basket.json`, both written by
  `python -m ml.src.powerlaw`.

### Deviations from the spec, and why

1. **`ambient_temp_delta` was dropped from the allowlist.** The warehouse computes it as track
   temperature minus `compound_optimal_temp_low` (`int_compound_cliff_predicted`), a guarded
   seed column. `track_temp_c` (the circuit-season median) carries the temperature signal
   instead.
2. **A level + shape model replaces the two raw regressors.**
   - `deg20` is the curve over the age-2 pace at age 20. It uses all 8 features and is
     monotone ↑ in hardness rank, track temperature and dirty-air share.
   - `β` uses era, track energy, abrasiveness, stint-start fuel and constructor pace.
   - Then `α = max(deg20, 0) / (20^β − 2^β)` and `tyre(k) = max(0, α·(k^β − 2^β))`.

   Rank, dirty air and temperature move the level only, so raising any of them scales the whole
   curve up at every lap. The P3.3 sanity gates and the hardness ordering hold by construction.
   The WI's two-anchor recovery cannot promise that: raising one anchor with the other fixed
   lowers the curve on one side of it. It also graded no better (scratch comparison, T-fit MAE
   0.470 vs 0.466). Direct `(α, β)` regressors gave 7-24 s MAE and are unusable. The files are
   named for their outputs (`powerlaw_deg20_v1`, `powerlaw_beta_v1`), not `powerlaw_alpha_v1`.
3. **The hardness-rank monotone constraint sits on the level, not on α.** α is derived, so
   "softer means α goes up" cannot be expressed. The data do not show softer-means-more
   either: the rank medians of `incr_20` are 0.67, 0.51, 0.53, 0.59, 0.33, 0.05 and 0.50 for
   ranks 1-7.
4. **The objective is pseudo-Huber, with fixed a-priori hyperparameters** (300 trees, depth 3,
   `min_child_weight` 1,500 laps, weighted by `n_laps`). The targets are fat-tailed:
   `incr_20` runs from −6.2 to +5.1 s. For the ONNX conversion the objective is retagged to
   `reg:squarederror`, which has the same identity link, and parity proves the output is
   unchanged.
5. **The season-forward check trains ≤ 2023 and tests on 2024.** The WI's ≤ 2024 / 2025 fold
   cannot run, because 2025 has no hardness rank after W50. It is labelled *not a holdout
   claim*.
6. **T54 has no C6 to test.** The WI's "59 C6 laps" were counted against the pre-W50 seed's
   2025 rows. It ran on rank 6's actual occupants (2018 ULTRASOFT, an interpolation test) and
   on rank 7 (2018 HYPERSOFT, the top of the scale, as the extrapolation analogue).

### Results against the restated criteria (W49, Option A)

**Criterion 1: form adequacy. PASS on all 5 basket cells.** A weighted fit of `c + α·k^β` to
each cell's observed p50 (laps with n ≥ 10) scores these P3.1 MAEs: RBR HARD 0.16, Monza HARD
0.33, RBR MEDIUM 0.15, Yas HARD 0.10, Istanbul INTERMEDIATE 0.21 (all ≤ 0.5 s).

**Criterion 2: held-out curve MAE, GroupKFold(5) by race, 339 cells. PASS at every age against
both baselines, under both truths.** MAE is in seconds at ages 5 / 10 / 15 / 20, then the mean.

| Truth | Power-law model | Rank-median curve | Current term, rebuilt without the fold | Current term as shipped (in-sample) |
| :-- | :-- | :-- | :-- | :-- |
| T-fit, all cells | 0.19 / 0.39 / 0.56 / 0.75, **0.47** | 0.20 / 0.43 / 0.64 / 0.85, 0.53 | 1.02 / 1.46 / 1.88 / 2.32, 1.67 | 0.80 |
| T-fit, own-history cells (261) | **0.46** | 0.52 | 1.07 | 0.75 |
| T-obs, all scorable (284) | **0.88** | 0.92 | 1.77 | 0.61 |
| T-obs, own-history cells (223) | **0.87** | 0.90 | 1.10 | 0.69 |

- **The two truths.**
  - T-fit is the held-out cell's own within-stint fit.
  - T-obs is model-free and in the P3 truth's own definition: the median lap at ages a−1..a+1
    minus the median at age ≤ 2, per race cell.
- **How "current term" was rebuilt.** It is the simulator's working-window term (envelope p50
  plus isotonic fit, neutral inputs, no cliff term). It uses the app's own fallback chain:
  the compound's own history, then `_all`, then the analytical ramp. It was rebuilt on the
  training folds only.
- **How many cells had history.** 32 of the 339 cells land on the ramp (the circuit has no
  other race in its era) and 46 on `_all`. That is why the "own-history" rows are the
  like-for-like comparison.
- **Caveat on the shipped term.** The term as shipped has *seen* the graded race. Under T-obs,
  its own definition, it beats the model (0.61 vs 0.88). No held-out version of it does.
- **R² against the Step 0 ceiling (fraction of the achievable).**
  - `deg20`: 0.08 of 0.76 (11 %).
  - `incr_5`…`incr_20`: 0.08-0.12 (13-15 %).
  - β: −0.14 of 0.51.
  - α: 0.00 of 0.07.

  The β model adds almost nothing: a constant β scores 0.474 against 0.472.
- **Season-forward (≤ 2023 → 2024, 52 cells, not a holdout claim).** Model 0.63, rank median
  0.70, current term 1.57.

**Criterion 3: size and parity. PASS.** The two ONNX files total 227,401 B (under 500 KB).
ONNX-to-XGBoost max abs diff is 1.4e-6 (`deg20`) and 1.7e-6 (β) on the test fold, and 2.4e-6
over all cells, including a NaN-bearing copy.

**Criterion 4a: the browser matches Python. PASS.** `onnxruntime-web` in `powerLaw.test.ts`
was compared with Python on all 339 cells (all 141 races). The parameters differ by at most
2.6e-6 and the tyre curve by 8.9e-6. That is ≤ 1e-5, but with a thin margin: lap 50 amplifies
β's float32 difference.

**Criterion 4b: P3.1-P3.3 on held-out races. Not fully met: 3 of 4 dry cells.** Each race is
scored by the fold model that never saw it, and the races are pooled per basket cell, weighted
by `n_laps`.

- **P3.2 and P3.3 pass on all four dry cells:** monotone curves, sign, the dirty-air and
  temperature responses, and the RBR HARD lap-30 anchor (1.32 against 1.264 ± 0.5).
- **P3.1 passes on three:** RBR HARD 0.29, RBR MEDIUM 0.25 and Yas HARD 0.30.
- **P3.1 fails on Monza HARD post2022: 1.24 s.** The races' own in-sample fits fail there too
  (0.98 s). So the failure comes from the truth, not the model. The basket's cross-sectional
  p50 sits about 0.9 s above the fresh anchor by lap 5 and reaches 2.1 s by lap 20, while
  Monza's within-stint fits reach 0.5-0.9 s. Scored against the *current* dev envelope, the
  result is the same (model 1.06, oracle 0.80). `powerLaw.test.ts` records the cell as
  `it.fails` (`KNOWN_P31_FAILS`), so `npm test` stays green without hiding the failure.
- **Istanbul INTERMEDIATE is out of scope:** it is not a slick, so it has no hardness rank.

**T54 (reported).**
- **Rank 6 (2018 ULTRASOFT, 12 cells), trained without it:** MAE 0.65. Using rank 5's median
  curve gives 0.63. The true rank 5-6 gap at the same races is 0.33.
- **Rank 7 (HYPERSOFT, 5 cells):** MAE 0.70, with a −1.17 s bias at age 20. The model
  under-calls the softest compound, as the WI expected: trees do not extrapolate.

**T55 (reported).** Trained without 2018 and scored on 2018's 54 cells:

| Mapping | MAE |
| :-- | --: |
| Declared scale | 0.512 |
| Alternative | 0.508 |
| Era flag only (rank = missing) | **0.494** |

The alternative mapping is Pirelli's 2019 guidance as recalled, unverified: HARD = 1, MEDIUM = 2,
SOFT = 3, SUPERSOFT = 3.5, ULTRASOFT = 4, HYPERSOFT = 5. **Era flag only wins**, so neither
mapping earns its place for 2018. The hardness rank carries no transferable signal across the
2018/2019 construction change.

### Step 4: not wired

The basket is the isotonic term's own data (in-sample MAE ≈ 0), so the power-law term cannot
beat it there. Nothing user-visible changed. Wiring it later needs the simulator to supply:

- a hardness rank per circuit × season × compound, which needs a lookup the app lacks;
- `era_code` with 2018 split from 2019-21 (the UI only has pre/post-2022);
- a circuit-median `track_temp_c` (not in `dim_circuits`);
- stint-start fuel, dirty air and constructor pace, which it already has.

### Definition of done, as run here

1. The Step 0 report exists, and the grain and reasons are recorded above.
2. `dbt build -s int_power_law_lap` then
   `dbt build -s int_stint_power_law_fit int_cell_power_law_fit fct_power_law_training
   compound_hardness_scale` both pass on dev: PASS=15 and PASS=42, including T50-T52 and
   `assert_hardness_scale_no_gaps`.
3. `python -m ml.src.powerlaw` passes, and `pytest ml/tests` passes 270 tests, 37 of them new.
4. `vitest run` passes 406 tests (36 in `powerLaw.test.ts`, one of them `it.fails` on purpose).
   `tsc --noEmit`, eslint and sqlfluff are clean on the new files.
5. Not run: `ml.src.features --check`, any export of `fct_cliff_prediction_features`, and any
   manifest publish.
6. `board.py --check`: OK, with `BUILD-ORDER.md` regenerated. The stage is MEASURED, and the
   history entry names what was rebuilt.

**Raised on the watch list.**
- W51 (hazard): the fuel-corrected lap time, the rubber split and the constructor coefficient
  are priced from the compound seed, one step removed.
- W52 (pending-ruling): the Monza P3.1 failure (criterion 4b is 3 of 4).
- W53 (debt): there are no 2025 hardness ranks, so the real C6 T54 and the 2025 fold cannot
  run.
- W54 (stale-artifact): the P3 basket fixtures predate the current warehouse.
