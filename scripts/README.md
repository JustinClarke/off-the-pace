# scripts/-Reference Doc Generators

Five Python generators that keep `docs/reference/` in sync with the source code and
schema files. Run by `make docs-reference`; CI fails if the generated MDX drifts from what's
committed.

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
| `gen_dbt_reference.py` | `docs/reference/models/**` + `macros/**` | `transform/target/manifest.json` |
| `gen_schema_reference.py` | `docs/reference/schemas/**` | `ingestion/schemas/*.json` |
| `gen_cli_reference.py` | `docs/reference/cli/**` | Python `--help` output from `ingestion/src/` |
| `gen_macro_reference.py` | `docs/reference/macros/**` | macro SQL + docstrings |
| `gen_ml_reference.py` | `docs/reference/ml/degradation-model-v1.mdx` | `ml/model_card.yml` |
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
```

---

← Previous in tour: [docs/](../docs/README.md) · **Next in tour: [Makefile + .github/](../.github/CONTRIBUTING.md) →**
