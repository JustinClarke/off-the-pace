# ml/tests/-The 27-Test Leakage and Parity Spine

These tests are the ML layer's CI gate. They enforce three non-negotiable properties: no data
leakage, ONNX numerical parity, and beating the baseline. All 27 pass before any model is
considered production-ready.

## Test files

| File | What it asserts | Count |
|---|---|---|
| `test_features.py` | No leaked columns (`driver_skill_*`, `driver_id`, `race_year`) reach `X`; no forward-looking features; feature set matches `schema.FEATURE_COLUMNS` | ~6 |
| `test_targets.py` | Target distributions are non-degenerate (not constant, not all-zero); regression targets are ≥ 0 | ~4 |
| `test_predict.py` | Predictions have correct shape, dtype, and value range per model type (regressor: float, classifier: valid class label) | ~5 |
| `test_onnx_parity.py` | Every ONNX model's output matches the `.bst` booster within `atol=1e-5` on 100 randomly sampled rows | ~5 |
| `test_evaluate.py` | Every model beats a strong per-cohort mean baseline on its headline metric; calibration within tolerance | ~7 |

## Infrastructure

- `conftest.py`-shared fixtures: loads `models/manifest.json`, initialises DuckDB from
  bronze fixtures in `transform/tests/fixtures/bronze/`, and provides a pre-loaded feature
  matrix. Tests that need a populated mart gate on the fixture being present.
- `__init__.py`-empty; marks this directory as a Python package for pytest discovery.

## Run

```bash
make ml-test     # runs all 27 tests via pytest ml/tests/ -v
```

CI pipeline: `.github/workflows/ml-ci.yml`-any failure is red.
