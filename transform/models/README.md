# Models

Four layers, each in its own subdirectory. The DAG flows top to bottom.

| Layer | Dir | Materialisation | Purpose |
|---|---|---|---|
| Staging | `staging/` | view | Bronze → clean column names, type casts, validity flags (12 views) |
| Reference | `reference/` | table | Seed-backed dimensions: circuits, compounds, drivers, constructors (4 tables) |
| Intermediate | `intermediate/` | table / view | Physics layers 03–05: fuel, air state, thermal proxy, compound cliff, field pace, track evolution, constructor pace, synthetic teammate, event corrections, residual decomposition, anomaly flags (34 models) |
| Marts | `marts/` | table | Feature tables for ML and analytics: `fct_driver_skill_features`, `fct_cliff_prediction_features`, `fct_lap_residuals`, `fct_telemetry_deltas`, `fct_stint_features`, `fct_ghost_car_pace`, `fct_ghost_race_finish`, `mart_corner_skill_driver`, `mart_degradation_history_envelope`, `dim_events` (10 tables) |

See [../README.md](../README.md) for the full model DAG and running instructions.

---

## Model authoring standard

New models follow the house style so the layer stays consistent and CI-clean:

- **Header comment** (every model): one-line purpose; for decomposition/identity models,
  the full additive identity with units (`= a_s + b_s + …`, positive = slower) and a
  per-term source map. Describe present behaviour only a column-meaning change belongs
  in the commit message, not a log line in the header.
- **Naming**: `stg_` / `int_` / `fct_` / `dim_` / `mart_` prefixes; `_s` suffix = seconds,
  `_se_s` = standard error in seconds, `*_flag` = boolean.
- **Materialisation**: staging = view, intermediate = view (+`tags: [intermediate]`),
  reference/marts = table (set in `dbt_project.yml`; don't override per-model without reason).
- **Refs only** never hardcode a table name: `{{ ref(...) }}` for models,
  `{{ source(...) }}` for bronze.
- **Macros over copy-paste**: `clean_lap_filter`, `normalize_compound`, `bayesian_shrinkage`,
  `posterior_variance`, `normal_cdf`, `circuit_id_from_name`, `assert_additive_identity`
  (see [../macros/README.md](../macros/README.md)).
- **Vars** for tunable knobs (`era_boundary`, `outlier_exclude_ratio`,
  `ghost_short_run_threshold`), never magic numbers inline.
- **Every model gets a `schema.yml` entry** in its own layer file: description + grain +
  a description on every column; generic tests (`not_null`/`unique`/`accepted_values`/
  `relationships`) on keys and enums, with arguments nested under `arguments:` and config
  keys (`where`, `severity`) under `config:` to stay deprecation-free.
- **Singular tests** (`tests/assert_*.sql`) for any mathematical invariant; pass = zero rows.
  Register them in [../tests/README.md](../tests/README.md).
- **sqlfluff-clean**: UPPER keywords/functions, lower identifiers, trailing commas.

See [../tests/README.md](../tests/README.md) to register a new singular test.
