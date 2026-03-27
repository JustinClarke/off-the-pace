---
sidebar_position: 0
title: "Orientation & Overview"
---

# Learn dbt: Off The Pace Transform Layer

A comprehensive, hands-on developer training guide to the `transform/` pipeline. Each part of this sequence builds upon the previous, starting from raw ingested Parquet data and culminating in gold-level feature marts mapped to downstream machine learning models.

**Total read time:** ~40 minutes. **Run time (hands-on):** ~90 minutes.

---

## Parts

| # | File | Topic | Lines |
|---|---|---|---|
| 0 | [00_what_is_dbt.md](./00_what_is_dbt.md) | What is dbt? Concepts, vocabulary, the DAG | ~200 |
| 1 | [01_getting_set_up.md](./01_getting_set_up.md) | Prerequisites, local DuckDB profiles, essential CLI commands | ~150 |
| 2 | [02_bronze_silver_bridge.md](./02_bronze_silver_bridge.md) | Sources, staging models, multi-session qualifying unions, regex flag checks | ~250 |
| 3 | [03_reference_data.md](./03_reference_data.md) | Seeds, circuit dimensions, and fitted coefficient promoters | ~120 |
| 4 | [04_physics_layer.md](./04_physics_layer.md) | Physics-informed intermediates: fuel splits, dirty air tax, thermodynamic decay | ~400 |
| 5 | [05_baseline_layer.md](./05_baseline_layer.md) | Mathematical baselines: structural constructor pace, Bayesian prior shrinkage | ~350 |
| 6 | [06_residual_layer.md](./06_residual_layer.md) | Causal residual decomposition, multi-grain sector timing, anomaly flags | ~250 |
| 7 | [07_mart_layer.md](./07_mart_layer.md) | Gold feature marts, Docusaurus exposures, and schema contract enforcements | ~150 |
| 8 | [08_tests_docs_toolchain.md](./08_tests_docs_toolchain.md) | Singular math validation, assertion macros, CI enforcements | ~150 |
| 9 | [09_cookbook.md](./09_cookbook.md) | Practical recipes: adding seasons, re-fitting survival models, debugging | ~150 |
| 10 | [10_f1_vocabulary.md](./10_f1_vocabulary.md) | Formula 1 technical vocabulary | ~50 |
| 11 | [11_where_next.md](./11_where_next.md) | Project references and dbt resources | ~50 |

---

## Quick Orientation

The transformation layer reads Bronze Hive-partitioned Parquet (168 races, 2018–2024) via DuckDB and generates 9 feature/analytics marts (representing ML inputs and analytics datasets). All **58 active models** pass validation tests. The pipeline runs locally in seconds with zero warehouse configurations.

Before starting:
1. Confirm Bronze Parquet exists at `data/bronze/`
2. Confirm you have built your local virtual environment (see [Part 1](./01_getting_set_up.md))

For the current pipeline specifications, known exceptions, and build diagnostics, see [transform/README.md](https://github.com/justinclarke/off-the-pace/blob/main/transform/README.md).
