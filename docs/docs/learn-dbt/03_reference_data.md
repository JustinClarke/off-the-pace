---
sidebar_position: 4
title: "Part 3: Seeds & Dimensions"
---

# Part 3: Reference data: seeds and dimensions

Reference data provides the physical, logistical, and historical context required to interpret telemetry and lap-time data. This includes track geometries, physical characteristics, tyre compound properties, and driver/constructor metadata.

---

## 3.1  The Role of Seeds in dbt

A **Seed** is a static CSV file managed inside `seeds/` that dbt compiles and loads directly into the database as physical tables via the `dbt seed` execution step.

### Seed Criteria
*   The raw data is relatively small (< 10K rows) and changes rarely.
*   The parameters are calculated externally (e.g. calculated via offline statistical models) and need to be version-controlled in Git.
*   Other pipeline models import these parameters using standard Jinja `{{ ref() }}` statements.

---

## 3.2  Pipeline Seeds

The transform pipeline utilizes **6 distinct seeds** to govern calculations:

| Seed Table | Purpose | Main Columns |
|---|---|---|
| `circuit_reference.csv` | Physical circuit parameters and weight-penalty coefficients. | `circuit_key`, `lap_length_km`, `n_corners`, `weight_penalty_factor` |
| `compound_cliff_params.csv` | Kaplan-Meier survival curves and wear rates. | `season`, `compound`, `compound_cliff_onset_laps`, `compound_cliff_severity` |
| `dim_corners.csv` | Apex distance metrics and track geometries. | `circuit_key`, `corner_number`, `distance_m` |
| `race_to_track.csv` | Map race event identifiers to track geometries. | `race_id`, `circuit_key` |
| `raw_dim_events.csv` | Outlier descriptors and structural safety periods. | `race_id`, `event_type`, `lap_start`, `lap_end` |
| `tyre_allocations.csv` | Pre-allocated compound assignments. | `season`, `compound`, `allocation_code` |

---

## 3.3  `dim_circuits`   Physical Circuit Constants

`dim_circuits` is a SQL model compiled from `circuit_reference.csv`. It structures the track metrics necessary to calculate fuel consumption and weight-corrections downstream.

Example track metadata Suzuka (Japan, `suzuka`):
*   `lap_length_km`: $5.807\text{ km}$
*   `n_corners`: **18**
*   `fuel_consumption_rate`: $1.85\text{ kg/lap}$
*   `weight_penalty_factor`: $0.028\text{ s/kg}$ (lap-time penalty incurred per additional kilogram of mass).

### Weight-Penalty Estimation Mechanics
The `weight_penalty_factor` represents the causal effect of fuel mass on pace. It is defined using two distinct estimation paradigms:
1.  **Fitted (`first_stint_regression_v1`):** Calibrated via Ordinary Least Squares (OLS) regression on clean first-stint telemetry where sample size is dense.
2.  **Formula-Based prior:** Applied when regression noise is high due to incident outliers or extreme weather variance:
    $$\text{weight\_penalty} = 0.02 + 0.0002 \times \text{corners} \times \bar{g}$$

---

## 3.4  `dim_compounds_season`   Tyre Wear Parameters

Tyre degradation is highly sensitive to compounds, track surfaces, and rule cycles. `dim_compounds_season` is a SQL model built from `compound_cliff_params.csv`, mapping fitted survival variables per circuit, compound, and season.

These parameters govern the tyre decay baseline:
*   `compound_grip_peak`: Base grip coefficient at zero tyre age.
*   `compound_wear_gradient`: Linear degradation rate (s/lap) under normal wear.
*   `compound_cliff_onset_laps`: Estimated tyre age (laps) at which the compound hits structural degradation (the cliff).
*   `compound_cliff_severity`: Accelerated wear gradient applied after the cliff onset.

### Kaplan-Meier Tyre Survival Analysis
Standard linear regression underestimates tyre life because drivers voluntarily pit before tyre failure occurs (right-censoring). To calculate the correct cliff onset ($\tau$), the offline model utilizes **Kaplan-Meier survival analysis**, treating voluntary pit stops as censored data points rather than failures.

---

## 3.5  Derived Dimensions: `dim_drivers` & `dim_constructors`

Unlike static seeds, driver and team profiles evolve dynamically as new race telemetry is ingested. To maintain exact consistency, `dim_drivers` and `dim_constructors` are calculated dynamically via SQL from staged records.

*   `dim_drivers` computes distinct identifiers, driver codes, and constructors.
*   `dim_constructors` normalizes team identities and maps constructors directly to their respective **Power Unit Family** (Mercedes, Ferrari, Honda, Renault).

---

## 3.6  Running the Reference Layer

From the `/transform` directory, compile the seeds and reference models:

```bash
# Load CSV seeds into DuckDB
dbt seed --profiles-dir profiles

# Build the reference tables
dbt run --profiles-dir profiles --select reference.*
```

Confirm build status by querying the resulting physical tables:
```sql
SELECT COUNT(*) FROM dim_circuits;          -- Expected: 44 circuits
SELECT COUNT(*) FROM dim_compounds_season;  -- Expected: 401 rows
```

---

**Before continuing:** verify you have populated database constants via `dbt seed`.

**Continue to [Part 4  The physics layer](./04_physics_layer.md).**
