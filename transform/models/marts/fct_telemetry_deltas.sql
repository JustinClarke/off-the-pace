-- fct_telemetry_deltas.sql · marts · grain: one row per teammate pair × lap ×
-- circuit turn
-- Teammate corner-metric deltas: braking point, minimum corner speed and
-- throttle-application point at each corner, driver_a minus driver_b.
--
-- Pairing (CO-22): teammates only, i.e. the two drivers entered by the same
-- constructor in that race (constructor_id from stg_laps, one per driver per
-- race). Same car is the only comparison a raw corner delta can stand for; a
-- cross-team delta is mostly the car. Before CO-22 every driver was paired
-- with every other driver in the race (31,812 pairs where 1,719 are teammates).
--
-- Missing sides (CO-22): the two drivers' corner metrics are FULL OUTER joined
-- on (corner, lap), so a corner either driver measured has a row. Where one
-- side has no measurement, or the metric itself is NULL on one side (a corner
-- taken flat has no braking point), the delta stays NULL. It was COALESCEd to
-- 0 before, which reads as "identical".
{{ config(materialized='table') }}

WITH metrics AS (
    SELECT * FROM {{ ref('int_corner_metrics') }}
),

entries AS (
    SELECT DISTINCT
        race_id,
        driver_id,
        constructor_id
    FROM {{ ref('stg_laps') }}
),

teammates AS (
    SELECT
        e1.race_id,
        e1.driver_id AS driver_a,
        e2.driver_id AS driver_b
    FROM entries AS e1
    INNER JOIN entries AS e2
        ON
            e1.race_id = e2.race_id
            AND e1.constructor_id = e2.constructor_id
            AND e1.driver_id < e2.driver_id
),

metrics_a AS (
    SELECT
        tm.race_id,
        tm.driver_a,
        tm.driver_b,
        m.corner_name,
        m.track_id,
        m.lap_number,
        m.braking_point_m,
        m.v_min_kph,
        m.throttle_point_m
    FROM teammates AS tm
    INNER JOIN metrics AS m
        ON
            tm.race_id = m.race_id
            AND tm.driver_a = m.driver_id
),

metrics_b AS (
    SELECT
        tm.race_id,
        tm.driver_a,
        tm.driver_b,
        m.corner_name,
        m.track_id,
        m.lap_number,
        m.braking_point_m,
        m.v_min_kph,
        m.throttle_point_m
    FROM teammates AS tm
    INNER JOIN metrics AS m
        ON
            tm.race_id = m.race_id
            AND tm.driver_b = m.driver_id
),

deltas AS (
    SELECT
        COALESCE(a.race_id, b.race_id) AS race_id,
        COALESCE(a.driver_a, b.driver_a) AS driver_a,
        COALESCE(a.driver_b, b.driver_b) AS driver_b,
        COALESCE(a.corner_name, b.corner_name) AS corner_name,
        COALESCE(a.track_id, b.track_id) AS track_id,

        -- NULL when either side is missing; never filled.
        ROUND(a.braking_point_m - b.braking_point_m, 1)
            AS braking_point_delta_m,

        ROUND(a.v_min_kph - b.v_min_kph, 2)
            AS v_min_delta_kph,

        ROUND(a.throttle_point_m - b.throttle_point_m, 1)
            AS throttle_point_delta_m,

        COALESCE(a.lap_number, b.lap_number) AS lap_number
    FROM metrics_a AS a
    FULL OUTER JOIN metrics_b AS b
        ON
            a.race_id = b.race_id
            AND a.driver_a = b.driver_a
            AND a.driver_b = b.driver_b
            AND a.corner_name = b.corner_name
            AND a.lap_number = b.lap_number
)

SELECT * FROM deltas
