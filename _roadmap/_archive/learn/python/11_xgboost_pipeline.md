# Module 11 — XGBoost, Optuna & ONNX Pipeline

> **Goal:** Understand the end-to-end ML pipeline: hyperparameter tuning, model training, ONNX export, and parity testing.

---

## 1. Concept: XGBoost basics

XGBoost builds an ensemble of decision trees, each one correcting the errors of the previous.

```python
import xgboost as xgb
import numpy as np

# Regression
X = np.random.randn(100, 5).astype(np.float32)
y = X[:, 0] * 2 + X[:, 1] + np.random.randn(100) * 0.1

model = xgb.XGBRegressor(
    n_estimators=100,    # number of trees
    max_depth=4,         # max depth per tree
    learning_rate=0.1,   # shrinkage factor
    tree_method="hist",  # fast histogram-based splitting
)
model.fit(X, y)
predictions = model.predict(X[:5])

# Classification
model_cls = xgb.XGBClassifier(
    objective="multi:softprob",
    num_class=4,
    n_estimators=100,
)
```

### Codebase connection

The repo constructs models based on the target spec:

```python
# ml/src/train.py (lines 55-63)
def _make_model(spec, params):
    common = dict(tree_method="hist", random_state=S.RANDOM_STATE, n_jobs=os.cpu_count(), **params)
    if spec.kind == "quantile":
        return xgb.XGBRegressor(objective="reg:quantileerror", quantile_alpha=spec.quantile_alpha, **common)
    if spec.kind == "classification":
        return xgb.XGBClassifier(objective="multi:softprob", **common)
    return xgb.XGBRegressor(objective="reg:squarederror", **common)
```

Three objectives for five models:
- `reg:quantileerror` — degradation p10, p50, p90
- `multi:softprob` — cliff classifier
- `reg:squarederror` — stint life regressor

---

## 2. Concept: Hyperparameter tuning with Optuna

Optuna searches for the best hyperparameters using Bayesian optimization (TPE sampler).

```python
import optuna

def objective(trial):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 200, 700, step=100),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
    }
    # Train model with params, evaluate on validation set
    model = xgb.XGBRegressor(**params)
    model.fit(X_train, y_train)
    score = some_metric(y_val, model.predict(X_val))
    return score

study = optuna.create_study(direction="minimize")
study.optimize(objective, n_trials=50)
print(f"Best params: {study.best_params}")
```

### Codebase connection

```python
# ml/src/tune.py (lines 36-47)
def _suggest(trial: optuna.Trial) -> dict:
    return {
        "n_estimators": trial.suggest_int("n_estimators", 200, 700, step=100),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 5.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
        "gamma": trial.suggest_float("gamma", 1e-3, 5.0, log=True),
    }
```

Key features:
- **`log=True`** for learning rate and regularization — searches on a logarithmic scale (0.02 to 0.2 is better than 0.02 to 200)
- **MedianPruner** stops unpromising trials early
- **TPESampler** uses previous results to guide the search (not random)
- Study is persisted to SQLite so you can resume interrupted runs

---

## 3. Concept: Save and load XGBoost models

```python
# Save
model.save_model("model.bst")  # binary format

# Load (need to know the model type)
loaded = xgb.XGBRegressor()
loaded.load_model("model.bst")
```

### Codebase connection

```python
# ml/src/train.py (lines 127-128)
bst_path = MODELS_DIR / f"{S.artefact_name(spec, version)}.bst"
final.save_model(str(bst_path))
```

---

## 4. Concept: ONNX export — making models portable

ONNX (Open Neural Network Exchange) is a standard format that runs anywhere — Python, JavaScript (browser), C++, mobile.

```python
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType

# Convert XGBoost → ONNX
onx = onnxmltools.convert_xgboost(
    model,
    initial_types=[("input", FloatTensorType([None, n_features]))]
)
Path("model.onnx").write_bytes(onx.SerializeToString())
```

