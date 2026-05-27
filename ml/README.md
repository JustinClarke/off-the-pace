# `ml/` Machine Learning Layer

XGBoost tyre-degradation models trained on `fct_cliff_prediction_features` (the gold lap-grain mart).
Reads the warehouse **read-only**; publishes artefacts to `ml/models/`, which the application layer pulls from.
Narrative docs: [Machine Learning section](../docs/ml/overview.mdx) · auto-generated [model card](../docs/reference/ml/degradation-model-v1.mdx).

## Production artefacts

- `degradation_regressor_p10` / `_p50` / `_p90` quantile trio for next-lap fuel-corrected pace jump (s).
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
tests/    test_features.py · test_targets.py · test_predict.py · test_onnx_parity.py · test_evaluate.py
models/   *.bst/*.onnx (gitignored) · encoders.json / manifest.json / model_card.json (tracked) · training_logs/ optuna_studies/
artefacts/ PNGs + eval parquets (gitignored, regen-able)
```

## Contracts

- **Holdout** is data-derived (`MAX(race_year)+1`), never hardcoded pinned by `test_no_hardcoded_holdout`.
- **No leaked columns** (`driver_skill_*`, identifiers, targets, gate) ever enter `X` pinned by `schema.EXCLUDED_LEAKAGE_COLUMNS` and `transform/tests/assert_no_leakage_columns.sql`.
- **Feature contract ⊆ live mart** `test_feature_contract_subset_of_mart` fails the build on schema drift in either direction.
- **Determinism** `RANDOM_STATE` everywhere; dataset SHA256 fingerprint logged in the card.
- **ONNX parity** every `.onnx` must match its `.bst` within `atol=1e-5`; the tolerance is never loosened.

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
