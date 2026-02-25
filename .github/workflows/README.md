# .github/workflows/-CI Pipeline Index

Three GitHub Actions workflows gate every pull request. Each mirrors the `make` targets you can
run locally-if it passes locally, it passes here.

## Workflow index

| Workflow | File | Triggers on | What it gates |
|---|---|---|---|
| **dbt CI** | `dbt-ci.yml` | Changes to `transform/`, `ingestion/`, `requirements.txt` | Build all 46 models; run 339 tests including `assert_additive_identity`; confirm the seven-term identity holds on every lap |
| **Docs CI** | `docs-ci.yml` | Changes to `docs/`, `scripts/`, `transform/models/**`, `ingestion/schemas/**` | Build Docusaurus; run `python scripts/build_reference.py && git diff --exit-code`-fails if any generated MDX drifts from its source |
| **ML CI** | `ml-ci.yml` | Changes to `ml/`, `scripts/gen_ml_reference.py` | 27-test leakage spine (static guards always run; warehouse-dependent guards gate on bronze fixtures); ONNX parity; beats-baseline; no hardcoded holdout year in `ml/src`; model-card MDX drift check |

## Local equivalents

```bash
make dbt-test          # mirrors dbt-ci.yml
make docs-reference    # mirrors the drift-check step in docs-ci.yml
make ml-test           # mirrors ml-ci.yml test steps
```

## Architecture decisions

`.github/adr/DECISIONS.md` records why key architectural choices were made-DuckDB over
Postgres, Hive partitioning, the additive identity as a CI gate, etc.
