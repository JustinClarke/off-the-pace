-- Initial transform: 7-term residual decomposition per lap.
-- Decomposes actual lap_time_s into seven additive components, yielding a
-- driver-skill residual stripped of field pace baseline, fuel mass, tyre compound
-- trajectory, rubber track evolution, ambient weather, constructor structural pace,
-- and dirty-air tax (initial addition).
--
-- Residual identity (all terms in seconds, positive = slower):
--   pace_delta_s = lap_time_s-base_track_pace_s
--               =  fuel_component_s
--                + compound_component_s
--                + rubber_component_s
--                + ambient_component_s
--                + constructor_component_s
--                + dirty_air_tax_s          ← Initial release: extracted from driver_skill_residual_s
--                + driver_skill_residual_s
--                + track_unexplained_s      (informational; not in total_explained_s)
--
-- base_track_pace_s      : field_pace_smoothed_s from int_field_pace_curve (trimmed field median)
-- pace_delta_s           : lap_time_s base_track_pace_s
-- fuel_component_s       : weight_penalty_s from int_lap_fuel_state
-- compound_component_s   : expected_compound_pace_s from int_compound_cliff_predicted
-- rubber_component_s     : rubber_component_s from int_track_evolution
-- ambient_component_s    : ambient_component_s from int_track_evolution
-- constructor_component_s: constructor_structural_pace_s from int_constructor_structural_pace (#6)
-- dirty_air_tax_s        : per-lap dirty-air tax from int_dirty_air_tax_component (#8)
-- driver_skill_residual_s: pace_delta_s minus all above; cleaned of dirty-air signal
--
-- BREAKING CHANGE (2026-05-20): driver_skill_residual_s is a delta-from-field-pace residual.
-- BREAKING CHANGE (initial transform): constructor source changed from int_constructor_pace_index to
--   int_constructor_structural_pace; dirty_air_tax_s added; driver_skill_residual_s is smaller.
--
-- correction_weight from int_event_corrections is carried but NOT applied here.
{{ config(materialized='table') }}

WITH field_pace AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        field_pace_smoothed_s
    FROM {{ ref('int_field_pace_curve') }}
),

fuel AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_corrected_lap_time,
        fuel_mass_kg,
        weight_penalty_s
    FROM {{ ref('int_lap_fuel_state') }}
),

geom AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        age_in_stint,
        compound_in_stint           AS compound,
        stint_length_actual
    FROM {{ ref('int_stint_geometry') }}
),

laps_meta AS (
    SELECT
        lap_id,
        constructor_id,
        position
    FROM {{ ref('stg_laps') }}
),

cliff AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        compound,
        age_in_stint,
        expected_compound_pace_s,
        expected_degradation_rate_s_per_lap,
        cliff_onset_passed,
        ambient_temp_delta,
        laps_past_cliff
    FROM {{ ref('int_compound_cliff_predicted') }}
),

evolution AS (
    SELECT
        race_year,
        race_id,
        lap_number,
        rubber_component_s,
        ambient_component_s,
        unexplained_residual_s      AS track_unexplained_s,
        track_temp_c,
        rainfall_flag
    FROM {{ ref('int_track_evolution') }}
),

constructor_struct AS (
    -- Initial transform: panel-regression constructor coefficient replaces the EW rolling index.
    -- Grain: (race_year, race_id, constructor_id) one row per constructor per race.
    SELECT
        race_year,
        race_id,
        constructor_id,
        constructor_structural_pace_s,
        constructor_structural_pace_se_s,
        constructor_structural_pace_ci_low_s,
        constructor_structural_pace_ci_high_s,
        panel_observations_n
    FROM {{ ref('int_constructor_structural_pace') }}
),

constructor_interaction AS (
    -- Third-Iteration: circuit-constructor interaction to capture circuit-specific baseline deviations
    SELECT
        race_year,
        race_id,
        constructor_id,
        circuit_constructor_interaction_s,
        interaction_se_s,
        interaction_obs_n
    FROM {{ ref('int_circuit_x_constructor_interaction') }}
),

