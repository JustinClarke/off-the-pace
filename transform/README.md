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

Reading order down the DAG is also the layer's family taxonomy eight families, walked in
topological order. The full per-model breakdown (every model, its lineage, and its family) is
generated and gate-checked, so it lives on the docs site rather than as a second, hand-maintained
copy here: see [the layer overview](https://offthepace.mintlify.app/transform/overview) for the
DAG diagram and [Model Reference](https://offthepace.mintlify.app/reference/models/stg/stg_laps)
for every model.

```
Bronze Parquet (laps / results / track_status / session_status / circuit_info / weather / telemetry / qualifying)
    └── Staging                  Bronze → clean views, no joins
            ├── Reference        seed-backed dims (circuits, compounds) + live dims (drivers, constructors)
            └── Physics          fuel, air state, thermal proxy, dirty air, corner metrics, telemetry cliff signals
                    └── Pace Baselines    field pace, track evolution, compound trajectory, constructor structural pace
                            ├── Skill                 car FE, LORO baseline, shrinkage, era bridges
                            └── Residual Decomposition  where the seven-term identity closes
                                    └── Strategy        pit-loss, degradation sensitivity, SC hazard
                                            └── Feature Marts   the contract with ml/ and app/
```

---

## Directory structure

```
transform/
├── models/
│   ├── staging/            Bronze → clean views (stg_laps, stg_results, …)
│   ├── reference/          Dimension tables: two seed-backed, two derived live from stg_laps
│   ├── intermediate/       Physics · pace baselines · skill · residual · strategy
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

See [Quick Start](https://offthepace.mintlify.app/ingestion/quickstart) for environment setup and [the seven-term identity](https://offthepace.mintlify.app/decomposition/seven-term-identity) for what this layer computes.

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

---

← Previous in tour: [data/](../data/README.md) · **Next in tour: [ml/](../ml/README.md) →**
