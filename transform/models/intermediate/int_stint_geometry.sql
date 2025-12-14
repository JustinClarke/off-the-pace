-- Layer 03: Foundation for all downstream window functions.
-- Partition key for all physics-layer windows is `stint_id`, not lap_number.
-- age_in_stint uses tyre_life (may exceed lap_in_stint if set used in qualifying).
{{ config(materialized='table') }}

WITH laps AS (
    SELECT * FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap = TRUE
),

with_stint_id AS (
    SELECT
        *,
        CONCAT(
            CAST(race_year    AS VARCHAR), '_',
            CAST(race_id      AS VARCHAR), '_',
            CAST(driver_id    AS VARCHAR), '_',
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
        ) AS stint_length_actual
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
    tyre_life                           AS age_in_stint,
    compound                            AS compound_in_stint,
    -- compound_code (C1–C5) is circuit-specific; populated once stg_tyre_allocations is ingested
    NULL::VARCHAR                       AS compound_code,
    stint_length_actual,
    NULL::BOOLEAN                       AS planned_vs_actual_flag
FROM with_stint_length
