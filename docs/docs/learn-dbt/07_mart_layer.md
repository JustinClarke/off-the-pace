---
sidebar_position: 8
title: "Part 7: Feature Marts"
---

# Part 7: The mart layer and ML handoff

The mart layer defines the interface (data contract) between the transformation pipeline and the downstream machine learning systems at `ml/`. It builds optimized, physical tables (`materialized = 'table'`) representing clean features designed for predictive tasks.

---

## 7.1  All nine marts at a glance

| Mart | Grain | Primary use |
|---|---|---|
| `dim_events` | race | Race event flags (damage, retirements, penalties) |
| `fct_driver_skill_features` | driver × race | ML input A driver skill extraction |
| `fct_cliff_prediction_features` | lap | ML input B tyre cliff XGBoost (target: `next_lap_degradation_jump_s`) |
| `fct_lap_residuals` | lap | Analytics full residual decomposition with anomaly flags |
| `fct_telemetry_deltas` | telemetry (corner × driver pair) | Sector micro-analysis teammate corner speed deltas |
| `fct_stint_features` | stint | Strategy features thermal load, cliff onset, pit decision class |
| `fct_racecraft` | driver × race | Overtaking / defending on-track pass counts, DRS share, penalties |
| `fct_ghost_car_pace` | lap × ego driver × host constructor | Counterfactual pace decomposition |
| `fct_ghost_race_finish` | driver × race × host constructor | Simulated finish times under alternate-constructor scenarios |

---

## 7.2  ML Mart Separation and Leakage Protection

The machine learning models for tyre degradation (the Cliff Model) and driver ratings (the Driver Skill Model) consume entirely separate feature tables. Mixing features across these domains introduces severe **data leakage** and circular reasoning.

| Mart Table | Grain | Target Column | Excluded Features |
|---|---|---|---|
| `fct_driver_skill_features` | Driver × Race | `driver_skill_residual_mean_s` | Thermal loads, tyre push-load proxies. |
| `fct_cliff_prediction_features` | Lap | `next_lap_degradation_jump_s` | Driver-specific ratings, teammate deltas. |

*   **Driver Skill Mart** isolates driver skill and team constructor metrics, excluding push loads since explaining skill with pushing efforts is circular.
*   **Tyre Cliff Mart** isolates physical tyre decay, slide inputs, weather, and thermal EWMA loads, excluding driver identifiers to force the ML model to focus strictly on tyre physics.

---

## 7.3  Primary Machine Learning Marts

### 1. `fct_driver_skill_features`
This table aggregates lap-grain residuals up to the driver-race level. Each row captures the statistical summary of a driver’s execution across an event:
*   `driver_skill_proxy_mean_s`: Race-level average of the synthetic teammate delta.
*   `driver_residual_mean_s`: Race-level average of the seven-term residual.
*   `n_eligible_laps`: Count of clean racing laps contributing to the aggregations.
*   `ml_eligible`: Boolean flag excluding events with insufficient sample sizes.

### 2. `fct_cliff_prediction_features`
A lap-grain table designed to train the tyre-degradation predictor:
*   `age_in_stint`: Current tyre age (primary feature).
*   `cumulative_push_load_surface`: Accumulated EWMA thermal load proxy.
*   `dirty_air_intensity`: Wake exposure level from `int_lap_air_state`.
*   `next_lap_degradation_jump_s`: The ML target variable (how much pace is lost on the following lap compared to this one).

*Note: The last lap of a stint will carry a `NULL` target because no "next lap" exists on that tyre set. The ML training script automatically filters out these terminating laps.*

---

## 7.4  Racecraft & Strategy Marts

### 5. `fct_racecraft`
Race-craft summary per driver per race. Aggregates on-track pass statistics from `int_overtakes`, distinguishing: on-track passes (telemetry-confirmed), pit-cycle gains, SC/restart passes, and net position delta. Also carries penalty counts from `int_penalties`.

### 6. `fct_stint_features`
Stint-grain strategy feature table. Includes stint length, compound, starting tyre age, end-of-stint thermal load, cumulative dirty air tax, cliff onset lap, and an OLS pace-falloff slope. The `pit_decision_class` column (`optimal / overran / undercut_forced / early`) is derived from `int_pit_strategy_value` opportunity cost analysis.

---

## 7.5  Simulation Marts

### 7. `fct_ghost_car_pace`
This model generates pace simulations. It isolates the lap time a "ghost car" would complete if the ego driver were placed in a different constructor's car net of fuel weight, dirty air, and constructor disadvantages, leaving pure driver execution. Degenerate identity: ego == host constructor → predicted == actual.

### 8. `fct_ghost_race_finish`
Calculates simulated race finish positions by projecting cumulative race time for each (driver, host-constructor) scenario. Filtered to `recombination_confidence >= 0.3` to exclude sparse-panel extrapolations.

---

## 7.6  Model Schema Contracts

To protect downstream machine learning scripts from breaking due to upstream changes, we implement **dbt Model Contracts** inside `marts/schema.yml`.

dbt enforces these contracts at compilation time:
*   Any schema change (such as altering a column's data type from `DOUBLE` to `INTEGER` or renaming a target column) will fail the build before execution begins.
*   This prevents corrupted or mistyped columns from silently breaking automated training pipelines.

---

## 7.7  Verifying Gold Mart Output Counts

Run direct validation checks from the project root using DuckDB:

```bash
# Execute row checks against gold tables
.venv/bin/python -c "
import duckdb
con = duckdb.connect('data/dev.duckdb')
print('driver skill rows:', con.execute('SELECT COUNT(*) FROM fct_driver_skill_features').fetchone()[0])
print('cliff features rows:', con.execute('SELECT COUNT(*) FROM fct_cliff_prediction_features').fetchone()[0])
print('ml_eligible rows:', con.execute('SELECT COUNT(*) FROM fct_cliff_prediction_features WHERE ml_eligible = TRUE').fetchone()[0])
"
```

Expected outputs will scale with your ingested seasons (typically several thousand driver-race rows and over $100\text{K}$ lap feature rows).

---

**Before continuing:** confirm that all schema contract validations pass using `dbt test`.

**Continue to [Part 8  Tests, docs, and the production toolchain](./08_tests_docs_toolchain.md).**
