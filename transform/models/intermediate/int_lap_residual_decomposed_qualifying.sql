-- Third Model Sequence #5 (sub): Qualifying lap residual decomposition.
-- Applies the same 7-term identity as int_lap_residual_decomposed but for quali sessions.
--
-- Key physical differences from race decomposition:
--  -fuel_component_s ≈ 0 (12 kg flat, no burnoff)
--  -compound_component_s: tyre age is low (push lap); cliff dynamics suppressed
--  -constructor_component_s: qualifying-trim coefficient (#5 sub-model)
--  -dirty_air_tax_s: typically zero in quali (clear track for push laps)
--  -driver_skill_residual_s: purer single-lap pace signal
--
-- Residual identity (seconds, positive = slower):
--   quali_pace_delta_s = fuel + compound + rubber + ambient
--                      + constructor + dirty_air_tax + driver_skill + unexplained
--
-- Output grain: lap_id one row per valid qualifying lap.
-- PK: lap_id (FK to stg_laps_qualifying).

{{ config(materialized='table', tags=['simulation', 'qualifying']) }}

WITH quali_laps AS (
    SELECT
        q.lap_id,
        q.race_year,
        q.race_id,
        q.driver_id,
        q.constructor_id,
        q.lap_number,
        q.session_type,
        q.lap_time_s,
        q.tyre_life,
        q.compound,
        q.is_personal_best,
        q.is_valid_lap
    FROM {{ ref('stg_laps_qualifying') }} q
    WHERE q.is_valid_lap = TRUE
      AND q.lap_time_s IS NOT NULL
),

fuel AS (
    SELECT
        lap_id,
        fuel_mass_kg,
        fuel_component_s
    FROM {{ ref('int_lap_fuel_state_qualifying') }}
),

-- Session median as the field pace baseline (no lap-number smoothing needed for quali)
field_pace AS (
    SELECT
        race_year,
        race_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lap_time_s)
            FILTER (WHERE is_valid_lap = TRUE AND lap_time_s IS NOT NULL)
            AS session_median_s
    FROM {{ ref('stg_laps_qualifying') }}
    GROUP BY race_year, race_id
),

constructor_coef AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        constructor_structural_pace_s,
        constructor_structural_pace_se_s,
        constructor_structural_pace_ci_low_s,
        constructor_structural_pace_ci_high_s
    FROM {{ ref('int_constructor_structural_pace_qualifying') }}
),

-- Ambient / track evolution: reuse the race-day data for the same event.
-- Qualifying happens the day before the race; we use same-event weather as an approximation.
weather_proxy AS (
    SELECT DISTINCT ON (race_year, race_id)
        race_year,
        race_id,
        COALESCE(rubber_component_s, 0.0)   AS rubber_component_s,
        COALESCE(ambient_component_s, 0.0)  AS ambient_component_s,
        track_temp_c
    FROM {{ ref('int_track_evolution') }}
    ORDER BY race_year, race_id
),

combined AS (
    SELECT
        q.lap_id,
        q.race_year,
        q.race_id,
        q.driver_id,
        q.constructor_id,
        q.lap_number,
        q.session_type,
        q.lap_time_s,
        q.tyre_life,
        q.compound,
        q.is_personal_best,
        f.fuel_mass_kg,
        f.fuel_component_s,
        fp.session_median_s                                   AS base_track_pace_s,
        COALESCE(w.rubber_component_s, 0.0)                   AS rubber_component_s,
        COALESCE(w.ambient_component_s, 0.0)                  AS ambient_component_s,
        w.track_temp_c,
        -- Constructor qualifying-mode coefficient
        COALESCE(cc.constructor_structural_pace_s, 0.0)       AS constructor_component_s,
        COALESCE(cc.constructor_structural_pace_se_s, 0.0)    AS constructor_component_se_s,
        cc.constructor_structural_pace_ci_low_s,
        cc.constructor_structural_pace_ci_high_s,
        -- Compound degradation: use tyre_life as age proxy; cliff suppressed in quali
        -- by limiting to small age values. No survival-model cliff for quali.
        -- Simple linear wear model: wear_gradient × tyre_life.
        COALESCE(cp.compound_wear_gradient, 0.0) * q.tyre_life AS compound_component_s,
        -- Dirty air tax: assume zero in quali (each driver runs a clear lap).
        0.0                                                   AS dirty_air_tax_s,
        0.0                                                   AS dirty_air_tax_se_s
    FROM quali_laps q
    LEFT JOIN fuel f          USING (lap_id)
    LEFT JOIN field_pace fp   ON q.race_year = fp.race_year AND q.race_id = fp.race_id
    LEFT JOIN constructor_coef cc
        ON q.race_year = cc.race_year
        AND q.race_id  = cc.race_id
        AND q.constructor_id = cc.constructor_id
    LEFT JOIN weather_proxy w ON q.race_year = w.race_year AND q.race_id = w.race_id
    LEFT JOIN {{ ref('race_to_track') }} r2t
        ON q.race_id = r2t.race_id
    LEFT JOIN {{ ref('dim_compounds_season') }} cp
        ON r2t.track_id    = cp.circuit_key
        AND q.race_year    = cp.season
        AND q.compound     = cp.compound_code
),

with_residual AS (
    SELECT
        *,
        -- Pace delta vs session median
        lap_time_s-COALESCE(base_track_pace_s, lap_time_s) AS quali_pace_delta_s,

        -- Total physics explained
        COALESCE(fuel_component_s, 0.0)
            + COALESCE(compound_component_s, 0.0)
            + COALESCE(rubber_component_s, 0.0)
            + COALESCE(ambient_component_s, 0.0)
            + COALESCE(constructor_component_s, 0.0)
            + COALESCE(dirty_air_tax_s, 0.0)          AS total_explained_s,

        -- Driver skill residual: closed form
        (lap_time_s-COALESCE(base_track_pace_s, lap_time_s))
           -COALESCE(fuel_component_s, 0.0)
           -COALESCE(compound_component_s, 0.0)
           -COALESCE(rubber_component_s, 0.0)
           -COALESCE(ambient_component_s, 0.0)
           -COALESCE(constructor_component_s, 0.0)
           -COALESCE(dirty_air_tax_s, 0.0)           AS quali_driver_skill_residual_s
    FROM combined
)

SELECT
    lap_id,
    race_year,
    race_id,
    driver_id,
    constructor_id,
    lap_number,
    session_type,
    lap_time_s,
    tyre_life,
    compound,
    is_personal_best,
    base_track_pace_s,
    quali_pace_delta_s,
    fuel_mass_kg,
    fuel_component_s,
    compound_component_s,
    rubber_component_s,
    ambient_component_s,
    constructor_component_s,
    constructor_component_se_s,
    constructor_structural_pace_ci_low_s    AS constructor_component_ci_low_s,
    constructor_structural_pace_ci_high_s   AS constructor_component_ci_high_s,
    dirty_air_tax_s,
    dirty_air_tax_se_s,
    total_explained_s,
    quali_driver_skill_residual_s,
    track_temp_c
FROM with_residual
ORDER BY race_year, race_id, driver_id, lap_number