### Codebase connection

```python
# ml/src/export_onnx.py (lines 60-68)
def convert(target, version):
    spec = S.TARGET_BY_NAME[target]
    bst_path, onnx_path = _paths(spec, version)
    model = _load_sklearn(spec, bst_path)
    n_features = int(getattr(model, "n_features_in_", len(S.FEATURE_COLUMNS)))
    onx = onnxmltools.convert_xgboost(
        model, initial_types=[("input", FloatTensorType([None, n_features]))]
    )
    onnx_path.write_bytes(onx.SerializeToString())
```

**Why ONNX?** The models are trained in Python but scored in the **browser** (JavaScript). ONNX Runtime Web runs the same model in both environments with identical results.

---

## 5. Concept: Parity testing — proving the export is faithful

After converting to ONNX, you must **prove** the ONNX model produces the same predictions as the original XGBoost model.

```python
import onnxruntime as ort
import numpy as np

# Run both models on the same input
sample = X_test[:500].astype(np.float32)

# XGBoost predictions
xgb_pred = model.predict(sample)

# ONNX predictions
sess = ort.InferenceSession("model.onnx", providers=["CPUExecutionProvider"])
onnx_pred = sess.run(None, {"input": sample})[0].reshape(-1)

# Check parity
max_diff = np.max(np.abs(xgb_pred - onnx_pred))
assert np.allclose(xgb_pred, onnx_pred, atol=1e-5, rtol=1e-5), f"Parity failed: max_diff={max_diff}"
```

### Codebase connection

```python
# ml/src/export_onnx.py (lines 84-103)
def parity(target, version, sample):
    # ... load both models, run predictions
    a, b = bst.reshape(-1).astype(np.float64), onx.reshape(-1).astype(np.float64)
    max_abs = float(np.max(np.abs(a - b)))
    max_rel = float(np.max(np.abs(a - b) / (np.abs(a) + 1e-9)))
    ok = bool(np.allclose(a, b, atol=ATOL, rtol=RTOL))
    return {"target": target, "max_abs_diff": max_abs, "max_rel_diff": max_rel, "pass": ok}
```

Critical detail: the parity test uses a **NaN-bearing sample** — real data with missing values:

```python
# ml/src/export_onnx.py (lines 106-121)
def nan_bearing_sample(n=500, seed=S.RANDOM_STATE):
    """500-row float32 sample GUARANTEED to contain NaN."""
    # ... picks 50% NaN rows, 50% clean rows
    assert np.isnan(sample).any(), "parity sample must contain NaN"
    return sample
```

**Why NaN-bearing?** XGBoost handles NaN natively (it learns which direction to send missing values at each split). The ONNX export must preserve this behavior exactly. Testing only on clean data would miss NaN-handling bugs.

---

## 6. Concept: The publish manifest

The ONNX export produces a `manifest.json` — the single file the browser app reads to discover and correctly use the models.

```python
# ml/src/export_onnx.py (lines 176-211)
manifest = {
    "model_version": version,
    "input": {
        "feature_order": list(S.FEATURE_COLUMNS),   # positional — DO NOT reorder
        "encoding": {"encoders": encoders},
    },
    "models": [{"name": "degradation_regressor_p50", "onnx": "model.onnx", ...}],
    "provenance": {"training_seasons": [...], "dataset_fingerprint": "abc123"},
}
```

---

## 7. Guided exercises

### Exercise 1: Train and evaluate an XGBoost model

