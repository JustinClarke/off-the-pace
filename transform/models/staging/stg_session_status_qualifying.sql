-- stg_session_status_qualifying.sql · staging · grain: one row per qualifying
-- session lifecycle event
-- Mirrors stg_session_status for Q sessions. This is the only record of where
-- Q1, Q2 and Q3 begin and end: the qualifying lap table carries no segment
-- column, so int_qualifying_segments splits the session on the Started /
-- Finished pairs here. 'Aborted' marks a red-flag stoppage inside a segment.
-- No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_session_status_qualifying') }}
)

SELECT
    CONCAT(
        CAST(race_id AS VARCHAR), '_Q_',
        CAST(session_time_s AS VARCHAR)
    ) AS session_status_id,

    -- race_id = numeric FastF1 event id (matches stg_laps_qualifying.race_id);
    -- race_slug = name.
    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(race AS VARCHAR) AS race_slug,
    CAST('Q' AS VARCHAR) AS session_type,

    CAST(session_time_s AS DOUBLE) AS session_time_s,
    CAST(status AS VARCHAR) AS status,

    LOWER(CAST(status AS VARCHAR)) = 'aborted' AS is_red_flag_stop,
    -- Raw green-light event. NOT one per segment: a red flag inside Q1/Q2/Q3
    -- shows as 'Aborted', and the resumption is another 'Started'.
    -- int_qualifying_segments is what separates the two.
    LOWER(CAST(status AS VARCHAR)) = 'started' AS is_green_light,
    -- Raw chequered-flag event. Usually three per session, but a segment
    -- red-flagged at its end never gets one   the session goes straight to
    -- 'Finalised' (10 of the 149 staged sessions).
    LOWER(CAST(status AS VARCHAR)) = 'finished' AS is_chequered_flag
FROM source
