-- Gold layer: lap-grain feature table for machine learning (XGBoost degradation model).
-- Thin wrapper over int_lap_residual_decomposed that adds:
--   • ml_eligible flag -rows the model should train on (full weight, compound known)
--   • pu_family        -power-unit lineage for constructor grouping
--   • debut_year       -driver vintage for era-normalisation features
--
-- Residual identity (all in seconds, positive = slower):
--   lap_time_s = fuel_component_s + compound_component_s + rubber_component_s
--              + ambient_component_s + constructor_component_s
--              + driver_skill_residual_s + [unexplained]
--
-- correction_weight < 1.0 rows are retained but ml_eligible = FALSE.
-- Consumers that want clean laps only: WHERE ml_eligible = TRUE.
{{ config(materialized='table') }}

WITH base AS (
    SELECT * FROM {{ ref('int_lap_residual_decomposed') }}
),

drivers AS (
    SELECT driver_id, debut_year
    FROM {{ ref('dim_drivers') }}
),

constructors AS (
    SELECT constructor_id, pu_family
    FROM {{ ref('dim_constructors') }}
)

SELECT
    -- Grain keys
    b.lap_id,
    b.stint_id,
    b.race_year,
    b.race_id,
    b.driver_id,
    b.constructor_id,
    b.lap_number,

    -- Position / race context
    b.position,
    b.compound,
    b.age_in_stint,
    b.lap_in_stint,
    b.stint_length_actual,
    b.cliff_onset_passed,
    b.laps_past_cliff,
    b.fuel_mass_kg,

    -- Dimension attributes (for feature engineering)
    d.debut_year                        AS driver_debut_year,
    c.pu_family,

    -- Raw and weight-corrected time
    b.lap_time_s,
    b.weight_corrected_lap_time,

    -- Additive decomposition components (seconds, positive = slower)
    b.fuel_component_s,
    b.compound_component_s,
    b.rubber_component_s,
    b.ambient_component_s,
    b.constructor_component_s,
    b.total_explained_s,

    -- Residuals
    b.driver_skill_residual_s,
    b.track_unexplained_s,

    -- Physics metadata (informational)
    b.expected_degradation_rate_s_per_lap,
    b.ambient_temp_delta,
    b.track_temp_c,
    b.rainfall_flag,
    -- Initial transform release: legacy EW index columns replaced by structural pace SE and CI
    b.constructor_component_se_s,
    b.constructor_component_ci_low_s,
    b.constructor_component_ci_high_s,
    b.dirty_air_tax_s,
    b.dirty_air_tax_se_s,
    b.cumulative_dirty_air_tax_race_s,

    -- Correction metadata (for masking decisions)
    b.correction_class,
    b.correction_weight,
    b.is_safety_car_lap,
    b.is_vsc_lap,
    b.is_restart_lap,
    b.is_pre_controlled_lap,
    b.is_local_yellow_lap,
    b.is_major_outlier_lap,

    -- ML eligibility: full-weight lap with plausible decomposition components.
    -- Excludes: out-laps (compound NULL), SC/flag laps (correction_weight < 1),
    -- and component blowups (compound > 10s or |constructor| > 10s) from thin samples.
    b.correction_weight = 1.0
        AND b.compound_component_s IS NOT NULL
        AND b.compound_component_s <= 10.0
        AND ABS(b.constructor_component_s) <= 10.0
        AND b.lap_time_s IS NOT NULL            AS ml_eligible

FROM base b
LEFT JOIN drivers d     USING (driver_id)
LEFT JOIN constructors c USING (constructor_id)
ORDER BY b.race_year, b.race_id, b.driver_id, b.lap_number
