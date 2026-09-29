-- F9 OPTION B: Sample weighting for decoupling
-- Instead of hard-excluding 'mistake' rows, keep them with reduced weight
--
-- This experimental model keeps both 'clean_cliff' and 'mistake' rows in training,
-- but assigns 'mistake' rows a weight < 1.0 to reduce their influence.
-- This avoids the hard selection bias of excluding them entirely while still
-- down-weighting rows that don't match the seed's cliff detection.
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
        (sg.stint_length_actual IS NOT NULL AND r.lap_in_stint = sg.stint_length_actual) AS is_in_lap
    FROM residuals r
    LEFT JOIN residual_stats rs ON
        r.race_year = rs.race_year AND r.race_id = rs.race_id AND r.driver_id = rs.driver_id
    LEFT JOIN trailing_mad AS tm ON r.lap_id = tm.lap_id
    LEFT JOIN stint_lengths sg ON r.lap_id = sg.lap_id
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
    CASE
        WHEN correction_class = 'exclude' THEN 'event_driven'
        WHEN is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap OR is_restart_lap OR is_pre_controlled_lap
            THEN 'event_driven'
        WHEN COALESCE(rainfall_flag, FALSE) THEN 'conditions'
        WHEN is_local_yellow_lap THEN 'event_driven'
        -- clean_cliff: large positive spike AND past cliff onset (same as original)
        WHEN mad_score > 3.0 AND cliff_onset_passed AND driver_skill_residual_s > trailing_median_s
            THEN 'clean_cliff'
        -- mistake: large positive spike NOT explained by cliff (same classification)
        WHEN mad_score > 3.0 AND driver_skill_residual_s > trailing_median_s
            THEN 'mistake'
        ELSE 'normal'
    END AS anomaly_class,
    (
        mad_score > 3.0
        AND cliff_onset_passed
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
    -- F9 OPTION B: Add weight for 'mistake' rows to allow soft exclusion instead of hard
    -- mistake rows (mad_score > 3.0, not cliff_onset_passed): weight 0.5
    -- all other anomalies and conditions: hard exclude (weight 0.0)
    -- normal rows: full weight (1.0)
    CASE
        WHEN correction_class = 'exclude' THEN 0.0
        WHEN COALESCE(rainfall_flag, FALSE) THEN 0.0
        WHEN is_safety_car_lap OR is_vsc_lap OR is_red_flag_lap OR is_restart_lap THEN 0.0
        WHEN is_in_lap OR is_out_lap THEN 0.0
        -- Reduced weight for 'mistake' rows: apply sample weighting instead of hard exclusion
        WHEN mad_score > 3.0 AND driver_skill_residual_s > trailing_median_s AND NOT cliff_onset_passed THEN 0.5
        -- Hard exclude other anomalies (clean_cliff must be handled separately per family)
        WHEN mad_score > 3.0 THEN 0.0
        ELSE 1.0
    END AS training_weight_option_b,
    driver_skill_residual_s
FROM with_boundaries
ORDER BY race_year, race_id, driver_id, lap_number
