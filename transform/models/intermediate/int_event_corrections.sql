-- Extended pipeline: Race-control derived lap corrections.
-- Classifies each lap in the race as affected by SC, VSC, red flag, or yellow sector,
-- and provides a correction multiplier that downstream residual decomposition uses to
-- either exclude or down-weight contaminated laps.
-- Source: stg_laps track_status strings + stg_pits (for pit-lap classification).
-- Grain: one row per race_year × race_id × driver_id × lap_number.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        lap_number,
        lap_time_s,
        track_status,
        is_safety_car_lap,
        is_vsc_lap,
        is_pit_lap,
        is_deleted,
        is_accurate,
        is_fastf1_generated
    FROM {{ ref('stg_laps') }}
),

race_fastest AS (
    SELECT
        race_year,
        race_id,
        MIN(lap_time_s) AS fastest_lap_s
    FROM laps
    WHERE lap_time_s IS NOT NULL
    GROUP BY race_year, race_id
),

-- Identify laps adjacent to a SC/VSC period (1 lap before deployment laps at full speed
-- and 1 lap after the restart are excluded both are anomalous in different directions).
sc_windows AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        lap_number,
        is_safety_car_lap,
        is_vsc_lap,
        -- SC/VSC lap on the preceding lap number (restart anomaly)
        LAG(is_safety_car_lap OR is_vsc_lap) OVER (
            PARTITION BY race_year, race_id, driver_id
            ORDER BY lap_number
        ) AS prev_lap_was_controlled,
        -- SC/VSC lap on the following lap (entry anomaly-bunching)
        LEAD(is_safety_car_lap OR is_vsc_lap) OVER (
            PARTITION BY race_year, race_id, driver_id
            ORDER BY lap_number
        ) AS next_lap_is_controlled
    FROM laps
),

-- Yellow flag in any sector (digit 2 anywhere in track_status) but not full SC/VSC
yellow_flag AS (
    SELECT
        lap_id,
        REGEXP_MATCHES(track_status, '.*2.*')
            AND NOT REGEXP_MATCHES(track_status, '.*[4567].*')  AS is_local_yellow_lap
    FROM laps
),

classified AS (
    SELECT
        l.lap_id,
        l.race_year,
        l.race_id,
        l.driver_id,
        l.lap_number,
        l.lap_time_s,
        l.track_status,

        -- Primary control flags (from stg_laps)
        l.is_safety_car_lap,
        l.is_vsc_lap,
        l.is_pit_lap,
        l.is_deleted,
        l.is_accurate,
        l.is_fastf1_generated,

        -- Derived adjacency flags
        COALESCE(sc.prev_lap_was_controlled, FALSE) AS is_restart_lap,
        COALESCE(sc.next_lap_is_controlled, FALSE)  AS is_pre_controlled_lap,

        -- Local yellow (sector caution, no full neutralisation)
        COALESCE(y.is_local_yellow_lap, FALSE)       AS is_local_yellow_lap,

        -- Time relative to race fastest (magnitude check)
        CASE
            WHEN l.lap_time_s IS NOT NULL AND rf.fastest_lap_s IS NOT NULL
                THEN l.lap_time_s / rf.fastest_lap_s
            ELSE NULL
        END AS lap_time_ratio_to_fastest,

        -- Slow outlier flag (>120% of fastest-severe incident / full neutralisation)
        CASE
            WHEN l.lap_time_s IS NOT NULL AND rf.fastest_lap_s IS NOT NULL
                THEN l.lap_time_s > 1.20 * rf.fastest_lap_s
            ELSE FALSE
        END AS is_major_outlier_lap

    FROM laps l
    LEFT JOIN sc_windows sc
        USING (race_year, race_id, driver_id, lap_number)
    LEFT JOIN yellow_flag y
        USING (lap_id)
    LEFT JOIN race_fastest rf
        USING (race_year, race_id)
)

SELECT
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    track_status,

    is_safety_car_lap,
    is_vsc_lap,
    is_local_yellow_lap,
    is_restart_lap,
    is_pre_controlled_lap,
    is_pit_lap,
    is_deleted,
    is_major_outlier_lap,
    is_fastf1_generated,

    -- Composite correction class mutually exclusive, priority ordered
    CASE
        WHEN is_deleted OR is_major_outlier_lap OR is_fastf1_generated
            THEN 'exclude'
        WHEN is_safety_car_lap OR is_vsc_lap OR is_restart_lap OR is_pre_controlled_lap
            THEN 'neutralisation'
        WHEN is_pit_lap
            THEN 'pit'
        WHEN is_local_yellow_lap
            THEN 'yellow'
        ELSE 'clean'
    END AS correction_class,

    -- correction_weight used by int_lap_residual_decomposed:
    --   1.0 = no adjustment, 0.0 = fully excluded from aggregates
    --   Partial weights allow soft-down-weighting without hard exclusion
    CASE
        WHEN is_deleted OR is_major_outlier_lap OR is_fastf1_generated
            THEN 0.0
        WHEN is_safety_car_lap OR is_vsc_lap
            THEN 0.0
        WHEN is_restart_lap OR is_pre_controlled_lap
            THEN 0.3
        WHEN is_pit_lap
            THEN 0.0
        WHEN is_local_yellow_lap
            THEN 0.6
        ELSE 1.0
    END AS correction_weight,

    lap_time_ratio_to_fastest

FROM classified
ORDER BY race_year, race_id, driver_id, lap_number
