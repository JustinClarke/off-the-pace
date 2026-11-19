-- int_corner_metrics.sql · intermediate · grain: one row per driver × lap ×
-- circuit turn
-- Aggregates 10 Hz telemetry to per-corner metrics: braking point, minimum
-- speed through the corner, and the point where full throttle returns on the
-- way out. Upstream of int_corner_skill_residuals and fct_telemetry_deltas.
--
-- Corner windows come from dim_corners, which is keyed per race, so the join is
-- on race_id and every session is measured against its own corner geometry.
-- race_to_track has left the path with it: its event-slug key once dropped
-- 2018_14, the one race that was missing from that map (filled by WI-05/F8),
-- out of the chain entirely.
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
        brake_applied,
        -- 3-sample running median of speed (edges keep the raw value): a single
        -- decoding sample cannot define the apex speed.
        CASE
            WHEN LAG(speed_kph) OVER lap_order IS NULL OR LEAD(speed_kph) OVER lap_order IS NULL
                THEN speed_kph
            ELSE GREATEST(
                LEAST(LAG(speed_kph) OVER lap_order, speed_kph),
                LEAST(GREATEST(LAG(speed_kph) OVER lap_order, speed_kph), LEAD(speed_kph) OVER lap_order)
            )
        END AS speed_med3_kph
    FROM {{ ref('stg_telemetry') }}
    WINDOW lap_order AS (PARTITION BY race_id, driver_id, lap_number ORDER BY session_time_s, distance_m)
),

corners AS (
    SELECT
        race_id,
        track_id,
        corner_name,
        apex_distance_m,
        start_distance_m,
        end_distance_m,
        LAG(apex_distance_m) OVER (PARTITION BY race_id ORDER BY apex_distance_m) AS prev_apex_m,
        LEAD(apex_distance_m) OVER (PARTITION BY race_id ORDER BY apex_distance_m) AS next_apex_m
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

    -- v_min_kph: slowest raw sample anywhere in the window. KEPT unchanged (raw).
    -- Windows reach ~200 m before and ~150 m after the apex and overlap the
    -- neighbours, so in ~39 % of race x corner cells the median location of
    -- this minimum is more than 100 m from the apex: it often measures the
    -- NEXT corner.
    MIN(t.speed_kph) AS v_min_kph,

    -- v_apex_kph: slowest 3-sample-median speed within +/- apex_band_m of the
    -- apex, cut at the midpoints to the previous / next apex and at the window
    -- ends. This is the apex speed the mid-corner term should use.
    MIN(CASE
        WHEN
            t.distance_m BETWEEN
            GREATEST(c.apex_distance_m - {{ var('apex_band_m', 88) }}, COALESCE((c.prev_apex_m + c.apex_distance_m) / 2, c.start_distance_m), c.start_distance_m)
            AND LEAST(c.apex_distance_m + {{ var('apex_band_m', 88) }}, COALESCE((c.apex_distance_m + c.next_apex_m) / 2, c.end_distance_m), c.end_distance_m)
            THEN t.speed_med3_kph
    END) AS v_apex_kph,

    MIN(CASE
        WHEN
            -- Full throttle is the 98-99 plateau plus 100, not exactly 100:
            -- the car channel reads 99 at full throttle far more often than
            -- 98, and the pos/interpolation channels are fractional near 100.
            -- Upper bound 104 keeps the sensor spike (104) inside full throttle.
            -- Measured in the scratch copy (2026-11-19 throttle investigation).
            t.throttle_pct BETWEEN 98 AND 104
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
