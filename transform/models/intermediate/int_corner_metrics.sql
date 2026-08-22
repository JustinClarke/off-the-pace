-- int_corner_metrics.sql · intermediate · grain: one row per driver × lap ×
-- circuit turn
-- Aggregates 10 Hz telemetry to per-corner metrics: braking point, minimum
-- speed through the corner, and the point where full throttle returns on the
-- way out. Upstream of int_corner_skill_residuals and fct_telemetry_deltas.
--
-- Corner windows come from dim_corners, which is keyed per race, so the join is
-- on race_id and every session is measured against its own corner geometry.
-- race_to_track has left the path with it: its event-slug key dropped 2018_14,
-- the one race missing from that map, out of the chain entirely.
--
-- throttle_point_m is the first full-throttle sample at or after the apex --
-- where the driver gets back on power, which is what the column is documented
-- to mean and what exit_residual_s downstream reads it as. Taking the last such
-- sample in the window instead measures the lift for the *next* corner, and
-- under the abutting blocks the old catalogue used it landed on the window
-- boundary for 41% of cells.
{{ config(materialized='table') }}

WITH telemetry AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        distance_m,
        speed_kph,
        throttle_pct,
        brake_applied
    FROM {{ ref('stg_telemetry') }}
),

corners AS (
    SELECT
        race_id,
        track_id,
        corner_name,
        apex_distance_m,
        start_distance_m,
        end_distance_m
    FROM {{ ref('dim_corners') }}
)

SELECT
    t.driver_id,
    t.lap_number,
    t.race_id,
    t.race_year,
    c.corner_name,
    c.track_id,

    -- Braking point: first sample on the brakes inside the window. NULL where
    -- the corner is taken flat, which is a real answer, not missing data.
    MIN(CASE WHEN t.brake_applied THEN t.distance_m END) AS braking_point_m,

    MIN(t.speed_kph) AS v_min_kph,

    MIN(CASE
        WHEN
            t.throttle_pct = 100
            AND t.distance_m >= c.apex_distance_m
            THEN t.distance_m
    END) AS throttle_point_m
FROM telemetry AS t
INNER JOIN corners AS c
    ON
        t.race_id = c.race_id
        AND t.distance_m BETWEEN c.start_distance_m AND c.end_distance_m
GROUP BY
    t.driver_id,
    t.lap_number,
    t.race_id,
    t.race_year,
    c.corner_name,
    c.track_id
