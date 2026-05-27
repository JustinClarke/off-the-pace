-- stg_track_status.sql · staging · grain: one row per track-status change event
-- FastF1 session.track_status timeline (SC/VSC/yellow/red). Decodes the numeric
-- Status into named flags and orders events within each race by session_time_s.
-- Feeds int_sc_hazard_history (§5.2). No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_track_status') }}
),

renamed AS (
    SELECT
        CONCAT(
            CAST(race_id AS VARCHAR), '_',
            CAST(session_time_s AS VARCHAR)
        ) AS track_status_id,

        -- race_id = numeric FastF1 event id (matches stg_laps.race_id); race_slug = name.
        CAST(season AS INTEGER)  AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(race    AS VARCHAR) AS race_slug,

        CAST(session_time_s AS DOUBLE) AS session_time_s,
        CAST(Status AS VARCHAR)        AS status_code,
        CAST(Message AS VARCHAR)       AS status_message,

        -- Named decode of the FastF1 status code. Mapping ground-truthed against
        -- the Message column in bronze: 4=SCDeployed, 6=VSCDeployed, 7=VSCEnding.
        -- (Note: this corrects the stale comment in stg_laps, which has 5/6/7
        -- mislabelled; the FastF1 truth is 5=Red, 6=VSC, 7=VSC-ending.)
        CASE CAST(Status AS VARCHAR)
            WHEN '1' THEN 'all_clear'
            WHEN '2' THEN 'yellow'
            WHEN '4' THEN 'safety_car'
            WHEN '5' THEN 'red_flag'
            WHEN '6' THEN 'vsc'
            WHEN '7' THEN 'vsc_ending'
            ELSE 'unknown'
        END AS status_label,

        CAST(Status AS VARCHAR) = '4'         AS is_safety_car,
        CAST(Status AS VARCHAR) IN ('6', '7') AS is_vsc,
        CAST(Status AS VARCHAR) = '5'         AS is_red_flag
    FROM source
)

SELECT
    *,
    -- Duration this status was in effect: until the next change in the same race
    -- (NULL for the final, open-ended event).
    LEAD(session_time_s) OVER (
        PARTITION BY race_year, race_id ORDER BY session_time_s
    ) - session_time_s AS status_duration_s
FROM renamed
