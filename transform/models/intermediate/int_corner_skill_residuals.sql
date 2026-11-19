-- Corner-level skill decomposition.
-- Grain: (lap_id, corner_name) one row per corner per lap.
-- PK: corner_id = lap_id || '_C_' || corner_name
--
-- Decomposes corner performance into braking_loss_s, mid_corner_residual_s,
-- and exit_residual_s relative to backward-only (trailing-5) field medians.
-- All residuals are NULL when field_corner_sample_n < 5 (insufficient
-- comparison set).
--
-- SIGN CONVENTION (one for all three phases, 00d): POSITIVE = SECONDS LOST vs
-- the field median, NEGATIVE = seconds gained. The direction of the underlying
-- measure decides the subtraction, not habit:
--   braking_point_m   higher is FASTER (braking later)  -> (field - own)
--   v_min_kph         higher is FASTER (carrying speed) -> (field - own)
--   throttle_point_m  higher is SLOWER (on power later) -> (own - field)
-- corner_residual_total_s is their straight sum and is therefore a real
-- "seconds lost at this corner".
-- Before 00d, braking_loss_s alone was (own - field) -- positive meant braking
-- LATER, i.e. faster -- and mart_corner_skill_driver summed all three z-scores
-- and ordered ASC, so one of three terms entered the shipped leaderboard
-- inverted. transform/tests/assert_corner_skill_sign_convention.sql pins the
-- direction from the raw geometry so it cannot regress silently.
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
        -- apex speed (3-sample median, band around the apex); a window that
        -- touched speed 0 keeps 0 so the zero guard below still NULLs it
        CASE WHEN v_min_kph = 0 THEN 0 ELSE v_apex_kph END AS v_min_kph,
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
        -- Reported UNFLOORED, which is the macro's documented contract: "the
        -- count is what the floor is applied to, so it is reported unfloored".
        -- 02g wrapped this in a CASE that returned NULL below 5, which
        -- destroyed the only thing the companion column is for -- it made "no
        -- prior laps at all" and "four prior laps, one short of the gate"
        -- indistinguishable, and it contradicted this column's own `not_null`
        -- test in schema.yml (416,639 failing rows). The residuals do not need
        -- it to NULL out anyway: trailing_median already carries
        -- min_observations=5 and returns NULL on its own, and with_residuals
        -- gates on `< 5` below.
        {{ trailing_observation_count(
            'braking_point_m',
            ['race_year', 'race_id', 'corner_name'],
            ['lap_number'],
            lookback=5,
            frame='range'
        ) }} AS field_corner_sample_n
    FROM corners_with_keys
    -- GRAIN GUARD (02c, repairing 02g). corners_with_keys is at DRIVER grain,
    -- and the block bucket this CTE replaced collapsed it with a GROUP BY. The
    -- window functions above do not: they return one row per input row, so
    -- every (race, corner, lap) emits one copy of its medians per driver on
    -- track. The LEFT JOIN below then fans the model out by the field size --
    -- measured 2,206,939 -> 38,444,069 rows (17.4x), breaking the corner_id PK
    -- that schema.yml declares unique.
    --
    -- Deduplicating here is value-preserving, not a choice of representative:
    -- the RANGE frame orders by lap_number, so every driver row at the same
    -- lap_number is a peer and sees an IDENTICAL frame. Verified on the
    -- fanned-out build -- zero corner_ids carried more than one distinct value
    -- of any median or of field_corner_sample_n. ROWS would NOT have this
    -- property, which is the other reason `frame='range'` is load-bearing here.
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
        -- SIGN: (field - own), so POSITIVE = braking EARLIER than the field
        -- median = time LOST. 00d: this was built as (own - field), which made
        -- it the only one of the three phases where positive meant faster,
        -- while mart_corner_skill_driver summed all three z-scores and ordered
        -- ASC. Fixed at the source rather than negated in the mart so the
        -- column means what its name says, corner_residual_total_s becomes a
        -- real "seconds lost" total, and every downstream consumer inherits one
        -- convention. Matches the house convention already in the feature
        -- contract: int_lap_telemetry_aggregates' braking_point_drift_m is
        -- (baseline - own) for the same reason.
        -- Pinned by transform/tests/assert_corner_skill_sign_convention.sql.
        CASE
            WHEN
                fm.field_corner_sample_n < 5
                OR fm.field_corner_braking_point_m IS NULL
                THEN NULL
            ELSE
                (fm.field_corner_braking_point_m - ck.braking_point_m)
                * ck.dt_per_dm
        END AS braking_loss_s,
        -- MID-CORNER TIME (seconds). L_m * (1/v_own - 1/v_field), speeds in
        -- m/s, so positive = slower than the field = time lost. L_m is the
        -- MEASURED per-race corner length (brake onset to throttle >= 90 %,
        -- median over clean laps) from int_corner_length_measured. NULL there
        -- (fewer than 5 laps, no onset, no throttle recovery) gives a NULL
        -- term; there is no constant fallback. Before this fix the term was
        -- (km/h difference) * (s/m), which has no length and is not seconds.
        CASE
            WHEN
                fm.field_corner_sample_n < 5
                OR fm.field_corner_v_min_kph IS NULL
                OR fm.field_corner_v_min_kph = 0
                OR ck.v_min_kph IS NULL
                OR ck.v_min_kph = 0
                OR cl.corner_length_m IS NULL
                -- demonstrably invalid observation (stopped, near-stopped,
                -- distance-axis misalignment): kept raw upstream, excluded here
                -- explicit guard: the lap-corner measurement row must exist
                -- (no row = no validated observation = no term), and must not
                -- carry an exclusion reason
                OR lq.race_id IS NULL
                OR lq.exclusion_reason IS NOT NULL
                THEN NULL
            ELSE
                cl.corner_length_m
                * (
                    1.0 / (ck.v_min_kph / 3.6)
                    - 1.0 / (fm.field_corner_v_min_kph / 3.6)
                )
        END AS mid_corner_residual_raw_s,
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
    LEFT JOIN {{ ref('int_corner_length_measured') }} AS cl
        ON
            ck.race_id = cl.race_id
            AND ck.corner_name = cl.corner_name
    LEFT JOIN {{ ref('int_corner_lap_measured') }} AS lq
        ON
            ck.race_id = lq.race_id
            AND ck.driver_id = lq.driver_id
            AND ck.lap_number = lq.lap_number
            AND ck.corner_name = lq.corner_name
),

