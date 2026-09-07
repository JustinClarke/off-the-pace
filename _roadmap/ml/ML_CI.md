# ML CI & Evaluation Testing

The Continuous Integration (CI) pipeline for the **Off The Pace** ML layer enforces unusually strict statistical parity, schema safety, and anti-leakage guarantees. It is built to ensure that no corrupted model, feature drift, or uncalibrated hyperparameter can reach production.

Run primarily via `pytest` (in `ml/tests`), the suite gates production builds on several rigid axioms.

---

## 1. Strict Leakage Guards

Leakage is the deadliest risk when predicting physical residuals from highly structured racing data.

* **`test_features.py`**: Ensures no forbidden variables (e.g., `driver_skill_residual_s`, `lap_id`, target variables, or future-peeking aggregations) sneak into the training `X` matrix. These are hardcoded in `schema.EXCLUDED_LEAKAGE_COLUMNS` and mirrored by SQL assertions in the transform layer.
* **Temporal Integrity**: Ensures that the `holdout_season` is strictly derived (`MAX(race_year) + 1`), preventing models from being over-optimistically tested against historical data they have implicitly learned from.

---

## 2. ONNX Parity Enforcement

Since models are evaluated in Python (XGBoost) but deployed in the browser (ONNX), inference parity must be mathematically exact.

* **`test_onnx_parity.py`**: Ensures that every single exported `.onnx` model matches its `.bst` counterpart exactly across the validation set. The predictions must align to an absolute tolerance (`atol`) of **`1e-5`**. If the ONNX conversion degrades precision or mishandles NaNs (a common issue with tree models and null splits), the build fails.

---

## 3. Contract & Schema Drift Tests

The ML models operate on a 41-feature contract that must remain perfectly synchronized with the upstream dbt `fct_cliff_prediction_features` mart.

* **`test_feature_contract_subset_of_mart`**: Asserts that every feature required by the model exists in the latest build of the data warehouse. It will fail on schema drift in either direction (missing features, or newly unmapped columns).

---

## 4. Model Evaluation & Baselines

Before a model replaces the current production active version, it is dynamically verified against strong heuristic baselines.

* **`test_evaluate.py` / Beats-Baseline Verification**: The evaluation runs the model against a deterministic baseline (e.g., empirical 10th/90th percentile across compound+circuit+age-bucket cells for degradation, or the majority-class prior for the classifier). The CI flags an error or warning if the new ML model fails to outperform these basic aggregated heuristics on the evaluation fold. 
* **Target Schema Tests (`test_targets.py`)**: Tests ensure target labels have logical properties, for instance ensuring regression predictions conform to valid boundaries and classes adhere strictly to soft probability limits.

---

## 5. Determinism & Reproducibility

* **Dataset Fingerprinting**: The pipeline takes a SHA256 fingerprint of the dataset and logs it into the auto-generated `model_card.yml`. This tracks whether upstream data mutations silently altered the underlying dataset.
* **Random State Enforcement**: `RANDOM_STATE` is propagated universally to guarantee that retrying the `make ml-train` pipeline identically reconstructs the exact same splits and decision boundaries.
