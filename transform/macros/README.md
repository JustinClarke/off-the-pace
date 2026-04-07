# dbt Macros

Custom macros for validation, statistical operations, and reusable filter predicates. Each one exists to eliminate pattern duplication: a definition lives once here instead of being copy-pasted, and silently diverging, across models.

## Implemented Macros

### `assert_additive_identity(model_ref, total_col, component_cols, residual_col, tolerance=0.0001)`

Validates that an additive decomposition identity holds: `total = sum(components) + residual ± tolerance`.

**Used by:** the lap seven-term identity test (`assert_lap_7term_identity`) and its worked
macro-usage duplicate (`assert_example_identity_closure`). The other identity-closure tests
assert different identity shapes with their own inline SQL rather than this macro.

**Example:**
```sql
-- In tests/assert_lap_7term_identity.sql
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

**Used by:** `int_driver_circuit_affinity`, `int_driver_circuit_era_affinity`, and
`int_driver_season_ratings`.

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

**Used by:** the same three shrinkage models as `bayesian_shrinkage` above
(`int_driver_circuit_affinity`, `int_driver_circuit_era_affinity`, `int_driver_season_ratings`)
to emit `_se_s` and CI bounds derived from posterior variance.

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

**Used by:** no model directly today this is the canonical recommended pattern, not yet an
adopted one. Every current skill-extracting model (including `fct_driver_skill_features`, the
driver-skill ML feature mart) inlines the equivalent three-condition filter itself rather than
calling this macro, the silent-divergence risk this macro's own definition exists to prevent.

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

**Scope warning:** use this **only** on ML-facing feature joins (e.g. `fct_cliff_prediction_features`). Do **not** apply it inside `int_compound_cliff_predicted`-that model's output feeds `compound_component_s` in `int_lap_residual_decomposed`, and normalising there would silently re-attribute compound vs. driver skill for 2018 laps. Residual nulls after normalisation are intentional and handled by XGBoost's native missing-value path.

**Used by:** no model today. `fct_cliff_prediction_features` is the intended consumer (its
compound-params join is exactly the 2018-legacy-name problem this macro solves) but currently
handles compound normalisation inline rather than calling this macro.

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

### `circuit_id_from_name(name_col)`

Derives a stable physical-circuit identifier by slugifying a circuit's display name
(`lower` → non-alphanumerics to `_` → trimmed). The seed key (`circuit_key`) is really a
grand-prix/event slug, so one physical venue can carry several keys (renamed events,
double-headers). Slugifying `circuit_name` collapses those into one `circuit_id` so an
"equal-car track record at a circuit" pools all races run at the same venue.

**Used by:** `int_driver_circuit_era_affinity` and `dim_circuits` (physical-circuit grain).

**Example:**
```sql
SELECT
  {{ circuit_id_from_name('circuit_name') }} AS circuit_id,
  circuit_name
FROM dim_circuits
```

---

### `normal_cdf(x)`

Standard normal CDF Φ(x). DuckDB has no `erf`/normal-CDF builtin, so this inlines the
Zelen & Severo rational approximation (Abramowitz & Stegun 26.2.17), max absolute error
~7.5e-8 over the whole real line. Pass a simple column or scalar expression (it is inlined
several times, so avoid an expensive sub-expression).

**Used by:** `fct_ghost_race_finish` (SE propagation: `p_beats_next`, finish-position
probabilities).

**Example:**
```sql
SELECT
  driver_id,
  {{ normal_cdf('pace_gap_s / pace_gap_se_s') }} AS p_beats_next
FROM ranked_pairs
```

---

## Future Candidates

Patterns that appear in 3+ models but are not yet extracted to macros:

- **Nanosecond-to-seconds cast** (`CAST(x AS DOUBLE) / 1e9`)  -  used in `stg_laps`, `stg_weather`, `stg_telemetry`
- **Trailing-N-lap window bounds** (`ROWS BETWEEN N PRECEDING AND CURRENT ROW`)  -  currently hard-coded in several intermediate models
- **Exponential moving average** (EW smoothing with configurable τ)  -  used in `int_lap_air_state`, `int_lap_thermal_proxy`

These will be extracted when they repeat across 3+ models or when a subsequent refactoring makes the pattern frequency obvious.
