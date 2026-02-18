---
id: manifest
sidebar_position: 11
title: "Project File Manifest"
---

**Audience:** Developer / Architect · **Status:** Current · **Updated:** 2026-05-27

---

# Project File Manifest

File-by-file map of the repository for developers navigating the codebase.

---

## Repository structure

```text
off-the-pace/
├── .github/
│   └── workflows/
│       ├── dbt-ci.yml           # dbt build + test gate
│       └── docs-ci.yml          # Docusaurus build, lychee links, Vale, cspell, drift check
├── Makefile                     # Unified task runner
├── README.md                    # Repo entry point
├── requirements.txt             # Python deps
│
├── ingestion/
│   └── src/
│       ├── ingest.py            # CLI: --start-season --end-season --sessions {R,Q,both}
│       ├── api_client.py        # FastF1 + OpenF1 wrappers
│       ├── data_quality.py      # Bronze-layer DQ checks
│       ├── replay_simulator.py  # Lap-by-lap replay for testing
│       ├── create_fixtures.py   # Test fixture builder
│       ├── environment.py       # Env + path config
│       └── logging_config.py    # Structured logging setup
│
├── transform/
│   ├── models/
│   │   ├── staging/             # 8 stg_ models (FastF1 + OpenF1 → clean rows)
│   │   ├── reference/           # 4 dim_ models (circuits, compounds, constructors, drivers)
│   │   ├── intermediate/        # 26 int_ models (physics decomposition layers)
│   │   └── marts/               # 8 fct_ + dim_events models
│   ├── macros/
│   │   ├── assert_additive_identity.sql  # CI invariant: seven terms sum to zero
│   │   ├── bayesian_shrinkage.sql
│   │   ├── clean_lap_filter.sql
│   │   └── posterior_variance.sql
│   ├── seeds/
│   │   ├── circuit_reference.csv        # Weight penalty per circuit (24 circuits)
│   │   ├── compound_cliff_params.csv    # KM cliff onset per (circuit, compound, season) for 401 groups
│   │   ├── dim_corners.csv
│   │   ├── race_to_track.csv
│   │   ├── raw_dim_events.csv
│   │   └── tyre_allocations.csv
│   ├── tasks/
│   │   └── coefficients/
│   │       ├── fit_compound_cliff.py    # Kaplan-Meier survival fitter
│   │       ├── fit_weight_penalty.py
│   │       ├── check_freshness.py
│   │       ├── seed_writer.py
│   │       ├── survival.py
│   │       └── provenance.py
│   └── profiles/                        # dbt profiles (dev + ci targets)
│
├── data/
│   ├── bronze/                          # Hive-partitioned Parquet (FastF1 2015–2024)
│   ├── dev.duckdb                       # Local DuckDB (dbt dev target)
│   └── ci.duckdb                        # CI DuckDB
│
├── docs/
│   ├── docs/
│   │   ├── intro.md                     # Site home and two-path signpost
│   │   ├── understand/                  # Explanation section (5 files)
│   │   └── reference/                   # Generated reference (dbt models + macros + CLI + schemas)
│   ├── docusaurus.config.ts
│   ├── sidebars.ts
│   └── src/
│
├── scripts/
│   ├── build_reference.py       # Orchestrator: runs all gen_ scripts
│   ├── gen_dbt_reference.py     # dbt manifest → model MDX pages
│   ├── gen_schema_reference.py  # Bronze schemas → MDX
│   ├── gen_cli_reference.py     # ingest.py CLI → MDX
│   ├── gen_macro_reference.py   # dbt macros → MDX
│   └── mdx_utils.py             # Shared MDX escaping utilities
│
├── agents/
│   └── lineage_agent/           # Data lineage agent (deferred)
│
└── _roadmap/                    # Planning documents
```

---

## Key entry points

| Goal | File |
|---|---|
| Run the full transform locally | `Makefile` → `make dbt-dev` |
| Understand the additive identity | `transform/macros/assert_additive_identity.sql` |
| See the seven-term decomposition | `transform/models/intermediate/int_lap_residual_decomposed.sql` |
| See the main output mart | `transform/models/marts/fct_lap_residuals.sql` |
| Regenerate reference docs | `scripts/build_reference.py` |
| Fit tyre cliff coefficients | `transform/tasks/coefficients/fit_compound_cliff.py` |
| Ingest new seasons | `ingestion/src/ingest.py` |
