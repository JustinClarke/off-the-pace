-- Extended pipeline: Anomaly classification per lap.
-- Combines control-event contamination (from int_event_corrections) with
-- statistical outlier detection on the driver_skill_residual from
-- int_lap_residual_decomposed to produce a multi-label anomaly summary.
--
-- anomaly_class (spec values):
--   'clean_cliff' -statistically extreme residual consistent with tyre cliff pattern
--   'mistake'     -large positive residual spike not explained by cliff (driver error or damage)
--   'event_driven' lap contaminated by a controllable race event (SC, VSC, restart, yellow)
--   'conditions'  -rain lap or ambient condition anomaly
--   'normal'      -no anomaly detected
--
-- Scale estimator: trailing-7-lap MAD (Median Absolute Deviation) per driver × race,
-- floored at 0.10s. MAD is robust to the cliff itself; stddev is contaminated.
-- residual_z_score is retained for traceability but anomaly_class uses MAD-based thresholds.
{{ config(materialized='table') }}

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
        is_restart_lap,
        is_pre_controlled_lap,
        is_local_yellow_lap,
        is_major_outlier_lap,
        cliff_onset_passed,
        laps_past_cliff
    FROM {{ ref('int_lap_residual_decomposed') }}
),

-- Global z-score within driver × race (retained for traceability)
residual_stats AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        AVG(driver_skill_residual_s)    AS mean_residual_s,
        STDDEV(driver_skill_residual_s) AS stddev_residual_s,
        COUNT(*)                        AS residual_lap_count
    FROM residuals
    WHERE correction_weight = 1.0
    GROUP BY race_year, race_id, driver_id
),

-- Trailing-7-lap MAD: pre-compute per-window medians via self-join.
-- DuckDB does not support MEDIAN as a window function, so we join each lap
-- to the up-to-7 preceding laps within the same driver × race and take MEDIAN.
trailing_window AS (
    SELECT
        r.lap_id,
        r.race_year,
        r.race_id,
        r.driver_id,
        r.lap_number,
        r.driver_skill_residual_s,
        -- Trailing median over laps [lap_number-6, lap_number] (inclusive, trailing-only)
        MEDIAN(w.driver_skill_residual_s) AS trailing_median_s
    FROM residuals r
    JOIN residuals w
        ON r.race_year  = w.race_year
        AND r.race_id   = w.race_id
        AND r.driver_id = w.driver_id
        AND w.lap_number BETWEEN r.lap_number-6 AND r.lap_number
    GROUP BY
        r.lap_id,
        r.race_year,
        r.race_id,
        r.driver_id,
        r.lap_number,
        r.driver_skill_residual_s
),

-- MAD = MEDIAN(ABS(residual-trailing_median)) over the same 7-lap window
trailing_mad AS (
    SELECT
        r.lap_id,
        tw.trailing_median_s,
        -- MAD from the trailing window, floored at 0.10s
        GREATEST(
            MEDIAN(ABS(w.driver_skill_residual_s-tw.trailing_median_s)),
            0.10
        ) AS mad_floored_s
    FROM residuals r
    JOIN trailing_window tw USING (lap_id)
    JOIN residuals w
        ON r.race_year  = w.race_year
        AND r.race_id   = w.race_id
        AND r.driver_id = w.driver_id
        AND w.lap_number BETWEEN r.lap_number-6 AND r.lap_number
    GROUP BY r.lap_id, tw.trailing_median_s
),

with_scores AS (
    SELECT
        r.*,
        rs.mean_residual_s,
        rs.stddev_residual_s,
        rs.residual_lap_count,

        -- Global z-score (traceability only; not used for anomaly_class)
        CASE
            WHEN rs.stddev_residual_s > 0
                THEN (r.driver_skill_residual_s-rs.mean_residual_s)
                     / rs.stddev_residual_s
            ELSE 0.0
        END                                                 AS residual_z_score,

        tm.trailing_median_s,
        tm.mad_floored_s,

        -- MAD-based local score (robust to cliff)
        CASE
            WHEN tm.mad_floored_s > 0
                THEN ABS(r.driver_skill_residual_s-tm.trailing_median_s)
                     / tm.mad_floored_s
            ELSE 0.0
        END                                                 AS mad_score

    FROM residuals r
    LEFT JOIN residual_stats rs USING (race_year, race_id, driver_id)
    LEFT JOIN trailing_mad tm   USING (lap_id)
),

-- Stint boundary flags
with_boundaries AS (
    SELECT
        s.*,
        s.lap_in_stint = 1                                  AS is_out_lap,
        (sg.stint_length_actual IS NOT NULL
            AND s.lap_in_stint = sg.stint_length_actual)    AS is_in_lap
    FROM with_scores s
    LEFT JOIN (
        SELECT lap_id, stint_length_actual
        FROM {{ ref('int_lap_residual_decomposed') }}
    ) sg USING (lap_id)
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

    -- Source correction metadata
    correction_class,
    correction_weight,
    is_safety_car_lap,
    is_vsc_lap,
    is_restart_lap,
    is_pre_controlled_lap,
    is_local_yellow_lap,
    is_major_outlier_lap,

    -- Cliff metadata
    cliff_onset_passed,
    laps_past_cliff,

    -- Statistical anomaly scores
    residual_z_score,
    mad_score,
    mad_floored_s,
    trailing_median_s,
    mean_residual_s,
    stddev_residual_s,
    residual_lap_count,

    -- Boundary flags
    is_out_lap,
    is_in_lap,
    COALESCE(rainfall_flag, FALSE)                          AS is_rain_lap,

    -- Composite anomaly class (spec values: clean_cliff, mistake, event_driven, conditions, normal)
    CASE
        WHEN correction_class = 'exclude'
            THEN 'event_driven'
        WHEN is_safety_car_lap OR is_vsc_lap OR is_restart_lap OR is_pre_controlled_lap
            THEN 'event_driven'
        WHEN COALESCE(rainfall_flag, FALSE)
            THEN 'conditions'
        WHEN is_local_yellow_lap
            THEN 'event_driven'
        -- cliff_candidate: large positive residual spike AND past cliff onset
        WHEN mad_score > 3.0 AND cliff_onset_passed AND driver_skill_residual_s > trailing_median_s
            THEN 'clean_cliff'
        -- mistake: large positive spike NOT explained by cliff (driver error, damage, lock-up)
        WHEN mad_score > 3.0 AND driver_skill_residual_s > trailing_median_s
            THEN 'mistake'
        ELSE 'normal'
    END                                                     AS anomaly_class,

    -- cliff_candidate_flag: dedicated boolean for fct_cliff_prediction_features
    (
        mad_score > 3.0
        AND cliff_onset_passed
        AND driver_skill_residual_s > trailing_median_s
    )                                                       AS cliff_candidate_flag,

    -- usable_for_modelling shorthand (preserved for backwards compat)
    CASE
        WHEN correction_class = 'exclude'                   THEN FALSE
        WHEN COALESCE(rainfall_flag, FALSE)                 THEN FALSE
        WHEN is_safety_car_lap OR is_vsc_lap OR is_restart_lap THEN FALSE
        WHEN is_in_lap OR is_out_lap                        THEN FALSE
        WHEN mad_score > 3.0                                THEN FALSE
        ELSE TRUE
    END                                                     AS usable_for_modelling,

    driver_skill_residual_s

FROM with_boundaries
ORDER BY race_year, race_id, driver_id, lap_number
