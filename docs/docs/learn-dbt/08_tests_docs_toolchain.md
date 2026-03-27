---
sidebar_position: 9
title: "Part 8: Tests & Docs"
---

# Part 8: Tests, docs, and the production toolchain

Testing and documentation are treated as first-class, compile-time enforcements in this workspace. Every mathematical identity must close exactly, every model schema must adhere to its typed contract, and every build must be validated in CI before merging.

---

## 8.1  dbt Testing Paradigms

We divide testing into two distinct validation layers:
1.  **Schema Tests (Generic):** Declared in `.yml` configurations. They check standard relational integrity rules (`unique`, `not_null`, foreign key `relationships`, and accepted domain ranges) on every build.
2.  **Singular Tests (Custom):** Written as custom SQL scripts inside `tests/`. A singular test fails if the query returns a single row, implying an anomaly occurred.

---

## 8.2  Mathematical Closure: `assert_additive_identity`

Our seven-term causal pace decomposition is an exact identity: the sum of the fuel, compound, rubber, ambient, constructor, and dirty air tax components, plus the driver skill residual, must equal the raw field-relative pace delta.

To enforce this, we implement a custom validation macro, `assert_additive_identity` inside `macros/assert_additive_identity.sql`:

```sql
{% macro assert_additive_identity(model_ref, total_col, component_cols, residual_col, tolerance=0.0001) %}
    SELECT *
    FROM {{ model_ref }}
    WHERE ABS(
        {{ total_col }}-(
            {% for col in component_cols %}
                {{ col }} +
            {% endfor %}
            {{ residual_col }}
        )
    ) > {{ tolerance }}
{% endmacro %}
```

### The Singular Assertion
In `tests/assert_lap_residual_identity.sql`, we instantiate this macro:

```sql
{{ assert_additive_identity(
     ref('int_lap_residual_decomposed'),
     'pace_delta_s',
     ['fuel_component_s', 'compound_component_s', 'rubber_component_s',
      'ambient_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
     'driver_skill_residual_s',
     tolerance=0.0001
) }}
```

If a refactor or model edit alters how a physical component calculates its timing penalty without making matching adjustments to the residual subtraction, this test immediately returns rows, failing `make dbt-test` and blocking integration.

---

## 8.3  Profiles and Schema Variables

Our pipeline runs locally without external database configurations. We declare targets and file paths inside `transform/profiles/profiles.yml`:

```yaml
off_the_pace:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: '../data/dev.duckdb'
      threads: 4
    ci:
      type: duckdb
      path: '../data/ci.duckdb'
      threads: 2
```

### External Location Variables
Rather than hardcoding physical file paths inside staging sources, staging paths are parameterized using dbt variables:

```yaml
# transform/models/staging/src_formula1.yml
sources:
 -name: bronze_f1
    tables:
     -name: raw_laps
        meta:
          external_location: "{{ var('bronze_base', '../data/bronze') }}/laps/*/*/*.parquet"
```

This configuration enables the pipeline to adapt dynamically:
*   **Local Development:** Defaults to `../data/bronze`.
*   **Continuous Integration (CI):** Bypasses dev databases and reads from fixture Parquet locations by executing `dbt run --vars 'bronze_base: tests/fixtures/bronze'`.

---

## 8.4  CI/CD Production Toolchain

The production engine is **DuckDB** (local + CI). Microsoft Fabric Lakehouse is a planned future target but is not yet wired up see [Limitations](../understand/limitations.md) for the honest framing.

In the current CI pipeline (`.github/workflows/dbt-ci.yml`):
1.  **Fixture build:** `dbt build --target ci` reads from `tests/fixtures/bronze/` (3 races × 4 datasets) so no full Bronze Parquet is needed in CI.
2.  **Full test suite:** All 27 singular math-identity assertions + ~312 generic schema tests must pass.
3.  **Validation Gate:** All schema contracts and mathematical closure tests must pass before a PR is merged into `main`.

---

**Continue to [Part 9  Common task recipes](./09_cookbook.md).**
