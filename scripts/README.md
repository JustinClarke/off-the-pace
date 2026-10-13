# scripts/ — doc generators, docs gates and pipeline tooling

Three kinds of script live here: the reference-doc generators and docs drift gates that keep the
[Mintlify site](../docs/README.md) honest, the app-data and CDN tooling behind the `make app-*`
targets, and one-off research scripts. The first section covers the five generators that keep
`docs/reference/` in sync with the source code and schema files. They run via
`make docs-reference`, and CI fails if the generated MDX drifts from what's committed.

## The generate → commit → drift-check loop

```
source files  →  scripts/build_reference.py  →  docs/reference/**/*.mdx
                       │
                       └── docs-ci.yml runs: python scripts/build_reference.py
                                              git diff --exit-code docs/reference/
                                              (fails the build if anything changed)
```

**Rule:** Edit the source (dbt YAML, Python docstrings, `ml/model_card.yml`)-never edit the
MDX directly. Run `make docs-reference` to regenerate and commit the result.

## Files

| File | What it generates | Source it reads |
|---|---|---|
| `build_reference.py` | Orchestrator-runs all five generators in sequence | all of the below |
| `gen_dbt_reference.py` | `docs/reference/models/**` | `transform/target/manifest.json` |
| `gen_schema_reference.py` | `docs/reference/schemas/**` | `ingestion/schemas/*.json` |
| `gen_cli_reference.py` | `docs/reference/cli/**` | Python `--help` output from `ingestion/src/` |
| `gen_macro_reference.py` | `docs/reference/macros/**` | macro SQL + docstrings |
| `gen_ml_reference.py` | `docs/reference/ml/degradation-model.mdx` | `ml/model_card.yml` |
| `mdx_utils.py` | (shared) |-MDX formatting helpers used by all generators |

## How to connect

- **Upstream:** dbt project (`transform/`), ingestion schemas (`ingestion/schemas/`), ML model card (`ml/model_card.yml`)
- **Downstream:** Mintlify site (`docs/reference/`), `docs-ci.yml`

## Run

```bash
make docs-reference          # regenerate all reference MDX
python scripts/build_reference.py --models   # regenerate dbt models only
python scripts/build_reference.py --schemas  # regenerate schema reference only
python scripts/build_reference.py --ml       # regenerate model card only
python scripts/build_reference.py --cli      # regenerate CLI reference only
python scripts/build_reference.py --macros   # regenerate macro reference only
```

## Docs drift gates

Each runs in `.github/workflows/docs-ci.yml`. The `*_docs_facts.py` scripts check by default and
regenerate their snippet with `--write`.

| File | What it checks or generates | Make target |
|---|---|---|
| `docs_audit.py` | Required READMEs exist, tour-stop READMEs carry a footer, source files carry headers | `make docs-audit` |
| `docs_facts.py` | Headline counts in `README.md` and the ML overview agree with the generated snippets | `make docs-facts` |
| `app_docs_audit.py` | Every shipped app feature has a `docs/app/<slug>.mdx` page in the App tab | `make docs-app-audit` |
| `ingestion_docs_facts.py` | `docs/snippets/bronze-coverage.mdx` from `ingestion/verify_bronze.py` | `make docs-coverage` |
| `overview_docs_facts.py` | `docs/snippets/overview-numbers.mdx` | `make docs-coverage` |
| `transform_docs_facts.py` | `docs/snippets/transform-inventory*.mdx` from the dbt manifest | `make docs-coverage` |
| `ml_docs_facts.py` | `docs/snippets/ml-inventory*.mdx` from `ml/src/schema.py`, the model card and pytest collection | `make docs-coverage` |
| `gen_project_graph.py`, `watch_project_graph.py` | `docs/project-graph.html`, once or on every source change | `make project-graph`, `make watch-graph` |

## App data and CDN

| File | Role | Make target |
|---|---|---|
| `export_app_data.py` | Exports warehouse tables to `app/public/data/` as Parquet | `make app-data` |
| `publish_cdn.sh` | Syncs data and models to the CDN bucket, manifest last | `make app-publish` |
| `smoke_cdn.sh`, `verify_published.sh` | Checks what the CDN and the live site actually serve | `make app-smoke`, `make verify-published` |
| `promote_cdn.sh`, `rollback_cdn.sh` | Promotes staging to prod, or rolls prod back | `make app-promote`, `make app-rollback` |
| `apply_bucket_lifecycle.sh` | Applies the bucket's object-lifecycle rules | `make bucket-lifecycle` |
| `setup_wif.sh` | One-off Workload Identity Federation setup for CI | — |
| `smoke_test_season.py` | Asserts a newly onboarded season is fully wired | `make add-season` |
| `generate_fitted_fixture.py`, `dump_parity_rows.py` | Fixtures for the Degradation Simulator and the app's ONNX parity test | — |

## Research and one-off analysis

Not part of any build. These back items in [`_roadmap/`](../_roadmap/README.md) and write their
results to `ml/artefacts/` or the roadmap's evidence folders.

| Pattern | What it is |
|---|---|
| `arms_*.py` | Add/drop ablation arms for a roadmap item (the item ID is in the name) |
| `gate_*.py`, `eval_*.py`, `measure_*.py`, `estimate_*.py` | Admission gates, evaluations and one-off measurements for the same items |
| `diagnose_*.py`, `validate_*.py`, `test_window_alternatives.py`, `ablation_telemetry.py`, `08p_*.py` | Diagnostics and validation runs |
| `analyze_race_case_study.py` | Data and charts for the São Paulo 2021 case study |
| `driver_network_rating.py`, `mc_finish_order.py` | Alternative driver rating and Monte Carlo finish-order experiments |
| `extract_types.py`, `extract_types_duckdb.py` | Helpers that write column types into `schema.yml` |

---

← Previous in tour: [docs/](../docs/README.md) · **Next in tour: [Makefile + .github/](../.github/CONTRIBUTING.md) →**
