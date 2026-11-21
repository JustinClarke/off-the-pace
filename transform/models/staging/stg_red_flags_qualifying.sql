-- stg_red_flags_qualifying.sql · staging · grain: one row per qualifying red-flag event
-- Red flags in qualifying from FastF1 track_status (Status '5' = Red). The qualifying
-- counterpart of stg_red_flags. stg_session_status_qualifying misses some of them: 7 of the
-- 72 qualifying sessions with a red flag have fewer 'Aborted' rows than red-flag messages
-- (2019_4, 2019_7, 2022_9, 2023_15, 2024_21, 2025_7, 2025_8), checked 2026-11-19.
-- No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_track_status_qualifying') }}
)

SELECT
    CONCAT(
        CAST(race_id AS VARCHAR), '_Q_RED_',
        CAST(session_time_s AS VARCHAR)
    ) AS red_flag_id,

    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(race AS VARCHAR) AS race_slug,

    CAST(session_time_s AS DOUBLE) AS session_time_s,
    CAST(Message AS VARCHAR) AS track_message
FROM source
WHERE CAST(Status AS VARCHAR) = '5'
