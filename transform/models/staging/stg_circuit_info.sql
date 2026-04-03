-- stg_circuit_info.sql · staging · grain: one row per corner per race
-- FastF1 circuit_info.corners corner geometry for the circuit map and the
-- corner-map prior in the race pack (§5.7). Ordered by distance along the lap.
-- Geometry can differ slightly between seasons, so race_year is part of the
-- key.
-- No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_circuit_info') }}
)

SELECT
    CONCAT(
        CAST(race_id AS VARCHAR), '_',
        CAST(number AS VARCHAR),
        COALESCE(CAST(letter AS VARCHAR), '')
    ) AS corner_id,

    -- race_id = numeric FastF1 event id (matches stg_laps.race_id); race_slug =
    -- name.
    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(race AS VARCHAR) AS race_slug,

    CAST(number AS INTEGER) AS corner_number,
    NULLIF(CAST(letter AS VARCHAR), '') AS corner_letter,

    CAST(x AS DOUBLE) AS corner_x,
    CAST(y AS DOUBLE) AS corner_y,
    CAST(angle AS DOUBLE) AS corner_angle_deg,
    CAST(distance AS DOUBLE) AS corner_distance_m
FROM source
ORDER BY race_year, race_id, corner_distance_m
