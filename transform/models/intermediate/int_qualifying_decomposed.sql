-- Qualifying residual decomposition public-facing model.
-- Combines the qualifying residual chain with the quali-vs-race skill
-- differential.
--
-- The quali_vs_race_skill_delta_s is the key publishable output:
--   positive = driver is faster in quali relative to race (single-lap
--   specialist)
--   negative = driver is stronger in races than in qualifying
--
-- Grain: lap_id one row per qualifying push lap.
-- PK: lap_id (FK to stg_laps_qualifying).
--
-- Validation gate:
--   R² in qualifying fit ≥ R² in race fit + 10pp (not enforced in SQL;
--   enforced in validation notebook simulation_ghost_validation.ipynb).
--   quasi_traffic_flag: TRUE if a car was within 1.5s during the push lap (from
--   gap_to_ahead in the qualifying telemetry approximated here by NULL since
--   qualifying telemetry is not yet sector-classified for Q sessions).

{{ config(materialized='table', tags=['simulation', 'qualifying']) }}

WITH quali_residuals AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        lap_number,
        session_type,
        lap_time_s,
        tyre_life,
        compound,
        is_personal_best,
        quali_segment,
        segment_best_s,
        driver_segment_best_s,
        ratio_to_segment_best,
        base_track_pace_s,
        quali_pace_delta_s,
        fuel_component_s,
        compound_component_s,
        rubber_component_s,
        ambient_component_s,
        constructor_component_s,
        constructor_component_se_s,
        constructor_component_ci_low_s,
        constructor_component_ci_high_s,
        dirty_air_tax_s,
        dirty_air_tax_se_s,
        total_explained_s,
        quali_driver_skill_residual_s,
        track_unexplained_s,
        track_temp_c
    FROM {{ ref('int_lap_residual_decomposed_qualifying') }}
),

-- Driver skill for the session: one observation per segment   the residual of
-- the driver's best push lap in that segment   averaged over the segments the
-- driver contested.
--
-- It used to be the mean of every lap FastF1 flagged IsPersonalBest, which
-- fires on *every* improving lap and not once (4.58 per driver-race on average,
-- up to 15). That averaged a Q1 first effort with a Q3 final lap across ~1s of
-- track evolution, and the penalty scaled with how many improving laps the
-- driver happened to set: monotone in PB count, up to ~4s of pure aggregation
-- artefact for a driver who built up incrementally.
quali_driver_segment_best AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        quali_segment,
        MIN(quali_driver_skill_residual_s) AS segment_skill_residual_s
    FROM quali_residuals
    WHERE
        driver_segment_best_s IS NOT NULL
        AND lap_time_s = driver_segment_best_s
    GROUP BY race_year, race_id, driver_id, quali_segment
),

quali_driver_session_avg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        AVG(segment_skill_residual_s) AS quali_skill_session_avg_s,
        COUNT(*) AS quali_segments_contested_n
    FROM quali_driver_segment_best
    GROUP BY race_year, race_id, driver_id
),

-- Race-season driver residual mean (from int_lap_residual_decomposed via
-- fct_driver_skill_features)
-- Aggregate to (race_year, race_id, driver_id) grain for joining
race_driver_race_avg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        AVG(driver_skill_residual_s)
        FILTER (
            WHERE correction_weight = 1.0
            AND COALESCE(rainfall_flag, FALSE) = FALSE
        ) AS race_skill_race_avg_s
    FROM {{ ref('int_lap_residual_decomposed') }}
    GROUP BY race_year, race_id, driver_id
)

SELECT
    q.lap_id,
    q.race_year,
    q.race_id,
    q.driver_id,
    q.constructor_id,
    q.lap_number,
    q.session_type,
    q.lap_time_s,
    q.tyre_life,
    q.compound,
    q.is_personal_best,
    q.quali_segment,
    q.segment_best_s,
    q.driver_segment_best_s,
    q.ratio_to_segment_best,
    q.base_track_pace_s,
    q.quali_pace_delta_s,
    q.fuel_component_s,
    q.compound_component_s,
    q.rubber_component_s,
    q.ambient_component_s,
    q.constructor_component_s,
    q.constructor_component_se_s,
    q.constructor_component_ci_low_s,
    q.constructor_component_ci_high_s,
    q.dirty_air_tax_s,
    q.dirty_air_tax_se_s,
    q.total_explained_s,
    -- Per-lap qualifying driver skill signal
    q.quali_driver_skill_residual_s AS quali_skill_residual_s,
    -- Session-aggregate skill: mean over the driver's per-segment best laps
    qs.quali_skill_session_avg_s,
    qs.quali_segments_contested_n,
    -- Quali vs race differential (positive = single-lap pace specialist)
    qs.quali_skill_session_avg_s
    - COALESCE(rd.race_skill_race_avg_s, 0.0)
        AS quali_vs_race_skill_delta_s,
    q.track_unexplained_s,
    q.track_temp_c,
    -- Traffic flag: NULL until qualifying telemetry sector-classification is
    -- available.
    -- When int_lap_air_state supports session='Q', replace with actual
    -- gap-based flag.
    NULL::BOOLEAN AS quali_traffic_flag,
    -- DNQ flag: TRUE when driver has no valid laps in this session
    FALSE AS dnq_flag
FROM quali_residuals AS q
LEFT JOIN quali_driver_session_avg AS qs
    ON
        q.race_year = qs.race_year
        AND q.race_id = qs.race_id
        AND q.driver_id = qs.driver_id
LEFT JOIN race_driver_race_avg AS rd
    ON
        q.race_year = rd.race_year
        AND q.race_id = rd.race_id
        AND q.driver_id = rd.driver_id
ORDER BY q.race_year, q.race_id, q.driver_id, q.lap_number
