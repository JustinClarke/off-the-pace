# Contributing to Off The Pace

Welcome, and thank you for your interest in contributing. This is the **canonical**
contributing guide-GitHub surfaces it automatically when you open a pull request or issue.
Follow it to go from zero to running models in under 30 minutes.

---

## Prerequisites

- **Python 3.11+**
- **Node.js (v18+)** and **pnpm** (needed if you are developing the React app or docs site)
- **Git**
- **Make** (standard on macOS/Linux)

No cloud credentials are required. The local DuckDB pipeline is the starting point; Microsoft
Fabric deployment is planned for subsequent streaming integration-**do not add cloud dependencies to the local pipeline.**

---

## Setup

```bash
git clone https://github.com/justinclarke/off-the-pace.git
cd off-the-pace
make setup        # builds ./.venv and installs Python/dbt dependencies
```

For the machine layer, also run `make ml-setup` (installs `ml/requirements.txt`).

For the web frontend and documentation site, install Node dependencies:
```bash
make docs-install # install Docusaurus docs dependencies
make app-install  # install React app dependencies
```

---

## Run the pipeline locally

```bash
make ingest-all   # pull historical F1 data via FastF1 → Bronze Parquet (optional; large)
make dbt-dev      # build all 46 dbt models against local DuckDB
make dbt-test     # run the 339 tests, including the seven-term identity
```

To verify the core invariant-every lap's seven components sum to zero-holds:

```bash
make dbt-test     # assert_lap_7term_identity must pass
```

`make dbt-dev` works out of the box on the committed seeds and fixtures; you do **not** need to
run `make ingest-all` (≈8 GB) just to build and test the transform layer.

---

## Understanding the data flow

| Layer | What it is | Where it lives |
|---|---|---|
| Bronze | Raw Parquet from FastF1, partitioned by season/race | `data/bronze/` |
| Silver | Typed and cleaned staging models | dbt `stg_*` |
| Gold | Decomposed feature marts for ML and dashboards | dbt `fct_*`, `dim_*` |

For the full repo layout and a file-by-file walkthrough, start at the
[README](../README.md#repo-layout) and the per-directory READMEs
([`transform/`](../transform/README.md), [`ml/`](../ml/README.md),
[`ingestion/`](../ingestion/README.md), [`data/`](../data/README.md)).

---

## Testing

```bash
# dbt models + identity tests
make dbt-test

# ML spine (27 tests: leakage, ONNX parity, schema, beats-baseline)
make ml-test

# Ingestion (mocked API calls-no network, runs in <5s)
pytest ingestion/tests/ -v
mypy ingestion/src/
```

### Single-race ingestion smoke test

Before submitting ingestion changes, test one race:

```bash
python ingestion/src/ingest.py --season 2024 --round 1 --session R --force
ls -la data/bronze/laps/season=2024/race=bahrain_grand_prix/
```

This fetches Bahrain 2024 and writes Parquet to `data/bronze/`.

---

## Code style & quality

### Python

- **Type hints on all public functions.**
  ```python
  def ingest_race(year: int, round_num: int, slug: str, force: bool) -> tuple[str, dict]:
      """Ingest a single race. Returns (status, manifest_row)."""
  ```
  Check with `mypy ingestion/src/`.
- **Use `logging`, not `print()`.** Sensitive data is masked automatically-see
  [`ingestion/src/environment.py`](../ingestion/src/environment.py) for secure credential handling.
- **No hardcoded secrets.** Environment variables only-never commit API keys, connection
  strings, or credentials.

### dbt / SQL

- Every model needs a description and column docs in its `schema.yml`.
- Every new model needs at least one test.
- Match the existing header-comment style (layer, grain, the identity/contract it satisfies) -
  see [`int_lap_fuel_state.sql`](../transform/models/intermediate/int_lap_fuel_state.sql) for the pattern.

---

## Adding work, by layer

### Add a dbt model
Full guide: [off-the-pace.onrender.com/guides/add-a-new-model](https://off-the-pace.onrender.com/guides/add-a-new-model). Quick checklist:
1. Write the SQL in `transform/models/`.
2. Add a description + column docs to `schema.yml`.
3. Add at least one dbt test.
4. Run `make dbt-dev` and `make dbt-test`.
5. **If the model participates in the seven-term identity,** confirm `assert_lap_7term_identity` still passes.
6. Open a PR-CI runs the full build automatically.

### Ingestion changes
See [`ingestion/README.md`](../ingestion/README.md) for module architecture, data-quality checks, and known issues. Key principles:
- **Graceful degradation**-one dataset failure doesn't abort the race.
- **Idempotent writes**-re-runs produce identical output.
- **Data-quality gates**-schema validation before write.
- **Retry resilience**-exponential backoff for transient network errors.

### ML / docs changes
- ML: see [`ml/README.md`](../ml/README.md); run `make ml-test`.
- Reference docs are **auto-generated**-edit the source (dbt `schema.yml`, docstrings, `ml/model_card.yml`), then run `make ml-reference` / the generators in `scripts/`. CI fails if the committed reference drifts.

---

## Pull request process

1. **Test locally**-the relevant suite(s) above (`make dbt-test`, `make ml-test`, and/or `pytest ingestion/tests/` + `mypy`).
2. **Keep PRs focused**-one change per PR.
3. **Write a descriptive title**-e.g. "Add dry-run flag to ingest CLI", not "Fix stuff".
4. **Include context in the description**-what problem it solves, what you tested, any known limitations.
5. **Keep commits logical**-one feature or fix per commit, with clear messages.
6. **Expect iteration**-reviews may request changes; respond and re-push. Questions go in the PR comments.

---

## Reporting issues

1. **Search existing issues first.**
2. **Provide context**-Python version and OS, the exact command you ran, the full error message.
3. **Include reproduction steps**-exact command, relevant tool versions (e.g. FastF1), and whether it's consistently reproducible.

---

## Getting help

- Usage questions → the relevant directory README (e.g. [`ingestion/README.md`](../ingestion/README.md)).
- Architecture & rationale → the [explanation docs](https://off-the-pace.onrender.com/understand/goal-and-approach) and the [ADR log](adr/DECISIONS.md).
- Bugs / feature requests → open an issue or a discussion on GitHub.

---

## Code of Conduct

We are committed to a welcoming and respectful environment for everyone, regardless of
background, experience level, or identity.

**Expected behaviour**
- Welcoming and inclusive language
- Respect for differing opinions and experience levels
- Graceful acceptance of constructive feedback
- Focus on what is best for the project and community

**Unacceptable behaviour**
- Harassment, discrimination, or personal attacks
- Publishing others' private information without consent
- Any conduct that would be considered inappropriate in a professional setting

Instances of unacceptable behaviour can be reported by opening a private issue or contacting
the maintainer directly via GitHub. All reports will be reviewed and investigated, and
responses will be proportionate to the severity of the conduct.

This Code of Conduct is adapted from the [Contributor Covenant](https://www.contributor-covenant.org/), version 2.1.

---

Thank you for contributing to Off The Pace. ✌️
