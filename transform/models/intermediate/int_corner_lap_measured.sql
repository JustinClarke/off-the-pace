-- int_corner_lap_measured.sql · intermediate · grain: one row per driver x lap x corner
-- PK: (race_id, driver_id, lap_number, corner_name).
--
-- LAP-LEVEL RAW MEASUREMENT plus validation flags for the measured corner
-- length. Every clean-lap observation that int_corner_length_measured used to
-- take is kept here (nothing is dropped); `is_excluded` says whether it enters
-- the VALIDATED corner length, `exclusion_reason` says why not. The other flags
-- are anomaly flags only: they never exclude.
--
-- MEASUREMENT (unchanged from the previous int_corner_length_measured):
--   onset_m   last brake false->true switch at or before the apex, within
--             600 m (0.3 s flicker merge); throttle_m first sample at or after
--             the apex with throttle >= 90 %, within 600 m;
--   length_m  = throttle_m - onset_m, kept only if 0 < length_m <= 1200.
--
-- EXCLUSIONS (only demonstrably invalid observations):
--   stopped       any sample in the corner window (dim_corners start..end) with
--                 speed = 0. The car was stationary.
--   near_stopped  window dwell time AND speed collapse are both extreme: the
--                 cell-robust z of ln(window time) >= the upper Tukey outer
--                 fence AND the z of ln(window minimum speed) <= the lower
--                 fence (fences = Q1 -/+ 3 IQR of the pooled z, i.e. derived
--                 from the data, not fixed numbers).
--   distance misalignment, and ONLY on laps whose max distance deviates from
--   the race median lap distance by a robust z beyond the Tukey outer fence:
--       - the whole lap is excluded when the misalignment is GLOBAL: at least
--         half of its corners are shifted coherently (all three landmarks --
--         brake onset, throttle-on, speed minimum -- displaced beyond the
--         fence on the same side, fence from clean laps) AND the shifts agree
--         (MAD of the offsets <= half the offset fence);
--       - otherwise only the affected corners are excluded: a coherently
--         shifted corner, or one whose length is outside the length fence.
--       The other corners of such a lap look like clean laps (see evidence).
--
-- ANOMALY FLAGS (never exclude; Tukey multiplier 3, data-derived fences):
--   flag_low_speed_outlier, flag_high_speed_outlier (z of ln window min speed),
--   flag_driver_systematic (driver's median speed z in this cell beyond the
--   fence of driver medians), flag_length_outlier.
--
-- LINKED-CORNER QUALITY FLAG (definition of linked corners unchanged; this
-- only reports where the measured window crosses into a neighbour):
--   throttle_past_next_apex  throttle-back-on lies beyond the NEXT apex;
--   brake_before_prev_apex   brake onset lies before the PREVIOUS apex.
--   linked_corner_flag is the OR of the two; reason column names which.
{{ config(materialized='table', tags=['intermediate', 'feature_engineering']) }}

WITH clean_laps AS (
    SELECT race_id, driver_id, lap_number
    FROM {{ ref('stg_laps') }}
    WHERE
        is_valid_lap
        AND NOT is_safety_car_lap
        AND NOT is_vsc_lap
        AND NOT is_red_flag_lap
),

corners AS (
    SELECT
        race_id,
        race_year,
        track_id,
        corner_name,
        apex_distance_m,
        start_distance_m,
        end_distance_m,
        LAG(apex_distance_m) OVER (PARTITION BY race_id ORDER BY apex_distance_m) AS prev_apex_m,
        LEAD(apex_distance_m) OVER (PARTITION BY race_id ORDER BY apex_distance_m) AS next_apex_m
    FROM {{ ref('dim_corners') }}
    WHERE apex_distance_m IS NOT NULL
),

