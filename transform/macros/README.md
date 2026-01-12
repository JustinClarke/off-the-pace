# dbt Macros

Custom macros for validation, statistical operations, and reusable filter predicates. Established initially to eliminate pattern duplication across 10 new models (§3.2 of the implementation plan).

## Implemented Macros

### `assert_additive_identity(model_ref, total_col, component_cols, residual_col, tolerance=0.0001)`

Validates that an additive decomposition identity holds: `total = sum(components) + residual ± tolerance`.

**Used by:** identity-closure singular tests in #4, #5, #6, #7, #8, and any future additive model.

**Example:**
```sql
-- In tests/assert_lap_residual_identity.sql
{{ assert_additive_identity(
     ref('int_lap_residual_decomposed'),
     'pace_delta_s',
     ['fuel_component_s', 'compound_component_s', 'rubber_component_s',
      'ambient_component_s', 'constructor_component_s', 'dirty_air_tax_s'],
     'driver_skill_residual_s',
     tolerance=0.0001
) }}
```

---

### `bayesian_shrinkage(n_col, observed_col, prior_mean_expr, prior_weight)`

Computes normal-normal conjugate shrinkage: `posterior = (n × observed + weight × prior) / (n + weight)`.

Handles `n=0` by returning NULL, which is correct for unobserved cells.

**Used by:** #3 (driver affinity shrinkage) and #10 (era-bridge anchor shrinkage).

**Example:**
```sql
SELECT
  driver_id,
  {{ bayesian_shrinkage(
       'panel_observations_n',
       'observed_circuit_affinity',
       '0',  -- zero-centered prior
       '15'  -- 15 equivalent sample weight
  ) }} as shrunken_affinity_s
FROM panel_data
```

---

### `posterior_variance(n_col, observation_variance_expr, prior_variance_expr)`

Computes posterior variance from normal-normal conjugate model: `1 / (n/σ² + 1/σ₀²)`.

Returns NULL if any input is NULL or ≤0 (precision-weighted inversion requires positive variances).

**Used by:** shrinkage models (#3, #10) to emit `_se_s` and CI bounds derived from posterior variance.

**Example:**
```sql
SELECT
  driver_id,
  shrunken_skill,
  SQRT({{ posterior_variance(
             'sample_count',
             'observation_variance_from_fit',
             'prior_variance'
       ) }}) as posterior_se_s
FROM fitted_panel
```

---

### `clean_lap_filter()`

Reusable WHERE clause predicate filtering to "clean" laps suitable for driver skill extraction.

Clean lap criteria:
1. `correction_weight = 1.0` (no manual outlier downweighting)
2. `anomaly_class ∉ ('mistake', 'conditions')` (excludes crashes, water runoff)
3. `is_rain_lap = FALSE` (excludes wet-compound laps)

This is the canonical definition; use it everywhere skill signals are extracted to prevent silent divergence.

**Used by:** #3, #4, #5, #6, #8, #10, and any future model extracting driver skill or reading anomaly flags.

**Example:**
```sql
SELECT
  driver_id,
  AVG(driver_skill_residual_s) as clean_skill_mean
FROM int_lap_residual_decomposed
WHERE {{ clean_lap_filter() }}
GROUP BY driver_id
```

---

### `normalize_compound(compound_col)`

Maps Pirelli's 2018-era legacy compound names onto the modern SOFT/MEDIUM/HARD taxonomy so that compound-parameter joins (`dim_compounds_season`) land correctly for 2018.

Pirelli ran a 7-compound range in 2018 (HYPERSOFT/ULTRASOFT/SUPERSOFT/SOFT/MEDIUM/HARD/SUPERHARD). The cliff-parameter seed only fits the modern 5-name set (`{SOFT, MEDIUM, HARD, INTERMEDIATE, WET}`). Without this macro the three legacy soft variants (8,836 laps, all 2018) produce a 100%-NULL compound-param join.

**Scope warning:** use this **only** on ML-facing feature joins (e.g. `fct_cliff_prediction_features`). Do **not** apply it inside `int_compound_cliff_predicted`-that model's output feeds `compound_component_s` in `int_lap_residual_decomposed`, and normalising there would silently re-attribute compound vs. driver skill for 2018 laps. Residual nulls after normalisation are intentional and handled by XGBoost's native missing-value path. See `ml/BUILD_LOG.md` (L0-2).

**Used by:** `fct_cliff_prediction_features` (compound-params join only).

**Example:**
```sql
SELECT
  {{ normalize_compound('compound') }} as compound_normalised,
  cliff_onset_lap_in_stint
FROM stg_laps
JOIN dim_compounds_season
  ON {{ normalize_compound('compound') }} = dim_compounds_season.compound
```

---

## Future Candidates

Patterns that appear in 3+ models but are not yet extracted to macros:

- **Nanosecond-to-seconds cast** (`CAST(x AS DOUBLE) / 1e9`)-used in `stg_laps`, `stg_weather`, `stg_telemetry`
- **Trailing-N-lap window bounds** (`ROWS BETWEEN N PRECEDING AND CURRENT ROW`)-currently hard-coded in several intermediate models
- **Exponential moving average** (EW smoothing with configurable τ)-used in `int_lap_air_state`, `int_lap_thermal_proxy`

These will be extracted when they repeat across 3+ models or when a subsequent refactoring makes the pattern frequency obvious.
