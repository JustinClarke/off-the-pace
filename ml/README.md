# `ml/` Machine Learning Layer

XGBoost tyre-degradation models trained on `fct_cliff_prediction_features` (the gold lap-grain mart).
Reads the warehouse **read-only**; publishes artefacts to `ml/models/`, which the application layer pulls from.
Narrative docs: [Machine Learning section](../docs/ml/overview.mdx) · auto-generated [model card](../docs/reference/ml/degradation-model.mdx).

## Production artefacts

- `degradation_regressor_p10` / `_p50` / `_p90` quantile trio for the **cumulative fuel-corrected
  pace jump over the next five laps** (s, `next_5_lap_cumulative_jump_s`). Phase 7 moved the trio off
  the next-lap column; Phase 9 (2026-09-05) promoted `MODEL_VERSION_DEFAULT` to `v10`, so the
  published artefacts now match — the 5-lap fit against the pruned 24-feature contract. Phase 10a
  (2026-09-05) then took it to `v11`, adding the 9-column `proximity` group (33 features): true
  pairwise track gaps measured from the telemetry stream's position channel, which is the first
  feature family in the project sourced from a different sensor rather than from a further
  transform of lap times or the car channel (see `src/schema.py`, `DEGRADATION_TARGET` /
  `FEATURE_GROUPS`). The shipped version is now `v14`, on a 39-column contract: the 7-column
  `qualifying` group (2026-09-21) is read by the cliff classifier only, so the trio and stint
  life take 32 (`PER_TARGET_FEATURE_MASK`).
- `cliff_classifier` `laps_until_cliff_class` ∈ {`0_to_2`, `3_to_5`, `6_plus`, `none_in_stint`}.
- `stint_life_regressor` `remaining_stint_life_laps` (synthesised; ≥ 0).

Each ships as a `.bst` **and** a parity-tested `.onnx`. Artefacts are versioned; the active
version, feature list and metrics are defined in `src/schema.py` (`MODEL_VERSION_DEFAULT`) and
recorded in `models/manifest.json` / `models/model_card.json`. Older versions are kept for diffing.

### Label spine version bump (WI-01 + WI-12, 2026-09-27)

The shipped `v14` model card above was trained on the **pre-WI-01 label**. WI-01
(`_roadmap/_fixes/wi/WI-01-label-spine.md`) rebuilt `int_field_pace_curve` and
`int_lap_residual_decomposed`, and the residual both labels are built from now has
**five additive terms, not seven**:
`pace_delta_s = fuel + compound + constructor + dirty_air_tax + driver_skill`.

- The field base is fuel- **and** compound-neutral (not just fuel). Rubber and
  ambient track state live only inside the base; they are no longer subtracted a
  second time on top of it (they stay on the table as informational columns).
- Laps with no measured field base, or an unknown tyre cost, carry a NULL label
  instead of a fabricated one, and unknown-tyre laps no longer enter the base.
- `compound_grip_peak` (a unitless ratio) is no longer added into
  `expected_compound_pace_s` as if it were seconds.
- `circuit_constructor_interaction_s` is out of `constructor_component_s` (it sat on
  top of a per-race constructor level that already spans the circuit).
- `theta_air` is 0.331 s/lap (`theta_air_label_value`): the within-stint estimate
  (stint fixed effects plus tyre-age bins), fitted with tyre cost subtracted from its
  calibration residual the same way fuel is, on a declared season window
  (`theta_air_fit_season_max: 2025`), and frozen as a declared value.
- `event_driven` laps (SC/VSC/red-flag/restart/pre-deployment/local yellow) and the
  lap after an SC or red-flag restart are excluded from `is_training_eligible` (FD2).

`next_5_lap_cumulative_jump_s` and `laps_until_cliff_class` move on this rebuild
(F38 alone moved 72% of pre-fix labels by more than 250 ms).

**WI-01 and WI-12 together are one version bump.** `theta_air` passed through two
interim values inside it: WI-01's pooled 0.503 s/lap, then 0.331 once WI-12's 06b
re-measure showed the pooled slope bills some car pace as dirty air (ruling W40,
2026-09-27; `_roadmap/_fixes/wi/WI-12-06b-remeasure.md`). The final label, the one a
`v14` configuration is rebuilt on for comparison, carries 0.331. Nothing measured on
the 0.503 state is kept as a comparison base. Moving from 0.503 to 0.331 alone moved
84,486 of 106,394 `next_5_lap_cumulative_jump_s` labels (31,551 by more than 250 ms)
and 4,207 `laps_until_cliff_class` values.

