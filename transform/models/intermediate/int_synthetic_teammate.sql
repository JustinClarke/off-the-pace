-- Layer 04: Synthetic teammate comparison.
-- For each ego driver × lap, finds the teammate (same constructor, different driver)
-- on the same lap and adjusts their raw lap time to the ego's tyre state using
-- int_compound_cliff_predicted delta. driver_skill_proxy_s > 0 = ego is faster.
-- pair_quality_weight = 1/(1 + stddev of teammate speed_residuals last 5 laps).
-- strategic_divergence_flag = TRUE when stints diverge by > 3 laps.
{{ config(materialized='table') }}

WITH fuel_state AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        weight_corrected_lap_time
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
        compound_in_stint           AS compound,
        age_in_stint
    FROM {{ ref('int_stint_geometry') }}
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
        expected_compound_pace_s
    FROM {{ ref('int_compound_cliff_predicted') }}
),

laps AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        lap_number,
        position
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap = TRUE
),

-- Identify teammate pairs (same constructor, same lap)
pairs AS (
    SELECT
        e.race_year,
        e.race_id,
        e.lap_number,
        e.driver_id                                 AS ego_driver_id,
        t.driver_id                                 AS teammate_driver_id,
        e.constructor_id
    FROM laps e
    JOIN laps t
        ON e.race_year      = t.race_year
        AND e.race_id       = t.race_id
        AND e.lap_number    = t.lap_number
        AND e.constructor_id = t.constructor_id
        AND e.driver_id     != t.driver_id
),

-- Join ego and teammate fuel state + cliff predictions
ego_data AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        f.lap_number,
        f.weight_corrected_lap_time         AS ego_wc_lap_time_s,
        g.lap_in_stint                      AS ego_lap_in_stint,
        c.expected_compound_pace_s          AS ego_compound_pace_s
    FROM fuel_state f
    JOIN geom g USING (lap_id)
    JOIN cliff c USING (lap_id)
),

teammate_data AS (
    SELECT
        f.race_year,
        f.race_id,
        f.driver_id,
        f.lap_number,
        f.lap_time_s                        AS tm_raw_lap_time_s,
        f.weight_corrected_lap_time         AS tm_wc_lap_time_s,
        g.lap_in_stint                      AS tm_lap_in_stint,
        c.expected_compound_pace_s          AS tm_compound_pace_s
    FROM fuel_state f
    JOIN geom g USING (lap_id)
    JOIN cliff c USING (lap_id)
),

joined AS (
    SELECT
        p.race_year,
        p.race_id,
        p.lap_number,
        p.ego_driver_id,
        p.teammate_driver_id,
        p.constructor_id,
        e.ego_wc_lap_time_s,
        e.ego_lap_in_stint,
        e.ego_compound_pace_s,
        t.tm_raw_lap_time_s,
        t.tm_wc_lap_time_s,
        t.tm_lap_in_stint,
        t.tm_compound_pace_s,
        -- Tyre-state correction: adjust teammate weight-corrected time to ego compound/age
        t.tm_wc_lap_time_s
            + (e.ego_compound_pace_s-t.tm_compound_pace_s)   AS teammate_pace_adjusted_s,
        -- Skill proxy: positive = ego is faster than synthetic teammate
        (t.tm_wc_lap_time_s + (e.ego_compound_pace_s-t.tm_compound_pace_s))
           -e.ego_wc_lap_time_s                               AS driver_skill_proxy_s,
        -- Strategic divergence: stint positions differ by > 3 laps
        ABS(t.tm_lap_in_stint-e.ego_lap_in_stint) > 3        AS strategic_divergence_flag,
        t.tm_raw_lap_time_s IS NOT NULL                         AS teammate_available_flag
    FROM pairs p
    JOIN ego_data e
        ON p.race_year     = e.race_year
        AND p.race_id      = e.race_id
        AND p.lap_number   = e.lap_number
        AND p.ego_driver_id = e.driver_id
    JOIN teammate_data t
        ON p.race_year         = t.race_year
        AND p.race_id          = t.race_id
        AND p.lap_number       = t.lap_number
        AND p.teammate_driver_id = t.driver_id
),

-- Pair quality: inverse of rolling stddev of skill proxy over last 5 laps
with_quality AS (
    SELECT
        *,
        -- Low stddev → consistent pairing → high quality weight
        1.0 / (1.0 + COALESCE(
            STDDEV(driver_skill_proxy_s) OVER (
                PARTITION BY race_year, race_id, ego_driver_id, teammate_driver_id
                ORDER BY lap_number
                ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
            ),
            0.5
        ))                                                      AS pair_quality_weight
    FROM joined
)

SELECT
    race_year,
    race_id,
    lap_number,
    ego_driver_id,
    teammate_driver_id,
    constructor_id,
    ego_wc_lap_time_s,
    tm_raw_lap_time_s,
    tm_wc_lap_time_s,
    teammate_pace_adjusted_s,
    driver_skill_proxy_s,
    pair_quality_weight,
    strategic_divergence_flag,
    teammate_available_flag
FROM with_quality
ORDER BY race_year, race_id, ego_driver_id, lap_number
