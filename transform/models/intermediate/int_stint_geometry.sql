-- Layer 03: Foundation for all downstream window functions.
-- Partition key for all physics-layer windows is `stint_id`, not lap_number.
-- age_in_stint uses tyre_life (may exceed lap_in_stint if set used in
-- qualifying).
-- Carries the FULL chronological lap sequence (SC/VSC/pit/invalid laps
-- included) so downstream LAG/EWMA windows decay correctly across those
-- gaps instead of treating the lap before/after a gap as adjacent.
-- `lap_in_stint` is the chronological ordinal (total laps); `valid_lap_in_stint`
-- is the ordinal among valid laps only (NULL on invalid laps) for consumers
-- that fit pace/regression models and need SC/pit laps excluded.
{{ config(materialized='table') }}

WITH laps AS (
    SELECT * FROM {{ ref('stg_laps') }}
),

with_stint_id AS (
    SELECT
        *,
        CONCAT(
            CAST(race_year AS VARCHAR), '_',
            CAST(race_id AS VARCHAR), '_',
            CAST(driver_id AS VARCHAR), '_',
            CAST(stint_number AS VARCHAR)
        ) AS stint_id,

        ROW_NUMBER() OVER (
            PARTITION BY race_year, race_id, driver_id, stint_number
            ORDER BY lap_number
        ) AS lap_in_stint
    FROM laps
),

with_stint_length AS (
    SELECT
        *,
        COUNT(*) OVER (
            PARTITION BY stint_id
        ) AS stint_length_actual,
        COUNT(*) FILTER (WHERE is_valid_lap) OVER (
            PARTITION BY stint_id
        ) AS stint_length_valid,
        CASE
            WHEN is_valid_lap THEN
                COUNT(*) FILTER (WHERE is_valid_lap) OVER (
                    PARTITION BY stint_id
                    ORDER BY lap_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                )
        END AS valid_lap_in_stint
    FROM with_stint_id
)

SELECT
    stint_id,
    lap_id,
    race_year,
    race_id,
    driver_id,
    lap_number,
    stint_number,
    lap_in_stint,
    valid_lap_in_stint,
    tyre_life AS age_in_stint,
    compound AS compound_in_stint,
    -- compound_code (C1–C5) is circuit-specific; populated once
    -- stg_tyre_allocations is ingested
    CAST(NULL AS VARCHAR) AS compound_code,
    stint_length_actual,
    stint_length_valid,
    is_valid_lap,
    is_pit_lap,
    is_safety_car_lap,
    is_vsc_lap,
    is_red_flag_lap,
    CAST(NULL AS BOOLEAN) AS planned_vs_actual_flag
FROM with_stint_length
