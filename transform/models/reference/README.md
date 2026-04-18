# Reference Models

Static dimension tables derived from dbt seeds. Loaded once and reused across the DAG
as lookup and join targets. All materialised as **tables**.

---

## Models

| Model | Grain | Contents |
|---|---|---|
| `dim_circuits` | circuit | Physical track characteristics: corner count, abrasiveness index, weight-penalty factor, calibration deltas |
| `dim_drivers` | driver | Driver identity, team history, and era membership |
| `dim_constructors` | constructor × season | Constructor identity with season-level metadata |
| `dim_compounds_season` | compound × season | Tyre compound assignments per season with hardness classification |

---

## Seed sources

Seeds live in `seeds/` and are committed to version control:

| Seed | Updates when |
|---|---|
| `circuit_reference` | New circuit added or track characteristics remeasured |
| `compound_cliff_params` | Kaplan-Meier survival fit re-run via `make coefficients-fit` + `make coefficients-promote` |

See [tasks/coefficients/README.md](../../tasks/coefficients/README.md) for the full offline-solver lifecycle.

---

## Tests

Referential integrity checks (`relationships`) confirm that every `circuit_id` in the
intermediate layer resolves to a row in `dim_circuits`. These live in `schema.yml`.

---

## How it connects

- **Upstream (depends on):** `transform/seeds/`-CSV files (hand-authored and fitted) loaded by `dbt seed`
- **Downstream (consumed by):** `transform/models/intermediate/`-joins `dim_circuits`, `dim_drivers`, `dim_constructors`, `dim_compounds_season` to add physics parameters to lap-grain models

## Layer contract

- Materialised as **tables** (stable lookups; loaded once per `dbt run`)
- Never written at lap grain-reference models are slowly-changing dimensions only
- Must have a `schema.yml` entry with `relationships` tests to the intermediate layer

---

← [transform/README.md](../../README.md) | Part of tour stop 3: Transform