**Every number published against `v14` (or any earlier version) is "not
fixed-target" from this point on.** A new headline on the new label is compared only
against a `v14` configuration rebuilt on the new label, never against the published
numbers. Until a `v15` retrain lands (not yet scheduled; WI-01 is what unblocks it),
`v14`'s artefacts in `ml/models/` are still the ones the app serves, fit on the
pre-bump label. WI-12 is not a retrain: it is the 06b dirty-air re-measure on the new
label, and its W40 ruling set the label's final `theta_air`.

### Label version bump for v15 (WI-02b seed + CO-02 + CO-04, recorded 2026-10-15)

`v15` never shipped, so its label is the final one, and everything that moved the label
after the 2026-09-27 snapshot is **one** bump, recorded here by CO-03
(`_roadmap/_ai-integration/wi/CO-03-v15-gates-rerun.md`):

- WI-02b's compound-seed re-estimate (2026-10-03).
- CO-02, the cliff label (`_roadmap/_ai-integration/wi/CO-02-cliff-label-defects.md`):
  wear is no longer subtracted twice, severity is the regression step with wear excluded,
  the ramp is 2.5 laps (`cliff_ramp_span_laps`), 2025 is refit on 2018-24, and 2018 is fitted
  on its own laps (ruling CD2 = C). Seed `compound_cliff_params.csv`, 499 rows, sha256
  `12fcc131...77f8`, frozen.
- CO-04, measurement honesty (`_roadmap/_ai-integration/wi/CO-04-measurement-honesty.md`):
  missing telemetry is NULL, not clear air; restart laps get their own field mean; thin
  field-base cells are skipped.
- CD1 = A: 'mistake' laps stay dropped from training; the unused `training_weight_f9` column
  was removed from `int_lap_anomaly_flags`.

`theta_air` is unchanged (0.331). `transform/seeds/label_stability_baseline.csv` (T9) was
re-taken the same day. All seven completed seasons moved against the 09-27 snapshot, for
example 2018 12,560 -> 11,282 labelled rows and mean -0.1736 -> -0.2810 s, and 2023
-0.0617 -> -0.3734 s. The trio trains on 83,424 rows (85,859 on the 09-29 label), the
classifier on 105,525 (115,356) and stint life on 124,501 (123,133).

**2018 is an in-sample fit** (CD2 = C). It is a training season only. It is never an
evaluation season: `cv_final_fold` scores 2025, and the CV folds validate 2021-2025.

`v15` is the `v14` configuration on this label: the same `*_best_params.json` (no re-tune),
uniform quantile weights (W58), the realised-stint-end stint-life gauge (D5), training
2018-2025, and 2026 as the blind test. So the only fixed-target comparison for `v15` is
against its own baselines on this label. The published `v14` numbers are on the pre-WI-01
label and are reference only. The `*_v15uni` / `*_v15ipw` artefacts (W58, 2026-09-29) are
on the 09-29 label and are not this model. `MODEL_VERSION_DEFAULT` stays `v14` until the
owner promotes.

### Label version v16 (OPEN: CO-09 and CO-15 in the working tree, numbers owed by CO-17; recorded 2026-10-24)

