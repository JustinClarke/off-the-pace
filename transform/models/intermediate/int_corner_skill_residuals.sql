-- Second Model Sequence #4b: Corner-level skill decomposition.
-- Grain: (lap_id, corner_name) one row per corner per lap.
-- PK: corner_id = lap_id || '_C_' || corner_name
--
-- Decomposes corner performance into braking_loss_s, mid_corner_residual_s,
-- and exit_residual_s relative to 5-lap-bucket field medians.
-- All residuals are NULL when field_corner_sample_n < 5 (insufficient comparison set).
--
-- Speed proxy: sector 2 speed trap (speed_i2_kph) used as dt_per_dm denominator.
-- Note: int_corner_metrics has no lap_id joined via (race_year, race_id, driver_id, lap_number)
-- composite key through int_stint_geometry.

{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH corner_metrics AS (
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
    FROM {{ ref('int_corner_metrics') }}
),

lap_keys AS (
    SELECT
        sg.lap_id,
        sg.stint_id,
        sg.race_year,
        sg.race_id,
        sg.driver_id,
        sg.lap_number,
        sl.constructor_id
    FROM {{ ref('int_stint_geometry') }} sg
    JOIN {{ ref('stg_laps') }} sl USING (lap_id)
),

sector2_speed AS (
    SELECT
        lap_id,
        speed_trap_kph AS s2_speed_trap_kph
    FROM {{ ref('stg_sector_times') }}
    WHERE sector = 2
      AND speed_trap_kph IS NOT NULL
      AND speed_trap_kph > 0
),

corners_with_keys AS (
    SELECT
        cm.driver_id,
        cm.lap_number,
        cm.race_id,
        cm.race_year,
        cm.corner_name,
        cm.track_id,
        cm.braking_point_m,
        cm.v_min_kph,
        cm.throttle_point_m,
        lk.lap_id,
        lk.stint_id,
        lk.constructor_id,
        s2.s2_speed_trap_kph,
        1.0 / NULLIF(s2.s2_speed_trap_kph * (1000.0 / 3600.0), 0) AS dt_per_dm,
        FLOOR(CAST(cm.lap_number AS DOUBLE) / 5.0) * 5.0           AS lap_window
    FROM corner_metrics cm
    JOIN lap_keys lk
        ON  cm.race_year  = lk.race_year
        AND cm.race_id    = lk.race_id
        AND cm.driver_id  = lk.driver_id
        AND cm.lap_number = lk.lap_number
    LEFT JOIN sector2_speed s2 USING (lap_id)
),

field_medians AS (
    SELECT
        race_year,
        race_id,
        corner_name,
        lap_window,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY braking_point_m)
            FILTER (WHERE braking_point_m IS NOT NULL)  AS field_corner_braking_point_m,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v_min_kph)
            FILTER (WHERE v_min_kph IS NOT NULL)        AS field_corner_v_min_kph,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY throttle_point_m)
            FILTER (WHERE throttle_point_m IS NOT NULL) AS field_corner_throttle_point_m,
        COUNT(*) FILTER (WHERE braking_point_m IS NOT NULL) AS field_corner_sample_n
    FROM corners_with_keys
    GROUP BY race_year, race_id, corner_name, lap_window
),

with_residuals AS (
    SELECT
        ck.lap_id,
        ck.stint_id,
        ck.driver_id,
        ck.race_id,
        ck.race_year,
        ck.constructor_id,
        ck.corner_name,
        ck.track_id,
        ck.lap_number,
        fm.field_corner_sample_n,
        CASE
            WHEN fm.field_corner_sample_n < 5 OR fm.field_corner_braking_point_m IS NULL
                THEN NULL
            ELSE (ck.braking_point_m-fm.field_corner_braking_point_m) * ck.dt_per_dm
        END AS braking_loss_s,
        CASE
            WHEN fm.field_corner_sample_n < 5 OR fm.field_corner_v_min_kph IS NULL
                OR fm.field_corner_v_min_kph = 0
                THEN NULL
            ELSE (fm.field_corner_v_min_kph-ck.v_min_kph)
                 * (1.0 / NULLIF(fm.field_corner_v_min_kph * (1000.0 / 3600.0), 0))
        END AS mid_corner_residual_s,
        CASE
            WHEN fm.field_corner_sample_n < 5 OR fm.field_corner_throttle_point_m IS NULL
                THEN NULL
            ELSE (ck.throttle_point_m-fm.field_corner_throttle_point_m) * ck.dt_per_dm
        END AS exit_residual_s,
        (fm.field_corner_sample_n IS NULL OR fm.field_corner_sample_n < 5) AS corner_unmapped_flag
    FROM corners_with_keys ck
    LEFT JOIN field_medians fm
        ON  ck.race_year   = fm.race_year
        AND ck.race_id     = fm.race_id
        AND ck.corner_name = fm.corner_name
        AND ck.lap_window  = fm.lap_window
)

SELECT
    CONCAT(lap_id, '_C_', corner_name)  AS corner_id,
    lap_id,
    stint_id,
    driver_id,
    race_id,
    race_year,
    constructor_id,
    corner_name,
    track_id,
    lap_number,
    braking_loss_s,
    mid_corner_residual_s,
    exit_residual_s,
    braking_loss_s + mid_corner_residual_s + exit_residual_s AS corner_residual_total_s,
    CASE
        WHEN braking_loss_s IS NOT NULL
             AND mid_corner_residual_s IS NOT NULL
             AND exit_residual_s IS NOT NULL
            THEN 0.0
        ELSE NULL
    END AS corner_residual_unexplained_s,
    field_corner_sample_n,
    corner_unmapped_flag
FROM with_residuals
ORDER BY race_year, race_id, driver_id, lap_number, corner_name
