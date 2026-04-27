-- fct_telemetry_deltas.sql · marts · grain: one row per driver × lap × circuit turn
-- Driver vs. ghost-car corner-metric deltas: speed deficit, throttle gap, brake
-- differential at each corner. Powers the Telemetry Style Fingerprint feature
-- (Feature #19). Joins int_corner_metrics to fct_ghost_car_pace by corner.
{{ config(materialized='table') }}

WITH metrics AS (
    SELECT * FROM {{ ref('int_corner_metrics') }}
),

laps_info AS (
    SELECT DISTINCT
        race_id,
        driver_id,
        lap_number
    FROM {{ ref('stg_laps') }}
),

teammates AS (
    SELECT
        l1.race_id,
        l1.driver_id AS driver_a,
        l2.driver_id AS driver_b
    FROM laps_info l1
    INNER JOIN laps_info l2
        ON l1.race_id = l2.race_id
        AND l1.lap_number = l2.lap_number
    WHERE l1.driver_id < l2.driver_id
    GROUP BY 1, 2, 3
),

deltas AS (
    SELECT
        tm.race_id,
        tm.driver_a,
        tm.driver_b,
        m_a.corner_name,
        m_a.track_id,

        ROUND(COALESCE(m_a.braking_point_m-m_b.braking_point_m, 0), 1)
            AS braking_point_delta_m,

        ROUND(COALESCE(m_a.v_min_kph-m_b.v_min_kph, 0), 2)
            AS v_min_delta_kph,

        ROUND(COALESCE(m_a.throttle_point_m-m_b.throttle_point_m, 0), 1)
            AS throttle_point_delta_m,

        m_a.lap_number
    FROM teammates tm
    LEFT JOIN metrics m_a
        ON tm.race_id = m_a.race_id
        AND tm.driver_a = m_a.driver_id
    LEFT JOIN metrics m_b
        ON tm.race_id = m_b.race_id
        AND tm.driver_b = m_b.driver_id
        AND m_a.corner_name = m_b.corner_name
        AND m_a.lap_number = m_b.lap_number
    WHERE m_a.corner_name IS NOT NULL
)

SELECT * FROM deltas
