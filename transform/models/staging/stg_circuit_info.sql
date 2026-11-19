-- stg_circuit_info.sql · staging · grain: one row per corner per race
-- FastF1 circuit_info.corners corner geometry for the circuit map. Ordered by
-- distance along the lap.
-- Geometry can differ slightly between seasons, so race_year is part of the
-- key.
-- Source precedence: the race-session file (circuit_info/*/*/circuit_info.parquet)
-- wins. The qualifying file (session=Q) is used only for races with no race file
-- (2018 Australia, Bahrain, Italy; 2026 Monaco). Before this, the qualifying files
-- were skipped, so those races had no corners.
-- No joins, no aggregations.
{{ config(materialized='view') }}

WITH race_src AS (
    SELECT *, 'race' AS corner_source
    FROM {{ source('bronze_f1', 'raw_circuit_info') }}
),

quali_src AS (
    SELECT *, 'quali' AS corner_source
    FROM {{ source('bronze_f1', 'raw_circuit_info_quali') }}
),

-- Races that have a race-session file; their qualifying file is dropped.
race_keys AS (
    SELECT DISTINCT season, race_id FROM race_src
),

-- Explicit columns: the qualifying files carry extra columns (session, session_type).
source AS (
    SELECT X, Y, Number, Letter, Angle, Distance, race_id, season, race, corner_source FROM race_src
    UNION ALL
    SELECT X, Y, Number, Letter, Angle, Distance, race_id, season, race, corner_source FROM quali_src q
    WHERE NOT EXISTS (
        SELECT 1 FROM race_keys r
        WHERE r.season = q.season AND r.race_id = q.race_id
    )
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
    CAST(distance AS DOUBLE) AS corner_distance_m,
    corner_source
FROM source
ORDER BY race_year, race_id, corner_distance_m
