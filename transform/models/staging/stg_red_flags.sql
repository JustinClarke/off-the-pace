-- stg_red_flags.sql · staging · grain: one row per red-flag event
-- Red flags from FastF1 track_status (Status '5' = Red). Built from track status
-- because session_status is not complete: 2025 Belgium has a red flag at 3,390 s
-- in track status and no 'Aborted' row in session_status, so stg_session_status
-- misses it. 191 races agree on the rest (checked 2026-11-19).
-- No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_track_status') }}
)

SELECT
    CONCAT(
        CAST(race_id AS VARCHAR), '_RED_',
        CAST(session_time_s AS VARCHAR)
    ) AS red_flag_id,

    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(race AS VARCHAR) AS race_slug,

    CAST(session_time_s AS DOUBLE) AS session_time_s,
    CAST(Message AS VARCHAR) AS track_message
FROM source
WHERE CAST(Status AS VARCHAR) = '5'
