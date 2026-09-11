-- Corner-level skill decomposition.
-- Grain: (lap_id, corner_name) one row per corner per lap.
-- PK: corner_id = lap_id || '_C_' || corner_name
--
-- Decomposes corner performance into braking_loss_s, mid_corner_residual_s,
-- and exit_residual_s relative to backward-only (trailing-5) field medians.
-- All residuals are NULL when field_corner_sample_n < 5 (insufficient
-- comparison set).
--
-- Field medians use RANGE frame to include all drivers at the same lap number,
-- looking back exactly 5 laps (excluding current lap, t-5...t-1).
-- Lap 2 returns NULL for all fields (no prior lap), consistent with trailing
-- window design: deterministic loss (21.4pp coverage on laps ≤ 6),
-- recoverable and non-leaking (documented in schema.yml).
--
-- Speed proxy: sector 2 speed trap (speed_i2_kph) used as dt_per_dm
-- denominator.
-- Note: int_corner_metrics has no lap_id joined via (race_year, race_id,
-- driver_id, lap_number) composite key through int_stint_geometry.

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
    FROM {{ ref('int_stint_geometry') }} AS sg
    INNER JOIN {{ ref('stg_laps') }} AS sl ON sg.lap_id = sl.lap_id
    -- int_stint_geometry now carries SC/pit/invalid laps too; exclude them
    -- here or their braking/speed metrics pollute the trailing windowed field
    -- medians below.
    WHERE sg.is_valid_lap = TRUE
),

sector2_speed AS (
    SELECT
        lap_id,
        speed_trap_kph AS s2_speed_trap_kph
    FROM {{ ref('stg_sector_times') }}
    WHERE
        sector = 2
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
        1.0 / NULLIF(s2.s2_speed_trap_kph * (1000.0 / 3600.0), 0) AS dt_per_dm
    FROM corner_metrics AS cm
    INNER JOIN lap_keys AS lk
        ON
            cm.race_year = lk.race_year
            AND cm.race_id = lk.race_id
            AND cm.driver_id = lk.driver_id
            AND cm.lap_number = lk.lap_number
    LEFT JOIN sector2_speed AS s2 ON lk.lap_id = s2.lap_id
),

field_medians AS (
    SELECT
        race_year,
        race_id,
        corner_name,
        lap_number,
        {{ trailing_median(
            'braking_point_m',
            ['race_year', 'race_id', 'corner_name'],
            ['lap_number'],
            lookback=5,
            frame='range',
            min_observations=5
        ) }} AS field_corner_braking_point_m,
        {{ trailing_median(
            'v_min_kph',
            ['race_year', 'race_id', 'corner_name'],
            ['lap_number'],
            lookback=5,
            frame='range',
            min_observations=5
        ) }} AS field_corner_v_min_kph,
        {{ trailing_median(
            'throttle_point_m',
            ['race_year', 'race_id', 'corner_name'],
            ['lap_number'],
            lookback=5,
            frame='range',
            min_observations=5
        ) }} AS field_corner_throttle_point_m,
        -- Reported UNFLOORED, which is the macro's documented contract: "the count
        -- is what the floor is applied to, so it is reported unfloored". 02g wrapped
        -- this in a CASE that returned NULL below 5, which destroyed the only thing
        -- the companion column is for -- it made "no prior laps at all" and "four
        -- prior laps, one short of the gate" indistinguishable, and it contradicted
        -- this column's own `not_null` test in schema.yml (416,639 failing rows).
        -- The residuals do not need it to NULL out anyway: trailing_median already
        -- carries min_observations=5 and returns NULL on its own, and with_residuals
        -- gates on `< 5` below.
        {{ trailing_observation_count(
            'braking_point_m',
            ['race_year', 'race_id', 'corner_name'],
            ['lap_number'],
            lookback=5,
            frame='range'
        ) }} AS field_corner_sample_n
    FROM corners_with_keys
    -- GRAIN GUARD (02c, repairing 02g). corners_with_keys is at DRIVER grain, and
    -- the block bucket this CTE replaced collapsed it with a GROUP BY. The window
    -- functions above do not: they return one row per input row, so every
    -- (race, corner, lap) emits one copy of its medians per driver on track. The
    -- LEFT JOIN below then fans the model out by the field size -- measured
    -- 2,206,939 -> 38,444,069 rows (17.4x), breaking the corner_id PK that
    -- schema.yml declares unique.
    --
    -- Deduplicating here is value-preserving, not a choice of representative: the
    -- RANGE frame orders by lap_number, so every driver row at the same lap_number
    -- is a peer and sees an IDENTICAL frame. Verified on the fanned-out build --
    -- zero corner_ids carried more than one distinct value of any median or of
    -- field_corner_sample_n. ROWS would NOT have this property, which is the other
    -- reason `frame='range'` is load-bearing here.
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY race_year, race_id, corner_name, lap_number
        ORDER BY driver_id
    ) = 1
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
            WHEN
                fm.field_corner_sample_n < 5
                OR fm.field_corner_braking_point_m IS NULL
                THEN NULL
            ELSE
                (ck.braking_point_m - fm.field_corner_braking_point_m)
                * ck.dt_per_dm
        END AS braking_loss_s,
        CASE
            WHEN
                fm.field_corner_sample_n < 5
                OR fm.field_corner_v_min_kph IS NULL
                OR fm.field_corner_v_min_kph = 0
                THEN NULL
            ELSE
                (fm.field_corner_v_min_kph - ck.v_min_kph)
                * (
                    1.0
                    / NULLIF(fm.field_corner_v_min_kph * (1000.0 / 3600.0), 0)
                )
        END AS mid_corner_residual_s,
        CASE
            WHEN
                fm.field_corner_sample_n < 5
                OR fm.field_corner_throttle_point_m IS NULL
                THEN NULL
            ELSE
                (ck.throttle_point_m - fm.field_corner_throttle_point_m)
                * ck.dt_per_dm
        END AS exit_residual_s,
        (fm.field_corner_sample_n IS NULL OR fm.field_corner_sample_n < 5)
            AS corner_unmapped_flag
    FROM corners_with_keys AS ck
    LEFT JOIN field_medians AS fm
        ON
            ck.race_year = fm.race_year
            AND ck.race_id = fm.race_id
            AND ck.corner_name = fm.corner_name
            AND ck.lap_number = fm.lap_number
)

SELECT
    CONCAT(lap_id, '_C_', corner_name) AS corner_id,
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
    braking_loss_s
    + mid_corner_residual_s
    + exit_residual_s AS corner_residual_total_s,
    CASE
        WHEN
            braking_loss_s IS NOT NULL
            AND mid_corner_residual_s IS NOT NULL
            AND exit_residual_s IS NOT NULL
            THEN 0.0
    END AS corner_residual_unexplained_s,
    field_corner_sample_n,
    corner_unmapped_flag
FROM with_residuals
ORDER BY race_year, race_id, driver_id, lap_number, corner_name