The next label version is **v16**, matching the next free model name. It is opened by
CO-09 (`_roadmap/_ai-integration/wi/CO-09-stint-label-fix.md`) and is shared with CO-15
(the Monaco wear hold, ruling CD9), so the label moves once. Both parts are now in the
working tree (CO-15's below); the frozen-label seed (`transform/seeds/label_stability_baseline.csv`) is
refreshed once, on CO-17's trusted rebuild, not per item. Nothing is retrained (CO-18)
or promoted (owner) here. `MODEL_VERSION_DEFAULT` stays `v14`.

CO-09's part, working tree 2026-10-24 (owner rulings D4, D5, D6 and CD14):

- **A stint is a tyre run.** `stint_id` is re-keyed at its one source,
  `int_stint_geometry` (D4: everywhere, no separate run id). Consecutive FastF1 stints of
  a driver-race join when the compound is the same, the tyre age continues at last
  age + 1 (CD14 1a), and the earlier stint did not end on a green-flag lap (CD14 2). The
  run ends where its last fragment ends. A run never joined keeps its old `stint_id`; a
  joined run takes its first fragment's id and `stint_number`, so numbers can skip.
- **Stint-life censoring** (`schema.STINT_LIFE_CENSOR_COLUMN` = `is_stint_life_censored`,
  was `is_censored_stint`): only a green-flag tyre change is an observed life. Red-flag
  tyre changes (D5) and safety-car / VSC stops (D6) are censored, as are the flag and
  retirements.
- **Flag question** (`int_stint_end_regime.reached_flag`, `flag_chance.EVENT_NOT_REACHED`):
  a red-flag tyre change is censored, not 0.
- `stint_end_cause` keeps its six classes; `is_censored_stint` keeps "final run".

Measured on a scratch copy of the 2026-10-22 dev warehouse (evidence:
`_roadmap/_ai-integration/_evidence/co-09-2026-10-24/`): 9,374 -> 8,968 stints (406
FastF1 stints folded: 299 safety-car drive-throughs, 107 red-flag pauses) in 31 races;
every season moves (2018 and 2019 by one run each); Canada 2025 loses its 49 fake one-lap
stints and its 17 real final stints become `race_end`. The lap grain is unchanged
(189,418 laps), but per-stint detrending moves the degradation label too: 2020-2023 fail
`assert_prior_season_labels_frozen` on purpose until the CO-17 refresh. Stint-life
training rows 124,497, censored share 53.5% (scratch, before CO-15).

CO-09 follow-up, same working tree, 2026-10-24 (evidence
`_roadmap/_ai-integration/_evidence/co-09-2026-10-24-b/`):

- **Penalty stops join too** (owner, recorded on CD14): a green-flag same-tyre boundary
  joins when race control recorded a drive-through, stop-go or time penalty for that car
  within one lap of the earlier stint's last lap. 23 of the 36 green age + 1 pairs join;
  13 stay split. 8,968 -> 8,945 stints (23 `green_pit` ends become part of their run).
  2018 and 2024 now also fail the frozen-label check; stint-life rows 124,496, censored
  share 53.5%.
- **Cut-short fields stored, not used**: `fct_stint_features` carries is_fresh_tyre_raw, and on sc_pit / vsc_pit runs
  clean_laps_to_cut, slope_to_cut_s_per_lap, mean_clean_pace_s, cut_reason,
  slope_reliable. No model reads them; admitting any as a feature is a later decision.

CO-15's part, working tree 2026-10-24 (ruling CD9; `_roadmap/_ai-integration/wi/CO-15-monaco-wear-hold.md`),
in this same label version, not a second bump:

- **The linear wear term is held past onset + 5.** `macros/compound_cliff_wear.sql`
  charges `wear_gradient * LEAST(age, onset + compound_wear_hold_after_onset_laps)` (new
  dbt var, 5.0) instead of `wear_gradient * age`; the slope is fitted on ages 3..onset-2
  and the step measured by onset + 5, so past that the curve was never measured. It moves
  `expected_compound_pace_s`, so `driver_skill_residual_s` and both residual-based targets,
  and the pit-strategy cost curve (same macro).
- **Two new error tests**: `assert_compound_wear_not_extrapolated` and
  `assert_field_base_drift_tracks_observed` (wear drift may not exceed the observed
  weight-corrected drift by more than 7 s in any dry race). `assert_field_pace_honest_range`
  keeps its 0.920 floor.
- Probe numbers (2026-10-22 dev, before CO-09), to be reproduced on CO-17's rebuild:
  honest-range failures 15 -> 0, `2024_8` lap 77 field base 0.905 -> about 0.972 x fastest
  lap, laps on the 10 s cap 323 -> 0, about 23,973 of 161,040 `int_compound_cliff_predicted`
  rows change (max about 6.3 s).
- **CO-17 audit follow-ups (2026-10-24, same label version, no label moves):**
  `expected_degradation_rate_s_per_lap` (a feature in all five models) now follows the
  hold: 0 from onset + 5 on, instead of the wear gradient on a flat curve (26,382 rows).
  `int_pit_strategy_value` no longer takes a same-tyre stop a CO-09 run was joined across
  as the run's stop (119 stints: 111 race_end, 8 retirement). Tests
  `assert_degradation_rate_follows_wear_hold`, `assert_pit_not_taken_from_joined_boundary`.
  The frozen-label seed is unaffected (`next_5_lap_cumulative_jump_s` unchanged).

## Quickstart (one venv at repo root)

```bash
make ml-setup       # install ml/requirements.txt into ./.venv
make ml-features    # audit: leakage guards + forward-window + season split
make ml-train       # smoke / production train
make ml-predict     # score all laps → data/marts/mart_degradation_predictions.parquet
make ml-onnx        # export + parity gate → ml/models/
make ml-tune        # Optuna search + production refit
make ml-evaluate    # baselines, cohorts, calibration, importance
make ml-card        # assemble model_card.yml / .json
make ml-reference   # regenerate the docs model-card MDX
make ml-all         # the whole pipeline, end to end
make ml-test        # leakage spine · ONNX parity · schema · beats-baseline · survival · version contract
```

## Layout

```
src/      schema.py · features.py · train.py · tune.py · predict.py · export_onnx.py · evaluate.py · card.py
          survival.py (AFT) · crps.py · ceiling.py + intervals.py (attainable denominators)
          evaluate_10c.py (cause-specific evaluation) · inspect_trials.py + monitor_tune.py (Optuna helpers)
          attribution.py (what the within-stint signal is, and whether a feature could carry it)
          powerlaw_fit.py · powerlaw_ceiling.py · powerlaw.py (WI-17 power-law tyre curve; separate from v14)
tests/    test_features.py · test_targets.py · test_predict.py · test_onnx_parity.py · test_evaluate.py
          test_survival.py · test_manifest_contract.py · test_ceiling.py · test_attribution.py · test_crps.py
          test_fit_parity.py (search == evaluation == production refit) · test_powerlaw_export.py (WI-17)
models/   *.bst/*.onnx (gitignored) · encoders.json / manifest.json / model_card.json (tracked) · training_logs/ optuna_studies/
artefacts/ PNGs + eval parquets (gitignored, regen-able)
```

## Contracts

- **Holdout** is pinned to `holdout_config.HOLDOUT_SEASON` (2026, WI-03 FD4 ruling); previously derived as `MAX(race_year)+1` which was structurally broken. `holdout_populated` is false until 2026 data arrives (derived from warehouse state, not pinned).
- **No leaked columns** (`driver_skill_*`, identifiers, targets, gate) ever enter `X` pinned by `schema.EXCLUDED_LEAKAGE_COLUMNS` and `transform/tests/assert_no_leakage_columns.sql`.
- **Feature contract ⊆ live mart** `test_feature_contract_subset_of_mart` fails the build on schema drift in either direction.
- **Determinism** `RANDOM_STATE` everywhere; dataset SHA256 fingerprint logged in the card.
- **ONNX parity** every `.onnx` must match its `.bst` within `atol=1e-5`; the tolerance is never loosened.
- **Every claim carries an interval** a `beats_baseline: true` with no interval on it is not a claim, and
  `card.py` refuses to write one. The effective sample is ~7,200 stints, not ~95,500 laps, so each margin is
  reported both as a paired t over the season folds and as a bootstrap resampling whole stints.
- **A flatten is a measurement, never feature guidance** replacing a feature with its per-stint mean says what
  the model *uses*; on a forward-looking target it also hands the model laps that had not run. `make ml-attribution`
  re-runs any group that clears the noise floor over laps 1..t (`causal_delta`) and over laps t..N (`future_delta`)
  and publishes a `causally_reachable` verdict. Act on that, not on `flatten_delta`.
- **Every headline carries a denominator** skill is published as a fraction of the *attainable* quantity
  (`ceiling.py`), never as a fraction of 1.0. A pinball of 0.20 means nothing until you know what a predictor
  with perfect stint-level knowledge could reach.

## Tracked vs generated

| Path | Status | Notes |
|---|---|---|
| `models/encoders.json` | **tracked** | Ordinal encoder mappings required at inference time |
| `models/manifest.json` | **tracked** | Model registry: names, versions, feature list, paths |
| `models/model_card.json` | **tracked** | Machine-readable model card (source: `model_card.yml`) |
| `models/*.bst` | gitignored | XGBoost binary checkpoints regenerate with `make ml-train` |
| `models/*.onnx` | gitignored | ONNX exports regenerate with `make ml-onnx` |
| `models/training_logs/` | gitignored | Optuna / XGBoost training logs |
| `models/optuna_studies/` | gitignored | Optuna study databases |
| `artefacts/*.png` | gitignored | Evaluation plots regenerate with `make ml-evaluate` |
| `artefacts/*.parquet` | gitignored | Evaluation data frames regenerate with `make ml-evaluate` |

---

← Previous in tour: [transform/](../transform/README.md) · **Next in tour: [app/](../app/README.md) →**
