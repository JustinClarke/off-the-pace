# `ml/`-Machine Learning Layer ✅ (all 7 build milestones complete)

XGBoost degradation models trained on `fct_cliff_prediction_features` (the gold lap-grain mart).
Reads the warehouse **read-only**; publishes artefacts to `ml/models/` (never to `app/`-application layer pulls).
Narrative docs: [Machine Learning section](../docs/docs/machine-learning/index.md) · auto-generated [model card](../docs/docs/reference/ml/degradation-model-v1.mdx).

## Five production artefacts
- `degradation_regressor_p10_v1`, `_p50_v1`, `_p90_v1`-quantile trio for next-lap fuel-corrected pace jump (s).
- `cliff_classifier_v1`-`laps_until_cliff_class` ∈ {`0_to_2`, `3_to_5`, `6_plus`, `none_in_stint`}.
- `stint_life_regressor_v1`-`remaining_stint_life_laps` (synthesised; ≥ 0).

Each ships as a `.bst` **and** a parity-tested `.onnx` (atol=1e-5).

## Quickstart (one venv at repo root)
```bash
make ml-setup       # install ml/requirements.txt into ./.venv
make ml-features    # audit: leakage guards + forward-window + season split
make ml-train       # smoke / production train
make ml-predict     # score all laps → data/marts/mart_degradation_predictions.parquet
make ml-onnx        # export + parity gate → ml/models/
make ml-tune        # Optuna search + production refit
make ml-evaluate    # baselines, cohorts, calibration, importance
make ml-card        # assemble model_card.yml/.json
make ml-reference   # regenerate the docs model card MDX
make ml-all         # the whole pipeline, end to end
make ml-test        # 27 tests: leakage spine, ONNX parity, schema, beats-baseline
```

## Layout
```
src/      schema.py · features.py · train.py · tune.py · predict.py · export_onnx.py · evaluate.py · card.py
tests/    test_features.py · test_targets.py · test_predict.py · test_onnx_parity.py · test_evaluate.py
models/   *.bst/*.onnx (gitignored) · encoders.json/manifest.json/model_card.json (tracked) · training_logs/ optuna_studies/
artefacts/ PNGs + eval parquets (gitignored, regen-able)
```

## Contracts
- **Holdout** is data-derived: `MAX(race_year)+1` (= 2025 today, not yet ingested). No literal `2025` in `ml/src`.
- **No leaked columns** (`driver_skill_*`, identifiers, targets, gate) ever enter `X`-pinned by `schema.EXCLUDED_LEAKAGE_COLUMNS` and `transform/tests/assert_no_leakage_columns.sql`.
- **Determinism:** `RANDOM_STATE` everywhere; dataset SHA256 fingerprint logged in the card.

See **`BUILD_LOG.md`** for the full build record, live reconciliation, and deviations.

## Tracked vs generated

| Path | Status | Notes |
|---|---|---|
| `models/encoders.json` | **tracked** | Ordinal encoder mappings-required at inference time |
| `models/manifest.json` | **tracked** | Model registry: names, versions, feature list, paths |
| `models/model_card.json` | **tracked** | Machine-readable model card (source: `model_card.yml`) |
| `models/*.bst` | gitignored | XGBoost binary checkpoints-regenerate with `make ml-train` |
| `models/*.onnx` | gitignored | ONNX exports-regenerate with `make ml-onnx` |
| `models/training_logs/` | gitignored | Optuna / XGBoost training logs |
| `models/optuna_studies/` | gitignored | Optuna study databases |
| `artefacts/*.png` | gitignored | Evaluation plots-regenerate with `make ml-evaluate` |
| `artefacts/*.parquet` | gitignored | Evaluation data frames-regenerate with `make ml-evaluate` |

---

← Previous in tour: [transform/](../transform/README.md) · **Next in tour: [app/](../app/README.md) →**
