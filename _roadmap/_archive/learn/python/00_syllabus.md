# Python Skill Sharpening — Off The Pace

> **Goal:** Go from "I know some Python" to "I can confidently contribute to this repo and ace a technical interview about it."

This is a self-paced course. Each module is one focused session (60–90 min). The exercises use real patterns from the Off The Pace codebase so you're learning *and* onboarding at the same time.

## How each module works

1. **Concept** (10 min) — plain-language explanation, no jargon until it's defined
2. **Codebase connection** — where this pattern appears in the repo (file links)
3. **Guided exercises** — build it yourself, step by step, with expected output
4. **Interview drills** — 3–5 questions you'd hear in a technical screen
5. **Checkpoint** — what you should now be able to explain to someone else

---

## The 12 modules

| # | Module | Skill area | Repo connection |
|---|--------|------------|-----------------|
| 01 | [Python foundations & project structure](01_foundations.md) | venv, pathlib, imports, `__name__` | Makefile, ingestion layout |
| 02 | [Data wrangling with Pandas](02_pandas.md) | DataFrames, dtypes, merge, groupby, I/O | `ingest.py`, `data_quality.py` |
| 03 | [File I/O & Parquet](03_file_io_parquet.md) | pathlib, Parquet, Hive partitioning, compression | Bronze layer, `export_app_data.py` |
| 04 | [HTTP clients & API patterns](04_http_apis.md) | requests, rate limiting, retry, pagination | `api_client.py`, `jolpica_client.py` |
| 05 | [Classes, dataclasses & OOP](05_oop_dataclasses.md) | `@dataclass`, static methods, class design | `DataQualityEngine`, `TargetSpec`, `FeatureBundle` |
| 06 | [Testing with pytest](06_testing_pytest.md) | fixtures, parametrize, mocking, conftest | `test_ingestion.py`, `test_features.py` |
| 07 | [Type hints & static analysis](07_type_hints.md) | annotations, mypy, `Optional`, generics | ingestion `mypy.ini`, ML schema |
| 08 | [CLI tools with argparse](08_argparse_cli.md) | parsers, mutually exclusive groups, subcommands | `ingest.py`, `train.py`, `tune.py` |
| 09 | [Logging, config & environment](09_logging_config.md) | `logging`, `python-dotenv`, 12-factor config | `logging_config.py`, `environment.py` |
| 10 | [NumPy & scikit-learn for ML](10_numpy_sklearn.md) | arrays, broadcasting, TimeSeriesSplit, metrics | `train.py`, `evaluate.py`, `features.py` |
| 11 | [XGBoost, Optuna & ONNX pipeline](11_xgboost_pipeline.md) | training, tuning, export, parity testing | `tune.py`, `export_onnx.py`, `predict.py` |
| 12 | [DuckDB, SQL & the dbt bridge](12_duckdb_dbt.md) | Python ↔ SQL, DuckDB queries, schema introspection | `features.py`, `validate_gate.py`, transform layer |

---

## Bonus interview topics (woven into modules)

These concepts appear across multiple modules and are explicitly called out as interview drills:

- **Hash fingerprinting & reproducibility** (modules 03, 10)
- **Leakage prevention in ML** (modules 10, 11)
- **Exponential backoff & retry patterns** (modules 04, 09)
- **The Parquet columnar format — why it matters** (module 03)
- **Time-series cross-validation vs random splits** (module 10)
- **ONNX model portability & parity testing** (module 11)
- **Data quality as code** (modules 02, 06)
- **The frozenset trick for immutable constants** (modules 05, 07)

---

## Prerequisites

- Python 3.11+ installed
- A terminal you're comfortable in
- Git basics (clone, branch, commit)
- You've run `make setup` in the repo root

If you haven't cloned the repo yet:

```bash
git clone https://github.com/justinclarke/off-the-pace
cd off-the-pace
make setup
```

---

## Recommended order

Go 01 → 12 in sequence. Each module builds on the previous one. If you already know a topic cold, skim the exercises, do the interview drills, and move on.

**Time estimate:** ~12–15 hours total (1–1.5 hours per module).

---

*Built for the Off The Pace codebase. Every exercise uses real code from the repo.*
