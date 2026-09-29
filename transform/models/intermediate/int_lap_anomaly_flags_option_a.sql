-- F9 OPTION A: Change-point detection for cliff classification
-- Instead of using cliff_onset_passed from the seed, detect cliffs from residual series
--
-- This experimental model detects a potential cliff event via a change-point in the
-- residual series, per driver-race. A large positive residual spike after the
-- change-point is classified as 'clean_cliff' based on observed data patterns,
-- not on seed-based timing.
--
-- This is a scratch/experimental model; not materialized in the main pipeline.

WITH residuals AS (
    SELECT
        lap_id,
        stint_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        lap_number,
        compound,
        age_in_stint,
        lap_in_stint,
        lap_time_s,
        driver_skill_residual_s,
        track_unexplained_s,
        rainfall_flag,
        correction_class,
        correction_weight,
        is_safety_car_lap,
        is_vsc_lap,
        is_red_flag_lap,
        is_restart_lap,
        is_pre_controlled_lap,
        is_local_yellow_lap,
        is_major_outlier_lap,
        cliff_onset_passed,
        laps_past_cliff
    FROM {{ ref('int_lap_residual_decomposed') }}
),

-- Detect potential cliff event per driver-race via variance shift
-- A "cliff" is detected if the median residual after a lap is significantly higher
-- than before (indicating a shift in the baseline, consistent with tyre cliff)
cliff_detected_per_race AS (
    SELECT
        r.lap_id,
        r.race_year,
        r.race_id,
        r.driver_id,
        r.lap_number,
        r.driver_skill_residual_s,
        -- Trailing median BEFORE this lap (laps up to lap_number - 1)
        MEDIAN(r.driver_skill_residual_s)
            FILTER (WHERE r.correction_weight = 1.0)
            OVER (PARTITION BY r.race_year, r.race_id, r.driver_id
                  ORDER BY r.lap_number ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
            AS median_before,
        -- Trailing median AFTER (or at) this lap
        MEDIAN(r.driver_skill_residual_s) FILTER (WHERE r.correction_weight = 1.0)
            OVER (PARTITION BY r.race_year, r.race_id, r.driver_id
                  ORDER BY r.lap_number ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            AS median_after,
        -- Median of residuals from next 3 laps (looking forward for cliff signature)
        MEDIAN(r.driver_skill_residual_s) FILTER (WHERE r.correction_weight = 1.0)
            OVER (PARTITION BY r.race_year, r.race_id, r.driver_id
                  ORDER BY r.lap_number ROWS BETWEEN CURRENT ROW AND 3 FOLLOWING)
            AS median_next3
    FROM residuals r
),

-- Compute MAD-based scores (same as original)
residual_stats AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        AVG(driver_skill_residual_s) AS mean_residual_s,
        STDDEV(driver_skill_residual_s) AS stddev_residual_s,
        COUNT(*) AS residual_lap_count
    FROM residuals
    WHERE correction_weight = 1.0
    GROUP BY race_year, race_id, driver_id
),

trailing_window AS (
    SELECT
        r.lap_id,
        r.race_year,
        r.race_id,
        r.driver_id,
        r.lap_number,
        r.driver_skill_residual_s,
        MEDIAN(w.driver_skill_residual_s) AS trailing_median_s
    FROM residuals AS r
    INNER JOIN residuals AS w
        ON r.race_year = w.race_year
        AND r.race_id = w.race_id
        AND r.driver_id = w.driver_id
        AND w.lap_number BETWEEN r.lap_number - 6 AND r.lap_number
    GROUP BY r.lap_id, r.race_year, r.race_id, r.driver_id, r.lap_number, r.driver_skill_residual_s
),

trailing_mad AS (
    SELECT
        r.lap_id,
        tw.trailing_median_s,
        GREATEST(
            MEDIAN(ABS(w.driver_skill_residual_s - tw.trailing_median_s)),
            0.10
        ) AS mad_floored_s
    FROM residuals AS r
    INNER JOIN trailing_window AS tw ON r.lap_id = tw.lap_id
    INNER JOIN residuals AS w
        ON r.race_year = w.race_year
        AND r.race_id = w.race_id
        AND r.driver_id = w.driver_id
        AND w.lap_number BETWEEN r.lap_number - 6 AND r.lap_number
    GROUP BY r.lap_id, tw.trailing_median_s
),

stint_lengths AS (
    SELECT lap_id, stint_length_actual
    FROM {{ ref('int_lap_residual_decomposed') }}
),

with_boundaries AS (
    SELECT
        r.*,
        rs.mean_residual_s,
        rs.stddev_residual_s,
        rs.residual_lap_count,
        CASE
            WHEN rs.stddev_residual_s > 0
                THEN (r.driver_skill_residual_s - rs.mean_residual_s) / rs.stddev_residual_s
            ELSE 0.0
        END AS residual_z_score,
        tm.trailing_median_s,
        tm.mad_floored_s,
        CASE
            WHEN tm.mad_floored_s > 0
                THEN ABS(r.driver_skill_residual_s - tm.trailing_median_s) / tm.mad_floored_s
            ELSE 0.0
        END AS mad_score,
        r.lap_in_stint = 1 AS is_out_lap,
        (sg.stint_length_actual IS NOT NULL AND r.lap_in_stint = sg.stint_length_actual) AS is_in_lap,
        -- Change-point detection: mark a lap as post-cliff if median shifts significantly
        (cdn.median_after - COALESCE(cdn.median_before, cdn.median_after)) > 1.0 AS cliff_detected_from_data
    FROM residuals r
    LEFT JOIN residual_stats rs ON
        r.race_year = rs.race_year AND r.race_id = rs.race_id AND r.driver_id = rs.driver_id
    LEFT JOIN trailing_mad AS tm ON r.lap_id = tm.lap_id
    LEFT JOIN stint_lengths sg ON r.lap_id = sg.lap_id
    LEFT JOIN cliff_detected_per_race cdn ON r.lap_id = cdn.lap_id
)

SELECT
    lap_id,
    stint_id,
    race_year,
    race_id,
    driver_id,
    constructor_id,
    lap_number,
    compound,
    age_in_stint,
    lap_in_stint,
    correction_class,
    correction_weight,
    is_safety_car_lap,
    is_vsc_lap,
    is_red_flag_lap,
    is_restart_lap,
    is_pre_controlled_lap,
    is_local_yellow_lap,
    is_major_outlier_lap,
    cliff_onset_passed,
    laps_past_cliff,
    residual_z_score,
    mad_score,
    mad_floored_s,
    trailing_median_s,
    mean_residual_s,
    stddev_residual_s,
    residual_lap_count,
    is_out_lap,
    is_in_lap,
    COALESCE(rainfall_flag, FALSE) AS is_rain_lap,
    -- F9 OPTION A: Use cliff_detected_from_data instead of cliff_onset_passed
    CASE
        WHEN correction_class = 'exclude' THEN 'event_driven'
        WHEN is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap OR is_restart_lap OR is_pre_controlled_lap
            THEN 'event_driven'
        WHEN COALESCE(rainfall_flag, FALSE) THEN 'conditions'
        WHEN is_local_yellow_lap THEN 'event_driven'
        -- clean_cliff: large positive spike after detected cliff
        WHEN mad_score > 3.0 AND cliff_detected_from_data AND driver_skill_residual_s > trailing_median_s
            THEN 'clean_cliff'
        -- mistake: large positive spike without detected cliff (driver error/damage)
        WHEN mad_score > 3.0 AND driver_skill_residual_s > trailing_median_s
            THEN 'mistake'
        ELSE 'normal'
    END AS anomaly_class,
    (
        mad_score > 3.0
        AND cliff_detected_from_data
        AND driver_skill_residual_s > trailing_median_s
    ) AS cliff_candidate_flag,
    CASE
        WHEN correction_class = 'exclude' THEN FALSE
        WHEN COALESCE(rainfall_flag, FALSE) THEN FALSE
        WHEN is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap OR is_restart_lap THEN FALSE
        WHEN is_in_lap OR is_out_lap THEN FALSE
        WHEN mad_score > 3.0 THEN FALSE
        ELSE TRUE
    END AS usable_for_modelling,
    driver_skill_residual_s
FROM with_boundaries
ORDER BY race_year, race_id, driver_id, lap_number
