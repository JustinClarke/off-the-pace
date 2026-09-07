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
tests/    test_features.py · test_targets.py · test_predict.py · test_onnx_parity.py · test_evaluate.py
          test_survival.py · test_manifest_contract.py · test_ceiling.py · test_attribution.py
          test_fit_parity.py (search == evaluation == production refit)
models/   *.bst/*.onnx (gitignored) · encoders.json / manifest.json / model_card.json (tracked) · training_logs/ optuna_studies/
artefacts/ PNGs + eval parquets (gitignored, regen-able)
```

## Contracts

- **Holdout** is data-derived (`MAX(race_year)+1`), never hardcoded pinned by `test_no_hardcoded_holdout`.
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
