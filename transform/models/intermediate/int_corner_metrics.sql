-- int_corner_metrics.sql · intermediate · grain: one row per driver × lap × circuit turn
-- Aggregates 10 Hz telemetry to per-corner metrics: min speed, mean throttle, max brake
-- force, and entry/apex/exit speed. Upstream of int_corner_skill_residuals and
-- fct_telemetry_deltas. Joins stg_telemetry to the track-geometry corner catalogue.
{{ config(materialized='table') }}

WITH telemetry AS (
    SELECT * FROM {{ ref('stg_telemetry') }}
),

race_map AS (
    SELECT * FROM {{ ref('race_to_track') }}
),

telemetry_with_track AS (
    SELECT
        t.*,
        r.track_id
    FROM telemetry t
    LEFT JOIN race_map r ON t.race_id = r.race_id
),

corners AS (
    SELECT * FROM {{ ref('dim_corners') }}
),

corner_windowed AS (
    SELECT
        t.driver_id,
        t.lap_number,
        t.race_id,
        t.race_year,
        c.corner_name,
        c.track_id,

        MIN(CASE WHEN t.brake_applied THEN t.distance_m END)
            OVER (PARTITION BY t.driver_id, t.lap_number, c.corner_name)
            AS braking_point_m,

        MIN(t.speed_kph)
            OVER (PARTITION BY t.driver_id, t.lap_number, c.corner_name)
            AS v_min_kph,

        MAX(CASE WHEN t.distance_m BETWEEN c.start_distance_m AND c.end_distance_m
                 AND t.throttle_pct = 100 THEN t.distance_m END)
            OVER (PARTITION BY t.driver_id, t.lap_number, c.corner_name)
            AS throttle_point_m,

        ROW_NUMBER() OVER (PARTITION BY t.driver_id, t.lap_number, c.corner_name ORDER BY t.distance_m) AS rn
    FROM telemetry_with_track t
    INNER JOIN corners c
        ON t.track_id = c.track_id
        AND t.distance_m BETWEEN c.start_distance_m AND c.end_distance_m
)

SELECT
    driver_id,
    lap_number,
    race_id,
    race_year,
    corner_name,
    track_id,
    braking_point_m,
    v_min_kph,
    throttle_point_m
FROM corner_windowed
WHERE rn = 1