-- MID-TERM TAIL FENCE (F2). Per race x corner cell: median and scaled MAD of
-- the raw mid term over the cell's non-NULL laps; fence = 3 * 1.4826 * MAD
-- (Tukey-style multiplier 3). Both numbers come from the data; no fixed
-- seconds threshold. Outliers are NULLed in mid_corner_residual_s but kept in
-- mid_corner_residual_raw_s and flagged. MAD of 0 or NULL: raw value kept,
-- flag 'mad_zero'.
cell_med AS (
    SELECT
        race_id,
        corner_name,
        QUANTILE_CONT(mid_corner_residual_raw_s, 0.5) AS cell_median_s
    FROM with_residuals
    WHERE mid_corner_residual_raw_s IS NOT NULL
    GROUP BY race_id, corner_name
),

cell_mad AS (
    SELECT
        w.race_id,
        w.corner_name,
        m.cell_median_s,
        QUANTILE_CONT(ABS(w.mid_corner_residual_raw_s - m.cell_median_s), 0.5)
            AS cell_mad_s
    FROM with_residuals AS w
    INNER JOIN cell_med AS m
        ON w.race_id = m.race_id AND w.corner_name = m.corner_name
    WHERE w.mid_corner_residual_raw_s IS NOT NULL
    GROUP BY w.race_id, w.corner_name, m.cell_median_s
),

fenced AS (
    SELECT
        w.*,
        CASE
            WHEN w.mid_corner_residual_raw_s IS NULL THEN NULL
            WHEN cm.cell_mad_s IS NULL OR cm.cell_mad_s = 0 THEN 'mad_zero'
            WHEN ABS(w.mid_corner_residual_raw_s - cm.cell_median_s)
                > 3 * 1.4826 * cm.cell_mad_s THEN 'outlier'
            ELSE 'ok'
        END AS mid_corner_outlier_flag
    FROM with_residuals AS w
    LEFT JOIN cell_mad AS cm
        ON w.race_id = cm.race_id AND w.corner_name = cm.corner_name
),

with_mid AS (
    SELECT
        *,
        CASE
            WHEN mid_corner_outlier_flag = 'outlier' THEN NULL
            ELSE mid_corner_residual_raw_s
        END AS mid_corner_residual_s
    FROM fenced
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
    mid_corner_residual_raw_s,
    mid_corner_outlier_flag,
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
FROM with_mid
ORDER BY race_year, race_id, driver_id, lap_number, corner_name
