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
  `FEATURE_GROUPS`).
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
make ml-test        # leakage spine · ONNX parity · schema · beats-baseline
```

## Layout

```
src/      schema.py · features.py · train.py · tune.py · predict.py · export_onnx.py · evaluate.py · card.py
          survival.py (AFT) · ceiling.py + intervals.py (attainable denominators)
          attribution.py (what the within-stint signal is, and whether a feature could carry it)
          powerlaw_fit.py · powerlaw_ceiling.py · powerlaw.py (WI-17 power-law tyre curve; separate from v14)
tests/    test_features.py · test_targets.py · test_predict.py · test_onnx_parity.py · test_evaluate.py
          test_survival.py · test_manifest_contract.py · test_ceiling.py · test_attribution.py
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
  `card.py` refuses to write one. The effective sample is ~7,100 stints, not ~137,000 laps, so each margin is
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