dirty_air AS (
    -- Initial transform: per-lap dirty-air tax extracted from driver_skill_residual_s.
    SELECT
        lap_id,
        dirty_air_tax_s,
        dirty_air_tax_se_s,
        dirty_air_intensity_lag1,
        tax_calibration_confidence,
        cumulative_dirty_air_tax_race_s,
        dirtiest_air_lap_in_race_flag
    FROM {{ ref('int_dirty_air_tax_component') }}
),

corrections AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        correction_class,
        correction_weight,
        is_safety_car_lap,
        is_vsc_lap,
        is_restart_lap,
        is_pre_controlled_lap,
        is_local_yellow_lap,
        is_major_outlier_lap
    FROM {{ ref('int_event_corrections') }}
),

-- Combine all physical components onto the lap grain
combined AS (
    SELECT
        f.lap_id,
        f.stint_id,
        f.race_year,
        f.race_id,
        f.driver_id,
        f.lap_number,
        lm.constructor_id,
        lm.position,
        f.lap_time_s,
        f.weight_corrected_lap_time,
        f.fuel_mass_kg,
        f.weight_penalty_s                                      AS fuel_component_s,
        c.compound,
        c.age_in_stint,
        c.expected_compound_pace_s                              AS compound_component_s,
        c.expected_degradation_rate_s_per_lap,
        c.cliff_onset_passed,
        c.laps_past_cliff,
        c.ambient_temp_delta,
        g.lap_in_stint,
        g.stint_length_actual,

        -- Field pace baseline (trimmed-mean field pace, smoothed 5-lap centred window)
        fp.field_pace_smoothed_s                                AS base_track_pace_s,

        -- Track evolution components (NULL for low-sample laps, filled 0 to preserve row)
        COALESCE(e.rubber_component_s, 0.0)                     AS rubber_component_s,
        COALESCE(e.ambient_component_s, 0.0)                    AS ambient_component_s,
        e.track_unexplained_s,
        e.track_temp_c,
        e.rainfall_flag,

        -- Constructor structural pace (#6): panel FE coefficient + circuit interaction.
        COALESCE(cs.constructor_structural_pace_s, 0.0)
            + COALESCE(cci.circuit_constructor_interaction_s, 0.0) AS constructor_component_s,
        -- Standard error is propagated via sqrt(se_pace^2 + se_interaction^2)
        SQRT(
            POWER(COALESCE(cs.constructor_structural_pace_se_s, 0.0), 2)
            + POWER(COALESCE(cci.interaction_se_s, 0.0), 2)
        )                                                       AS constructor_component_se_s,
        cs.constructor_structural_pace_ci_low_s
            + COALESCE(cci.circuit_constructor_interaction_s, 0.0) AS constructor_component_ci_low_s,
        cs.constructor_structural_pace_ci_high_s
            + COALESCE(cci.circuit_constructor_interaction_s, 0.0) AS constructor_component_ci_high_s,
        cs.panel_observations_n                                  AS constructor_panel_n,

        -- Dirty-air tax (#8): per-lap seconds attributable to following another car.
        COALESCE(da.dirty_air_tax_s, 0.0)                       AS dirty_air_tax_s,
        COALESCE(da.dirty_air_tax_se_s, 0.0)                    AS dirty_air_tax_se_s,
        da.dirty_air_intensity_lag1,
        COALESCE(da.tax_calibration_confidence, 0.0)            AS dirty_air_tax_confidence,
        COALESCE(da.cumulative_dirty_air_tax_race_s, 0.0)       AS cumulative_dirty_air_tax_race_s,
        COALESCE(da.dirtiest_air_lap_in_race_flag, FALSE)       AS dirtiest_air_lap_in_race_flag,

        -- Correction metadata
        cor.correction_class,
        cor.correction_weight,
        cor.is_safety_car_lap,
        cor.is_vsc_lap,
        cor.is_restart_lap,
        cor.is_pre_controlled_lap,
        cor.is_local_yellow_lap,
        cor.is_major_outlier_lap

    FROM fuel f
    JOIN geom g              USING (lap_id)
    JOIN laps_meta lm        USING (lap_id)
    LEFT JOIN cliff c        USING (lap_id)
    LEFT JOIN field_pace fp  ON f.race_year  = fp.race_year
                             AND f.race_id   = fp.race_id
                             AND f.lap_number = fp.lap_number
    LEFT JOIN evolution e    ON f.race_year  = e.race_year
                             AND f.race_id   = e.race_id
                             AND f.lap_number = e.lap_number
    LEFT JOIN constructor_struct cs
                             ON f.race_year        = cs.race_year
                             AND f.race_id         = cs.race_id
                             AND lm.constructor_id  = cs.constructor_id
    LEFT JOIN constructor_interaction cci
                             ON f.race_year        = cci.race_year
                             AND f.race_id         = cci.race_id
                             AND lm.constructor_id  = cci.constructor_id
    LEFT JOIN dirty_air da   USING (lap_id)
    LEFT JOIN corrections cor USING (lap_id)
),

with_residual AS (
    SELECT
        *,
        -- Driver delta vs trimmed field pace (the closure base)
        lap_time_s-COALESCE(base_track_pace_s, lap_time_s)   AS pace_delta_s,

        -- Total physics offsets subtracted from pace_delta_s (7-term, initial transform).
        -- dirty_air_tax_s is now accounted for separately; driver_skill_residual_s is cleaner.
        fuel_component_s
            + COALESCE(compound_component_s, 0.0)
            + rubber_component_s
            + ambient_component_s
            + constructor_component_s
            + dirty_air_tax_s                                   AS total_explained_s,

        -- Driver skill residual: pace_delta_s minus all 7 physics components.
        -- Identity: pace_delta_s = total_explained_s + driver_skill_residual_s + track_unexplained_s
        -- Initial transform: dirty_air_tax_s is subtracted here; residual is smaller and cleaner than pre-initial.
        (lap_time_s-COALESCE(base_track_pace_s, lap_time_s))
           -fuel_component_s
           -COALESCE(compound_component_s, 0.0)
           -rubber_component_s
           -ambient_component_s
           -constructor_component_s
           -dirty_air_tax_s                                   AS driver_skill_residual_s

    FROM combined
    WHERE lap_time_s IS NOT NULL
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    constructor_id,
    lap_number,
    position,
    compound,
    age_in_stint,
    lap_in_stint,
    stint_length_actual,
    cliff_onset_passed,
    laps_past_cliff,
    fuel_mass_kg,

    -- Raw time, weight-corrected time, and field-pace baseline
    lap_time_s,
    weight_corrected_lap_time,
    base_track_pace_s,
    pace_delta_s,

    -- Additive components (all in seconds, positive = slower contribution)
    fuel_component_s,
    compound_component_s,
    rubber_component_s,
    ambient_component_s,
    constructor_component_s,
    dirty_air_tax_s,
    total_explained_s,

    -- Residuals
    driver_skill_residual_s,
    track_unexplained_s,

    -- Physics metadata (informational, not part of residual identity)
    expected_degradation_rate_s_per_lap,
    ambient_temp_delta,
    track_temp_c,
    rainfall_flag,
    constructor_component_se_s,
    constructor_component_ci_low_s,
    constructor_component_ci_high_s,
    constructor_panel_n,
    dirty_air_tax_se_s,
    dirty_air_intensity_lag1,
    dirty_air_tax_confidence,
    cumulative_dirty_air_tax_race_s,
    dirtiest_air_lap_in_race_flag,

    -- Correction metadata (for downstream masking decisions)
    correction_class,
    correction_weight,
    is_safety_car_lap,
    is_vsc_lap,
    is_restart_lap,
    is_pre_controlled_lap,
    is_local_yellow_lap,
    is_major_outlier_lap

FROM with_residual
ORDER BY race_year, race_id, driver_id, lap_number
