-- Layer 04: Expected compound pace and cliff prediction.
-- Hockey-stick polynomial: β₀ + β₁×age + β₂×age² + β₃×GREATEST(0, age-cliff_onset)²
-- All β coefficients sourced from dim_compounds_season (placeholder values until
-- Python RANSAC estimation rewrites the seed).
-- ambient_temp_delta = track_temp-compound_optimal_temp_low, clipped [0,30].
{{ config(materialized='table') }}

WITH geom AS (
    SELECT
        stint_id,
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_in_stint,
        age_in_stint,
        compound_in_stint           AS compound
    FROM {{ ref('int_stint_geometry') }}
),

race_map AS (
    SELECT race_id, track_id FROM {{ ref('race_to_track') }}
),

compound_params AS (
    SELECT * FROM {{ ref('dim_compounds_season') }}
),

weather AS (
    SELECT DISTINCT ON (race_year, race_id, lap_number)
        race_year,
        race_id,
        lap_number,
        track_temp_c
    FROM {{ ref('stg_weather') }}
    ORDER BY race_year, race_id, lap_number
),

combined AS (
    SELECT
        g.stint_id,
        g.lap_id,
        g.race_year,
        g.race_id,
        g.driver_id,
        g.lap_number,
        g.lap_in_stint,
        g.age_in_stint,
        g.compound,
        rm.track_id,
        w.track_temp_c,
        cp.compound_cliff_onset_laps,
        cp.compound_cliff_severity,
        cp.compound_wear_gradient,
        cp.compound_grip_peak,
        cp.compound_optimal_temp_low
    FROM geom g
    JOIN race_map rm
        ON g.race_id = rm.race_id
    LEFT JOIN compound_params cp
        ON rm.track_id      = cp.circuit_key
        AND g.race_year     = cp.season
        AND g.compound      = cp.compound_code
    LEFT JOIN weather w
        ON g.race_year  = w.race_year
        AND g.race_id   = w.race_id
        AND g.lap_number = w.lap_number
),

with_pace AS (
    SELECT
        *,
        -- Temperature delta from compound optimum, clipped to [0, 30]
        LEAST(GREATEST(COALESCE(track_temp_c, 30.0)-COALESCE(compound_optimal_temp_low, 20.0), 0.0), 30.0)
                                                                AS ambient_temp_delta,
        -- Laps past cliff onset (0 before onset)
        GREATEST(CAST(age_in_stint AS DOUBLE)-COALESCE(compound_cliff_onset_laps, 999.0), 0.0)
                                                                AS laps_past_cliff,
        age_in_stint > COALESCE(compound_cliff_onset_laps, 999.0)
                                                                AS cliff_onset_passed
    FROM combined
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    lap_in_stint,
    age_in_stint,
    compound,
    cliff_onset_passed,
    -- Hockey-stick pace model:
    -- grip_peak baseline + linear wear + quadratic age term (rubber accumulation)
    -- + cliff_severity * laps_past_cliff (linear post-cliff acceleration-severity
    --   is the empirically fitted average s/lap rate of post-cliff degradation)
    COALESCE(compound_grip_peak, 0.0)
        + COALESCE(compound_wear_gradient, 0.0) * age_in_stint
        + 0.002 * POWER(age_in_stint, 2)
        + COALESCE(compound_cliff_severity, 0.0) * laps_past_cliff
        + 0.005 * ambient_temp_delta                            AS expected_compound_pace_s,
    -- First derivative: rate of pace loss at current age
    COALESCE(compound_wear_gradient, 0.0)
        + 0.004 * age_in_stint
        + COALESCE(compound_cliff_severity, 0.0)
                                                                AS expected_degradation_rate_s_per_lap,
    ambient_temp_delta,
    laps_past_cliff
FROM with_pace
