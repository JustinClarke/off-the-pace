-- stg_track_status.sql · staging · grain: one row per track-status change event
-- FastF1 session.track_status timeline (SC/VSC/yellow/red). Decodes the numeric
-- Status into named flags and orders events within each race by session_time_s.
-- Feeds int_sc_hazard_history. No joins, no aggregations.
{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM {{ source('bronze_f1', 'raw_track_status') }}
),

renamed AS (
    SELECT DISTINCT
        -- status_code is part of the key, not just race_id + session_time_s:
        -- some races log two distinct status codes at the identical
        -- session_time_s (see status_duration_s below), and without it those
        -- two genuinely different rows would collide on the same id.
        CONCAT(
            CAST(race_id AS VARCHAR), '_',
            CAST(session_time_s AS VARCHAR), '_',
            CAST(status AS VARCHAR)
        ) AS track_status_id,

        -- race_id = numeric FastF1 event id (matches stg_laps.race_id);
        -- race_slug = name.
        CAST(season AS INTEGER) AS race_year,
        CAST(race_id AS VARCHAR) AS race_id,
        CAST(race AS VARCHAR) AS race_slug,

        CAST(session_time_s AS DOUBLE) AS session_time_s,
        CAST(status AS VARCHAR) AS status_code,
        CAST(message AS VARCHAR) AS status_message,

        -- Named decode of the FastF1 status code. Mapping ground-truthed
        -- against
        -- the Message column in bronze: 4=SCDeployed, 6=VSCDeployed,
        -- 7=VSCEnding.
        -- (Note: this corrects the stale comment in stg_laps, which has 5/6/7
        -- mislabelled; the FastF1 truth is 5=Red, 6=VSC, 7=VSC-ending.)
        CASE CAST(status AS VARCHAR)
            WHEN '1' THEN 'all_clear'
            WHEN '2' THEN 'yellow'
            WHEN '4' THEN 'safety_car'
            WHEN '5' THEN 'red_flag'
            WHEN '6' THEN 'vsc'
            WHEN '7' THEN 'vsc_ending'
            ELSE 'unknown'
        END AS status_label,

        CAST(status AS VARCHAR) = '4' AS is_safety_car,
        CAST(status AS VARCHAR) IN ('6', '7') AS is_vsc,
        CAST(status AS VARCHAR) = '5' AS is_red_flag
    FROM source
)

SELECT
    *,
    -- Duration this status was in effect: until the next change in the same
    -- race
    -- (NULL for the final, open-ended event). Some races log two distinct
    -- status codes at the identical session_time_s (a same-instant
    -- transition, e.g. all_clear and yellow both stamped at 819.841s in
    -- 2024_17) — ORDER BY session_time_s alone leaves LEAD() to break that
    -- tie arbitrarily, which is non-deterministic across query plans.
    -- status_code as a secondary key makes the choice of which simultaneous
    -- event is "first" stable and reproducible; it does not claim that
    -- ordering is domain-meaningful.
    LEAD(session_time_s) OVER (
        PARTITION BY race_year, race_id ORDER BY session_time_s, status_code
    ) - session_time_s AS status_duration_s
FROM renamed
