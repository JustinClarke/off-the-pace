# ml/tests/ Leakage and Parity Spine

These tests are the ML layer's CI gate. They enforce three non-negotiable properties: no data
leakage, ONNX numerical parity, and beating the baseline. All must pass before any model is
considered production-ready.

## Test files

| File | What it asserts | Count |
|---|---|---|
| `test_features.py` | No leaked columns (`driver_skill_*`, `driver_id`, `race_year`) reach `X`; no forward-looking features; feature contract ⊆ live mart; non-null targets, bounded by the clip their own column carries, and never also a feature at any horizon; no hardcoded holdout year | 21 |
| `test_targets.py` | Target distributions are non-degenerate (not constant, not all-zero) | 3 |
| `test_predict.py` | Predictions have correct shape, dtype, and value range per model type (regressor: float, classifier: valid class label) | 3 |
| `test_onnx_parity.py` | Every ONNX model's output matches the `.bst` booster within `atol=1e-5` on a NaN-bearing sample | 5 |
| `test_evaluate.py` | Every model beats a strong per-cohort mean baseline on its headline metric; calibration within tolerance; every model carries an attainable ceiling and every beats-baseline claim an interval | 19 |
| `test_survival.py` | Stint life is fitted and scored as right-censored AFT, never as pooled RMSE; the manifest's constants really do turn a margin back into laps | 18 |
| `test_manifest_contract.py` | The manifest names a version whose artefacts exist and whose input width matches the real booster; the app copies match; every `beats_baseline` claim on the card carries an interval, and that gate is proven to fire | 18 |
| `test_ceiling.py` | The between-stint variance estimator recovers a known ICC where the naive one inflates it; rolling-window overlap is detected and thinned; the in-sample stint oracle really is the optimum over stint-constant predictors; clustered intervals are wider than lap-grain ones | 19 |

| `test_attribution.py` | The flatten really is a pure within-stint operation (per-stint means preserved, between-stint share driven to 1.0); a planted per-lap driver and a planted stint-level one separate under it where a drop cannot tell them apart; the causal summary over laps 1..t provably never reads a later lap; a planted look-ahead result is named unreachable | 33 |
| `test_fit_parity.py` | The search, the evaluation refit and the production refit fit the same model: the quantile trio's IPW survival weights and the AFT censoring flag reach every fold of every path, sliced to that fold's own rows; a quantile fit offered no weights raises rather than defaulting; and a refit that would replace a version fitted on a different target column is refused | 24 |
| `test_search_space.py` | The hyperparameter space is declared once and `_suggest` builds from it, so no suggestion can leave the bounds the pin detector reads; `boundary_params` names a best-params set that stopped on an edge, and is proven to fire at each ceiling, at each floor, and to stay silent in the interior | 14 |

## Infrastructure

- `conftest.py`-shared fixtures: loads `models/manifest.json`, initialises DuckDB from
  bronze fixtures in `transform/tests/fixtures/bronze/`, and provides a pre-loaded feature
  matrix. Tests that need a populated mart gate on the fixture being present.
- `__init__.py`-empty; marks this directory as a Python package for pytest discovery.

## Run

```bash
make ml-test     # runs all 177 tests via pytest ml/tests/ -v
```

CI pipeline: `.github/workflows/ml-ci.yml`-any failure is red.