```python
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit

# Generate fake time-series data
rng = np.random.default_rng(42)
n = 1000
seasons = np.repeat([2018, 2019, 2020, 2021, 2022, 2023, 2024], n // 7 + 1)[:n]
X = rng.standard_normal((n, 5)).astype(np.float32)
y = X[:, 0] * 0.5 + X[:, 2] * 0.3 + rng.standard_normal(n) * 0.1

# Season-based CV (like the repo)
unique_seasons = sorted(set(seasons))
tscv = TimeSeriesSplit(n_splits=5)
for fold, (tr_idx, val_idx) in enumerate(tscv.split(unique_seasons)):
    train_seasons = [unique_seasons[i] for i in tr_idx]
    val_seasons = [unique_seasons[i] for i in val_idx]
    
    train_mask = np.isin(seasons, train_seasons)
    val_mask = np.isin(seasons, val_seasons)
    
    model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, tree_method="hist")
    model.fit(X[train_mask], y[train_mask])
    pred = model.predict(X[val_mask])
    
    rmse = float(np.sqrt(np.mean((y[val_mask] - pred) ** 2)))
    print(f"Fold {fold}: train={train_seasons}, val={val_seasons}, RMSE={rmse:.4f}")
```

### Exercise 2: Convert to ONNX and check parity

```python
# After Exercise 1: export the final model
import onnxmltools
import onnxruntime as ort
from onnxmltools.convert.common.data_types import FloatTensorType

# Train final model on all data
final_model = xgb.XGBRegressor(n_estimators=100, max_depth=4)
final_model.fit(X, y)

# Convert to ONNX
onx = onnxmltools.convert_xgboost(
    final_model, initial_types=[("input", FloatTensorType([None, 5]))]
)
with open("test_model.onnx", "wb") as f:
    f.write(onx.SerializeToString())

# Parity check
sample = X[:100]
xgb_pred = final_model.predict(sample)

sess = ort.InferenceSession("test_model.onnx", providers=["CPUExecutionProvider"])
onnx_pred = sess.run(None, {"input": sample})[0].reshape(-1)

max_diff = float(np.max(np.abs(xgb_pred - onnx_pred)))
print(f"Max absolute diff: {max_diff:.2e}")
print(f"Parity: {'PASS' if max_diff < 1e-5 else 'FAIL'}")
```

---

## 8. Interview drills

**Q1:** Why export models to ONNX instead of serving XGBoost directly?

> **A:** The app runs entirely in the browser — there's no server. ONNX Runtime Web runs ONNX models in JavaScript. The user's browser downloads the ONNX files and runs inference locally. This means zero server costs for inference and sub-10ms predictions.

**Q2:** What is parity testing and why is it critical?

> **A:** Parity testing verifies that the ONNX model produces identical predictions to the original XGBoost model. The conversion process could introduce floating-point errors, change NaN handling, or reorder class probabilities. The repo tests with NaN-bearing samples at `atol=1e-5` and `rtol=1e-5`. If parity fails, the export is rejected — nothing ships.

**Q3:** What's the difference between `reg:quantileerror` and `reg:squarederror`?

> **A:** `squarederror` minimizes mean squared error (predicts the conditional mean). `quantileerror` minimizes pinball loss at a specific quantile. The repo trains three quantile models (p10, p50, p90) to get a prediction *interval* rather than a point estimate: "degradation will be 0.1s–0.5s with 80% confidence."

**Q4:** Why does Optuna use `log=True` for learning rate?

> **A:** Learning rate spans orders of magnitude (0.01 to 0.3). On a linear scale, Optuna would spend most trials between 0.15–0.3 and rarely try small values like 0.02. `log=True` searches uniformly on the log scale, giving equal exploration to 0.02–0.06 and 0.1–0.3.

**Q5:** What is the MedianPruner?

> **A:** It stops a trial early if its intermediate metric is worse than the median of all completed trials at the same step. In the repo, each "step" is a CV fold. If fold 2 already shows the params are worse than median, the remaining folds are skipped, saving 60% of compute.

---

## 9. Checkpoint

You should now be able to:

- [ ] Train XGBoost regressors and classifiers
- [ ] Use Optuna for Bayesian hyperparameter search
- [ ] Export XGBoost models to ONNX format
- [ ] Run ONNX inference with `onnxruntime`
- [ ] Implement and explain parity testing
- [ ] Explain the quantile regression trio pattern
