---
sidebar_position: 1
title: "Part 0: What is dbt?"
---

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
| **`.sql`** | `tests/` | Singular mathematical assertions that fail if a query returns any rows. |

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
            ├── Reference (4 tables): dim_circuits · dim_compounds_season
            │       · dim_constructors · dim_drivers
            └── Intermediate (36 tables-physics layers 03–05)
                    ├── L03 Physics (14): int_stint_geometry · int_lap_fuel_state · ...
                    ├── L04 Baseline (10): int_compound_cliff_predicted · int_constructor_structural_pace · ...
                    └── L05 Residual + Events (12): int_lap_residual_decomposed · int_overtakes · ...
                                    └── Feature Marts (9 tables)
                                            dim_events · fct_driver_skill_features
                                            · fct_cliff_prediction_features · fct_lap_residuals
                                            · fct_telemetry_deltas · fct_stint_features
                                            · fct_racecraft · fct_ghost_car_pace · fct_ghost_race_finish
```

---

## 0.6  Pipeline Boundaries

dbt is strictly an in-warehouse transformation engine. It operates with defined boundaries:

*   **What dbt does:** Reads from raw source directories, cleans data, performs mathematical and statistical modeling on relational schemas, executes unit/validation checks, and outputs gold tables.
*   **What dbt does NOT do:**
    *   Ingesting data from raw sources (handled via `ingestion/`).
    *   Fitting complex statistical survival rates (calculated via local Python fitting tasks).
    *   Training/evaluating machine learning algorithms (executed in `ml/`).
    *   Hosting user applications or dashboard servers.

At pipeline startup, raw Bronze Parquet files must reside in `data/bronze/`. dbt reads this data; it never modifies it.

---

**Continue to [Part 1  Getting set up](./01_getting_set_up.md).**