telemetry AS (
    SELECT
        t.race_id,
        t.driver_id,
        t.lap_number,
        t.distance_m,
        t.session_time_s,
        t.speed_kph,
        t.throttle_pct,
        t.brake_applied,
        -- 3-sample running median of speed (edges: raw). Removes one-sample
        -- collapses from the location of the speed minimum.
        CASE
            WHEN LAG(t.speed_kph) OVER lap_order IS NULL OR LEAD(t.speed_kph) OVER lap_order IS NULL
                THEN t.speed_kph
            ELSE GREATEST(
                LEAST(LAG(t.speed_kph) OVER lap_order, t.speed_kph),
                LEAST(GREATEST(LAG(t.speed_kph) OVER lap_order, t.speed_kph), LEAD(t.speed_kph) OVER lap_order)
            )
        END AS speed_med3_kph
    FROM {{ ref('stg_telemetry') }} AS t
    INNER JOIN clean_laps AS k
        ON t.race_id = k.race_id AND t.driver_id = k.driver_id AND t.lap_number = k.lap_number
    WINDOW lap_order AS (PARTITION BY t.race_id, t.driver_id, t.lap_number ORDER BY t.session_time_s, t.distance_m)
),

brake_switches AS (
    SELECT
        race_id, driver_id, lap_number, distance_m, brake_applied, session_time_s,
        LAG(brake_applied) OVER lap_order AS prev_brake,
        MAX(CASE WHEN brake_applied THEN session_time_s END) OVER (
            PARTITION BY race_id, driver_id, lap_number
            ORDER BY distance_m, session_time_s
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS last_brake_on_s
    FROM telemetry
    WHERE brake_applied IS NOT NULL
    WINDOW lap_order AS (PARTITION BY race_id, driver_id, lap_number ORDER BY distance_m, session_time_s)
),

brake_onsets AS (
    SELECT race_id, driver_id, lap_number, distance_m
    FROM brake_switches
    WHERE brake_applied
        AND COALESCE(prev_brake, FALSE) = FALSE
        AND NOT COALESCE(session_time_s - last_brake_on_s < 0.3, FALSE)
),

onset_per_lap AS (
    SELECT c.race_id, c.corner_name, o.driver_id, o.lap_number, MAX(o.distance_m) AS onset_m
    FROM corners AS c
    INNER JOIN brake_onsets AS o
        ON c.race_id = o.race_id AND o.distance_m BETWEEN c.apex_distance_m - 600 AND c.apex_distance_m
    GROUP BY c.race_id, c.corner_name, o.driver_id, o.lap_number
),

throttle_per_lap AS (
    SELECT c.race_id, c.corner_name, t.driver_id, t.lap_number, MIN(t.distance_m) AS throttle_m
    FROM corners AS c
    INNER JOIN telemetry AS t
        ON c.race_id = t.race_id
        AND t.distance_m BETWEEN c.apex_distance_m AND c.apex_distance_m + 600
        AND t.throttle_pct >= 90
    GROUP BY c.race_id, c.corner_name, t.driver_id, t.lap_number
),

lap_points AS (
    SELECT
        o.race_id, o.corner_name, o.driver_id, o.lap_number,
        o.onset_m, t.throttle_m, t.throttle_m - o.onset_m AS length_m
    FROM onset_per_lap AS o
    INNER JOIN throttle_per_lap AS t
        ON o.race_id = t.race_id AND o.corner_name = t.corner_name
        AND o.driver_id = t.driver_id AND o.lap_number = t.lap_number
    WHERE t.throttle_m - o.onset_m > 0 AND t.throttle_m - o.onset_m <= 1200
),

window_stats AS (
    SELECT
        p.race_id, p.corner_name, p.driver_id, p.lap_number,
        COUNT(*) AS n_samples,
        MAX(t.session_time_s) - MIN(t.session_time_s) AS window_time_s,
        COUNT(*) FILTER (WHERE t.speed_kph = 0) AS n_zero_speed,
        MIN(t.speed_kph) AS window_min_speed_kph,
        ARG_MIN(t.distance_m, t.speed_med3_kph) AS speed_min_loc_m
    FROM lap_points AS p
    INNER JOIN corners AS c ON p.race_id = c.race_id AND p.corner_name = c.corner_name
    INNER JOIN telemetry AS t
        ON p.race_id = t.race_id AND p.driver_id = t.driver_id AND p.lap_number = t.lap_number
        AND t.distance_m BETWEEN c.start_distance_m AND c.end_distance_m
    GROUP BY p.race_id, p.corner_name, p.driver_id, p.lap_number
),

lap_distance AS (
    SELECT race_id, driver_id, lap_number, MAX(distance_m) AS lap_distance_m
    FROM telemetry
    GROUP BY race_id, driver_id, lap_number
),

lap_distance_dev AS (
    SELECT
        race_id, driver_id, lap_number,
        lap_distance_m - MEDIAN(lap_distance_m) OVER (PARTITION BY race_id) AS dist_dev_m
    FROM lap_distance
),

lap_distance_z AS (
    SELECT
        race_id, driver_id, lap_number, dist_dev_m,
        dist_dev_m / NULLIF(MEDIAN(ABS(dist_dev_m)) OVER (PARTITION BY race_id) * 1.4826, 0) AS dist_dev_z
    FROM lap_distance_dev
),

lap_distance_fence AS (
    SELECT
        QUANTILE_CONT(dist_dev_z, 0.75) + 3 * (QUANTILE_CONT(dist_dev_z, 0.75) - QUANTILE_CONT(dist_dev_z, 0.25)) AS dist_z_hi
    FROM lap_distance_z
),

base AS (
    SELECT
        c.race_id, c.race_year, c.track_id, c.corner_name, c.apex_distance_m,
        c.prev_apex_m, c.next_apex_m,
        p.driver_id, p.lap_number, p.onset_m, p.throttle_m, p.length_m,
        w.n_samples, w.window_time_s, w.n_zero_speed, w.window_min_speed_kph, w.speed_min_loc_m,
        LN(GREATEST(w.window_min_speed_kph, 0.5)) AS ln_v,
        LN(NULLIF(w.window_time_s, 0)) AS ln_t,
        z.dist_dev_m, z.dist_dev_z
    FROM lap_points AS p
    INNER JOIN corners AS c ON p.race_id = c.race_id AND p.corner_name = c.corner_name
    INNER JOIN window_stats AS w
        ON p.race_id = w.race_id AND p.corner_name = w.corner_name
        AND p.driver_id = w.driver_id AND p.lap_number = w.lap_number
    LEFT JOIN lap_distance_z AS z
        ON p.race_id = z.race_id AND p.driver_id = z.driver_id AND p.lap_number = z.lap_number
),

cell_med AS (
    SELECT
        *,
        MEDIAN(ln_v) OVER cell AS m_ln_v,
        MEDIAN(ln_t) OVER cell AS m_ln_t,
        MEDIAN(length_m) OVER cell AS m_len
    FROM base
    WINDOW cell AS (PARTITION BY race_id, corner_name)
),

cell_mad AS (
    SELECT
        *,
        MEDIAN(ABS(ln_v - m_ln_v)) OVER cell * 1.4826 AS mad_ln_v,
        MEDIAN(ABS(ln_t - m_ln_t)) OVER cell * 1.4826 AS mad_ln_t,
        MEDIAN(ABS(length_m - m_len)) OVER cell * 1.4826 AS mad_len
    FROM cell_med
    WINDOW cell AS (PARTITION BY race_id, corner_name)
),

zed AS (
    SELECT
        *,
        (ln_v - m_ln_v) / NULLIF(mad_ln_v, 0) AS z_v,
        (ln_t - m_ln_t) / NULLIF(mad_ln_t, 0) AS z_t,
        (length_m - m_len) / NULLIF(mad_len, 0) AS z_len
    FROM cell_mad
),

fences AS (
    SELECT
        QUANTILE_CONT(z_v, 0.25) - 3 * (QUANTILE_CONT(z_v, 0.75) - QUANTILE_CONT(z_v, 0.25)) AS v_lo,
        QUANTILE_CONT(z_v, 0.75) + 3 * (QUANTILE_CONT(z_v, 0.75) - QUANTILE_CONT(z_v, 0.25)) AS v_hi,
        QUANTILE_CONT(z_t, 0.75) + 3 * (QUANTILE_CONT(z_t, 0.75) - QUANTILE_CONT(z_t, 0.25)) AS t_hi,
        QUANTILE_CONT(z_len, 0.25) - 3 * (QUANTILE_CONT(z_len, 0.75) - QUANTILE_CONT(z_len, 0.25)) AS len_lo,
        QUANTILE_CONT(z_len, 0.75) + 3 * (QUANTILE_CONT(z_len, 0.75) - QUANTILE_CONT(z_len, 0.25)) AS len_hi
    FROM zed
),

flagged AS (
    SELECT
        z.*,
        (z.n_zero_speed > 0) AS is_stopped,
        (z.z_t >= f.t_hi AND z.z_v <= f.v_lo) AS is_near_stopped,
        COALESCE(z.z_v <= f.v_lo, FALSE) AS flag_low_speed_outlier,
        COALESCE(z.z_v >= f.v_hi, FALSE) AS flag_high_speed_outlier,
        COALESCE(z.z_len <= f.len_lo OR z.z_len >= f.len_hi, FALSE) AS flag_length_outlier,
        COALESCE(ABS(z.dist_dev_z) >= d.dist_z_hi, FALSE) AS is_misaligned_lap
    FROM zed AS z
    CROSS JOIN fences AS f
    CROSS JOIN lap_distance_fence AS d
),

-- landmark offsets against cell medians of non-misaligned laps
landmark AS (
    SELECT
        *,
        onset_m - MEDIAN(CASE WHEN NOT is_misaligned_lap THEN onset_m END) OVER cell AS off_onset_m,
        throttle_m - MEDIAN(CASE WHEN NOT is_misaligned_lap THEN throttle_m END) OVER cell AS off_throttle_m,
        speed_min_loc_m - MEDIAN(CASE WHEN NOT is_misaligned_lap THEN speed_min_loc_m END) OVER cell AS off_speed_m
    FROM flagged
    WINDOW cell AS (PARTITION BY race_id, corner_name)
),

landmark2 AS (
    SELECT
        *,
        LEAST(off_onset_m, off_throttle_m, off_speed_m) AS off_lo,
        GREATEST(off_onset_m, off_throttle_m, off_speed_m) AS off_hi,
        off_onset_m + off_throttle_m + off_speed_m
            - LEAST(off_onset_m, off_throttle_m, off_speed_m)
            - GREATEST(off_onset_m, off_throttle_m, off_speed_m) AS off_mid_m
    FROM landmark
),

offset_fence AS (
    SELECT
        QUANTILE_CONT(off_mid_m, 0.25) - 3 * (QUANTILE_CONT(off_mid_m, 0.75) - QUANTILE_CONT(off_mid_m, 0.25)) AS off_lo_fence,
        QUANTILE_CONT(off_mid_m, 0.75) + 3 * (QUANTILE_CONT(off_mid_m, 0.75) - QUANTILE_CONT(off_mid_m, 0.25)) AS off_hi_fence
    FROM landmark2
    WHERE NOT is_misaligned_lap
),

coherent AS (
    SELECT
        l.*,
        (l.off_lo > o.off_hi_fence OR l.off_hi < o.off_lo_fence) AS is_coherent_shift,
        o.off_hi_fence
    FROM landmark2 AS l
    CROSS JOIN offset_fence AS o
),

lap_level AS (
    SELECT
        race_id, driver_id, lap_number,
        COUNT(*) AS n_corners,
        COUNT(*) FILTER (WHERE is_coherent_shift) AS n_coherent,
        MAD(off_mid_m) FILTER (WHERE is_coherent_shift) AS mad_coherent_offset_m,
        ANY_VALUE(off_hi_fence) AS off_hi_fence
    FROM coherent
    WHERE is_misaligned_lap
    GROUP BY race_id, driver_id, lap_number
),

-- driver systematic: driver's median speed z in the cell beyond the fence of driver medians
driver_cell AS (
    SELECT race_id, corner_name, driver_id, MEDIAN(z_v) AS drv_med_z
    FROM zed
    WHERE z_v IS NOT NULL
    GROUP BY race_id, corner_name, driver_id
    HAVING COUNT(*) >= 5
),

driver_fence AS (
    SELECT QUANTILE_CONT(drv_med_z, 0.25) - 3 * (QUANTILE_CONT(drv_med_z, 0.75) - QUANTILE_CONT(drv_med_z, 0.25)) AS drv_lo
    FROM driver_cell
)

SELECT
    c.race_id,
    c.race_year,
    c.track_id,
    c.corner_name,
    c.driver_id,
    c.lap_number,
    c.apex_distance_m,
    c.onset_m,
    c.throttle_m,
    c.length_m,
    c.window_min_speed_kph,
    c.n_zero_speed,
    c.window_time_s,
    c.z_v AS speed_z,
    c.z_t AS window_time_z,
    c.dist_dev_m,
    c.dist_dev_z,
    c.is_stopped,
    c.is_near_stopped,
    c.is_misaligned_lap,
    c.is_coherent_shift,
    COALESCE(
        c.is_misaligned_lap AND ll.n_coherent >= 0.5 * ll.n_corners
        AND ll.mad_coherent_offset_m <= ll.off_hi_fence / 2, FALSE
    ) AS is_global_misalignment,
    c.flag_low_speed_outlier,
    c.flag_high_speed_outlier,
    c.flag_length_outlier,
    COALESCE(dc.drv_med_z <= df.drv_lo, FALSE) AS flag_driver_systematic,
    COALESCE(c.throttle_m > c.next_apex_m, FALSE) AS throttle_past_next_apex,
    COALESCE(c.onset_m < c.prev_apex_m, FALSE) AS brake_before_prev_apex,
    (COALESCE(c.throttle_m > c.next_apex_m, FALSE) OR COALESCE(c.onset_m < c.prev_apex_m, FALSE)) AS linked_corner_flag,
    CASE
        WHEN COALESCE(c.throttle_m > c.next_apex_m, FALSE) AND COALESCE(c.onset_m < c.prev_apex_m, FALSE) THEN 'both'
        WHEN COALESCE(c.throttle_m > c.next_apex_m, FALSE) THEN 'throttle_past_next_apex'
        WHEN COALESCE(c.onset_m < c.prev_apex_m, FALSE) THEN 'brake_before_prev_apex'
    END AS linked_corner_reason,
    CASE
        WHEN c.is_stopped THEN 'stopped'
        WHEN c.is_near_stopped THEN 'near_stopped'
        WHEN c.is_misaligned_lap
            AND ll.n_coherent >= 0.5 * ll.n_corners AND ll.mad_coherent_offset_m <= ll.off_hi_fence / 2
            THEN 'misaligned_global_lap'
        WHEN c.is_misaligned_lap AND (c.is_coherent_shift OR c.flag_length_outlier) THEN 'misaligned_corner'
    END AS exclusion_reason
FROM coherent AS c
LEFT JOIN lap_level AS ll
    ON c.race_id = ll.race_id AND c.driver_id = ll.driver_id AND c.lap_number = ll.lap_number
LEFT JOIN driver_cell AS dc
    ON c.race_id = dc.race_id AND c.corner_name = dc.corner_name AND c.driver_id = dc.driver_id
CROSS JOIN driver_fence AS df
