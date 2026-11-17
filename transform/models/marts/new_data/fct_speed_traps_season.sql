-- TX-25. Season roll-up of the speed trap (SpeedST) per driver and per team,
-- per session type, over valid laps. Every value carries its n. NULL where
-- there is no reading; never 0. NOT exported (scratch-only).
{{ config(materialized='table', tags=['marts', 'new_data']) }}

WITH laps AS (
    SELECT race_year, race_id, 'R' AS session_type, driver_id, constructor_id, speed_st_kph
    FROM {{ ref('stg_laps') }}
    WHERE is_valid_lap
    UNION ALL
    SELECT race_year, race_id, 'Q' AS session_type, driver_id, constructor_id, speed_st_kph
    FROM {{ ref('stg_laps_qualifying') }}
    WHERE is_valid_lap
),

by_entity AS (
    SELECT race_year, session_type, 'driver' AS entity_type, driver_id AS entity_id,
        speed_st_kph, race_id
    FROM laps
    UNION ALL
    SELECT race_year, session_type, 'team' AS entity_type, constructor_id AS entity_id,
        speed_st_kph, race_id
    FROM laps
)

SELECT
    CONCAT(CAST(race_year AS VARCHAR), '_', session_type, '_', entity_type, '_', entity_id)
        AS season_entity_id,
    race_year,
    session_type,
    entity_type,
    entity_id,
    COUNT(DISTINCT race_id) AS n_races,
    COUNT(*) AS n_valid_laps,
    MAX(speed_st_kph) AS st_max_kph,
    MEDIAN(speed_st_kph) AS st_median_kph,
    COUNT(speed_st_kph) AS n_st_readings,
    COUNT(*) - COUNT(speed_st_kph) AS n_st_missing
FROM by_entity
GROUP BY race_year, session_type, entity_type, entity_id
ORDER BY race_year, session_type, entity_type, entity_id
