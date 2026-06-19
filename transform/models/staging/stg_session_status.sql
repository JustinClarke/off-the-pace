-- stg_session_status.sql · staging · grain: one row per session lifecycle event
-- FastF1 session.session_status (Inactive / Started / Aborted / Finished /
-- Finalised). 'Aborted' marks red-flag stoppages surfaced as is_red_flag_stop.
-- No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_session_status') }}
)

SELECT
    CONCAT(
        CAST(race_id AS VARCHAR), '_',
        CAST(session_time_s AS VARCHAR)
    ) AS session_status_id,

    -- race_id = numeric FastF1 event id (matches stg_laps.race_id); race_slug =
    -- name.
    CAST(season AS INTEGER) AS race_year,
    CAST(race_id AS VARCHAR) AS race_id,
    CAST(race AS VARCHAR) AS race_slug,

    CAST(session_time_s AS DOUBLE) AS session_time_s,
    CAST(status AS VARCHAR) AS status,

    LOWER(CAST(status AS VARCHAR)) = 'aborted' AS is_red_flag_stop
FROM source
