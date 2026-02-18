---
sidebar_position: 3
title: The feature pipeline
---

# The feature pipeline

The models see **38 features in 9 physics-grouped families**, all read from a single contracted mart, [`fct_cliff_prediction_features`](/reference/models/fct/fct_cliff_prediction_features). Nothing is hand-engineered inside `ml/` beyond deterministic encoding the physics lives in the dbt transform layer, and the machine layer consumes it read-only.

---

## The nine feature groups

| Group | # | Features | What it encodes |
|---|---|---|---|
| **stint_position** | 4 | `lap_number`, `lap_in_stint`, `age_in_stint`, `fuel_mass_kg` | where the lap sits in race and stint, and car mass |
| **compound** | 7 | `compound`, `compound_grip_peak`, `compound_wear_gradient`, `compound_optimal_temp_low/high`, `compound_cliff_onset_laps`, `compound_cliff_severity` | the compound and its fitted physical character |
| **cliff_prior** | 5 | `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`, `cliff_candidate_flag` | the statistical KM prior, handed to the model as a starting point |
| **thermal** | 3 | `push_residual`, `cumulative_push_load_surface`, `cumulative_push_load_bulk` | how hard the tyre has been worked, surface vs bulk |
| **dirty_air** | 4 | `dirty_air_share_lap`, `dirty_air_thermal_load_surface/bulk`, `air_state_dominant` | wake exposure and its heat load |
| **powertrain** | 6 | `n_gear_changes`, `mean_rpm`, `max_rpm`, `pct_full_throttle`, `pct_drs_active`, `short_shift_index` | driving style / energy signature from telemetry |
| **weather_air** | 4 | `ambient_temp_delta`, `air_density_kgm3`, `density_ratio_to_ref`, `is_rain_lap` | ambient conditions affecting grip and cooling |
| **track** | 2 | `track_energy_index`, `circuit_abrasiveness_index` | circuit-level tyre stress |
| **context** | 3 | `constructor_id`, `event_flag_any`, `anomaly_class` | car performance and lap anomalies |

These same nine groups are the unit of the **ablation study** ([Calibration & importance](/machine-learning/calibration-and-importance)) each group is dropped in turn to measure its contribution.

## Categorical handling

Four features are categorical and are ordinal-encoded deterministically (the encoder map is published in `ml/models/encoders.json`):

| Feature | Cardinality |
|---|---|
| `compound` | 8 |
| `air_state_dominant` | 4 |
| `constructor_id` | 18 |
| `anomaly_class` | 3 |

Unseen or NULL categories map to a reserved `-1` sentinel. Continuous NULLs are **preserved as NaN** and handled natively by XGBoost's default-direction splits not imputed. This matters because ~47% of laps have a NULL cliff-onset prior (2018 legacy compounds and un-fit circuits); the model carries that missingness as signal rather than papering over it. The choice is documented, and its ONNX round-trip is proven on a **NaN-bearing** parity sample.

## What the model is *not* allowed to see

A long list of columns is excluded from `X` as leakage, pinned by `schema.EXCLUDED_LEAKAGE_COLUMNS` and a dbt test (`assert_no_leakage_columns.sql`). They fall into three classes:

- **The targets themselves** and their alternate horizons (`next_lap_degradation_jump_s`, `next_3/5_lap_cumulative_jump_s`, `laps_until_cliff_class`, `remaining_stint_life_laps`).
- **Driver-skill signals** (`driver_id`, `driver_skill_residual_s`, `driver_skill_proxy_s`, …)-including them would let the trees relearn the exact human residual the decomposition works to strip out.
- **Identifiers that encode the season** (`race_year`, `race_id`, `circuit_key`, `stint_id`, `lap_id`) plus the training-eligibility gate.

`driver_id` and `race_year` are the two most important exclusions, and an [adversarial probe](/machine-learning/validation-and-leakage) demonstrates *why* they would leak rather than asserting it.

## From mart to matrix

`ml/src/features.py` is a read-only loader that turns the mart into a deterministic `float32` matrix: it applies the encoders, preserves NaN, drops NULL-target rows **per target**, fixes the 38-column order, and emits a **SHA256 dataset fingerprint** that is logged into the model card. The same bytes in produce the same fingerprint out the first link in the [reproducibility](/machine-learning/reproducibility-and-deployment) chain.
