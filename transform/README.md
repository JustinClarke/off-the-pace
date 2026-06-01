# dbt Transformation Layer

Batch transformation for **Off The Pace**. Reads Bronze Hive-partitioned Parquet via DuckDB and produces feature marts for ML and analytics.

---

## Quick Start

**New contributor?** Start here:
- [Getting Started](../README.md#quickstart) (10-minute local setup)
- [Project Architecture](../README.md#repo-layout) (understand the repo layout)
- [Contributing](../.github/CONTRIBUTING.md) (PR workflow and checklist)

**Reference & Explanation:**
- [Documentation Site](https://offthepace.mintlify.app)
- [Goal & Approach](https://offthepace.mintlify.app/decomposition/seven-term-identity) (core thesis and the seven-term identity)
- [Methodology](https://offthepace.mintlify.app/decomposition/methodology) (detailed physics-informed approach)
- [Limitations](https://offthepace.mintlify.app/decomposition/limitations) (current scope and boundaries)

---

## Stack

| Component | Choice |
|---|---|
| Transform engine | dbt Core 1.11 |
| Production engine | DuckDB (file-based, zero-infra, CI-validated) |
| Future target | Microsoft Fabric Lakehouse (deferred  -  not yet wired) |
| Adapter | dbt-duckdb (`external_location` sources) |

---

## Model DAG (summary)

```
Bronze Parquet (laps / results / track_status / session_status / circuit_info / weather / telemetry / qualifying)
    └── Staging
            stg_laps · stg_laps_qualifying · stg_sector_times · stg_telemetry · stg_weather
            · stg_pits · stg_tyre_allocations · stg_events
            · stg_results · stg_track_status · stg_session_status · stg_circuit_info
            ├── Reference (seed-backed dims)
            │       dim_circuits · dim_compounds_season · dim_constructors · dim_drivers
            └── Intermediate
                    ├── Physics: int_stint_geometry · int_lap_fuel_state
                    │       · int_lap_fuel_state_qualifying · int_lap_air_state
                    │       · int_lap_thermal_proxy · int_dirty_air_tax_component · int_corner_metrics
                    ├── Baseline / pace: int_compound_cliff_predicted · int_field_pace_curve
                    │       · int_track_evolution · int_constructor_structural_pace
                    │       · int_constructor_structural_pace_qualifying
                    │       · int_circuit_x_constructor_interaction · int_synthetic_teammate
                    │       · int_driver_season_ratings · int_era_normalized_driver_rating
                    │       · int_driver_circuit_affinity
                    ├── Residual / decomposition: int_lap_residual_decomposed
                    │       · int_lap_residual_decomposed_qualifying · int_sector_residual_decomposed
                    │       · int_corner_skill_residuals · int_tyre_surface_vs_bulk_decoupling
                    │       · int_qualifying_decomposed · int_lap_anomaly_flags · int_event_corrections
                    └── Strategy / hazard: int_pit_strategy_value
                            · int_constructor_deg_sensitivity · int_pit_loss_circuit
                            · int_sc_hazard_history
                                    └── Feature Marts
                                            ├── dim_events                        race event flags
                                            ├── fct_driver_skill_features         driver × race, ML input A
                                            ├── fct_cliff_prediction_features     lap-grain, ML input B (target: next_lap_degradation_jump_s)
                                            ├── fct_lap_residuals                 lap-grain, seven-term identity analytics
                                            ├── fct_telemetry_deltas              telemetry-grain, sector micro-analysis
                                            ├── fct_stint_features                stint-grain strategy features
                                            ├── fct_ghost_car_pace                lap-grain, counterfactual pace decomposition
                                            ├── fct_ghost_race_finish             driver × race, simulated finish + honest SE
                                            ├── mart_corner_skill_driver          driver × season, corner-skill aggregates
                                            └── mart_degradation_history_envelope circuit × era × compound × lap-in-stint, deg envelope
```

---

## Directory structure

```
transform/
├── models/
│   ├── staging/            Bronze → clean views (stg_laps, stg_results, …)
│   ├── reference/          Seed-based dimension tables
│   ├── intermediate/       Physics · baseline · residual · strategy
│   └── marts/              Feature marts + exposures.yml
├── seeds/                  CSV seeds (circuit_reference, compound_cliff_params, …)
│   └── _pending/           Fitted seeds awaiting promotion
├── tests/                  Singular SQL tests
│   └── fixtures/           CI fixture parquet (see fixtures/README.md)
├── tasks/
│   └── coefficients/       Python survival fitter (fit_compound_cliff, fit_weight_penalty)
├── profiles/
│   └── profiles.yml        dev (DuckDB → ../data/dev.duckdb), ci (DuckDB → ../data/ci.duckdb)
├── Makefile                dbt-dev, dbt-test, coefficients-fit, dbt-docs
└── dbt_project.yml
```

---

## Reading a model (for SQL developers)

New to dbt? Each `.sql` file under `models/` is a `SELECT` statement  -  dbt materialises it as a view or table. `{{ ref('x') }}` is a typed dependency; dbt sorts the DAG and runs models in topological order, so you never manage `DROP/CREATE` ordering manually.

See the [Quick Start](https://offthepace.mintlify.app/quickstart) page in the documentation site for setup and query details.

---

## ML handoff

The two feature marts are the contract with `ml/`. Schemas are enforced via dbt model contracts  -  breaking a column type will fail the build.

| Mart | Grain | ML use |
|---|---|---|
| `fct_driver_skill_features` | driver × race | Driver skill quantification |
| `fct_cliff_prediction_features` | lap | Tyre cliff XGBoost (target: `next_lap_degradation_jump_s`) |

Exposures are declared in [models/marts/exposures.yml](models/marts/exposures.yml).

---

## Running locally

```bash
# Full build
make dbt-dev

# Tests only
make dbt-test

# Docs site (port 8081)
make dbt-docs

# Re-fit coefficients → promote → rebuild
make coefficients-fit
make coefficients-promote
make dbt-dev-full
```

---

## Adding a new season

1. Ingest bronze: `python ingestion/src/ingest.py --start-season YYYY --end-season YYYY --sessions both`
2. `dbt run`  -  the `*/*/*/*.parquet` glob picks it up automatically
3. `make coefficients-fit`  -  re-fit cliff params on the expanded data window
4. `dbt test` to confirm quality
5. Update `seeds/tyre_allocations.csv` if new compounds were introduced

---

← Previous in tour: [data/](../data/README.md) · **Next in tour: [ml/](../ml/README.md) →**
