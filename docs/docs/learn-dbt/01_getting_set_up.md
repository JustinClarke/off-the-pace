---
sidebar_position: 2
title: "Part 1: Getting Set Up"
---

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
# Navigate to project root and activate venv
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

## 1.4  Makefile Tasks

| Target | Operation |
|---|---|
| `make dbt-dev` | Compiles seeds and runs models against the local developer DuckDB warehouse (`data/dev.duckdb`). |
| `make dbt-dev-full` | Performs a raw schema rebuild, executing source freshness scans first. |
| `make dbt-test` | Runs the schema, data contract, and mathematical validation test suite. |
| `make dbt-docs` | Builds the visual dependency DAG site and hosts it on port `8081`. |
| `make dbt-prod` | Builds models against the dev DuckDB target (Fabric deferred see [Limitations](../understand/limitations.md)). |
| `make query` | Boots Harlequin against `data/dev.duckdb` for interactive SQL queries. |
| `make coefficients-fit` | Fits compound cliff decay parameters using the Kaplan-Meier survival fitter. |
| `make coefficients-promote` | Promotes newly fitted coefficients from `_pending/` to active seeds. |

---

## 1.5  The Warehouse

The pipeline utilizes **DuckDB** for zero-infrastructure local execution:
*   **Developer target (`dev`)** writes schemas to `data/dev.duckdb`.
*   **Continuous Integration target (`ci`)** writes schemas to `data/ci.duckdb` against committed high-density fixture Parquet files (`tests/fixtures/bronze/`).

Inspect database states with the interactive client:
```bash
make query
```

---

## 1.6  CLI Row Count Verification

You can run direct DuckDB validation queries from your terminal shell to confirm execution states:

```bash
# Verify row count in clean staging view
.venv/bin/python -c "
import duckdb
con = duckdb.connect('data/dev.duckdb')
print('Staged rows:', con.execute('SELECT COUNT(*) FROM stg_laps').fetchone()[0])
"
```

The output will display an approximate lap count in the low hundreds of thousands (depending on the number of ingested seasons).

---

**Before continuing:** execute `make dbt-dev` and verify that all compilation layers complete. Run `make dbt-test` to verify that all data contracts and validation enforcements pass.

**Continue to [Part 2  The Bronze→Silver bridge](./02_bronze_silver_bridge.md).**
