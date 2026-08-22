-- stg_results_qualifying.sql · staging · grain: one row per driver × qualifying
-- session
-- FastF1 session.results for the Q session. The Q1/Q2/Q3 columns are the
-- official best lap each driver set in each segment   the only per-driver
-- record of the segment structure, and the anchor int_qualifying_segments uses
-- to tell a red-flag resumption from the start of the next segment. A NULL
-- segment time means the driver was eliminated before it (or set no time).
-- No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_results_qualifying') }}
)

SELECT
    -- Surrogate key
    CONCAT(
        CAST(race_id AS VARCHAR), '_Q_',
        CAST(abbreviation AS VARCHAR)
    ) AS quali_result_id,

    -- race_id = numeric FastF1 event id (matches stg_laps_qualifying.race_id);
    -- race_slug = human-readable name.
    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(race AS VARCHAR) AS race_slug,
    CAST('Q' AS VARCHAR) AS session_type,

    -- Driver / constructor
    CAST(abbreviation AS VARCHAR) AS driver_id,
    CAST(drivernumber AS VARCHAR) AS driver_number,
    CAST(teamname AS VARCHAR) AS constructor_id,

    -- Official qualifying classification (not the race grid: penalties are
    -- applied afterwards and show up in stg_results.grid_position).
    CAST(position AS INTEGER) AS quali_position,

    -- Segment best laps (nanoseconds → seconds)
    CASE WHEN q1 IS NOT NULL THEN CAST(q1 AS DOUBLE) / 1e9 END AS q1_time_s,
    CASE WHEN q2 IS NOT NULL THEN CAST(q2 AS DOUBLE) / 1e9 END AS q2_time_s,
    CASE WHEN q3 IS NOT NULL THEN CAST(q3 AS DOUBLE) / 1e9 END AS q3_time_s,

    -- Furthest segment the driver reached. Drivers who set no time at all are
    -- 'none' rather than NULL so the count is unambiguous downstream.
    CASE
        WHEN q3 IS NOT NULL THEN 'Q3'
        WHEN q2 IS NOT NULL THEN 'Q2'
        WHEN q1 IS NOT NULL THEN 'Q1'
        ELSE 'none'
    END AS final_segment_reached
FROM source
