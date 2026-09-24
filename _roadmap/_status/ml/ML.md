# Machine Learning Layer Breakdown

The **machine learning layer** of **Off The Pace** is tasked with predicting tyre degradation and forecasting when a tyre cliff will happen. Built on a spine of **42 features** extracted from the analytical dbt layer (`fct_cliff_prediction_features`), it comprises **five XGBoost models** trained on over 113,000 F1 laps spanning from 2018 to 2024. 

The primary goal of this layer is to provide real-time race-strategy analytics for the web app, identifying when a stint is about to fall off the degradation cliff and how much pace the driver is leaving on the track.

---

## 1. The Five Production Models

The layer serves a suite of distinct models predicting three critical aspects of tyre degradation and stint pacing.

* **`degradation_regressor_p10` / `_p50` / `_p90`**: A quantile regression trio predicting the next-lap fuel-corrected pace jump. The target is bounded to capture both tyre degradation and recovery events (e.g. burn-off, out-lap recovery).
* **`cliff_classifier`**: A multi-class soft probability classifier predicting the number of laps until the tyre cliff hits (`0_to_2`, `3_to_5`, `6_plus`, `none_in_stint`).
* **`stint_life_regressor`**: A standard squared-error regressor estimating the total remaining stint life (in laps).

All models are built using **XGBoost**. They decisively beat naive baselines constructed from cohort means, giving real predictive lift beyond historic averages.

---

## 2. Feature Engineering & Spine

Models consume an engineered spine of 41 physical, powertrain, and contextual features:

* **Stint Position**: `lap_number`, `lap_in_stint`, `age_in_stint`, `fuel_mass_kg`
* **Compound Traits**: Tyre type, peak grip, degradation gradients, optimal temperature window, and historical cliff onset priors.
* **Thermal Load & Clean-Lap Physics**: The calculated `push_residual`, cumulative load on bulk and surface.
* **Dirty Air**: Share of the lap spent in dirty air, along with the corresponding surface and bulk thermal loads.
* **Powertrain Telemetry**: Gear changes, RPM, full throttle %, DRS usage.
* **Weather & Track State**: Ambient temperature delta, rain flag, track energy index, circuit abrasiveness.
* **Contextual Features**: Constructor ID, anomaly class flags, and specific event flags.

---

## 3. Key Patterns & Statistical Practices

* **Quantile Regression (Pinball Loss)**: Instead of just predicting a single mean expectation for pace degradation, predicting the 10th, 50th, and 90th percentiles captures the asymmetrical variance inherent to tyre wear.
* **Holdout Validation via TimeSeriesSplit**: Data across seasons is highly non-stationary due to rule changes. The system uses season-grouped `TimeSeriesSplit` (expanding window) ensuring no future leakage. The headline evaluation happens on the final available fold (2024), acting as a proxy for true future holdout (2025).
* **Feature Leakage Exclusion**: Excluded explicitly are identifying traits that allow models to memorize the target: `race_year` is dropped because it acts as an adversarial proxy for driver skill (due to regulations/calendar), and `driver_id` is dropped to prevent the model from relearning the exact driver-skill residual extracted in the transform layer.

---

## 4. Architecture & Artefacts

* **Read-Only Data Ingestion**: The training pipeline reads strictly from the local data warehouse (built via dbt and DuckDB). No mutations happen to the base data inside the ML layer.
* **Model Artefacts**: Each trained model is dumped both as an XGBoost binary checkpoint (`.bst`) and exported to ONNX (`.onnx`) format.
* **Manifests & Registries**: Metadata tracking happens through version-controlled files like `models/manifest.json` and `models/model_card.json`, mapping models, feature layouts, and encoders.

---

## 5. Handoff to Application Layer

The final `.onnx` models are consumed directly by the React Browser Frontend (`app/`). This allows the application to execute the models at runtime in the client-side browser using **ONNX Runtime Web**, resulting in true zero-server-compute cost inference for dynamic race strategy simulations.
