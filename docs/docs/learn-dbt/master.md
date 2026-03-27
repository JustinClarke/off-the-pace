---
sidebar_position: 13
title: "Complete Single-Page Guide"
---

# Learn dbt: Off The Pace Transform Layer (Complete Guide)

A comprehensive, hands-on developer training guide to the `transform/` pipeline. This document compiles all 12 parts of the transform layer training guide into a single, complete master document.

**Total read time:** ~40 minutes. **Run time (hands-on):** ~90 minutes.

---

## Table of Contents

| # | Topic | Anchors |
|---|---|---|
| 0 | What is dbt? Concepts, vocabulary, the DAG | [Part 0](#part-0) |
| 1 | Prerequisites, local DuckDB profiles, essential CLI commands | [Part 1](#part-1) |
| 2 | Sources, staging models, multi-session qualifying unions, regex flag checks | [Part 2](#part-2) |
| 3 | Seeds, circuit dimensions, and fitted coefficient promoters | [Part 3](#part-3) |
| 4 | Physics-informed intermediates: fuel splits, dirty air tax, thermodynamic decay | [Part 4](#part-4) |
| 5 | Mathematical baselines: structural constructor pace, Bayesian prior shrinkage | [Part 5](#part-5) |
| 6 | Causal residual decomposition, multi-grain sector timing, anomaly flags | [Part 6](#part-6) |
| 7 | Gold feature marts, Docusaurus exposures, and schema contract enforcements | [Part 7](#part-7) |
| 8 | Tests, docs, selectors, CI, production | [Part 8](#part-8) |
| 9 | Common task recipes | [Part 9](#part-9) |
| 10 | F1 vocabulary appendix | [Part 10](#part-10) |
| 11 | Further reading | [Part 11](#part-11) |

---

<div id="part-0"></div>

# Part 0: What is dbt?

This section establishes the concepts, architecture, and structural primitives of **dbt (Data Build Tool)** as implemented in this F1 physics-informed pipeline.

Rather than managing massive, fragile data-cleaning scripts or hand-tuned pipelines, dbt acts as the compiler and execution planner for SQL-driven data warehouses. You write isolated, modular `.sql` models, and dbt compiles them, tracks dependencies, handles materializations, and runs validation assertions.

---

## 0.1  Core Mechanics

At its core, dbt is a topological compilation engine for SQL. You define individual tables and views as isolated `.sql` queries. dbt constructs a directed acyclic graph (DAG) by parsing `{{ ref('model_name') }}` Jinja statements inside your code.

**What happens during a `dbt run` cycle:**
1. **Parsing:** dbt inspects every model query, seed file, and schema configuration.
2. **Topological Sorting:** Jinja `ref()` calls are compiled to determine precise execution order, guaranteeing that upstream tables/views are successfully built before their downstream dependents run.
3. **Compilation:** Jinja statements are replaced with standard, warehouse-specific SQL paths.
4. **Execution:** dbt runs the compiled code against the warehouse in sorted order.
5. **Materialization:** Output structures are written as physical tables or virtual views as dictated by model configurations.

---

## 0.2  Declaring Dependencies: The Hello World Model

The simplest possible model represents a single file that maps to a corresponding table/view in your database.

```sql
-- models/staging/stg_hello.sql
SELECT 'world' AS greeting
```

Executing `dbt run --select stg_hello` compiles the file and builds a view named `stg_hello` in the database.

When a downstream model needs to consume this view, it uses `{{ ref() }}` to ensure the compiler understands the dependency graph:

```sql
-- models/intermediate/int_world.sql
SELECT 
    greeting,
    CONCAT(greeting, '_suffix') AS greeting_modified
FROM {{ ref('stg_hello') }}
```

During compilation, dbt automatically replaces `{{ ref('stg_hello') }}` with the fully qualified physical path in the local database schema (e.g. `main.stg_hello`), guaranteeing that `stg_hello` runs first.

---

## 0.3  Pipeline File Layout

A production dbt workspace consists of four primary structural file formats:

| Format | Path | Purpose |
|---|---|---|
| **`.sql`** | `models/` | Declarative SQL queries defining transformations (exactly one table or view per file). |
| **`.yml`** | `models/` | Schema validation contracts, data types, and documentation enforcements. |
| **`.csv`** | `seeds/` | Small static data tables version-controlled in Git (constants, fitted coefficients). |
| **`.sql`** | `tests/` | Custom singular tests  SQL that returns rows only when something is wrong |

---

## 0.4  Materialization Contracts

Each database model carries a `materialization` configuration. This is globally declared in `dbt_project.yml` or overridden locally inline.

| Layer | Materialization | Rationale |
|---|---|---|
| **`staging/`** | `view` | virtual query that evaluates on-demand, reading directly from Raw Hive-partitioned Parquet files via DuckDB's `external_location` pointer. |
| **`reference/`** | `table` | Materialized as a physical table since static context is small and frequently queried downstream. |
| **`intermediate/`** | `view` | Virtualized mid-pipeline views to limit physical storage overhead. Performance-heavy exceptions (`int_lap_residual_decomposed`) override to `table`. |
| **`marts/`** | `table` | Materialized physically as final, immutable data contracts for ML pipelines (`ml/`) and analytical tools. |

---

## 0.5  Directed Acyclic Graph (DAG)

The current pipeline consists of **58 active models** spanning staging, reference constants, intermediate physics layers, and feature marts:

```
Bronze Parquet (laps / weather / telemetry / race_control / qualifying)
    └── Staging (9 views): stg_laps · stg_laps_qualifying · stg_weather · stg_telemetry
            · stg_race_control · stg_sector_times · stg_pits · stg_events · stg_tyre_allocations
            ├── Reference (4 seed tables): dim_circuits · dim_compounds_season
            │       · dim_constructors · dim_drivers
            └── Intermediate (36 tables-physics layers 03–05)
                    ├── L03 Physics (14): int_stint_geometry · int_lap_fuel_state
                    │       · int_lap_fuel_state_qualifying · int_lap_air_state
                    │       · int_dirty_air_tax_component · int_lap_thermal_proxy
                    │       · int_coast_tax_component · int_air_density · int_wind_component
                    │       · int_corner_metrics · int_track_geometry · int_lap_line_deviation
                    │       · int_lap_powertrain_signature · int_lap_energy_management
                    ├── L04 Baseline (10): int_compound_cliff_predicted · int_field_pace_curve
                    │       · int_track_evolution · int_constructor_structural_pace
                    │       · int_constructor_structural_pace_qualifying
                    │       · int_circuit_x_constructor_interaction · int_synthetic_teammate
                    │       · int_driver_season_ratings · int_era_normalized_driver_rating
                    │       · int_driver_circuit_affinity
                    └── L05 Residual + Events (12): int_lap_residual_decomposed
                            · int_lap_residual_decomposed_qualifying · int_sector_residual_decomposed
                            · int_corner_skill_residuals · int_tyre_surface_vs_bulk_decoupling
                            · int_lap_anomaly_flags · int_event_corrections · int_race_control_events
                            · int_overtakes · int_penalties · int_pit_strategy_value
                            · int_qualifying_decomposed
                                    └── Feature Marts (9 tables): dim_events
                                            · fct_driver_skill_features · fct_cliff_prediction_features
                                            · fct_lap_residuals · fct_telemetry_deltas
                                            · fct_stint_features · fct_racecraft
                                            · fct_ghost_car_pace · fct_ghost_race_finish
```

---

**Continue to [Part 1  Getting set up](./01_getting_set_up.md).**

---

<div id="part-1"></div>

# Part 1: Getting set up

This section outlines the setup procedures, virtual environments, local DuckDB database paths, and essential CLI commands required to compile and build the pipeline.

---

## 1.1  Environment Prerequisites

Before compiling the pipeline, verify that the following dependencies are installed and available in your environment:

| Dependency | Validation Command | Expected Result / Purpose |
|---|---|---|
| **Python 3.11+** | `python3 --version` | Virtual environment interpreter |
| **Virtual Env (`.venv/`)** | `ls -d .venv` | Project package boundaries |
| **Bronze Parquet** | `ls data/bronze/` | Raw ingestion folders: `laps/`, `weather/`, `telemetry/` |

If raw Bronze Parquet files are missing, run the ingestion sequence first:
```bash
# Ingest Bronze data
make ingest
```
Refer to [ingestion/README.md](https://github.com/justinclarke/off-the-pace/blob/main/ingestion/README.md) for ingestion parameters and API key setups.

---

## 1.2  Activating the Virtual Environment

All pipeline processes and dbt commands execute within the project virtual environment. Activate it in your shell session:

```bash
cd "/Users/justin/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents/github/off-the-pace"
source .venv/bin/activate
```

Upon activation, your terminal prompt will display the `(.venv)` indicator.

---

## 1.3  Primary Development Targets

The project Makefile wraps dbt invocations, managing connection profiles and paths automatically. Execute these from the project root:

```bash
# Build all 58 active models (loads seeds and builds schemas)
make dbt-dev

# Execute the complete validation test suite
make dbt-test

# Generate and serve interactive dbt documentation locally (port 8081)
make dbt-docs

# Open the DuckDB terminal SQL interface (Harlequin) against the dev DB
make query
```

### Raw dbt Commands
If executing raw dbt commands, run them from the `transform/` root directory and supply the local `--profiles-dir profiles` argument. The local directory structure bypasses global user profiles (`~/.dbt/`):

```bash
cd transform

# Install packages
dbt deps --profiles-dir profiles

# Load seeds
dbt seed --profiles-dir profiles

# Compile and build the DAG
dbt run --profiles-dir profiles

# Run tests
dbt test --profiles-dir profiles
```

---

## 1.4  The Warehouse

The pipeline utilizes **DuckDB** for zero-infrastructure local execution:
*   **Developer target (`dev`)** writes schemas to `data/dev.duckdb`.
*   **Continuous Integration target (`ci`)** writes schemas to `data/ci.duckdb` against committed high-density fixture Parquet files (`tests/fixtures/bronze/`).

Inspect database states with the interactive client:
```bash
make query
```

---

**Continue to [Part 2  The Bronze→Silver bridge](./02_bronze_silver_bridge.md).**

---

<div id="part-2"></div>

# Part 2: The Bronze→Silver bridge: sources and staging

The staging layer is where raw, untyped Hive-partitioned Bronze data is structured into clean, typed, and schema-enforced relational views. Staging models are virtualized as views (`materialized = 'view'`), adding zero storage overhead while ensuring upstream sensor changes are cleanly normalized before intermediate calculations.

---

## 2.1  Model Overview

The staging layer comprises **9 active staging models** normalizing inputs across weather telemetry, pit events, laps, and race control variables:

| Staging Model | Source Table | Key Transformations |
|---|---|---|
| `stg_laps` | `raw_laps` | Casts types, scales time, parses safety car flags (Race session). |
| `stg_laps_qualifying` | `raw_laps_qualifying` | Casts and isolates qualifying telemetry (Qualifying session). |
| `stg_weather` | `raw_weather` | Casts ambient metrics, track temp, wind dynamics. |
| `stg_telemetry` | `raw_telemetry` | Standardizes distance offsets, speed, and throttle variables. |
| `stg_sector_times` | `stg_laps` | Unpivots sector columns into a sector-grain table. |
| `stg_pits` | `raw_pit_data` | Normalizes tyre swaps and pit duration intervals. |
| `stg_events` | `raw_dim_events` (seed) | Cleans incident descriptors and flag boundaries. |
| `stg_tyre_allocations` | `tyre_allocations` (seed)| Placeholder stub for future pre-race allocations. |

---

## 2.2  `stg_laps` & `stg_laps_qualifying`   The Core Data Feeds

These models normalize lap metadata. Staging renames columns to `snake_case`, scales nanoseconds to seconds, and defines clear booleans.

### Regular Expression Track Status Parsing
Staging implements regex checks using the DuckDB `REGEXP_MATCHES` engine rather than slow substring scanning:

```sql
-- Identify safety car flags (4 = Safety Car, 6 = SC Ending, 7 = Red Flag)
REGEXP_MATCHES(track_status, '.*[467].*') AS is_safety_car_lap,

-- Identify virtual safety car flags (5 = VSC)
REGEXP_MATCHES(track_status, '.*5.*')     AS is_vsc_lap
```

---

**Continue to [Part 3  Reference data](./03_reference_data.md).**

---

<div id="part-3"></div>

# Part 3: Reference data: seeds and dimensions

Reference data provides the physical, logistical, and historical context required to interpret telemetry and lap-time data. This includes track geometries, physical characteristics, tyre compound properties, and driver/constructor metadata.

---

## 3.1  The Role of Seeds in dbt

A **Seed** is a static CSV file managed inside `seeds/` that dbt compiles and loads directly into the database as physical tables via the `dbt seed` execution step.

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

### Weight-Penalty Estimation Mechanics
The `weight_penalty_factor` represents the causal effect of fuel mass on pace. It is defined using two distinct estimation paradigms:
1.  **Fitted (`first_stint_regression_v1`):** Calibrated via Ordinary Least Squares (OLS) regression on clean first-stint telemetry where sample size is dense.
2.  **Formula-Based prior:** Applied when regression noise is high:
    $$\text{weight\_penalty} = 0.02 + 0.0002 \times \text{corners} \times \bar{g}$$

---

## 3.4  `dim_compounds_season`   Tyre Wear Parameters

Tyre degradation follows a non-linear "hockey-stick" degradation curve. We estimate these coefficients and the cliff onset lap ($\tau$) using **Kaplan-Meier survival analysis**, treating voluntary pit stops as censored data points rather than failures.

---

**Continue to [Part 4  The physics layer](./04_physics_layer.md).**

---

<div id="part-4"></div>

# Part 4: The physics layer

The intermediate physics layer calculates the deterministic, physical forces that explain lap-time variation. By subtracting calculable physics (fuel mass, aerodynamic wake, tyre wear, and thermal loads) from raw lap times, we isolate the underlying driver performance signal.

---

## 4.1  `int_stint_geometry`   Stint Tracking

A **stint** is defined as the sequence of laps completed by a driver on a single set of tyres between pit events. `int_stint_geometry` maps every lap to its corresponding stint ID (`stint_id`), tyre age (`tyre_life`), and stint counter (`lap_in_stint`).

---

## 4.2  `int_lap_fuel_state` & `int_lap_fuel_state_qualifying`   Weight Corrections

To compare paces across different phases of a session, we must compute the "empty-tank equivalent" lap time by subtracting the fuel weight penalty.

### Race Fuel Mass Correction
At race start, cars carry up to $110\text{ kg}$ of fuel. Fuel mass is calculated as:
$$\text{fuel\_mass\_kg}_t = (\text{total\_laps} t + 1) \cdot \text{fuel\_consumption\_rate}$$

### Weight Penalty Subtraction
$$\text{weight\_penalty\_s}_t = \text{fuel\_mass\_kg}_t \cdot w_{\text{circuit}}$$
$$\text{weight\_corrected\_lap\_time\_s}_t = \text{lap\_time\_s}_t \text{weight\_penalty\_s}_t$$

---

## 4.3  `int_lap_air_state` & `int_dirty_air_tax_component`   Aerodynamic Wake

Using $10\text{ ms}$ high-frequency telemetry via `DistanceToDriverAhead`, laps are classified into four spatial states: `free_air`, `tow_zone`, `drs_zone`, and `dirty_air`.

`int_dirty_air_tax_component` calculates the causal lap-time penalty (in seconds) incurred due to trailing in another car's wake. It measures `dirty_air_share` (the percentage of the lap spent in the `< 1s` gap zone) to determine the exact pace taxation.

---

## 4.4  `int_lap_thermal_proxy` & `int_tyre_surface_vs_bulk_decoupling`   Tyre Thermal State

We approximate tyre thermal stress over a rolling window using an **Exponentially Weighted Moving Average (EWMA)** with a decay factor $\tau = 3\text{ laps}$:
$$\text{Thermal Load}_t = \sum_{k=0}^{t} P_k \cdot e^{-\frac{t-k}{\tau}}$$

The geometric decay ensures recent pushing efforts impact the current tyre temperature state far more than actions completed earlier in the stint.

---

**Continue to [Part 5  The baseline layer](./05_baseline_layer.md).**

---

<div id="part-5"></div>

# Part 5: The baseline layer

The baseline layer applies statistical modeling to establish what "normal" performance looks like. By defining baseline profiles for track grip, tyre degradation, vehicle performance, and driver-track affinities, we build a multi-component reference model.

---

## 5.1  `int_driver_circuit_affinity` & Bayesian Shrinkage

When sample sizes are small (e.g., a driver has only completed a few laps at a new track), their observed pace advantage is highly volatile. To prevent data sparsity from introducing extreme outliers, we apply **Bayesian Shrinkage** using the `bayesian_shrinkage` and `posterior_variance` macros.

### The Conjugate Normal-Normal Model
We assume a normal prior centered at $0$ (the field median). The shrunken posterior parameter is calculated as:
$$\mu_{\text{posterior}} = \frac{n \bar{x} + \tau \mu_0}{n + \tau}$$

Where:
*   $\bar{x}$: The observed pace advantage (empirical average).
*   $n$: The number of observations (laps completed).
*   $\mu_0$: The prior mean ($0$, meaning no track advantage).
*   $\tau$: The prior weight, set to $15$ equivalent laps of data.

The posterior variance, tracking rating uncertainty, is calculated using precision weights:
$$\sigma^2_{\text{posterior}} = \frac{1}{\frac{n}{\sigma^2} + \frac{1}{\sigma^2_0}}$$

---

## 5.2  `int_constructor_structural_pace`   Isolated Vehicle Speed

`int_constructor_structural_pace` implements a panel fixed-effects model to calculate relative constructor pace advantages, decoupled from the influence of their drivers:
*   **Power Index:** Long-straight performance (measured in S1 and S3).
*   **Aero Index:** Twisty, corner-heavy performance (measured in S2).

---

**Continue to [Part 6  The residual layer](./06_residual_layer.md).**

---

<div id="part-6"></div>

# Part 6: The residual layer

The residual layer isolates driver skill. By subtracting all calculated physical and baseline components from raw lap times, the remaining variance represents the causal contribution of the driver.

---

## 6.1  The Seven-Term Decomposition Identity

`int_lap_residual_decomposed` calculates the full additive decomposition. For every valid lap, the sum of all physical components plus the driver skill residual must equal the raw field-relative pace delta:

$$\text{pace\_delta\_s} = \text{fuel\_component\_s} + \text{compound\_component\_s} + \text{rubber\_component\_s} + \text{ambient\_component\_s} + \text{constructor\_component\_s} + \text{dirty\_air\_tax\_s} + \text{driver\_skill\_residual\_s}$$

The identity must close exactly on every single row to floating-point tolerance ($< 1e-4\text{ s}$). If any component is updated without matching adjustments in the residual, singular closure tests fail.

---

## 6.2  Multi-Grain Residuals: Sector, Corner & Surface Decoupling

*   `int_sector_residual_decomposed`: Computes the seven-term identity separately for Sectors 1, 2, and 3.
*   `int_corner_skill_residuals`: Normalizes minimum speeds, braking, and throttle points per corner against circuit-level medians.
*   `int_tyre_surface_vs_bulk_decoupling`: Separates tyre thermal load into fast-responding surface (τ≈3 laps) and slow-responding bulk (τ≈5 laps) components.

---

## 6.3  Race Events: `int_race_control_events`, `int_overtakes`, `int_penalties`

*   `int_race_control_events`: Forward-fills SC/VSC/red-flag windows from the race-control log (grain: race × lap, field-wide).
*   `int_overtakes`: Identifies on-track position changes from telemetry, distinguishing pit-cycle gains from racecraft passes.
*   `int_penalties`: Extracts penalty and investigation events from race-control messages.

---

## 6.4  `int_lap_anomaly_flags`   Trailing MAD Anomaly Detection

Laps with highly irregular residuals are statistically classified to determine their underlying causes. We implement a **Trailing Median Absolute Deviation (MAD)** window to protect the calculations from outlier distortion:
$$\text{MAD} = \text{median}\left(|x_i \text{median}(X)|\right)$$

The rolling window utilizes a trailing $7$-lap sequence (excluding the current lap $t$). **Centred windows are strictly prohibited** to prevent future lap leakage.

---

**Continue to [Part 7  The mart layer and ML handoff](./07_mart_layer.md).**

---

<div id="part-7"></div>

# Part 7: The mart layer and ML handoff

The mart layer defines the interface (data contract) between the transformation pipeline and the downstream machine learning systems at `ml/`. It builds optimized, physical tables (`materialized = 'table'`) representing clean features designed for predictive tasks.

---

## 7.1  All nine marts at a glance

| Mart | Grain | Use |
|---|---|---|
| `dim_events` | race | Race event flags |
| `fct_driver_skill_features` | driver × race | ML input A driver skill extraction |
| `fct_cliff_prediction_features` | lap | ML input B tyre cliff XGBoost |
| `fct_lap_residuals` | lap | Analytics full residual decomposition |
| `fct_telemetry_deltas` | corner × driver pair | Sector micro-analysis teammate speed deltas |
| `fct_stint_features` | stint | Strategy features thermal load, cliff onset, pit decision class |
| `fct_racecraft` | driver × race | Overtaking / defending pass counts, DRS share, penalties |
| `fct_ghost_car_pace` | lap × ego × host constructor | Counterfactual pace decomposition |
| `fct_ghost_race_finish` | driver × race × host constructor | Simulated finish positions |

---

## 7.2  Model Schema Contracts

To protect downstream machine learning scripts from breaking due to upstream changes, we implement **dbt Model Contracts** inside `marts/schema.yml`. Any schema change (such as altering a column’s data type from `DOUBLE` to `INTEGER`) will fail the build before execution begins.

---

**Continue to [Part 8  Tests, docs, and the production toolchain](./08_tests_docs_toolchain.md).**

---

<div id="part-8"></div>

# Part 8: Tests, docs, selectors, CI, production

Testing and documentation are treated as first-class, compile-time enforcements in this workspace.

---

## 8.1  Mathematical Closure: `assert_additive_identity`

To enforce the seven-term pace decomposition, we implement a custom validation macro, `assert_additive_identity` inside `macros/assert_additive_identity.sql`:

```sql
{% macro assert_additive_identity(model_ref, total_col, component_cols, residual_col, tolerance=0.0001) %}
    SELECT *
    FROM {{ model_ref }}
    WHERE ABS(
        {{ total_col }}-(
            {% for col in component_cols %}
                {{ col }} +
            {% endfor %}
            {{ residual_col }}
        )
    ) > {{ tolerance }}
{% endmacro %}
```

We instantiate this macro inside `tests/assert_lap_residual_identity.sql` to validate the intermediate decomposition tables.

---

**Continue to [Part 9  Common task recipes](./09_cookbook.md).**

---

<div id="part-9"></div>

# Part 9: Common task recipes

---

## Recipe 1  Running Specific Parts of the Lineage

```bash
# Compile and run a specific model
dbt run --profiles-dir profiles --select stg_laps

# Build a model and all of its upstream dependencies
dbt run --profiles-dir profiles --select +int_synthetic_teammate

# Run only the intermediate math identity tests
dbt test --profiles-dir profiles --select assert_lap_residual_identity
```

---

## Recipe 2  Re-fitting Compound Cliff Coefficients

To re-fit the Kaplan-Meier survival curves on the active data window, run the offline survival fitter:

```bash
# Fits compound cliff wear models and circuit weight factors
make coefficients-fit

# Promotes newly fitted coefficients from _pending/ to active seeds
make coefficients-promote

# Re-run dbt seeds and models
make dbt-dev-full
```

---

**Continue to [Part 10  Formula 1 Technical Vocabulary](./10_f1_vocabulary.md).**

---

<div id="part-10"></div>

# Part 10: F1 vocabulary appendix

Every F1 term used in this guide, defined in one sentence.

---

## Tyres and compounds

**Compound**: the rubber formula for a tyre set; in F1 there are five: C1–C5 mapped to Soft/Medium/Hard (dry), Intermediate (light wet), and Wet (heavy wet).

**Tyre life / age in stint**: how many laps a set of tyres has been on the car; tyre performance degrades with age.

**Stint**: the sequence of consecutive laps a driver completes on a single set of tyres, from pit-out to pit-in.

**Cliff**: the point in a tyre's life where degradation accelerates sharply; a tyre losing 0.05 s/lap can suddenly start losing 0.3 s/lap when it "goes off the cliff."

**Degradation**: the pace loss a tyre accumulates over its life due to heat cycling, wear, and surface chemistry changes.

**Push**: driving at high effort (aggressive throttle, late braking), which heats the tyres faster and accelerates degradation.

**Lift-and-coast**: deliberately backing off the throttle before a braking zone to save fuel or tyres, sacrificing lap time for strategic purposes.

**Fuel saving**: driving at reduced effort to manage fuel consumption when the car is heavier than planned.

---

## Race control events

**Safety car (SC)**: a physical Mercedes-AMG car deployed on track during incidents; all drivers must slow to a delta time and cannot overtake.

**Virtual safety car (VSC)**: an electronic delta-time limit imposed without a physical car; drivers slow but not as severely as under a full SC.

**Red flag**: the race is suspended; all cars must slow and return to the pit lane or grid.

**Yellow flag**: a hazard is present in a sector; drivers must slow and cannot overtake in that sector.

**DRS (Drag Reduction System)**: a rear wing flap a driver can open when within 1 second of the car ahead at specific detection points; reduces drag and increases straight-line speed to facilitate overtaking.

**Restart**: the lap immediately after a SC period ends; pace returns to racing speed.

---

## Aerodynamics and car performance

**Downforce**: aerodynamic force pressing the car into the track; enables faster cornering but increases drag.

**Dirty air**: turbulent air created behind a car at speed; following drivers lose downforce and get increased front-tyre temperatures.

**Free air**: racing without another car close enough to cause aerodynamic interference.

**Tow zone**: being close enough to the car ahead (roughly 1–3 seconds) to benefit from the slipstream (reduced drag) without severe downforce loss.

**Constructor**: the F1 team that builds the car (e.g. Mercedes, Ferrari, Red Bull).

**Power unit (PU)**: the hybrid power system: internal combustion engine + energy recovery systems. Teams supply PUs to multiple constructors (e.g. Mercedes PU powers Mercedes, Aston Martin, McLaren).

**Aero** shorthand for aerodynamic performance, usually in the context of corner speed.

---

## Timing and analysis

**Lap time**: elapsed time for one full lap of the circuit.

**Sector time**: elapsed time for one of three sectors of the circuit; used to diagnose where a driver gains or loses time.

**Speed trap**: a fixed measurement point on a straight where the car's top speed is recorded.

**Trimmed mean**: the arithmetic mean after removing the top and bottom N% of values; more robust to outliers than a plain mean.

**MAD (Median Absolute Deviation)**: `median(|x-median(x)|)`; a robust measure of spread much less sensitive to outliers than standard deviation.

**Modified Z-score**: `0.6745 × (x-median) / MAD`; flags outliers in a robust way.

**Survival analysis**: statistical methods for analysing time-to-event data where some observations are censored (the event hasn't happened yet). Used here to estimate tyre cliff onset without being biased by voluntary early pits.

**Cox proportional hazards**: a semi-parametric survival model that estimates the effect of covariates on the hazard (instantaneous failure rate). Used in the compound cliff fitter to control for compound class, season, and circuit.

**ASOF join**: a join that returns the most recent matching row from one table before (or at) a given timestamp in another  used to match weather readings to lap timestamps.

---

**Continue to [Part 11  Next Steps](./11_where_next.md).**

---

<div id="part-11"></div>

# Part 11: Where next?

You have walked through the full transformation layer  from raw Bronze Parquet directories to verified gold marts, with tests validated at every compilation step.

---

## Canonical Architecture and Methodology

*   [Goal & Approach](../understand/goal-and-approach.md): The system architecture: how ingestion, transform, and machine learning layers interface.
*   [Methodology](../understand/methodology.md): The causal inference approach: why we decompose pace additively, what we isolate, and the limits of the physical estimators.

---

## Adjacent Components

*   [ingestion/README.md](https://github.com/justinclarke/off-the-pace/blob/main/ingestion/README.md): Where Bronze data is sourced. If you need to add a new session type or modify sensor variables, start here.
*   [transform/tasks/coefficients/](https://github.com/justinclarke/off-the-pace/tree/main/transform/tasks/coefficients/): The survival analysis coefficient fitter. Review this block before running `make coefficients-fit`.
*   [ml/](https://github.com/justinclarke/off-the-pace/tree/main/ml/): The downstream consumer of the gold feature marts (`fct_driver_skill_features` and `fct_cliff_prediction_features`).

---

## Interactive Exploration & Verification

To inspect model details, column schema types, and SQL lineage:

```bash
# Generate and open the interactive dbt docs lineage graph
make dbt-docs

# Open the SQL explorer interface (Harlequin) against the dev DB
make query
```
